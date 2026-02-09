"""
股票日线数据模型
存储从 Baostock 获取的 A 股日线数据
"""
from extensions import db
from datetime import datetime


class StockDaily(db.Model):
    """股票日线数据表"""
    __tablename__ = 'stock_daily'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # 股票基本信息
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码，如 sh.600000')
    stock_name = db.Column(db.String(50), comment='股票名称')
    
    # 交易日期
    trade_date = db.Column(db.String(10), nullable=False, comment='交易日期 YYYY-MM-DD')
    
    # 开盘收盘数据
    open_price = db.Column(db.Numeric(15, 4), comment='开盘价')
    high_price = db.Column(db.Numeric(15, 4), comment='最高价')
    low_price = db.Column(db.Numeric(15, 4), comment='最低价')
    close_price = db.Column(db.Numeric(15, 4), comment='收盘价')
    pre_close_price = db.Column(db.Numeric(15, 4), comment='昨收价')
    
    # 成交量数据
    volume = db.Column(db.Numeric(20, 0), comment='成交量(股)')
    turnover = db.Column(db.Numeric(20, 4), comment='成交额(元)')
    turnover_rate = db.Column(db.Numeric(10, 4), comment='换手率')
    
    # 涨跌幅数据
    change = db.Column(db.Numeric(10, 4), comment='涨跌幅')
    change_percent = db.Column(db.Numeric(10, 4), comment='涨跌额')
    
    # 盘口数据
    bid_volume_1 = db.Column(db.Numeric(20, 0), comment='买卖盘买一量')
    bid_volume_2 = db.Column(db.Numeric(20, 0), comment='买卖盘买二量')
    bid_volume_3 = db.Column(db.Numeric(20, 0), comment='买卖盘买三量')
    bid_volume_4 = db.Column(db.Numeric(20, 0), comment='买卖盘买四量')
    bid_volume_5 = db.Column(db.Numeric(20, 0), comment='买卖盘买五量')
    
    ask_volume_1 = db.Column(db.Numeric(20, 0), comment='买卖盘卖一量')
    ask_volume_2 = db.Column(db.Numeric(20, 0), comment='买卖盘卖二量')
    ask_volume_3 = db.Column(db.Numeric(20, 0), comment='买卖盘卖三量')
    ask_volume_4 = db.Column(db.Numeric(20, 0), comment='买卖盘卖四量')
    ask_volume_5 = db.Column(db.Numeric(20, 0), comment='买卖盘卖五量')
    
    bid_price_1 = db.Column(db.Numeric(15, 4), comment='买一价')
    bid_price_2 = db.Column(db.Numeric(15, 4), comment='买二价')
    bid_price_3 = db.Column(db.Numeric(15, 4), comment='买三价')
    bid_price_4 = db.Column(db.Numeric(15, 4), comment='买四价')
    bid_price_5 = db.Column(db.Numeric(15, 4), comment='买五价')
    
    ask_price_1 = db.Column(db.Numeric(15, 4), comment='卖一价')
    ask_price_2 = db.Column(db.Numeric(15, 4), comment='卖二价')
    ask_price_3 = db.Column(db.Numeric(15, 4), comment='卖三价')
    ask_price_4 = db.Column(db.Numeric(15, 4), comment='卖四价')
    ask_price_5 = db.Column(db.Numeric(15, 4), comment='卖五价')
    
    # 板块信息
    industry = db.Column(db.String(50), comment='所属行业')
    market = db.Column(db.String(20), comment='市场类型:主板/中小板/创业板/科创板')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    # 复合索引
    __table_args__ = (
        db.Index('idx_stock_date', 'stock_code', 'trade_date'),
        db.Index('idx_trade_date', 'trade_date'),
        db.Index('idx_turnover', 'trade_date', 'turnover'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'volume': int(self.volume) if self.volume else None,
            'turnover': float(self.turnover) if self.turnover else None,
            'turnover_rate': float(self.turnover_rate) if self.turnover_rate else None,
            'change': float(self.change) if self.change else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'industry': self.industry,
            'market': self.market,
        }

