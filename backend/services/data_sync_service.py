"""
数据同步服务
提供批量获取不同周期K线数据的功能
"""
import baostock as bs
import pandas as pd
import time
import json
import logging
import socket
import concurrent.futures
from datetime import datetime, timedelta
from models.kline import (
    StockDailyKLine,
    StockWeeklyKLine,
    StockMonthlyKLine,
    StockMinuteKLine,
    StockSector,
    StockSectorRelation,
    DataSyncTask
)

logger = logging.getLogger(__name__)


# baostock SDK 内部 socket 没有读超时，一旦服务端不发数据，调用会无限阻塞。
# 用独立线程 + Future.result(timeout=...) 强制中断业务等待。被弃用的工作线程
# 仍然 hang 在 socket.recv 上，调用方必须把 self.lg 置 None 触发下一次重连，
# 由 baostock 重新握手时关闭旧 socket，hang 线程才会随之退出。
_BAOSTOCK_QUERY_TIMEOUT_SEC = 30


class BaostockServiceUnavailable(Exception):
    """baostock 持续超时，判定服务不可用，应中止整个任务"""
    pass


def _call_baostock_with_timeout(call_fn, timeout=_BAOSTOCK_QUERY_TIMEOUT_SEC):
    # 2026-05-26: 修复 with ThreadPoolExecutor 退出时阻塞 bug
    #   旧代码 `with ... as ex:` 退出时默认 shutdown(wait=True)，即使主流程已抛
    #   TimeoutError，with 块还会等 hang 线程跑完（永远等不到），导致 main 也卡死
    #   现在显式 shutdown(wait=False) 让 hang 线程后台泄漏（接受 baostock SDK 缺陷的代价）
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(call_fn)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"baostock 调用超时（>{timeout}s）")
    finally:
        # 不等线程（hang 线程会留在内存，daydayup-backend 重启时清空）
        ex.shutdown(wait=False)


