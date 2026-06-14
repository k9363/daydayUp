#!/usr/bin/env python3
"""
Phase 2c: 赢家配置稳健性检验（2026-06-14）

固定 Phase 2b 赢家配置: 进所有底部信号 + 跌破MA60退出(需先收复) + 不叠加超买退出。
检验: 4 个基准(中证1000/中证500/沪深300/上证) × 3 个区间(全程/前半<2016-09/后半>=2016-09),
看择时是否在多基准、两个半段都跑赢买入持有(确认非单段单基准运气)。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/rb.py
"""
import math
from app import create_app

IDX = 'sh.000001'
EXIT_MA = 60
RT = 0.001
SPLIT = '2016-09-01'
BASKETS = [('中证1000', 'sh.000852'), ('中证500', 'sh.000905'), ('沪深300', 'sh.000300'), ('上证', 'sh.000001')]
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
        import pandas as pd, numpy as np
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 600})) ()

        def series(c):
            r = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                 "WHERE stock_code=:c AND close_price>0 ORDER BY trade_date"), {"c": c}).fetchall()
            return pd.Series({str(d): float(p) for d, p in r})
        ic = series(IDX)
        dates = list(ic.index); pos = {d: i for i, d in enumerate(dates)}
        mser = ic.rolling(EXIT_MA).mean()
        bias20 = (ic / ic.rolling(20).mean() - 1) * 100  # 未用(不超买退出),保留口径
        # 生成持仓段(基准无关,信号全来自上证)
        ents = sorted(e for e in ENTRIES if e in pos)
        holds = []; last = -1
        for e in ents:
            ei = pos[e]
            if ei <= last:
                continue
            above = False; xi = None
            for j in range(ei + 1, len(dates)):
                d = dates[j]; mv = mser.get(d, float('nan'))
                if not math.isnan(mv) and ic[d] >= mv:
                    above = True
                if above and not math.isnan(mv) and ic[d] < mv:
                    xi = j; break
            holds.append((e, dates[xi if xi else len(dates) - 1])); last = (xi if xi else len(dates) - 1)
        print(f"[cfg] 配置: 进所有底/MA{EXIT_MA}退出/不超买退; 持仓段{len(holds)}", flush=True)

        def metr_timed(bk, lo, hi):
            bkd = [d for d in dates if d in bk and lo <= d < hi]
            if len(bkd) < 100:
                return None
            nav = 1.0; navs = []; indays = 0; rets = []
            for e, x in holds:
                if lo <= e < hi and e in bk and x in bk:
                    r = bk[x] / bk[e] - 1 - RT
                    rets.append(r); nav *= (1 + r); navs.append(nav); indays += pos[x] - pos[e]
            if not navs:
                return (0, 0, 0, 0, 0)
            navs = np.array(navs)
            tot = navs[-1] - 1
            ann = navs[-1] ** (242.0 / len(bkd)) - 1
            mdd = float((navs / np.maximum.accumulate(navs) - 1).min())
            return (tot * 100, ann * 100, mdd * 100, indays / len(bkd) * 100, (np.array(rets) > 0).mean() * 100)

        def metr_bh(bk, lo, hi):
            sd = [d for d in dates if d in bk and lo <= d < hi]
            if len(sd) < 100:
                return None
            tot = bk[sd[-1]] / bk[sd[0]] - 1
            ann = (1 + tot) ** (242.0 / len(sd)) - 1
            n = np.array([bk[d] for d in sd]) / bk[sd[0]]
            return (tot * 100, ann * 100, float((n / np.maximum.accumulate(n) - 1).min()) * 100)

        periods = [('全程', '1900', '9999'), ('前半<2016-09', '1900', SPLIT), ('后半>=2016-09', SPLIT, '9999')]
        for nm, code in BASKETS:
            bk = series(code)
            if len(bk) < 200:
                print(f"\n=== {nm}: 无数据,跳过 ==="); continue
            print(f"\n=== 基准 {nm} ===")
            print(f"{'区间':<14}{'择时总%':>9}{'择时年化':>9}{'择时回撤':>9}{'在场%':>7}{'胜%':>6} | {'买持总%':>9}{'买持年化':>9}{'买持回撤':>9}{'  赢?':>5}")
            for pn, lo, hi in periods:
                t = metr_timed(bk, lo, hi); b = metr_bh(bk, lo, hi)
                if not t or not b:
                    print(f"{pn:<14} (区间无数据)"); continue
                win = '✓' if t[0] > b[0] else '✗'
                print(f"{pn:<14}{t[0]:>9.0f}{t[1]:>9.1f}{t[2]:>9.0f}{t[3]:>7.0f}{t[4]:>6.0f} | {b[0]:>9.0f}{b[1]:>9.1f}{b[2]:>9.0f}{win:>5}")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
