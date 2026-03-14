"""
每日笔记模型 - 存储大盘分析和明日操作
"""
from datetime import datetime
from extensions import db


class DailyNote(db.Model):
    """每日笔记实体类"""
    __tablename__ = 'daily_note'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    trade_date = db.Column(db.String(10), nullable=False, unique=True, comment='交易日期(YYYY-MM-DD)，唯一key')
    market_analysis = db.Column(db.Text, nullable=True, comment='大盘分析（富文本）')
    next_action = db.Column(db.Text, nullable=True, comment='明日操作（富文本）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'tradeDate': self.trade_date,
            'marketAnalysis': self.market_analysis,
            'nextAction': self.next_action,
            'createTime': self.create_time.isoformat() if self.create_time else None,
            'updateTime': self.update_time.isoformat() if self.update_time else None,
            # 兼容下划线命名
            'trade_date': self.trade_date,
            'market_analysis': self.market_analysis,
            'next_action': self.next_action,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }
