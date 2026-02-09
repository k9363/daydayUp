"""
数据同步服务
提供批量获取不同周期K线数据的功能
"""
import baostock as bs
import pandas as pd
import time
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
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        rs = bs.query_all_stock(day=date)
        data_list = []

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

        rs = bs.query_history_k_data_plus(
            code=code,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            frequency=bs_freq,
            adjustflag=adjustflag
        )

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
        saved_count = 0
        model_class = self._get_model_class(frequency)

        for row in data_list:
            if not row.get('code') or row.get('close') == '':
                continue

            # 检查是否已存在
            code = row['code']
            trade_date = row.get('date', '')

            # 分钟线需要组合日期和时间
            if frequency in ['5', '15', '30', '60']:
                trade_date = f"{row.get('date', '')} {row.get('time', '')}"

            exists = db_session.query(model_class).filter(
                model_class.stock_code == code,
                model_class.trade_date == trade_date
            ).first()

            if exists:
                continue

            record = model_class(
                stock_code=code,
                stock_name=stock_name_map.get(code, ''),
                trade_date=trade_date,
                open_price=row.get('open', 0) or None,
                high_price=row.get('high', 0) or None,
                low_price=row.get('low', 0) or None,
                close_price=row.get('close', 0) or None,
                pre_close_price=row.get('preclose', 0) or None,
                volume=row.get('volume', 0) or None,
                turnover=row.get('amount', 0) or None,
                change_percent=row.get('pctChg', 0) or None,
            )

            # 周线和月线特有字段
            if frequency == 'weekly':
                record.week_open = row.get('open', 0) or None
                record.week_close = row.get('close', 0) or None
                record.week_high = row.get('high', 0) or None
                record.week_low = row.get('low', 0) or None
            elif frequency == 'monthly':
                record.month_open = row.get('open', 0) or None
                record.month_close = row.get('close', 0) or None
                record.month_high = row.get('high', 0) or None
                record.month_low = row.get('low', 0) or None
            elif frequency in ['5', '15', '30', '60']:
                record.frequency = frequency

            db_session.add(record)
            saved_count += 1

        db_session.commit()
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
                        stock_type='all', batch_size=100, request_interval=0.5):
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

        Returns:
            tuple: (总股票数, 已处理股票数, 总记录数, 已保存记录数)
        """
        task = DataSyncTask.query.get(task_id)
        if not task:
            raise Exception(f"任务不存在: {task_id}")

        task.status = 'running'
        task.start_time = datetime.now()
        db_session.commit()

        try:
            self.login()

            # 获取股票列表
            stock_list = self.get_stock_list(date=start_date, stock_type=stock_type)
            if not stock_list:
                raise Exception("未获取到股票列表")

            stock_codes = [s['code'] for s in stock_list]
            stock_name_map = {s['code']: s['name'] for s in stock_list}
            task.total_stocks = len(stock_codes)
            db_session.commit()

            total_processed = 0
            total_saved = 0
            batch_data = []

            for i, code in enumerate(stock_codes):
                try:
                    # 获取K线数据
                    data_list = self.get_kline_data(code, start_date, end_date, frequency)

                    if data_list:
                        batch_data.extend(data_list)

                        # 批量保存
                        if len(batch_data) >= batch_size:
                            saved = self.save_kline_data(db_session, batch_data, frequency, stock_name_map)
                            total_saved += saved
                            batch_data = []
                            db_session.commit()

                    total_processed += 1
                    task.processed_stocks = total_processed
                    task.total_records = len(batch_data) + sum(
                        d.get('count', 0) for d in task.results if hasattr(task, 'results')
                    )

                    if (i + 1) % 100 == 0:
                        db_session.commit()
                        logger.info(f"进度: {i + 1}/{len(stock_codes)}")

                    time.sleep(request_interval)

                except Exception as e:
                    logger.error(f"获取 {code} 数据失败: {e}")
                    continue

            # 保存最后一批
            if batch_data:
                saved = self.save_kline_data(db_session, batch_data, frequency, stock_name_map)
                total_saved += saved
                db_session.commit()

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

            task.status = 'completed'
            task.end_time = datetime.now()
            task.processed_stocks = total_processed
            task.saved_records = total_saved
            db_session.commit()

            return task.total_stocks, total_processed, task.total_records, total_saved

        except Exception as e:
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

