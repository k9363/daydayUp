"""
股票交割单模型
存储个人股票交易历史记录
"""
from extensions import db
from datetime import datetime
import re


class StockDelivery(db.Model):
    """
    股票交割单表
    存储个人股票交易历史记录
    """
    __tablename__ = 'stock_delivery'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # 交易日期和时间
    trade_date = db.Column(db.String(10), nullable=False, comment='成交日期 YYYYMMDD')
    trade_time = db.Column(db.String(8), comment='成交时间 HH:MM:SS')
    
    # 证券信息
    security_code = db.Column(db.String(20), nullable=False, comment='证券代码')
    security_name = db.Column(db.String(50), comment='证券名称')
    
    # 操作类型
    operation = db.Column(db.String(20), comment='操作: 买入/卖出/配股等')
    
    # 成交信息
    quantity = db.Column(db.Integer, comment='成交数量')
    deal_no = db.Column(db.String(50), comment='成交编号')
    price = db.Column(db.Numeric(16, 3), comment='成交价格')
    amount = db.Column(db.Numeric(16, 2), comment='成交金额')
    
    # 余额
    balance = db.Column(db.Numeric(16, 2), comment='余额')
    stock_balance = db.Column(db.Integer, comment='股票余额')
    
    # 发生金额
    occur_amount = db.Column(db.Numeric(16, 2), comment='发生金额')
    
    # 费用
    commission = db.Column(db.Numeric(16, 3), comment='佣金')
    stamp_duty = db.Column(db.Numeric(16, 3), comment='印花税')
    other_fee = db.Column(db.Numeric(16, 3), comment='其他杂费')
    transfer_fee = db.Column(db.Numeric(16, 3), comment='过户费')
    other_expense = db.Column(db.Numeric(16, 3), comment='其他费')
    
    # 资金
    fund_balance = db.Column(db.Numeric(16, 2), comment='资金余额')
    current_amount = db.Column(db.Numeric(16, 2), comment='本次金额')
    
    # 合同编号
    contract_no = db.Column(db.String(20), comment='合同编号')
    
    # 交易市场
    market = db.Column(db.String(20), comment='交易市场')
    
    # 复盘记录
    review_note = db.Column(db.Text, comment='复盘记录')
    
    # 创建时间
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        db.Index('idx_trade_date', 'trade_date'),
        db.Index('idx_security_code', 'security_code'),
        db.Index('idx_operation', 'operation'),
        db.UniqueConstraint('deal_no', name='uq_deal_no'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'trade_date': self.trade_date,
            'trade_time': self.trade_time,
            'security_code': self.security_code,
            'security_name': self.security_name,
            'operation': self.operation,
            'quantity': self.quantity,
            'deal_no': self.deal_no,
            'price': float(self.price) if self.price else None,
            'amount': float(self.amount) if self.amount else None,
            'balance': float(self.balance) if self.balance else None,
            'stock_balance': self.stock_balance,
            'occur_amount': float(self.occur_amount) if self.occur_amount else None,
            'commission': float(self.commission) if self.commission else None,
            'stamp_duty': float(self.stamp_duty) if self.stamp_duty else None,
            'other_fee': float(self.other_fee) if self.other_fee else None,
            'transfer_fee': float(self.transfer_fee) if self.transfer_fee else None,
            'other_expense': float(self.other_expense) if self.other_expense else None,
            'fund_balance': float(self.fund_balance) if self.fund_balance else None,
            'current_amount': float(self.current_amount) if self.current_amount else None,
            'contract_no': self.contract_no,
            'market': self.market,
            'review_note': self.review_note,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
    
    @staticmethod
    def has_letters(text):
        """检查文本是否包含字母"""
        if not text:
            return False
        # 检查是否包含任何英文字母
        return bool(re.search(r'[a-zA-Z]', str(text)))

