"""
炒股笔记模型 - 存储股票投资心得
"""
from datetime import datetime
from extensions import db


class StockNote(db.Model):
    """炒股笔记实体类"""
    __tablename__ = 'stock_note'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    # 关联股票代码（可选，不关联时为通用笔记）
    stock_code = db.Column(db.String(10), nullable=True, index=True, comment='股票代码')
    stock_name = db.Column(db.String(50), nullable=True, comment='股票名称')
    # 笔记内容（富文本 HTML）
    content = db.Column(db.Text, nullable=False, comment='笔记内容（富文本）')
    # 标题（自动从内容提取或手动填写）
    title = db.Column(db.String(200), nullable=True, comment='笔记标题')
    # 标签（逗号分隔）
    tags = db.Column(db.String(500), nullable=True, comment='标签，多个用逗号分隔')
    # 是否置顶
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'stockCode': self.stock_code,
            'stockName': self.stock_name,
            'content': self.content,
            'title': self.title,
            'tags': self.tags,
            'isPinned': self.is_pinned,
            'createTime': self.create_time.isoformat() if self.create_time else None,
            'updateTime': self.update_time.isoformat() if self.update_time else None,
        }
