"""
运行时初始化
"""
from extensions import db
from models import init_db

def init_app(app):
    """初始化应用"""
    # 初始化数据库
    init_db(app)
    
    # 返回app
    return app

