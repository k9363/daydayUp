#!/usr/bin/env python3
"""
测试 ma20 和 ma20_y1 的因子计算逻辑
"""
import sys
sys.path.insert(0, '/Users/jxh/Public/gugu/daydayUp/backend')

from app import app
from models.kline import StockDailyKLine
from datetime import datetime, timedelta
import pandas as pd

def test_ma20_ma20_y1(stock_code='000001', trade_date='2025-03-07'):
    """测试 ma20 和 ma20_y1 的计算"""
    
    with app.app_context():
        # 1. 查询该股票的历史K线（包含当天）
        end_date = datetime.strptime(trade_date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=60)
        start_str = start_date.strftime('%Y-%m-%d')
        
        klines = StockDailyKLine.query.filter(
            StockDailyKLine.stock_code == stock_code,
            StockDailyKLine.trade_date >= start_str,
            StockDailyKLine.trade_date <= trade_date,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).order_by(StockDailyKLine.trade_date.desc()).all()
        
        print(f"\n{'='*60}")
        print(f"股票代码: {stock_code}, 交易日期: {trade_date}")
        print(f"查询到 {len(klines)} 条历史K线数据")
        print(f"日期范围: {klines[-1].trade_date} ~ {klines[0].trade_date}")
        print(f"{'='*60}\n")
        
        # 2. 构建DataFrame（按日期降序）
        hist_data = []
        for k in klines:
            hist_data.append({
                'trade_date': k.trade_date,
                'close_price': float(k.close_price) if k.close_price else 0,
            })
        
        df = pd.DataFrame(hist_data)
        
        print("最近25天收盘价数据（降序）:")
        print(df.head(25).to_string(index=False))
        
        # 3. 手动计算 ma20（包含今天）
        if len(df) >= 20:
            ma20_today = df.head(20)['close_price'].mean()
            print(f"\n📊 ma20 (包含今天): {ma20_today:.4f}")
            print(f"    数据: {df.head(20)['trade_date'].tolist()}")
        
        # 4. 手动计算 ma20_y1（昨日MA20，从昨天开始往前20天）
        if len(df) >= 21:  # 需要至少21天才能计算昨日MA20
            ma20_y1 = df.head(21).iloc[1:21]['close_price'].mean()
            print(f"\n📊 ma20_y1 (昨日MA20, iloc[1:21]): {ma20_y1:.4f}")
            print(f"    数据: {df.head(21).iloc[1:21]['trade_date'].tolist()}")
        
        # 5. 使用代码中的逻辑计算
        print("\n" + "="*60)
        print("使用代码逻辑 (head(20).iloc[1:]):")
        
        if len(df) >= 20:
            ma20_code = df.head(20)['close_price'].mean()
            ma20_y1_code = df.head(20).iloc[1:]['close_price'].mean()
            print(f"    ma20 = head(20).mean(): {ma20_code:.4f}")
            print(f"    ma20_y1 = head(20).iloc[1:].mean(): {ma20_y1_code:.4f}")
        
        print("\n" + "="*60)
        
        # 6. 对比: 确认两者是否应该相同
        print("\n验证:")
        print(f"  ma20 (head(20)): {df.head(20)['trade_date'].tolist()}")
        print(f"  ma20_y1 (head(20).iloc[1:]): {df.head(20).iloc[1:]['trade_date'].tolist()}")
        
        # 正确的 ma20_y1 应该是: 从昨天开始往前20天 = head(21).iloc[1:21]
        print(f"\n正确的 ma20_y1 应该是: head(21).iloc[1:21]")
        if len(df) >= 21:
            correct_ma20_y1 = df.head(21).iloc[1:21]['close_price'].mean()
            print(f"  正确的 ma20_y1: {correct_ma20_y1:.4f}")

if __name__ == '__main__':
    # 测试几个股票
    test_ma20_ma20_y1('000001', '2025-03-07')
    print("\n\n")
    test_ma20_ma20_y1('000001', '2025-03-10')
