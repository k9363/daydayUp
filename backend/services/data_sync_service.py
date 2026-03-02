"""
数据同步服务
提供批量获取不同周期K线数据的功能
"""
import baostock as bs
import pandas as pd
import time
import json
import logging
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


class DataSyncService:
    """数据同步服务"""

    def __init__(self):
        self.bs = None

    def login(self):
        """登录Baostock"""
        if self.bs is None:
            self.bs = bs
        lg = bs.login()
        if lg.error_code != '0':
            raise Exception(f"Baostock登录失败: {lg.error_msg}")
        return True

    def logout(self):
        """登出Baostock"""
        if self.bs:
            bs.logout()

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

        # 先登录
        self.login()
        
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
        # 确保已登录
        self.login()
        
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

        # 字段映射
        fields_map = {
            'd': 'date,code,open,high,low,close,preclose,volume,amount,pctChg,turn,peTTM,psTTM',
            'w': 'date,code,open,high,low,close,volume,amount,pctChg',
            'm': 'date,code,open,high,low,close,volume,amount,pctChg',
            '5': 'date,time,code,open,high,low,close,volume,amount,pctChg',
            '15': 'date,time,code,open,high,low,close,volume,amount,pctChg',
            '30': 'date,time,code,open,high,low,close,volume,amount,pctChg',
            '60': 'date,time,code,open,high,low,close,volume,amount,pctChg'
        }

        fields = fields_map.get(bs_freq, fields_map['d'])

        logger.info(f"查询K线: code={code}, start={start_date}, end={end_date}, freq={bs_freq}")

        rs = bs.query_history_k_data_plus(
            code=code,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            frequency=bs_freq,
            adjustflag=adjustflag
        )

        logger.info(f"Baostock返回: error_code={rs.error_code}, error_msg={rs.error_msg}")

        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(dict(zip(rs.fields, rs.get_row_data())))

        return data_list

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

        # 优化：先批量查询已存在的 (stock_code, trade_date) 组合
        code_date_pairs = []
        for row in data_list:
            if not row.get('code') or row.get('close') == '':
                continue
            code = row['code']
            trade_date = row.get('date', '')
            if frequency in ['5', '15', '30', '60']:
                trade_date = f"{row.get('date', '')} {row.get('time', '')}"
            code_date_pairs.append((code, trade_date))

        # 批量查询已存在的记录
        existing_set = set()
        if code_date_pairs:
            # 构建 IN 查询
            codes = list(set([p[0] for p in code_date_pairs]))
            dates = list(set([p[1] for p in code_date_pairs]))
            
            existing_records = db_session.query(
                model_class.stock_code,
                model_class.trade_date
            ).filter(
                model_class.stock_code.in_(codes),
                model_class.trade_date.in_(dates)
            ).all()
            
            existing_set = {(r.stock_code, r.trade_date) for r in existing_records}
            logger.info(f"批量查询: 发现 {len(existing_set)} 条已存在的记录")

        # 批量添加新记录 - 使用字典映射替代ORM对象
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

            # 检查是否已存在（使用预查询的结果）
            if (code, trade_date) in existing_set:
                logger.debug(f"数据已存在，跳过: {code} {trade_date}")
                continue

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
                'change_percent': row.get('pctChg', 0) or None,
            }

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

            mappings.append(mapping)
            saved_count += 1

        # 批量添加 - 使用 bulk_insert_mappings
        if mappings:
            db_session.bulk_insert_mappings(model_class, mappings)

        db_session.commit()
        logger.info(f"保存完成: 新增 {saved_count} 条")
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
            task = DataSyncTask.query.get(task_id)
        if not task:
            raise Exception(f"任务不存在: {task_id}")

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
            task.status = 'running'
            task.start_time = datetime.now()
            db_session.commit()

        try:
            self.login()

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
                
                # 根据 stock_type 过滤（使用 stock_type 字段）
                if stock_type in ['stock', 'etf', 'index']:
                    query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                        StockBasic.stock_type == stock_type
                    )
                elif stock_type == 'all':
                    # all 类型：获取 stock, etf, index 三种类型
                    query = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
                        StockBasic.stock_type.in_(['stock', 'etf', 'index'])
                    )
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

            # 断点续传：过滤掉已处理的股票
            remaining_codes = [code for code in stock_codes if code not in processed_codes_set]
            logger.info(f"剩余待处理: {len(remaining_codes)}/{len(stock_codes)} 只股票")
            
            total_processed = len(processed_codes_set)
            total_saved = 0

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

                    total_processed += 1
                    if task:
                        task.processed_stocks = total_processed
                        task.total_records = total_saved

                    # 断点续传：更新已处理的股票代码列表（每10个股票更新一次）
                    processed_codes_set.add(code)
                    if task and (total_processed) % 10 == 0:
                        task.processed_codes = json.dumps(list(processed_codes_set))
                        db_session.commit()
                        logger.info(f"进度: {i + 1}/{len(remaining_codes)}, 已保存: {total_saved} 条")

                    time.sleep(request_interval)

                except Exception as e:
                    logger.error(f"获取 {code} 数据失败: {e}")
                    continue

            # 最后一批不足阈值的也要保存
            if batch_data_list:
                saved = self.save_kline_data(db_session, batch_data_list, frequency, stock_name_map)
                logger.info(f"最后批量保存: {saved} 条")
                total_saved += saved

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
                task.status = 'completed'
                task.end_time = datetime.now()
                task.processed_stocks = total_processed
                task.saved_records = total_saved
                task.processed_codes = json.dumps(list(processed_codes_set))
                db_session.commit()
                return task.total_stocks, total_processed, task.total_records, total_saved
            else:
                # 没有任务时直接返回结果
                db_session.commit()
                return len(stock_codes), total_processed, total_saved, total_saved

        except Exception as e:
            if task:
                task.status = 'failed'
                task.end_time = datetime.now()
                task.error_message = str(e)
                db_session.commit()
            raise e
        finally:
            self.logout()

    def get_sync_task_status(self, task_id):
        """获取同步任务状态"""
        return DataSyncTask.query.get(task_id)

    def get_sync_task_list(self, status=None, limit=20):
        """获取同步任务列表"""
        query = DataSyncTask.query
        if status:
            query = query.filter(DataSyncTask.status == status)
        return query.order_by(DataSyncTask.create_time.desc()).limit(limit).all()


def get_data_sync_service():
    """获取数据同步服务实例"""
    return DataSyncService()

