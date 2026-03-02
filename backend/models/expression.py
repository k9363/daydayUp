"""
表达式配置模型
用于存储股票、板块、大盘的得分表达式配置
"""
from extensions import db
from datetime import datetime


class ScoreExpression(db.Model):
    """得分表达式配置表"""
    __tablename__ = 'score_expression'
    
    id = db.Column(db.Integer, primary_key=True)
    expression_name = db.Column(db.String(100), nullable=False, comment='表达式名称')
    
    # 作用域: stock-股票, sector-板块, market-大盘
    scope = db.Column(db.String(20), nullable=False, default='stock', comment='作用域')
    
    # 使用的因子列表 (JSON格式: ["factor1", "factor2"])
    factors = db.Column(db.JSON, comment='使用因子列表')
    
    # 计算表达式 (如: "factor1 + factor2 * 0.5")
    expression = db.Column(db.Text, nullable=False, comment='计算表达式')
    
    # 板块/大盘专用: 取前N
    top_n = db.Column(db.Integer, comment='取前N')
    
    # 描述
    description = db.Column(db.String(500), comment='描述')
    
    # 是否为默认表达式
    is_default = db.Column(db.Boolean, default=False, comment='是否为默认表达式')
    
    # 状态
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'expression_name': self.expression_name,
            'scope': self.scope,
            'factors': self.factors or [],
            'expression': self.expression,
            'top_n': self.top_n,
            'description': self.description,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<ScoreExpression {self.expression_name}: {self.scope}>'


# 表达式作用域常量
class ExpressionScope:
    STOCK = 'stock'      # 股票
    SECTOR = 'sector'   # 板块
    MARKET = 'market'   # 大盘
    
    CHOICES = [
        (STOCK, '股票'),
        (SECTOR, '板块'),
        (MARKET, '大盘'),
    ]
