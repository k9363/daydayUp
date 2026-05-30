"""
外部分析结果（如 TradingAgents-CN 的 LLM 多代理分析报告）的存档表。

设计：
- 一只股票一日一个来源最多一条（unique (stock_code, trade_date, source)）
- 关键字段：摘要 + 决策（买/卖/观望）+ 评分；原始 JSON 完整存档
- 关联 daydayUp 自己的 review_task（可选）便于前端复盘时拉报告卡片
"""
from datetime import datetime

from extensions import db


class ExternalAnalysis(db.Model):
    __tablename__ = 'external_analysis'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    source = db.Column(db.String(50), nullable=False, comment='来源系统标识，如 ta-cn')
    external_id = db.Column(db.String(100), nullable=True, comment='来源系统的分析 ID（如 TA-CN analysis_tasks.task_id）')
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码，如 sh.600000 或 600000')
    stock_name = db.Column(db.String(50), nullable=True, comment='股票名称（冗余）')
    trade_date = db.Column(db.String(10), nullable=True, comment='分析针对的交易日 YYYY-MM-DD')

    # 摘要 / 决策 / 评分（结构化以便前端筛选）
    decision = db.Column(db.String(20), nullable=True, comment='决策：buy/sell/hold/neutral')
    confidence = db.Column(db.Float, nullable=True, comment='置信度 0-1')
    target_price = db.Column(db.Float, nullable=True, comment='目标价（可选）')
    summary = db.Column(db.Text, nullable=True, comment='结论摘要（建议 200 字以内）')

    # 完整原始报告 JSON（避免丢失上下文）
    raw_report = db.Column(db.JSON, nullable=True, comment='原始多代理报告（含各 agent 输出）')
    report_url = db.Column(db.String(500), nullable=True, comment='完整报告页面 URL（如 TA-CN 前端）')

    # 关联 daydayUp 自己的复盘任务，便于前端联动（可选）
    related_review_task_id = db.Column(db.BigInteger, nullable=True, comment='关联的 review_task.id')

    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('source', 'external_id', name='uk_source_externalid'),
        db.Index('idx_stock_tradedate', 'stock_code', 'trade_date'),
        db.Index('idx_review_task', 'related_review_task_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source,
            'external_id': self.external_id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trade_date': self.trade_date,
            'decision': self.decision,
            'confidence': self.confidence,
            'target_price': self.target_price,
            'summary': self.summary,
            'raw_report': self.raw_report,
            'report_url': self.report_url,
            'related_review_task_id': self.related_review_task_id,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None,
        }
