"""
复盘结果模型
"""
from datetime import datetime
from extensions import db


class ReviewResult(db.Model):
    """复盘结果实体类"""
    __tablename__ = 'review_result'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    task_id = db.Column(db.BigInteger, db.ForeignKey('review_task.id'), nullable=False, comment='关联的复盘任务ID')
    dimension = db.Column(db.String(100), nullable=True, comment='分析维度')
    metric_name = db.Column(db.String(100), nullable=False, comment='指标名称')
    metric_value = db.Column(db.String(100), nullable=True, comment='指标值')
    compare_value = db.Column(db.String(100), nullable=True, comment='对比值')
    change_rate = db.Column(db.Float, nullable=True, comment='变化率')
    status = db.Column(db.String(20), default='normal', comment='状态: normal-正常, warning-警告, critical-严重')
    suggestion = db.Column(db.Text, nullable=True, comment='分析建议')
    detail_data = db.Column(db.Text, nullable=True, comment='详细数据(JSON格式)')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'dimension': self.dimension,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'compare_value': self.compare_value,
            'change_rate': self.change_rate,
            'status': self.status,
            'suggestion': self.suggestion,
            'detail_data': self.detail_data,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }

