#!/usr/bin/env python3
"""
Phase 2b: 底部择时轮回 系统性网格扫描（2026-06-14）

在 Phase 2 基础上扫描两个旋钮,找能跑赢买入持有或显著降回撤的组合:
  · 进场挑剔度: 只做 max跌停占比 ≥ LD_THRESH 的底(滤掉熊市假底),LD∈{0,10,30,50}
  · 退出: 趋势均线 EXIT_MA∈{20,30,60}(需先收复MA再跌破才算破位) × 是否叠加超买退出 OB∈{T,F}
篮子=中证1000(小盘弹性最能体现底部反弹);费0.1%往返;年化按全程(含空仓)折算。

进场=各底部事件首确认日,带 max跌停占比(来自 bottom_events_reconstruct.py)。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/sw.py
"""
import math
from app import create_app

IDX = 'sh.000001'
BASKET = 'sh.000852'   # 中证1000
RT = 0.001
# (首确认日, 该底max跌停占比%) —— 来自 bottom_events_reconstruct.py
ENTRIES = [('2007-02-02', 1), ('2007-06-04', 68), ('2007-06-29', 25), ('2007-11-08', 3), ('2008-01-21', 64),
           ('2008-05-26', 72), ('2008-08-05', 47), ('2008-12-23', 11), ('2009-02-26', 24), ('2009-08-12', 23),
           ('2009-09-28', 1), ('2009-11-27', 1), ('2010-04-19', 4), ('2010-06-29', 6), ('2010-11-16', 4),
           ('2011-01-17', 1), ('2011-05-27', 3), ('2011-07-25', 5), ('2011-11-30', 1), ('2012-01-05', 6),
           ('2012-03-28', 1), ('2012-06-25', 5), ('2013-03-04', 4), ('2013-06-20', 10), ('2014-03-10', 1),
           ('2014-04-28', 4), ('2015-02-02', 1), ('2015-05-07', 3), ('2015-06-19', 87), ('2015-11-27', 18),
           ('2016-01-04', 71), ('2016-02-29', 27), ('2016-05-09', 6), ('2017-05-08', 1), ('2017-08-11', 1),
           ('2018-02-06', 17), ('2018-03-23', 17), ('2018-05-30', 37), ('2018-08-03', 1), ('2018-10-11', 36),
           ('2019-04-29', 33), ('2020-01-23', 84), ('2020-02-28', 9), ('2020-09-09', 10), ('2021-03-08', 1),
           ('2021-07-27', 1), ('2022-01-25', 1), ('2022-03-15', 3), ('2022-04-25', 30), ('2023-06-26', 1),
           ('2024-02-05', 52), ('2025-01-02', 3), ('2025-04-07', 82), ('2025-11-21', 1), ('2026-02-02', 3),
           ('2026-03-23', 1), ('2026-06-08', 1)]


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        import pandas as pd
        import numpy as np
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 600})) ()

        def series(c):
            r = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                 "WHERE stock_code=:c AND close_price>0 ORDER BY trade_date"), {"c": c}).fetchall()
            return pd.Series({str(d): float(p) for d, p in r})
        ic = series(IDX); bk = series(BASKET)
        dates = list(ic.index); pos = {d: i for i, d in enumerate(dates)}
        bias20 = (ic / ic.rolling(20).mean() - 1) * 100
        delta = ic.diff()
        ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean()
        al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
        rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))
        ma = {m: ic.rolling(m).mean() for m in (20, 30, 60)}
        bkd = [d for d in dates if d in bk]
        print(f"[cfg] 篮子=中证1000 数据{bkd[0] if bkd else '?'}~{bkd[-1] if bkd else '?'} {len(bkd)}日; 进场信号{len(ENTRIES)}", flush=True)

        def run(ld_thresh, exit_ma, ob_exit):
            ents = sorted(d for d, ld in ENTRIES if ld >= ld_thresh and d in pos and d in bk)
            mser = ma[exit_ma]
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
                    ob = ob_exit and (bias20.get(d, 0) >= 2.5 or rsi6.get(d, 0) >= 75)
                    brk = above and not math.isnan(mv) and ic[d] < mv
                    if ob or brk:
                        xi = j; break
                if xi is None:
                    xi = len(dates) - 1
                holds.append((e, dates[xi])); last = xi
            rets, nav, navs, indays = [], 1.0, [], 0
            for e, x in holds:
                if e in bk and x in bk:
                    r = bk[x] / bk[e] - 1 - RT
                    rets.append(r); nav *= (1 + r); navs.append(nav); indays += pos[x] - pos[e]
            if not navs:
                return None
            navs = np.array(navs)
            tot = navs[-1] - 1
            ann = navs[-1] ** (242.0 / len(bkd)) - 1
            mdd = float((navs / np.maximum.accumulate(navs) - 1).min())
            win = (np.array(rets) > 0).mean() * 100
            return (len(holds), indays / len(bkd) * 100, tot * 100, ann * 100, mdd * 100, win)

        # 买入持有基准
        bh_tot = bk[bkd[-1]] / bk[bkd[0]] - 1
        bh_ann = (1 + bh_tot) ** (242.0 / len(bkd)) - 1
        bhn = np.array([bk[d] for d in bkd]) / bk[bkd[0]]
        bh_mdd = float((bhn / np.maximum.accumulate(bhn) - 1).min())
        print(f"\n买入持有中证1000: 总收益{bh_tot*100:.0f}% 年化{bh_ann*100:.1f}% 回撤{bh_mdd*100:.0f}%")
        print("=" * 96)
        print(f"{'跌停阈%':>7}{'退出MA':>7}{'超买退':>7} | {'段数':>5}{'在场%':>6}{'总收益%':>9}{'年化%':>7}{'回撤%':>7}{'胜率%':>7}")
        for ld in (0, 10, 30, 50):
            for em in (20, 30, 60):
                for ob in (True, False):
                    r = run(ld, em, ob)
                    if r:
                        n, ind, tot, ann, mdd, win = r
                        print(f"{ld:>7}{em:>7}{'是' if ob else '否':>6} | {n:>5}{ind:>6.0f}{tot:>9.0f}{ann:>7.1f}{mdd:>7.0f}{win:>7.0f}")
        print("\n对比基线 买持: 总收益{:.0f}% 年化{:.1f}% 回撤{:.0f}%".format(bh_tot*100, bh_ann*100, bh_mdd*100))
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
