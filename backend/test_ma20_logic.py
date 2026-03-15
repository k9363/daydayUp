#!/usr/bin/env python3
"""
测试 ma20 和 ma20_y1 的计算逻辑
使用模拟数据验证
"""
import pandas as pd

def test_ma20_calculation():
    """使用模拟数据测试 ma20 和 ma20_y1 的计算"""
    
    # 模拟25天收盘价数据（降序：今天在前）
    data = [
        {'trade_date': '2025-03-07', 'close_price': 15.0},   # 0: 今天
        {'trade_date': '2025-03-06', 'close_price': 14.9},   # 1: 昨天
        {'trade_date': '2025-03-05', 'close_price': 14.8},   # 2
        {'trade_date': '2025-03-04', 'close_price': 14.7},   # 3
        {'trade_date': '2025-03-03', 'close_price': 14.6},   # 4
        {'trade_date': '2025-02-28', 'close_price': 14.5},   # 5
        {'trade_date': '2025-02-27', 'close_price': 14.4},   # 6
        {'trade_date': '2025-02-26', 'close_price': 14.3},   # 7
        {'trade_date': '2025-02-25', 'close_price': 14.2},   # 8
        {'trade_date': '2025-02-24', 'close_price': 14.1},   # 9
        {'trade_date': '2025-02-21', 'close_price': 14.0},   # 10
        {'trade_date': '2025-02-20', 'close_price': 13.9},   # 11
        {'trade_date': '2025-02-19', 'close_price': 13.8},   # 12
        {'trade_date': '2025-02-18', 'close_price': 13.7},   # 13
        {'trade_date': '2025-02-17', 'close_price': 13.6},   # 14
        {'trade_date': '2025-02-14', 'close_price': 13.5},   # 15
        {'trade_date': '2025-02-13', 'close_price': 13.4},   # 16
        {'trade_date': '2025-02-12', 'close_price': 13.3},   # 17
        {'trade_date': '2025-02-11', 'close_price': 13.2},   # 18
        {'trade_date': '2025-02-10', 'close_price': 13.1},   # 19
        {'trade_date': '2025-02-07', 'close_price': 13.0},   # 20
        {'trade_date': '2025-02-06', 'close_price': 12.9},   # 21
        {'trade_date': '2025-02-05', 'close_price': 12.8},   # 22
        {'trade_date': '2025-02-04', 'close_price': 12.7},   # 23
        {'trade_date': '2025-02-03', 'close_price': 12.6},   # 24
    ]
    
    df = pd.DataFrame(data)
    
    print("="*60)
    print("数据：最近25天收盘价（降序排列）")
    print("="*60)
    for i, row in df.head(25).iterrows():
        print(f"  [{i}] {row['trade_date']}: {row['close_price']}")
    
    print("\n" + "="*60)
    print("测试1: ma20 (包含今天) = head(20)")
    print("="*60)
    
    ma20_data = df.head(20)
    ma20 = ma20_data['close_price'].mean()
    print(f"数据条数: {len(ma20_data)}")
    print(f"数据范围: {ma20_data.iloc[-1]['trade_date']} ~ {ma20_data.iloc[0]['trade_date']}")
    print(f"ma20 = {ma20:.4f}")
    
    print("\n" + "="*60)
    print("测试2: ma20_y1 (昨日MA20) = head(21).iloc[1:21]")
    print("="*60)
    
    ma20_y1_data = df.head(21).iloc[1:21]
    ma20_y1 = ma20_y1_data['close_price'].mean()
    print(f"数据条数: {len(ma20_y1_data)}")
    print(f"数据范围: {ma20_y1_data.iloc[-1]['trade_date']} ~ {ma20_y1_data.iloc[0]['trade_date']}")
    print(f"ma20_y1 = {ma20_y1:.4f}")
    
    print("\n" + "="*60)
    print("测试3: 错误的写法 head(20).iloc[1:] (只有19条数据)")
    print("="*60)
    
    wrong_data = df.head(20).iloc[1:]
    wrong_ma20 = wrong_data['close_price'].mean()
    print(f"数据条数: {len(wrong_data)} (错误! 应该是20条)")
    print(f"ma20_y1(错误) = {wrong_ma20:.4f}")
    
    print("\n" + "="*60)
    print("结论")
    print("="*60)
    print(f"ma20 = {ma20:.4f}")
    print(f"ma20_y1 = {ma20_y1:.4f}")
    print(f"差值 = {ma20 - ma20_y1:.4f}")
    
    if ma20 != ma20_y1:
        print("\n✓ ma20 和 ma20_y1 不相等，逻辑正确！")
    else:
        print("\n✗ ma20 和 ma20_y1 相等，逻辑有问题！")

if __name__ == '__main__':
    test_ma20_calculation()
