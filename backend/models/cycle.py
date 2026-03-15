from extensions import db
from datetime import datetime
from sqlalchemy import func


class Cycle(db.Model):
    """周期主表"""
    __tablename__ = 'cycle'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False, comment='周期标题')
    features = db.Column(db.Text, comment='周期特点')
    start_date = db.Column(db.String(20), nullable=False, comment='开始日期 YYYY-MM-DD')
    end_date = db.Column(db.String(20), comment='结束日期 YYYY-MM-DD')
    status = db.Column(db.String(20), default='active', comment='状态: active-进行中, completed-已结束')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联
    sub_periods = db.relationship('CycleSubPeriod', backref='cycle', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'features': self.features,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'status': self.status,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None,
            'sub_periods': [sp.to_dict() for sp in self.sub_periods.order_by(CycleSubPeriod.order_num).all()]
        }


class CycleSubPeriod(db.Model):
    """周期内的小周期"""
    __tablename__ = 'cycle_sub_period'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    cycle_id = db.Column(db.BigInteger, db.ForeignKey('cycle.id', ondelete='CASCADE'), nullable=False, comment='周期ID')
    period_type = db.Column(db.String(20), nullable=False, comment='小周期类型: chaos-混沌, rise-主升, oscillation-震荡, decline-退潮')
    name = db.Column(db.String(50), nullable=False, comment='小周期名称')
    features = db.Column(db.Text, comment='小周期特点')
    start_date = db.Column(db.String(20), nullable=False, comment='开始日期 YYYY-MM-DD')
    end_date = db.Column(db.String(20), comment='结束日期 YYYY-MM-DD')
    order_num = db.Column(db.Integer, default=0, comment='排序号')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联
    trade_days = db.relationship('CycleTradeDay', backref='sub_period', lazy='dynamic', cascade='all, delete-orphan')

    def trade_day_count(self):
        """按日期范围统计实际交易日数"""
        from models.reviewtask import ReviewTask
        query = db.session.query(func.count(func.distinct(ReviewTask.trade_date))).filter(
            ReviewTask.trade_date >= self.start_date
        )
        if self.end_date:
            query = query.filter(ReviewTask.trade_date <= self.end_date)
        return query.scalar() or 0

    def to_dict(self):
        return {
            'id': self.id,
            'cycle_id': self.cycle_id,
            'period_type': self.period_type,
            'name': self.name,
            'features': self.features,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'order_num': self.order_num,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None,
            'trade_day_count': self.trade_day_count()
        }


class CycleTradeDay(db.Model):
    """交易日与小周期关联"""
    __tablename__ = 'cycle_trade_day'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    sub_period_id = db.Column(db.BigInteger, db.ForeignKey('cycle_sub_period.id', ondelete='CASCADE'), nullable=False, comment='小周期ID')
    trade_date = db.Column(db.String(20), nullable=False, unique=True, comment='交易日期 YYYY-MM-DD')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    __table_args__ = (
        db.Index('idx_sub_period', 'sub_period_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'sub_period_id': self.sub_period_id,
            'trade_date': self.trade_date,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None
        }
