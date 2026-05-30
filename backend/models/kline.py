"""
股票板块和K线数据模型
存储板块元数据、股票-板块关联关系、以及不同周期的K线数据
"""
from extensions import db
from datetime import datetime


class StockSector(db.Model):
    """
    股票板块元数据表
    存储行业分类、概念板块、地区板块等信息
    """
    __tablename__ = 'stock_sector'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    sector_code = db.Column(db.String(50), unique=True, nullable=False, comment='板块代码')
    sector_name = db.Column(db.String(100), nullable=False, comment='板块名称')
    sector_type = db.Column(db.String(20), nullable=False, comment='板块类型: industry-行业, concept-概念, area-地区')
    description = db.Column(db.String(500), nullable=True, comment='板块描述')
    stock_count = db.Column(db.Integer, default=0, comment='包含股票数量')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联关系
    relations = db.relationship('StockSectorRelation', backref='sector', lazy='dynamic')

    __table_args__ = (
        db.Index('idx_sector_type', 'sector_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'sector_code': self.sector_code,
            'sector_name': self.sector_name,
            'sector_type': self.sector_type,
            'description': self.description,
            'stock_count': self.stock_count,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None,
        }


class StockSectorRelation(db.Model):
    """
    股票-板块关联关系表
    记录每只股票所属的板块
    """
    __tablename__ = 'stock_sector_relation'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码')
    sector_id = db.Column(db.BigInteger, db.ForeignKey('stock_sector.id'), nullable=False, comment='板块ID')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        db.Index('idx_stock_code', 'stock_code'),
        db.UniqueConstraint('stock_code', 'sector_id', name='uq_stock_sector'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'sector_id': self.sector_id,
            'sector_name': self.sector.sector_name if self.sector else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class MetadataProgress(db.Model):
    """
    元数据获取进度表
    记录断点续传进度，支持失败重试
    """
    __tablename__ = 'metadata_progress'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    task_type = db.Column(db.String(50), nullable=False, comment='任务类型: industry_sector-行业板块, concept_sector-概念板块')
    target_name = db.Column(db.String(100), nullable=True, comment='目标名称: 行业名称/概念名称')
    status = db.Column(db.String(20), default='pending', comment='状态: pending-待处理, processing-处理中, completed-已完成, failed-失败')
    retry_count = db.Column(db.Integer, default=0, comment='重试次数')
    max_retries = db.Column(db.Integer, default=3, comment='最大重试次数')
    error_message = db.Column(db.String(500), nullable=True, comment='错误信息')
    started_at = db.Column(db.DateTime, nullable=True, comment='开始时间')
    completed_at = db.Column(db.DateTime, nullable=True, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    __table_args__ = (
        db.Index('idx_task_type_status', 'task_type', 'status'),
        db.UniqueConstraint('task_type', 'target_name', name='uq_task_target'),
    )


class BaseKLine(db.Model):
    """
    K线数据基类
    """
    __abstract__ = True

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码')
    stock_name = db.Column(db.String(50), comment='股票名称')
    trade_date = db.Column(db.String(20), nullable=False, comment='交易日期时间')
    open_price = db.Column(db.Numeric(15, 4), comment='开盘价')
    high_price = db.Column(db.Numeric(15, 4), comment='最高价')
    low_price = db.Column(db.Numeric(15, 4), comment='最低价')
    close_price = db.Column(db.Numeric(15, 4), comment='收盘价')
    pre_close_price = db.Column(db.Numeric(15, 4), comment='昨收价')
    volume = db.Column(db.Numeric(20, 0), comment='成交量')
    turnover = db.Column(db.Numeric(20, 4), comment='成交额')
    change = db.Column(db.Numeric(10, 4), comment='涨跌额')
    change_percent = db.Column(db.Numeric(10, 4), comment='涨跌幅')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')


class StockDailyKLine(BaseKLine):
    """
    日K线数据表
    """
    __tablename__ = 'stock_daily_kline'

    turnover_rate = db.Column(db.Numeric(10, 4), comment='换手率')
    peTTM = db.Column(db.Numeric(15, 4), comment='市盈率TTM')
    psTTM = db.Column(db.Numeric(15, 4), comment='市销率TTM')
    industry = db.Column(db.String(50), comment='所属行业')
    market = db.Column(db.String(20), comment='市场类型')

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'trade_date', name='uq_stock_daily_kline_code_date'),
        db.Index('idx_daily_stock_date', 'stock_code', 'trade_date'),
        db.Index('idx_daily_trade_date', 'trade_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'pre_close_price': float(self.pre_close_price) if self.pre_close_price else None,
            'volume': float(self.volume) if self.volume else None,
            'turnover': float(self.turnover) if self.turnover else None,
            'change': float(self.change) if self.change else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'turnover_rate': float(self.turnover_rate) if self.turnover_rate else None,
            'peTTM': float(self.peTTM) if self.peTTM else None,
            'psTTM': float(self.psTTM) if self.psTTM else None,
            'industry': self.industry,
            'market': self.market,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class StockWeeklyKLine(BaseKLine):
    """
    周K线数据表
    """
    __tablename__ = 'stock_weekly_kline'

    # 周线特有字段
    week_open = db.Column(db.Numeric(15, 4), comment='周开盘价')
    week_close = db.Column(db.Numeric(15, 4), comment='周收盘价')
    week_high = db.Column(db.Numeric(15, 4), comment='周最高价')
    week_low = db.Column(db.Numeric(15, 4), comment='周最低价')
    avg_price = db.Column(db.Numeric(15, 4), comment='周均价')

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'trade_date', name='uq_stock_weekly_code_date'),
        db.Index('idx_weekly_stock_date', 'stock_code', 'trade_date'),
        db.Index('idx_weekly_trade_date', 'trade_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'pre_close_price': float(self.pre_close_price) if self.pre_close_price else None,
            'volume': float(self.volume) if self.volume else None,
            'turnover': float(self.turnover) if self.turnover else None,
            'change': float(self.change) if self.change else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'week_open': float(self.week_open) if self.week_open else None,
            'week_close': float(self.week_close) if self.week_close else None,
            'week_high': float(self.week_high) if self.week_high else None,
            'week_low': float(self.week_low) if self.week_low else None,
            'avg_price': float(self.avg_price) if self.avg_price else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class StockMonthlyKLine(BaseKLine):
    """
    月K线数据表
    """
    __tablename__ = 'stock_monthly_kline'

    # 月线特有字段
    month_open = db.Column(db.Numeric(15, 4), comment='月开盘价')
    month_close = db.Column(db.Numeric(15, 4), comment='月收盘价')
    month_high = db.Column(db.Numeric(15, 4), comment='月最高价')
    month_low = db.Column(db.Numeric(15, 4), comment='月最低价')
    avg_price = db.Column(db.Numeric(15, 4), comment='月均价')

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'trade_date', name='uq_stock_monthly_code_date'),
        db.Index('idx_monthly_stock_date', 'stock_code', 'trade_date'),
        db.Index('idx_monthly_trade_date', 'trade_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'pre_close_price': float(self.pre_close_price) if self.pre_close_price else None,
            'volume': float(self.volume) if self.volume else None,
            'turnover': float(self.turnover) if self.turnover else None,
            'change': float(self.change) if self.change else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'month_open': float(self.month_open) if self.month_open else None,
            'month_close': float(self.month_close) if self.month_close else None,
            'month_high': float(self.month_high) if self.month_high else None,
            'month_low': float(self.month_low) if self.month_low else None,
            'avg_price': float(self.avg_price) if self.avg_price else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class StockMinuteKLine(BaseKLine):
    """
    分钟K线数据表（5分钟、15分钟、30分钟、60分钟）
    """
    __tablename__ = 'stock_minute_kline'

    frequency = db.Column(db.String(10), nullable=False, comment='频率: 5, 15, 30, 60 (分钟)')

    __table_args__ = (
        db.Index('idx_minute_stock_date', 'stock_code', 'trade_date'),
        db.Index('idx_minute_freq_date', 'frequency', 'trade_date'),
        db.Index('idx_minute_trade_date', 'trade_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'pre_close_price': float(self.pre_close_price) if self.pre_close_price else None,
            'volume': float(self.volume) if self.volume else None,
            'turnover': float(self.turnover) if self.turnover else None,
            'change': float(self.change) if self.change else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'frequency': self.frequency,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


# 数据补充任务表
class DataSyncTask(db.Model):
    """
    数据同步任务表
    记录批量数据获取任务的状态
    """
    __tablename__ = 'data_sync_task'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    task_name = db.Column(db.String(100), nullable=False, comment='任务名称')
    start_date = db.Column(db.String(10), nullable=False, comment='开始日期')
    end_date = db.Column(db.String(10), nullable=False, comment='结束日期')
    frequency = db.Column(db.String(20), nullable=False, comment='K线频率: daily, weekly, monthly, 5, 15, 30, 60')
    stock_type = db.Column(db.String(20), default='all', comment='股票类型: all-全部, sh-上海, sz-深圳')
    status = db.Column(db.String(20), default='pending', comment='任务状态: pending, running, completed, failed')
    callback_type = db.Column(db.String(50), nullable=True, comment='回调类型: review_task')
    callback_params = db.Column(db.Text, nullable=True, comment='回调参数(JSON格式)')
    total_stocks = db.Column(db.Integer, default=0, comment='总股票数')
    processed_stocks = db.Column(db.Integer, default=0, comment='已处理股票数')
    total_records = db.Column(db.Integer, default=0, comment='总记录数')
    saved_records = db.Column(db.Integer, default=0, comment='已保存记录数')
    error_message = db.Column(db.Text, nullable=True, comment='错误信息')
    start_time = db.Column(db.DateTime, comment='开始时间')
    end_time = db.Column(db.DateTime, comment='结束时间')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    processed_codes = db.Column(db.Text(length=16777215), nullable=True, comment='已处理的股票代码列表，JSON格式')

    __table_args__ = (
        db.Index('idx_sync_status', 'status'),
        db.Index('idx_sync_dates', 'start_date', 'end_date'),
    )

    def to_dict(self, light=False):
        # light=True（列表视图）：① 不返回大字段 processed_codes（每行约 70KB 的全代码 JSON，
        #   50 行就 ~4.5MB 拖垮 /sync 页面）；② 仅对 running 任务做实时 COUNT(*)，
        #   否则 50 个任务各跑一次 over 140 万行的 COUNT(*) 会严重拖慢列表接口。
        #
        # 2026-05-26: saved_records 动态从 MySQL count（累加器在 running 状态不更新会偏小）；
        #   已完成任务的 saved_records 已是终值，无需再实时 count。
        live_saved = None
        need_live_count = (not light) or (self.status == 'running')
        if need_live_count:
            try:
                from extensions import db
                from sqlalchemy import text
                table_map = {
                    'daily': 'stock_daily_kline',
                    'weekly': 'stock_weekly_kline',
                    'monthly': 'stock_monthly_kline',
                }
                table = table_map.get(self.frequency)
                if table and self.start_date and self.end_date:
                    r = db.session.execute(
                        text(f"SELECT COUNT(*) FROM {table} WHERE trade_date >= :sd AND trade_date <= :ed"),
                        {"sd": self.start_date, "ed": self.end_date}
                    ).scalar()
                    live_saved = int(r) if r is not None else None
            except Exception:
                live_saved = None
        return {
            'id': self.id,
            'task_name': self.task_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'frequency': self.frequency,
            'stock_type': self.stock_type,
            'status': self.status,
            'total_stocks': self.total_stocks,
            'processed_stocks': self.processed_stocks,
            'total_records': self.total_records,
            # 优先用 MySQL 实时 count（永远准），count 失败/light 跳过则 fallback 累加字段
            'saved_records': live_saved if live_saved is not None else self.saved_records,
            'error_message': self.error_message,
            # 列表视图不返回大字段，详情视图（light=False）才带
            'processed_codes': None if light else self.processed_codes,
            'progress': round(self.processed_stocks / self.total_stocks * 100, 2) if self.total_stocks > 0 else 0,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None,
        }

