#!/usr/bin/env python3
"""
数据库初始化脚本
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db


def init_database():
    """初始化数据库"""
    app = create_app('development')
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("数据库表创建成功！")


if __name__ == '__main__':
    init_database()
