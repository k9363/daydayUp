#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入股票交割单数据
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import csv
import re
from datetime import datetime
from app import create_app, db
from models.delivery import StockDelivery


def has_letters(text):
    """检查文本是否包含字母"""
    if not text:
        return False
    return bool(re.search(r'[a-zA-Z]', str(text)))


def parse_number(value):
    """解析数字"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_int(value):
    """解析整数"""
    if value is None or value == '':
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def import_delivery_data(file_path):
    """导入交割单数据"""
    app = create_app()
    
    with app.app_context():
        # 清空旧数据（可选）
        # db.session.query(StockDelivery).delete()
        # db.session.commit()
        
        imported_count = 0
        skipped_letters = 0
        skipped_apply_allotment = 0
        
        with open(file_path, 'r', encoding='gbk', errors='replace') as f:
            reader = csv.reader(f, delimiter='\t')
            rows = list(reader)
        
        # Skip header
        for row in rows[1:]:
            if not row or len(row) < 21:
                continue
            
            try:
                # 提取字段
                trade_date = row[0].strip()  # 成交日期
                trade_time = row[1].strip()  # 成交时间
                security_code = row[2].strip()  # 证券代码
                security_name = row[3].strip()  # 证券名称
                operation = row[4].strip()  # 操作
                
                # 过滤条件1: 证券名称包含字母
                if has_letters(security_name):
                    skipped_letters += 1
                    print(f"跳过（证券名称含字母）: {security_name} - {operation}")
                    continue
                
                # 过滤条件2: 操作是"申请配号"
                if operation == '申请配号':
                    skipped_apply_allotment += 1
                    print(f"跳过（申请配号）: {security_code} {security_name}")
                    continue
                
                # 创建记录
                delivery = StockDelivery(
                    trade_date=trade_date,
                    trade_time=trade_time if trade_time else None,
                    security_code=security_code,
                    security_name=security_name if security_name else None,
                    operation=operation if operation else None,
                    quantity=parse_int(row[5]),
                    deal_no=row[6].strip() if len(row) > 6 else None,
                    price=parse_number(row[7]),
                    amount=parse_number(row[8]),
                    balance=parse_number(row[9]),
                    stock_balance=parse_int(row[10]),
                    occur_amount=parse_number(row[11]),
                    commission=parse_number(row[12]),
                    stamp_duty=parse_number(row[13]),
                    other_fee=parse_number(row[14]),
                    fund_balance=parse_number(row[15]),
                    current_amount=parse_number(row[16]),
                    contract_no=row[17].strip() if len(row) > 17 else None,
                    other_expense=parse_number(row[18]) if len(row) > 18 else None,
                    transfer_fee=parse_number(row[19]) if len(row) > 19 else None,
                    market=row[20].strip() if len(row) > 20 else None,
                )
                
                db.session.add(delivery)
                imported_count += 1
                
                # 批量提交
                if imported_count % 100 == 0:
                    db.session.commit()
                    print(f"已导入 {imported_count} 条记录...")
                    
            except Exception as e:
                print(f"导入错误: {e}, row: {row[:5]}")
                continue
        
        # 最后提交
        db.session.commit()
        
        print(f"\n=== 导入完成 ===")
        print(f"成功导入: {imported_count} 条")
        print(f"跳过（证券名称含字母）: {skipped_letters} 条")
        print(f"跳过（申请配号）: {skipped_apply_allotment} 条")
        print(f"总计: {imported_count + skipped_letters + skipped_apply_allotment} 条")


if __name__ == '__main__':
    file_path = '/Users/jxh/Desktop/table.xls'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    print(f"开始导入文件: {file_path}")
    import_delivery_data(file_path)

