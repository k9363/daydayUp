#!/usr/bin/env python3
"""
数据库迁移脚本
更新 stock_daily 表结构以匹配模型定义
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from extensions import db
from flask import Flask
from config import config

def run_migration():
    """执行数据库迁移"""
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)
    
    with app.app_context():
        # 获取 stock_daily 表的现有列
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_columns = [c['name'] for c in inspector.get_columns('stock_daily')]
        
        print(f"现有列: {existing_columns}")
        
        # 需要添加的列
        columns_to_add = [
            ('bid_volume_1', 'NUMERIC(20, 0)', '买卖盘买一量'),
            ('bid_volume_2', 'NUMERIC(20, 0)', '买卖盘买二量'),
            ('bid_volume_3', 'NUMERIC(20, 0)', '买卖盘买三量'),
            ('bid_volume_4', 'NUMERIC(20, 0)', '买卖盘买四量'),
            ('bid_volume_5', 'NUMERIC(20, 0)', '买卖盘买五量'),
            ('ask_volume_1', 'NUMERIC(20, 0)', '买卖盘卖一量'),
            ('ask_volume_2', 'NUMERIC(20, 0)', '买卖盘卖二量'),
            ('ask_volume_3', 'NUMERIC(20, 0)', '买卖盘卖三量'),
            ('ask_volume_4', 'NUMERIC(20, 0)', '买卖盘卖四量'),
            ('ask_volume_5', 'NUMERIC(20, 0)', '买卖盘卖五量'),
            ('bid_price_1', 'NUMERIC(15, 4)', '买一价'),
            ('bid_price_2', 'NUMERIC(15, 4)', '买二价'),
            ('bid_price_3', 'NUMERIC(15, 4)', '买三价'),
            ('bid_price_4', 'NUMERIC(15, 4)', '买四价'),
            ('bid_price_5', 'NUMERIC(15, 4)', '买五价'),
            ('ask_price_1', 'NUMERIC(15, 4)', '卖一价'),
            ('ask_price_2', 'NUMERIC(15, 4)', '卖二价'),
            ('ask_price_3', 'NUMERIC(15, 4)', '卖三价'),
            ('ask_price_4', 'NUMERIC(15, 4)', '卖四价'),
            ('ask_price_5', 'NUMERIC(15, 4)', '卖五价'),
            ('industry', 'VARCHAR(50)', '所属行业'),
            ('market', 'VARCHAR(20)', '市场类型'),
        ]
        
        # 检查并添加缺失的列
        added_columns = []
        for col_name, col_type, comment in columns_to_add:
            if col_name not in existing_columns:
                sql = f"ALTER TABLE stock_daily ADD COLUMN {col_name} {col_type} COMMENT '{comment}'"
                try:
                    db.session.execute(db.text(sql))
                    added_columns.append(col_name)
                    print(f"已添加列: {col_name}")
                except Exception as e:
                    print(f"添加列 {col_name} 失败: {e}")
        
        if added_columns:
            db.session.commit()
            print(f"\n成功添加 {len(added_columns)} 个列:")
            for col in added_columns:
                print(f"  - {col}")
        else:
            print("\n没有需要添加的列，数据库结构已是最新的。")
        
        # 检查索引
        existing_indexes = [i['name'] for i in inspector.get_indexes('stock_daily')]
        print(f"\n现有索引: {existing_indexes}")
        
        # 需要添加的索引
        indexes_to_add = [
            ('idx_turnover', 'trade_date, turnover'),
        ]
        
        added_indexes = []
        for idx_name, columns in indexes_to_add:
            if idx_name not in existing_indexes:
                sql = f"CREATE INDEX {idx_name} ON stock_daily ({columns})"
                try:
                    db.session.execute(db.text(sql))
                    added_indexes.append(idx_name)
                    print(f"已添加索引: {idx_name}")
                except Exception as e:
                    print(f"添加索引 {idx_name} 失败: {e}")
        
        if added_indexes:
            db.session.commit()
            print(f"\n成功添加 {len(added_indexes)} 个索引:")
            for idx in added_indexes:
                print(f"  - {idx}")

if __name__ == '__main__':
    run_migration()