class DataSyncService:
    """数据同步服务"""

    # Baostock 错误码：未登录或登录已过期
    LOGIN_ERROR_CODES = {'10002007', '10002001', '10002002', '10002003'}

    # 连续超时阈值：连续 N 只股票 baostock 查询都超时，判定服务整体不可用，中止任务
    MAX_CONSECUTIVE_TIMEOUTS = 5

    def __init__(self):
        self.lg = None
        self._consecutive_timeouts = 0

    def login(self):
        """登录Baostock（共享进程级锁 + 重试，避免多线程并发 login 撞同一全局会话）"""
        if self.lg is None or not self.lg.error_code == '0':
            from services.baostock_lock import safe_bs_login
            self.lg = safe_bs_login()
        return True

    def logout(self):
        """登出Baostock"""
        if self.lg:
            bs.logout()
            self.lg = None

    def _execute_callback(self, task):
        """执行任务完成后的回调"""
        if not task.callback_type:
            return
            
        logger.info(f"执行回调: type={task.callback_type}, task_id={task.id}")
        
        try:
            import json
            callback_params = json.loads(task.callback_params) if task.callback_params else {}
            logger.info(f"回调参数: {callback_params}")
        except:
            callback_params = {}
        
        try:
            if task.callback_type == 'review_task':
                review_task_id = callback_params.get('review_task_id')
                if review_task_id:
                    self._callback_review_task(review_task_id)
                else:
                    logger.warning(f"回调参数中缺少 review_task_id")
            else:
                logger.warning(f"未知的回调类型: {task.callback_type}")
        except Exception as e:
            logger.error(f"执行回调失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _callback_review_task(self, review_task_id):
        """回调复盘任务继续执行"""
        from flask import current_app
        from extensions import db
        from models.reviewtask import ReviewTask
        from services.review_service import ReviewTaskService

        logger.info(f"开始回调复盘任务: {review_task_id}")
        
        with current_app.app_context():
            review_task = ReviewTask.query.get(review_task_id)
            if not review_task:
                logger.error(f"复盘任务不存在: {review_task_id}")
                return
            
            logger.info(f"复盘任务当前状态: {review_task.status}")
            
            if review_task.status != 'waiting_for_sync':
                logger.warning(f"复盘任务状态不是 waiting_for_sync: {review_task.status}")
                return
            
            # 更新任务状态为 running
            review_task.status = 'running'
            review_task.waiting_for_sync = False
            review_task.sync_task_id = None
            db.session.commit()
            logger.info(f"复盘任务状态已更新为 running")
            
            # 直接在当前线程执行复盘任务（不再启动新线程，避免嵌套线程问题）
            service = ReviewTaskService()
            try:
                # 设置 skip_data_fetch=True 表示跳过数据获取步骤，直接继续分析
                service.execute_baostock_task_continue(review_task_id)
            except Exception as e:
                logger.error(f"回调执行复盘任务失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

    def ensure_login(self):
        """
        确保已登录，如果未登录或会话失效则自动重连
        
        Returns:
            bool: 登录成功返回 True
        """
        import socket
        import threading
        
        # 使用带超时的检测机制，避免会话失效后阻塞
        result = {'success': False, 'needs_relogin': False}
        
        def check_session():
            try:
                # 使用较短的超时检测会话
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(10)  # 10秒超时
                try:
                    rs = bs.query_trade_dates(start_date='2020-01-01', end_date='2020-01-01')
                    if rs.error_code == '0':
                        result['success'] = True  # 会话有效
                    else:
                        result['needs_relogin'] = True  # 需要重新登录
                finally:
                    socket.setdefaulttimeout(original_timeout)
            except Exception:
                result['needs_relogin'] = True  # 任何异常都需要重新登录
        
        # 在独立线程中运行检测，避免阻塞
        check_thread = threading.Thread(target=check_session)
        check_thread.daemon = True
        check_thread.start()
        check_thread.join(timeout=15)  # 最多等待15秒
        
        if check_thread.is_alive():
            # 检测超时，强制重新登录
            logger.warning("会话检测超时，强制重新登录")
            result['needs_relogin'] = True
        
        if result['success']:
            return True  # 会话有效
        
        # 需要重新登录
        if self.lg:
            self.lg = None
        return self.login()

    def get_stock_list(self, date=None, stock_type='all'):
        """
        获取股票列表

        Args:
            date: 日期，默认最新
            stock_type: 股票类型 all-全部, sh-上海, sz-深圳

        Returns:
            list: 股票代码列表
        """
        import baostock as bs

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 确保已登录
        self.ensure_login()
        
        # 先尝试指定日期
        rs = bs.query_all_stock(day=date)
        data_list = []
        error_msg = ''

        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            code = row[0]
            # 根据股票类型过滤
            if stock_type == 'sh' and not code.startswith('sh'):
                continue
            elif stock_type == 'sz' and not code.startswith('sz'):
                continue
            data_list.append({
                'code': code,
                'name': row[1] if len(row) > 1 else ''
            })

        # 如果指定日期没有数据，尝试从该日期起的最近交易日
        if not data_list:
            logger.warning(f"指定日期 {date} 没有股票数据，尝试查找最近的交易日...")
            
            # 尝试获取从指定日期起最近5天的股票列表
            start_search_date = datetime.strptime(date, '%Y-%m-%d')
            for i in range(1, 10):  # 扩大搜索范围到10天
                check_date = start_search_date + timedelta(days=i)
                check_date_str = check_date.strftime('%Y-%m-%d')
                
                rs = bs.query_all_stock(day=check_date_str)
                temp_list = []
                
                while (rs.error_code == '0') and rs.next():
                    row = rs.get_row_data()
                    code = row[0]
                    if stock_type == 'sh' and not code.startswith('sh'):
                        continue
                    elif stock_type == 'sz' and not code.startswith('sz'):
                        continue
                    temp_list.append({
                        'code': code,
                        'name': row[1] if len(row) > 1 else ''
                    })
                
                if temp_list:
                    logger.info(f"使用日期 {check_date_str} 的股票列表，共 {len(temp_list)} 只")
                    return temp_list
            
            error_msg = f"从 {date} 起最近10天都没有获取到股票数据"

        if not data_list:
            logger.error(f"获取股票列表失败: {error_msg}")

        return data_list

    def get_kline_data(self, code, start_date, end_date, frequency='d', adjustflag='2'):
        """
        获取K线数据

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 周期 d=日线, w=周线, m=月线, 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟
            adjustflag: 复权类型 2=不复权

        Returns:
            list: K线数据列表
        """
        # 确保已登录；登录失败/超时也计入连续超时熔断——否则全局 socket 卡死后会逐只重连超时,
        # 累计 MAX 次干净中止(抛 BaostockServiceUnavailable),而非逐只磨上百只 ×15s。
        try:
            self.ensure_login()
        except Exception as _le:
            self._consecutive_timeouts += 1
            self.lg = None
            if self._consecutive_timeouts >= self.MAX_CONSECUTIVE_TIMEOUTS:
                raise BaostockServiceUnavailable(
                    f"baostock 连续 {self._consecutive_timeouts} 次登录失败/超时，判定服务不可用"
                )
            logger.warning(f"baostock 登录失败({self._consecutive_timeouts}/{self.MAX_CONSECUTIVE_TIMEOUTS})，跳过本只 {code}: {_le}")
            return []

        # 映射频率到Baostock参数
        freq_map = {
            'daily': 'd',
            'weekly': 'w',
            'monthly': 'm',
            '5': '5',
            '15': '15',
            '30': '30',
            '60': '60'
        }
        bs_freq = freq_map.get(frequency, 'd')

        # 字段映射（参考 Baostock 官方文档）
        # 分钟线指标：code,date,time,open,high,low,close,volume,amount,adjustflag（无 pctChg）
        # 周月线指标：code,date,open,high,low,close,volume,amount,adjustflag,turn,pctChg
        # 日线指标：code,date,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST
        fields_map = {
            'd': 'code,date,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST',
            'w': 'code,date,open,high,low,close,volume,amount,adjustflag,turn,pctChg',
            'm': 'code,date,open,high,low,close,volume,amount,adjustflag,turn,pctChg',
            '5': 'code,date,time,open,high,low,close,volume,amount,adjustflag',
            '15': 'code,date,time,open,high,low,close,volume,amount,adjustflag',
            '30': 'code,date,time,open,high,low,close,volume,amount,adjustflag',
            '60': 'code,date,time,open,high,low,close,volume,amount,adjustflag'
        }

        fields = fields_map.get(bs_freq, fields_map['d'])

        logger.info(f"查询K线: code={code}, start={start_date}, end={end_date}, freq={bs_freq}")

        # baostock 长连接 socket 无读超时，必须用 ThreadPoolExecutor 包整段（query + rs.next() 消费）
        # 整段超时，避免 hang 在某次 recv 上整夜不返回（task 229 即为此例）
        def _do_query():
            rs = bs.query_history_k_data_plus(
                code=code,
                start_date=start_date,
                end_date=end_date,
                fields=fields,
                frequency=bs_freq,
                adjustflag=adjustflag,
            )
            rows = []
            if rs.error_code == '0':
                while rs.next():
                    rows.append(dict(zip(rs.fields, rs.get_row_data())))
            return rs.error_code, rs.error_msg, rows

        try:
            error_code, error_msg, data_list = _call_baostock_with_timeout(
                _do_query, timeout=_BAOSTOCK_QUERY_TIMEOUT_SEC
            )
        except TimeoutError as e:
            self._consecutive_timeouts += 1
            logger.warning(
                f"Baostock 查询超时: code={code}, {e}，"
                f"连续超时 {self._consecutive_timeouts}/{self.MAX_CONSECUTIVE_TIMEOUTS}，触发会话重建"
            )
            # 强制下次 ensure_login 重新握手，使旧的 hang 线程随 socket 关闭而释放
            self.lg = None
            if self._consecutive_timeouts >= self.MAX_CONSECUTIVE_TIMEOUTS:
                raise BaostockServiceUnavailable(
                    f"baostock 连续 {self._consecutive_timeouts} 次查询超时，判定服务不可用"
                )
            return []
        except Exception as e:
            logger.warning(f"Baostock 请求异常: code={code}, {e}")
            return []

        logger.info(f"Baostock返回: error_code={error_code}, error_msg={error_msg}")
        self._consecutive_timeouts = 0  # 成功一次即重置计数
        return data_list

    def ingest_intraday_to_tacn(self, stock_codes, trade_date, db_session):
        """盘后用 baostock 5分钟K 拉个股当日分时 → POST 给 TA-CN sink 端点写入 intraday_quotes
        （分时分离度因子 compute_intraday_deviation 的个股数据源）。

        架构：K 线落库(日K + 分钟K)是 daydayUp 的职责——daydayUp 拥有 baostock 采集，本方法拉取+
        驱动落库，TA-CN /api/sync/intraday-quotes 仅作 mongo 存储 sink，TA-CN 侧不再调度/采集 K 线。
        个股分钟 baostock 20:00 后才入库，故复盘已整体挪到 20:30；指数分钟仍由 TA-CN 既有 16:00
        refresh_all_indices 处理（baostock 不支持指数分钟）。北交所(bj.)baostock 不支持，跳过。
        昨收直接取 daydayUp 自己 MySQL（trade_date 之前最近交易日收盘），省一半 baostock 调用且更可靠。
        失败不阻断复盘（上层 try 兜住，分离度因子缺省 0）。

        Args:
            stock_codes: daydayUp 格式代码列表（sh.600000 / sz.000001 …，已由调用方按成交额 TopN 截断）
            trade_date: 'YYYY-MM-DD'
            db_session: 复盘当前 DB 会话（取昨收）
        Returns:
            int: TA-CN 实际 upsert/modify 的 bar 数（失败返回 0）
        """
        import os as _os
        import requests as _requests
        from models.kline import StockDailyKLine

        codes = [c for c in (stock_codes or []) if str(c).startswith(('sh.', 'sz.'))]  # 排除北交所 bj.
        if not codes:
            logger.info("分时灌库: 无可用个股（北交所 baostock 不支持），跳过")
            return 0

        # 昨收：trade_date 之前最近一个交易日收盘（一次 IN 查询，按代码取最新一条）
        prev_close = {}
        rows = (
            db_session.query(StockDailyKLine.stock_code, StockDailyKLine.close_price)
            .filter(
                StockDailyKLine.stock_code.in_(codes),
                StockDailyKLine.trade_date < trade_date,
                StockDailyKLine.close_price.isnot(None),
            )
            .order_by(StockDailyKLine.stock_code, StockDailyKLine.trade_date.desc())
            .all()
        )
        for sc, cp in rows:
            if sc not in prev_close and cp:
                prev_close[sc] = float(cp)

        bars = []
        pulled = 0
        for code in codes:
            pc = prev_close.get(code)
            if not pc:
                continue  # 无昨收（新股/数据缺）→ 无法算 pct_chg，跳过
            try:
                kl = self.get_kline_data(code, trade_date, trade_date, frequency='5', adjustflag='2')
            except BaostockServiceUnavailable:
                logger.warning("分时灌库: baostock 服务不可用，中止后续拉取")
                break
            except Exception as _e:
                logger.debug(f"分时灌库: {code} 5min 拉取失败: {_e}")
                continue
            if not kl:
                continue
            pulled += 1
            code6 = ''.join(ch for ch in code if ch.isdigit())[-6:]
            for r in kl:
                t_raw = r.get('time') or ''
                cl = r.get('close')
                if not t_raw or len(t_raw) < 12 or cl in (None, ''):
                    continue
                try:
                    close_f = float(cl)
                except (TypeError, ValueError):
                    continue
                bars.append({
                    'code': code6,
                    't': t_raw[8:10] + ':' + t_raw[10:12],   # "20260611093500000" -> "09:35"
                    'close': close_f,
                    'pct_chg': round((close_f / pc - 1) * 100, 4),
                })
        self.logout()  # 释放 baostock 会话

        if not bars:
            logger.warning("分时灌库: baostock 5分钟K 无数据，跳过 POST")
            return 0

        tacn = _os.getenv('TACN_API_BASE', 'http://host.docker.internal:8000').rstrip('/')
        token = _os.getenv('INTERNAL_TRIGGER_TOKEN', '')
        headers = {"X-Internal-Token": token} if token else {}
        sent = 0
        for i in range(0, len(bars), 5000):  # 分批 POST，避免单次 payload 过大
            chunk = bars[i:i + 5000]
            try:
                resp = _requests.post(
                    f"{tacn}/api/sync/intraday-quotes",
                    json={"trade_date": str(trade_date), "bars": chunk},
                    headers=headers,
                    timeout=120,
                )
                if resp.status_code != 200:
                    logger.warning(f"intraday-quotes 灌库 HTTP {resp.status_code}: {resp.text[:150]}")
                else:
                    sent += int((resp.json() or {}).get('upserted', 0))
            except Exception as _pe:
                logger.warning(f"intraday-quotes 灌库 POST 失败: {_pe}")
        logger.info(f"✅ 分时灌库完成: {pulled}/{len(codes)} 只拉到分时 → {len(bars)} 根5min bar，TA-CN upserted={sent}")
        return sent

    def save_kline_data(self, db_session, data_list, frequency, stock_name_map):
        """
        保存K线数据到数据库

        Args:
            db_session: 数据库会话
            data_list: K线数据列表
            frequency: 频率
            stock_name_map: 股票代码到名称的映射

        Returns:
            int: 保存的记录数
        """
        logger.info(f"开始保存 {len(data_list)} 条数据, frequency={frequency}")
        saved_count = 0
        model_class = self._get_model_class(frequency)

        # 2026-06-08 修复：超大批一次性查重(IN 子句含数千 code)在百万行表上耗时数十秒，
        # 触发 MySQL "Lost connection during query (timed out)" → 会话中毒 → 后续全部连环失败。
        # 分块处理：每块 ≤800 行独立查重+插入+commit，单次查询/事务受控。
        _CHUNK = 800
        if len(data_list) > _CHUNK:
            total = 0
            for _i in range(0, len(data_list), _CHUNK):
                total += self.save_kline_data(db_session, data_list[_i:_i + _CHUNK], frequency, stock_name_map)
            return total

        # 2026-06-08 根治：表已有唯一索引 uq_stock_daily_kline_code_date(stock_code,trade_date)，
        # 改用 INSERT ... ON DUPLICATE KEY UPDATE（upsert）由 DB 去重——
        # 删除原"先 IN 查重(6953 code 巨型 IN，百万行表 60s 超时元凶) 再逐条跳过"的冗余逻辑。
        # upsert 语义优于原"已存在就跳过"：缺失补全 + 已存在用最新值覆盖纠正（修掉旧脏数据永不更新的缺陷）。

        # 构建字典映射
        mappings = []
        for row in data_list:
            if not row.get('code') or row.get('close') == '':
                logger.warning(f"跳过无效数据: {row}")
                continue

            code = row['code']
            trade_date = row.get('date', '')

            # 分钟线需要组合日期和时间
            if frequency in ['5', '15', '30', '60']:
                trade_date = f"{row.get('date', '')} {row.get('time', '')}"

            # 获取股票名称：优先使用 stock_name_map，否则尝试从数据行获取
            stock_name = stock_name_map.get(code, '')
            if not stock_name:
                stock_name = row.get('code_name', '') or row.get('stock_name', '')

            # 构建字典映射
            mapping = {
                'stock_code': code,
                'stock_name': stock_name,
                'trade_date': trade_date,
                'open_price': row.get('open', 0) or None,
                'high_price': row.get('high', 0) or None,
                'low_price': row.get('low', 0) or None,
                'close_price': row.get('close', 0) or None,
                'pre_close_price': row.get('preclose', 0) or None,
                'volume': row.get('volume', 0) or None,
                'turnover': row.get('amount', 0) or None,
            }
            
            # 日线/周线/月线支持 pctChg，分钟线不支持
            if frequency in ['daily', 'weekly', 'monthly']:
                mapping['change_percent'] = row.get('pctChg', 0) or None
            else:
                mapping['change_percent'] = None

            # 周线和月线特有字段
            if frequency == 'weekly':
                mapping['week_open'] = row.get('open', 0) or None
                mapping['week_close'] = row.get('close', 0) or None
                mapping['week_high'] = row.get('high', 0) or None
                mapping['week_low'] = row.get('low', 0) or None
            elif frequency == 'monthly':
                mapping['month_open'] = row.get('open', 0) or None
                mapping['month_close'] = row.get('close', 0) or None
                mapping['month_high'] = row.get('high', 0) or None
                mapping['month_low'] = row.get('low', 0) or None
            elif frequency in ['5', '15', '30', '60']:
                mapping['frequency'] = frequency
                mapping['change_percent'] = None

            mappings.append(mapping)
            saved_count += 1

        # 批量 upsert：INSERT ... ON DUPLICATE KEY UPDATE（唯一索引 stock_code+trade_date 去重）
        # 2026-06-11 修复：冲突时用 COALESCE(新值, 旧值) —— 新值非空才覆盖(纠正/补全),
        #   新值为 NULL 则保留旧值。根治"半截数据(如EOD未落定时open/low/pctChg为空)冲掉已有完整数据"
        #   的破坏性覆盖(美的6/11被Tushare快速路径半截数据清零的根因)。
        if mappings:
            from sqlalchemy.dialects.mysql import insert as _mysql_insert
            from sqlalchemy import func as _func
            table = model_class.__table__
            present = set(mappings[0].keys())
            stmt = _mysql_insert(table).values(mappings)
            update_cols = {
                c.name: _func.coalesce(getattr(stmt.inserted, c.name), table.c[c.name])
                for c in table.columns
                if c.name in present and c.name not in ('id', 'stock_code', 'trade_date', 'create_time')
            }
            stmt = stmt.on_duplicate_key_update(**update_cols)
            db_session.execute(stmt)

        db_session.commit()
        logger.info(f"保存完成: upsert {saved_count} 条")
        return saved_count

    def _get_model_class(self, frequency):
        """根据频率获取对应的模型类"""
        model_map = {
            'daily': StockDailyKLine,
            'weekly': StockWeeklyKLine,
            'monthly': StockMonthlyKLine,
            '5': StockMinuteKLine,
            '15': StockMinuteKLine,
            '30': StockMinuteKLine,
            '60': StockMinuteKLine
        }
        return model_map.get(frequency, StockDailyKLine)

    def sync_kline_data(self, db_session, task_id, start_date, end_date, frequency='daily',
                        stock_type='all', batch_size=10, request_interval=0.1, stock_codes=None):
        """
        同步K线数据

        Args:
            db_session: 数据库会话
            task_id: 任务ID
            start_date: 开始日期
            end_date: 结束日期
            frequency: K线频率
            stock_type: 股票类型
            batch_size: 每批保存的记录数
            request_interval: 请求间隔
            stock_codes: 可选的股票代码列表，用于只处理特定股票

        Returns:
            tuple: (总股票数, 已处理股票数, 总记录数, 已保存记录数)
        """
        import json
        
        task = None
        if task_id > 0:
            task = db_session.query(DataSyncTask).get(task_id)
            if not task:
                raise Exception(f"任务不存在: {task_id}")
            
            # 设置回调参数
            if task.callback_type == 'review_task':
                try:
                    import json
                    callback_params = json.loads(task.callback_params) if task.callback_params else {}
                except:
                    callback_params = {}

        # 断点续传：检查是否已有已处理的股票列表
        processed_codes_set = set()
        if task and task.processed_codes:
            try:
                processed_codes_set = set(json.loads(task.processed_codes))
                logger.info(f"断点续传：已处理 {len(processed_codes_set)} 只股票")
            except:
                processed_codes_set = set()

        # 如果任务状态是 running，说明是中断后继续
        if task and task.status == 'running':
            logger.info(f"任务继续执行，已处理 {len(processed_codes_set)} 只股票")
        
        if task:
            logger.info(f"更新同步任务状态: {task.id} from {task.status} to running")
            task.status = 'running'
            task.start_time = datetime.now()
            db_session.commit()
            logger.info(f"同步任务状态已更新为 running")

        try:
            # baostock 登录失败不再阻断主流程：tushare 快速路径优先，baostock 仅兜底。
            # 旧逻辑 ensure_login 在最前，baostock 登录失败会直接让整个同步 failed、连
            # tushare 快速路径都跑不到 —— 复盘为一只停牌股就卡死的根因。
            baostock_ok = True
            try:
                self.ensure_login()
            except Exception as _be:
                baostock_ok = False
                logger.warning(f"⚠️ baostock 登录失败，本次只用 tushare 快速路径，baostock 兜底跳过: {_be}")

            # 如果传入了 stock_codes，直接使用；否则从数据库查询
            if stock_codes:
                stock_codes = list(stock_codes)  # 确保是列表
                # 获取股票名称映射
                from models.stockbasic import StockBasic
                stock_list_db = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                    StockBasic.stock_code.in_(stock_codes)
                ).all()
                stock_name_map = {s.stock_code: s.stock_name for s in stock_list_db}
                logger.info(f"使用传入的股票列表: {len(stock_codes)} 只股票")
            else:
                # 从数据库获取股票列表（从元数据初始化好的 stock_basic 表）
                from models.stockbasic import StockBasic
                
                # 分钟线不支持指数数据，需要排除
                is_minute = frequency in ['5', '15', '30', '60']
                
                # 根据 stock_type 过滤（使用 stock_type 字段）
                if stock_type in ['stock', 'etf', 'index']:
                    # 分钟线不支持指数
                    if is_minute and stock_type == 'index':
                        logger.warning("指数不支持分钟线数据，将跳过指数")
                        stock_list_db = []
                    else:
                        query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                            StockBasic.stock_type == stock_type
                        )
                        stock_list_db = query.all()
                elif stock_type == 'all':
                    # all 类型：获取 stock, etf, index 三种类型
                    if is_minute:
                        # 分钟线不支持指数，排除 index
                        logger.info("分钟线模式：排除指数类型")
                        query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                            StockBasic.stock_type.in_(['stock', 'etf'])
                        )
                    else:
                        query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                            StockBasic.stock_type.in_(['stock', 'etf', 'index'])
                        )
                    stock_list_db = query.all()
                else:
                    # 兼容旧版本：sh/sz 使用 exchange 字段
                    query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                        ~StockBasic.market.in_(['bond_sh', 'bond_sz'])
                    )
                    if stock_type == 'sh':
                        query = query.filter(StockBasic.exchange == 'sh')
                    elif stock_type == 'sz':
                        query = query.filter(StockBasic.exchange == 'sz')
                    stock_list_db = query.all()
                
                if not stock_list_db:
                    raise Exception("数据库中未找到股票列表，请先进行元数据初始化")

                stock_codes = [s.stock_code for s in stock_list_db]
                stock_name_map = {s.stock_code: s.stock_name for s in stock_list_db}
                logger.info(f"从数据库获取到 {len(stock_codes)} 只股票")
            
            if task:
                task.total_stocks = len(stock_codes)
                db_session.commit()

            # 2026-05-26: stock-level 增量过滤 —— 跳过区间内 (code, trade_date) 已齐全的股票
            #   原行为：record-level 增量（拿完数据才查 existing_set 决定写不写），baostock 5500 次调用全跑
            #   新行为：先查 MySQL 已有 (code, trade_date)，**根本不调 baostock** for 已齐全的股票
            #   重跑场景从 25-30min → 几十秒（视未跑完比例）
            already_done_codes = set()
            try:
                from datetime import datetime as _dt, timedelta as _td
                model_class = self._get_model_class(frequency)
                # 计算区间内交易日数（粗略：日历日数；查 existing 数会容错）
                # 简化判断：如果某只股 trade_date 范围 >= 1 即视为齐全（日 K 单日同步场景）
                sd_obj = _dt.strptime(start_date, "%Y-%m-%d")
                ed_obj = _dt.strptime(end_date, "%Y-%m-%d")
                expected_min_count = 1  # 单日同步至少 1 条
                # SQL: GROUP BY stock_code 取已存在区间内的 count
                from sqlalchemy import func
                rows = db_session.query(
                    model_class.stock_code,
                    func.count().label("c"),
                ).filter(
                    model_class.stock_code.in_(stock_codes),
                    model_class.trade_date >= start_date,
                    model_class.trade_date <= end_date,
                ).group_by(model_class.stock_code).all()
                already_done_codes = {r.stock_code for r in rows if r.c >= expected_min_count}
                logger.info(
                    f"✅ stock-level 增量：{len(already_done_codes)}/{len(stock_codes)} 只股票区间内"
                    f"[{start_date}~{end_date}]已有数据，跳过 baostock 调用"
                )
            except Exception as e:
                logger.warning(f"⚠️ stock-level 增量检查失败（不影响主流程，全量重跑）: {e}")

            # 断点续传 + 增量：过滤已处理 + 已有完整数据
            remaining_codes = [code for code in stock_codes
                               if code not in processed_codes_set and code not in already_done_codes]
            logger.info(f"剩余待处理: {len(remaining_codes)}/{len(stock_codes)} 只股票"
                        f"（断点续传跳过 {len(processed_codes_set)} + 已有数据跳过 {len(already_done_codes)}）")

            total_processed = len(processed_codes_set)
            total_saved = 0
            failed_codes = []  # 记录失败的股票代码

            # 2026-05-26: Tushare 快速路径 — 单日同步走 TA-CN /api/sync/market-daily 一次拉全市场（<10 秒）
            # baostock 仅作兜底补缺失。仅对日线 + 单日范围启用，避免覆盖历史回填场景
            tushare_covered_codes = set()
            if frequency == 'daily' and start_date == end_date and remaining_codes:
                try:
                    import os as _os
                    import requests as _req
                    # daydayup-backend 不在 tradingagents-network，无法用 container name DNS
                    # 走宿主机 IP / host.docker.internal（与 mysql 同款方式）
                    tacn_base = _os.getenv('TACN_API_BASE', 'http://host.docker.internal:8000')
                    token = _os.getenv('INTERNAL_TRIGGER_TOKEN', '')
                    headers = {'X-Internal-Token': token} if token else {}
                    td_compact = start_date.replace('-', '')
                    logger.info(f"🚀 Tushare 快速路径开始: 调 TA-CN /api/sync/market-daily?trade_date={td_compact}")
                    resp = _req.get(
                        f"{tacn_base}/api/sync/market-daily",
                        params={'trade_date': td_compact, 'include_funds': 'true', 'include_index': 'true'},
                        headers=headers,
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        body = resp.json()
                        items = body.get('items') or []
                        # 只取在 remaining_codes 列表里的（不超出本次同步范围）
                        remaining_set = set(remaining_codes)
                        relevant_items = [it for it in items if it.get('code') in remaining_set]
                        # 2026-06-11 修复(fix2): 完整性校验——EOD 未落定时 market-daily 可能返回
                        #   open/low/pctChg 为空的半截行。只接受 OHLC+涨跌幅齐全的;不齐的不算覆盖、
                        #   留给 baostock 兜底补全(否则半截数据会让因子涨跌全失真,如美的6/11)。
                        def _complete(it):
                            return all(str(it.get(k, '')).strip() not in ('', 'None', 'nan')
                                       for k in ('open', 'high', 'low', 'close', 'pctChg'))
                        _before = len(relevant_items)
                        relevant_items = [it for it in relevant_items if _complete(it)]
                        if _before != len(relevant_items):
                            logger.warning(f"⚠️ Tushare 快速路径剔除 {_before - len(relevant_items)} 只半截数据(open/low/pctChg空),转 baostock 兜底")
                        if relevant_items:
                            logger.info(f"✅ Tushare 拿到 {len(items)} 行（本批适用 {len(relevant_items)} 只齐全），开始批量写入")
                            saved = self.save_kline_data(db_session, relevant_items, frequency, stock_name_map)
                            total_saved += saved
                            tushare_covered_codes = {it.get('code') for it in relevant_items}
                            # 标记 processed
                            for code in tushare_covered_codes:
                                processed_codes_set.add(code)
                            total_processed += len(tushare_covered_codes)
                            if task:
                                task.processed_stocks = total_processed
                                task.total_records = total_saved
                                task.saved_records = total_saved
                                task.processed_codes = json.dumps(list(processed_codes_set))
                                db_session.commit()
                            logger.info(f"🚀 Tushare 快速路径完成: 覆盖 {len(tushare_covered_codes)} 只，"
                                       f"baostock 还需补 {len(remaining_codes) - len(tushare_covered_codes)} 只")
                        else:
                            logger.warning(f"⚠️ Tushare 返回 {len(items)} 行但无任何在 remaining_codes 范围内")
                    else:
                        logger.warning(f"⚠️ Tushare 快速路径 HTTP {resp.status_code}，退回 baostock 全量")
                except Exception as e:
                    logger.warning(f"⚠️ Tushare 快速路径失败（不影响主流程，走 baostock）: {e}")
                    # 2026-06-08：失败(尤其 MySQL 超时)会使 session 进入"事务已回滚"中毒态，
                    # 不 rollback 则后续 baostock 路径每次 save/commit 全部连环失败、任务空转。
                    try:
                        db_session.rollback()
                    except Exception:
                        pass

                # 重新计算 remaining_codes 把 Tushare 覆盖的剔除
                remaining_codes = [c for c in remaining_codes if c not in tushare_covered_codes]
                logger.info(f"baostock 兜底处理剩余: {len(remaining_codes)} 只")

            # baostock 不可用时跳过兜底（tushare 已覆盖的正常股不受影响；剩余多为停牌/次新无数据）
            if not baostock_ok and remaining_codes:
                logger.warning(f"⚠️ baostock 不可用，跳过 {len(remaining_codes)} 只兜底股（多为停牌/次新/无 tushare 数据）")
                failed_codes.extend(remaining_codes)
                remaining_codes = []

            # 批量保存：积累多只股票数据后再保存
            batch_data_list = []  # 积累多只股票的数据
            current_batch_size = 0
            save_batch_size = 100  # 每100条数据批量保存一次

            for i, code in enumerate(remaining_codes):
                try:
                    # 获取K线数据
                    data_list = self.get_kline_data(code, start_date, end_date, frequency)
                    logger.info(f"获取 {code} 数据: {len(data_list)} 条")

                    if data_list:
                        # 积累数据
                        batch_data_list.extend(data_list)
                        current_batch_size += len(data_list)

                        # 达到批量阈值时保存
                        if current_batch_size >= save_batch_size:
                            saved = self.save_kline_data(db_session, batch_data_list, frequency, stock_name_map)
                            logger.info(f"批量保存: {saved} 条")
                            total_saved += saved
                            batch_data_list = []  # 清空批次
                            current_batch_size = 0
                    else:
                        # 获取到空数据也视为失败
                        failed_codes.append(code)

                    total_processed += 1
                    if task:
                        task.processed_stocks = total_processed
                        task.total_records = total_saved
                        task.saved_records = total_saved  # 2026-05-26: running 时也实时同步（之前只在 stopped/completed 才更新）

                    # 断点续传：更新已处理的股票代码列表（每10个股票更新一次）
                    processed_codes_set.add(code)
                    if task and (total_processed) % 10 == 0:
                        task.processed_codes = json.dumps(list(processed_codes_set))
                        db_session.commit()
                        logger.info(f"进度: {i + 1}/{len(remaining_codes)}, 已保存: {total_saved} 条")

                        # 检查任务是否被暂停
                        db_session.expire(task)
                        if task.status == 'stopped':
                            logger.info("任务已暂停，正在保存进度...")
                            break

                    # 2026-05-26: 去掉 time.sleep(request_interval=0.1) — baostock 服务端自身有限速
                    # 本地 sleep 没意义，省 100ms/只 × 7100 只 = ~12 分钟
                    # if request_interval > 0: time.sleep(request_interval)

                except BaostockServiceUnavailable:
                    # baostock 连续超时，整体中止任务并保留断点
                    logger.error(f"Baostock 服务不可用，中止同步任务 (task_id={task_id})，已处理 {total_processed} 只")
                    if task:
                        task.processed_codes = json.dumps(list(processed_codes_set))
                        task.processed_stocks = total_processed
                        db_session.commit()
                    raise
                except Exception as e:
                    logger.error(f"获取 {code} 数据失败: {e}")
                    failed_codes.append(code)
                    # 单只失败(含 save 时 DB 异常)后 rollback，避免毒化 session 拖垮后续所有股
                    try:
                        db_session.rollback()
                    except Exception:
                        pass
                    continue

            # 检查是否因暂停而退出循环
            if task and task.status == 'stopped':
                logger.info("任务已暂停，正在保存进度...")
                # 保存最后一批数据
                if batch_data_list:
                    saved = self.save_kline_data(db_session, batch_data_list, frequency, stock_name_map)
                    logger.info(f"暂停前批量保存: {saved} 条")
                    total_saved += saved

                # 保存当前进度
                task.processed_stocks = total_processed
                task.saved_records = total_saved
                task.processed_codes = json.dumps(list(processed_codes_set))
                task.end_time = datetime.now()
                db_session.commit()
                logger.info(f"暂停完成，已处理 {total_processed} 只股票，已保存 {total_saved} 条")
                return task.total_stocks, total_processed, task.total_records, total_saved

            # 最后一批不足阈值的也要保存
            if batch_data_list:
                saved = self.save_kline_data(db_session, batch_data_list, frequency, stock_name_map)
                logger.info(f"最后批量保存: {saved} 条")
                total_saved += saved

            # 第一轮处理完成，检查是否有失败的股票，进行重试
            if failed_codes:
                logger.info(f"第一轮处理完成，{len(failed_codes)} 只股票获取失败，开始重试...")
                retry_count = 0
                max_retries = 2  # 最多重试2次

                while failed_codes and retry_count < max_retries:
                    retry_count += 1
                    retry_failed = []
                    
                    for code in failed_codes:
                        try:
                            # 确保每次重试前都检查登录状态
                            self.ensure_login()

                            data_list = self.get_kline_data(code, start_date, end_date, frequency)
                            if data_list:
                                batch_data_list.extend(data_list)
                                current_batch_size += len(data_list)
                                logger.info(f"重试获取 {code} 成功: {len(data_list)} 条")
                            else:
                                retry_failed.append(code)
                        except BaostockServiceUnavailable:
                            logger.error(f"Baostock 服务不可用，中止重试阶段")
                            raise
                        except Exception as e:
                            logger.error(f"重试获取 {code} 失败: {e}")
                            retry_failed.append(code)
                    
                    # 保存重试获取的数据
                    if batch_data_list:
                        saved = self.save_kline_data(db_session, batch_data_list, frequency, stock_name_map)
                        logger.info(f"重试批量保存: {saved} 条")
                        total_saved += saved
                        batch_data_list = []
                        current_batch_size = 0
                    
                    failed_codes = retry_failed
                    logger.info(f"第 {retry_count} 轮重试完成，剩余失败: {len(failed_codes)} 只")
                    
                    if failed_codes:
                        # 等待后继续重试
                        time.sleep(2)

                if failed_codes:
                    logger.warning(f"重试后仍有 {len(failed_codes)} 只股票获取失败: {failed_codes[:10]}...")

            # 补充元数据（股票信息、板块信息、股票-板块关联）
            logger.info(f"开始为 {len(stock_codes)} 只股票补充元数据...")
            try:
                from services.metadata_service import get_metadata_service
                from services.metadata_config import is_auto_supplement_enabled, get_metadata_config

                # 检查是否启用自动补充
                if is_auto_supplement_enabled('sync'):
                    metadata_service = get_metadata_service()

                    # 使用统一的综合补充方法
                    result = metadata_service.supplement_metadata(
                        stock_codes=stock_codes,
                        db_session=db_session,
                        context='sync'
                    )
                    logger.info(f"元数据补充完成: {result}")
                else:
                    logger.info("数据同步时自动补充元数据已禁用")

            except Exception as e:
                logger.error(f"补充元数据失败: {e}")
                # 元数据补充失败不应影响主流程

            if task:
                logger.info(f"更新同步任务状态: {task.id} from {task.status} to completed")
                task.status = 'completed'
                task.end_time = datetime.now()
                task.processed_stocks = total_processed
                task.saved_records = total_saved
                task.processed_codes = json.dumps(list(processed_codes_set))
                db_session.commit()
                
                logger.info(f"同步任务 {task.id} 状态已更新为 completed")
                
                logger.info(f"数据同步任务 {task.id} 完成，准备执行回调...")
                
                # 执行回调
                self._execute_callback(task)
                
                logger.info(f"数据同步任务 {task.id} 回调执行完成")
                
                return task.total_stocks, total_processed, task.total_records, total_saved
            else:
                # 没有任务时直接返回结果
                db_session.commit()
                return len(stock_codes), total_processed, total_saved, total_saved

        except Exception as e:
            if task:
                logger.info(f"更新同步任务状态: {task.id} from {task.status} to failed")
                task.status = 'failed'
                task.end_time = datetime.now()
                task.error_message = str(e)
                db_session.commit()
            raise e
        finally:
            self.logout()

    def get_sync_task_status(self, task_id):
        """获取同步任务状态"""
        from models.kline import DataSyncTask
        return db.session.query(DataSyncTask).get(task_id)

    def get_sync_task_list(self, status=None, limit=20):
        """获取同步任务列表"""
        from models.kline import DataSyncTask
        query = db.session.query(DataSyncTask)
        if status:
            query = query.filter(DataSyncTask.status == status)
        return query.order_by(DataSyncTask.create_time.desc()).limit(limit).all()


def get_data_sync_service():
    """获取数据同步服务实例"""
    return DataSyncService()

