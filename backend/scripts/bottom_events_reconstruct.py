#!/usr/bin/env python3
"""
忠实复刻 TA-CN 大盘底部确认信号，跑出 2007-2026 全部底部事件（Phase 1 地基）。

底部确认 = 超卖门控 + ≥1 恐慌确认（TA-CN topbottom_dashboard.build_market_gauge 同口径）：
  超卖 = 上证 bias20≤-3% 或 RSI6≤25（RSI6: ewm com=5 adjust=True）
  恐慌 = 跌停潮(全市场跌停家数250日分位≥0.90，不足则绝对>100) 或 抱团补跌(top100中位涨跌幅<-3%)
跌停近似: stock_type=stock 且 change_percent<=-9.7。top100=当日成交额前100(stock)。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/be.py
"""
import math
from app import create_app
IDX = 'sh.000001'
GAP = 15   # 两个底部确认日相隔>GAP个交易日 → 视为不同底部事件


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import pandas as pd
        import numpy as np
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 1800, 'connect_timeout': 30}))()

        # 1) 上证读数
        rows = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                "WHERE stock_code=:c AND close_price>0 ORDER BY trade_date"), {"c": IDX}).fetchall()
        ic = pd.Series({str(d): float(p) for d, p in rows})
        dates = list(ic.index)
        ma20 = ic.rolling(20).mean()
        bias20 = (ic / ma20 - 1) * 100
        delta = ic.diff()
        ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean()
        al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
        rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))
        oversold = (bias20 <= -3) | (rsi6 <= 25)
        print(f"[idx] 上证 {dates[0]}~{dates[-1]} {len(dates)}日，超卖日 {int(oversold.sum())}", flush=True)

        # 2+3) 仅在超卖日扫一次当日全市场(走 trade_date 索引,快)——同一次查询里同时算:
        #   跌停占比(跌停家数/当日数, 比例跨regime中性, 替代需全表+250日分位的跌停潮)
        #   top100中位涨跌幅(成交额前100)
        # 不做全表 GROUP BY(那张回填后大表无 change_percent 索引,全表扫太慢)。
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        os_days = [d for d in dates if bool(oversold.get(d))]
        day_breadth = {}   # D -> (top100_chg, ld_ratio, ld_count)
        import time as _t; _t0 = _t.time()
        for _i, D in enumerate(os_days):
            bts.rollback()
            if _i % 100 == 0:
                print(f"[breadth] {_i}/{len(os_days)} {_t.time()-_t0:.0f}s", flush=True)
            r = bts.execute(text("SELECT stock_code, turnover, change_percent FROM stock_daily_kline "
                                 "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            ss = [(c, float(t), cp) for c, t, cp in r if c in stock_set and cp is not None]
            if not ss:
                continue
            ld_cnt = sum(1 for _, _, cp in ss if cp <= -9.7)
            top100 = sorted(ss, key=lambda x: -x[1])[:100]
            day_breadth[D] = (float(np.median([x[2] for x in top100])), ld_cnt / len(ss), ld_cnt)

        # 4) 底部确认 = 超卖 且 (跌停占比≥3% 或 top100中位<-3%)
        confirms = []
        for D in os_days:
            if D not in day_breadth:
                continue
            tc, ldr, ldn = day_breadth[D]
            panic = []
            if ldr >= 0.03:
                panic.append(f"跌停潮({ldn}家,占{ldr*100:.0f}%)")
            if tc < -3:
                panic.append(f"抱团补跌(top100中位{tc:+.1f}%)")
            if panic:
                confirms.append((D, float(bias20.get(D)), float(rsi6.get(D)), ldn, panic))

        # 5) 聚类成"底部事件"(相隔>GAP日另起)
        episodes = []
        for rec in confirms:
            D = rec[0]; di = dates.index(D)
            if episodes and di - dates.index(episodes[-1][-1][0]) <= GAP:
                episodes[-1].append(rec)
            else:
                episodes.append([rec])

        print(f"\n{'='*84}\n底部确认事件  共 {len(confirms)} 个确认日 → 聚成 {len(episodes)} 个底部事件\n{'='*84}")
        for ep in episodes:
            d0 = ep[0][0]; dn = ep[-1][0]
            # 事件内指数最低点
            lo_d = min(ep, key=lambda r: ic.get(r[0], 9e9))[0]
            print(f"\n■ {d0} ~ {dn}  ({len(ep)}个确认日)  指数低点日 {lo_d} 收{ic.get(lo_d):.0f}")
            for D, b, r6, ldn, panic in ep[:4]:
                print(f"    {D}  乖离{b:+.1f}% RSI6={r6:.0f} 跌停{ldn}  | {'、'.join(panic)}")
            if len(ep) > 4:
                print(f"    …共{len(ep)}个确认日")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
