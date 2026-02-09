"""
股票基本信息模型
存储股票的静态元数据信息
"""
from extensions import db
from datetime import datetime


class StockBasic(db.Model):
    """
    股票基本信息表
    存储股票的静态元数据，如公司名称、上市日期、交易所等
    """
    __tablename__ = 'stock_basic'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # 股票代码和名称
    stock_code = db.Column(db.String(20), unique=True, nullable=False, comment='股票代码，如 sh.600000')
    stock_name = db.Column(db.String(50), nullable=False, comment='股票名称')
    
    # 交易所和市场
    exchange = db.Column(db.String(10), comment='交易所: sh-上海, sz-深圳')
    market = db.Column(db.String(20), comment='市场类型: 主板/中小板/创业板/科创板')
    
    # 公司基本信息
    company_name = db.Column(db.String(200), comment='公司全称')
    industry = db.Column(db.String(50), comment='所属行业')
    area = db.Column(db.String(50), comment='所在地区')
    
    # 上市信息
    list_date = db.Column(db.String(10), comment='上市日期 YYYY-MM-DD')
    delist_date = db.Column(db.String(10), comment='退市日期 YYYY-MM-DD')
    is_hs = db.Column(db.Integer, default=0, comment='是否沪深港通: 0-否, 1-是')
    
    # 股本信息
    total_shares = db.Column(db.Numeric(20, 2), comment='总股本(万股)')
    circulate_shares = db.Column(db.Numeric(20, 2), comment='流通股本(万股)')
    
    # 扩展信息
    remarks = db.Column(db.String(500), comment='备注')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联关系 - 使用primaryjoin指定股票代码关联
    sector_relations = db.relationship('StockSectorRelation', 
        primaryjoin="foreign(StockSectorRelation.stock_code)==StockBasic.stock_code",
        backref='stock', 
        lazy='dynamic')

    __table_args__ = (
        db.Index('idx_stock_exchange', 'exchange'),
        db.Index('idx_stock_industry', 'industry'),
        db.Index('idx_stock_list_date', 'list_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'exchange': self.exchange,
            'market': self.market,
            'company_name': self.company_name,
            'industry': self.industry,
            'area': self.area,
            'list_date': self.list_date,
            'delist_date': self.delist_date,
            'is_hs': self.is_hs,
            'total_shares': float(self.total_shares) if self.total_shares else None,
            'circulate_shares': float(self.circulate_shares) if self.circulate_shares else None,
            'remarks': self.remarks,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None,
        }

