"""
股票标签模型
存储自定义标签和股票标签关联
"""
from extensions import db
from datetime import datetime


class StockTag(db.Model):
    """
    股票标签表
    存储用户自定义的标签
    """
    __tablename__ = 'stock_tag'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # 标签名称
    name = db.Column(db.String(50), nullable=False, comment='标签名称')
    
    # 标签颜色
    color = db.Column(db.String(20), default='#409EFF', comment='标签颜色')
    
    # 创建时间
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    stock_relations = db.relationship('StockTagRelation', backref='tag', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('name', name='uk_tag_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }


class StockTagRelation(db.Model):
    """
    股票标签关联表
    存储股票和标签的多对多关系
    """
    __tablename__ = 'stock_tag_relation'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # 股票代码
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码')
    
    # 标签ID
    tag_id = db.Column(db.BigInteger, db.ForeignKey('stock_tag.id', ondelete='CASCADE'), nullable=False, comment='标签ID')
    
    # 创建时间
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'tag_id', name='uk_stock_tag'),
        db.Index('idx_stock_code', 'stock_code'),
        db.Index('idx_tag_id', 'tag_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'tag_id': self.tag_id,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
