"""
复盘任务模型
"""
from datetime import datetime
from extensions import db


class ReviewTask(db.Model):
    """复盘任务实体类"""
    __tablename__ = 'review_task'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    task_name = db.Column(db.String(100), nullable=False, comment='任务名称')
    
    # 数据源信息（原 DataSource 和 DataRecord 的字段）
    data_source_type = db.Column(db.String(20), default='baostock', comment='数据源类型: excel, csv, database, api, stock, baostock')
    data_source_name = db.Column(db.String(100), comment='数据源名称')
    data_source_desc = db.Column(db.String(500), comment='数据源描述')
    file_path = db.Column(db.String(500), comment='文件路径')
    stock_code = db.Column(db.String(20), comment='股票代码')
    trade_date = db.Column(db.String(10), comment='交易日期(YYYY-MM-DD)')
    row_count = db.Column(db.Integer, default=0, comment='数据行数')
    column_count = db.Column(db.Integer, default=0, comment='列数')
    data_summary = db.Column(db.Text, comment='数据摘要')
    
    # 复盘配置
    review_type = db.Column(db.String(20), nullable=False, comment='复盘类型: daily-日复盘, weekly-周复盘, monthly-月复盘, custom-自定义')
    dimensions = db.Column(db.Text, comment='分析维度(JSON数组)')
    rules = db.Column(db.Text, comment='复盘规则(JSON格式)')
    
    # 执行状态
    status = db.Column(db.String(20), default='pending', comment='状态: pending-待执行, running-执行中, completed-已完成, failed-失败')
    result_summary = db.Column(db.Text, comment='执行结果摘要')
    start_time = db.Column(db.DateTime, comment='开始时间')
    end_time = db.Column(db.DateTime, comment='结束时间')
    error_message = db.Column(db.Text, comment='错误信息')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 关联关系
    results = db.relationship('ReviewResult', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'taskName': self.task_name,
            'dataSourceType': self.data_source_type,
            'dataSourceName': self.data_source_name,
            'dataSourceDesc': self.data_source_desc,
            'filePath': self.file_path,
            'stockCode': self.stock_code,
            'tradeDate': self.trade_date,
            'rowCount': self.row_count,
            'columnCount': self.column_count,
            'dataSummary': self.data_summary,
            'reviewType': self.review_type,
            'dimensions': self.dimensions,
            'rules': self.rules,
            'status': self.status,
            'resultSummary': self.result_summary,
            'startTime': self.start_time.isoformat() if self.start_time else None,
            'endTime': self.end_time.isoformat() if self.end_time else None,
            'errorMessage': self.error_message,
            'createTime': self.create_time.isoformat() if self.create_time else None,
            'updateTime': self.update_time.isoformat() if self.update_time else None,
            # 兼容下划线命名
            'task_name': self.task_name,
            'data_source_type': self.data_source_type,
            'data_source_name': self.data_source_name,
            'data_source_desc': self.data_source_desc,
            'file_path': self.file_path,
            'stock_code': self.stock_code,
            'trade_date': self.trade_date,
            'row_count': self.row_count,
            'column_count': self.column_count,
            'data_summary': self.data_summary,
            'review_type': self.review_type,
            'dimensions': self.dimensions,
            'rules': self.rules,
            'result_summary': self.result_summary,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error_message': self.error_message,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }
    
    def to_dict_with_summary(self):
        """转换为字典(包含结果统计)"""
        total = self.results.count()
        normal = self.results.filter_by(status='normal').count()
        warning = self.results.filter_by(status='warning').count()
        critical = self.results.filter_by(status='critical').count()
        
        return {
            **self.to_dict(),
            'summary': {
                'total': total,
                'normal': normal,
                'warning': warning,
                'critical': critical
            }
        }
