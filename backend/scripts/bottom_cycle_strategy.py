#!/usr/bin/env python3
"""
Phase 2: 底部择时完整轮回回测（2026-06-13）

策略: 底部确认进场 → 持有 → 上证超买(顶) 或 跌破 MA(破位) 清仓 → 等下个底，周而复始。
- 进场信号 = bottom_events_reconstruct.py 的每个底部事件的**首个确认日**(可实现,非事后低点)。
- 退出 = 上证 bias20≥2.5 或 RSI6≥75(顶) 或 close<MA{EXIT_MA}(破位)。
- 篮子分别用 上证/沪深300/中证500/中证1000 对比(看小盘弹性);成本往返 0.1%。
对比: 择时轮回 vs 同一篮子买入持有。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/bc.py [exit_ma]
"""
import sys
import math
from app import create_app

IDX = 'sh.000001'
EXIT_MA = int(sys.argv[1]) if len(sys.argv) > 1 else 20
RT_COST = 0.001
BASKETS = {'上证': 'sh.000001', '沪深300': 'sh.000300', '中证500': 'sh.000905', '中证1000': 'sh.000852'}
# 各底部事件首个确认日(来自 bottom_events_reconstruct.py,可实现进场信号)
ENTRIES = ['2007-02-02', '2007-06-04', '2007-06-29', '2007-11-08', '2008-01-21', '2008-05-26', '2008-08-05',
           '2008-12-23', '2009-02-26', '2009-08-12', '2009-09-28', '2009-11-27', '2010-04-19', '2010-06-29',
           '2010-11-16', '2011-01-17', '2011-05-27', '2011-07-25', '2011-11-30', '2012-01-05', '2012-03-28',
           '2012-06-25', '2013-03-04', '2013-06-20', '2014-03-10', '2014-04-28', '2015-02-02', '2015-05-07',
           '2015-06-19', '2015-11-27', '2016-01-04', '2016-02-29', '2016-05-09', '2017-05-08', '2017-08-11',
           '2018-02-06', '2018-03-23', '2018-05-30', '2018-08-03', '2018-10-11', '2019-04-29', '2020-01-23',
           '2020-02-28', '2020-09-09', '2021-03-08', '2021-07-27', '2022-01-25', '2022-03-15', '2022-04-25',
           '2023-06-26', '2024-02-05', '2025-01-02', '2025-04-07', '2025-11-21', '2026-02-02', '2026-03-23',
           '2026-06-08']


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        import pandas as pd
        import numpy as np
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 600})) ()

        def series(code):
            r = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                 "WHERE stock_code=:c AND close_price>0 ORDER BY trade_date"), {"c": code}).fetchall()
            return pd.Series({str(d): float(p) for d, p in r})
        ic = series(IDX)
        dates = list(ic.index); pos = {d: i for i, d in enumerate(dates)}
        ma = ic.rolling(EXIT_MA).mean()
        bias20 = (ic / ic.rolling(20).mean() - 1) * 100
        delta = ic.diff()
        ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean()
        al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
        rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))

        entries = sorted(e for e in ENTRIES if e in pos)
        print(f"[cfg] 退出MA={EXIT_MA} 进场信号{len(entries)}个 区间{dates[0]}~{dates[-1]}", flush=True)

        # 生成持仓区间(进场→退出),跳过持仓中又触发的进场。
        # 退出=超买(顶) 或 破位;破位仅在"价格已收复MA后再跌破"才算(底部进场时本就在MA下方,
        # 不能一进场就判破位 → 必须先站上MA确认上升,之后跌破才退)。
        holds = []
        last_exit_i = -1
        for e in entries:
            ei = pos[e]
            if ei <= last_exit_i:
                continue
            above = False
            xi = None
            for j in range(ei + 1, len(dates)):
                d = dates[j]
                mv = ma.get(d, float('nan'))
                if not math.isnan(mv) and ic[d] >= mv:
                    above = True
                ob = (bias20.get(d, 0) >= 2.5) or (rsi6.get(d, 0) >= 75)
                brk = above and not math.isnan(mv) and ic[d] < mv
                if ob or brk:
                    xi = j; break
            if xi is None:
                xi = len(dates) - 1
            holds.append((e, dates[xi])); last_exit_i = xi
        in_days = sum(pos[x] - pos[e] for e, x in holds)
        print(f"[holds] {len(holds)} 段持仓, 在场交易日 {in_days}/{len(dates)} ({in_days/len(dates)*100:.0f}%), 平均持有 {in_days/len(holds):.0f}日", flush=True)

        def stat(navs, n_cycles, ppy_days):
            navs = np.array(navs)
            tot = navs[-1] - 1
            yrs = ppy_days / 242.0
            ann = navs[-1] ** (1 / yrs) - 1 if yrs > 0 else float('nan')
            mdd = float((navs / np.maximum.accumulate(navs) - 1).min())
            return tot, ann, mdd

        print(f"\n{'='*92}")
        print(f"底部择时轮回 vs 买入持有  (退出=超买或破MA{EXIT_MA},费{RT_COST*100:.1f}%往返)")
        print(f"{'='*92}")
        print(f"{'篮子':<10}{'择时总收益':>11}{'年化':>8}{'回撤':>8}{'胜率':>7} | {'买持总收益':>11}{'买持年化':>9}{'买持回撤':>9}")
        full_yrs = (pos[dates[-1]] - pos[dates[0]])
        for nm, code in BASKETS.items():
            s = series(code)
            if len(s) < 200:
                print(f"{nm:<10} (无数据,跳过)"); continue
            sd = [d for d in dates if d in s]   # 该篮子有数据的交易日(全程)
            # 择时:逐段 close[exit]/close[entry]-1 - 费;段间现金
            rets, navs, nav = [], [], 1.0
            for e, x in holds:
                if e in s and x in s:
                    r = s[x] / s[e] - 1 - RT_COST
                    rets.append(r); nav *= (1 + r); navs.append(nav)
            if not navs:
                continue
            tot, ann, mdd = stat(navs, len(holds), len(sd))   # 年化按全程折算(含空仓,公平对比买持)
            win = (np.array(rets) > 0).mean() * 100
            # 买入持有(全程)
            bh_tot = s[sd[-1]] / s[sd[0]] - 1
            bh_ann = (1 + bh_tot) ** (242.0 / len(sd)) - 1
            bh_nav = np.array([s[d] for d in sd]) / s[sd[0]]
            bh_mdd = float((bh_nav / np.maximum.accumulate(bh_nav) - 1).min())
            print(f"{nm:<10}{tot*100:>10.0f}%{ann*100:>7.1f}%{mdd*100:>7.0f}%{win:>6.0f}% | "
                  f"{bh_tot*100:>10.0f}%{bh_ann*100:>8.1f}%{bh_mdd*100:>8.0f}%")
        print("\n注: 择时年化按在场天数折算(非全程),与买持年化口径不同;在场天数比例见上。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
