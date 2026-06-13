#!/usr/bin/env python3
"""
候选因子批量横截面 IC 扫描（2026-06-13）——挖正向因子用

在「成交额前 POOL 的 stock_type=stock 池」内（与选股因子回测同口径），对一组纯 K 线候选因子
算 Rank IC(因子 vs 未来收益)，同时给**全样本**与**最近一年**两列，看谁长期+近期都正。
快：直接从 close/turnover 向量化算因子，不走慢的 calculate_stock_factors。

候选因子(在信号日 D 计算)：
  rev5/rev10/rev20   = -(close[D]/close[D-k]-1)        短期反转(动量取反)
  vol20              = 近20日日收益标准差                低波异象(IC负=低波占优)
  ln_turn            = ln(成交额[D])                     流动性/规模
  ln_turn_avg20      = ln(近20日均成交额)
  volsurge           = 成交额[D]/近20日均额              放量
  dist_ma5/dist_ma20 = close/MA-1                        乖离(IC负=追高反转)
  below_high20       = close[D]/近20日最高-1 (≤0)        距高点

用法(容器内, PYTHONPATH=/app):
  python factor_mining_ic_scan.py <interval> <pool> [recent_start]
"""
import sys
import math

from app import create_app

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 5
POOL = int(sys.argv[2]) if len(sys.argv) > 2 else 100
RECENT = sys.argv[3] if len(sys.argv) > 3 else '2025-06-12'
HORIZONS = [1, 3, 5, 10]
LB = 20          # 因子回看
MIN_POOL = 30


def spearman(a, b):
    import pandas as pd
    s = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(s) < 10 or s['a'].nunique() < 3 or s['b'].nunique() < 3:
        return None
    return s['a'].rank().corr(s['b'].rank())


def agg(vals):
    import numpy as np
    v = np.array([x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))], dtype=float)
    if len(v) < 5:
        return (len(v), float('nan'), float('nan'))
    m, sd = v.mean(), v.std(ddof=1)
    t = (m / sd * math.sqrt(len(v))) if sd > 0 else float('nan')
    return (len(v), m, t)


def factors_for(closes, turns):
    """closes/turns: 长度 LB+1 的列表(global[i0-LB..i0])，末元素=D。返回 dict 因子值或 None。"""
    import numpy as np
    if any(c is None for c in closes[-6:]) or closes[-1] is None or closes[-6] is None:
        return None
    c = np.array([x if x is not None else np.nan for x in closes], dtype=float)
    v = np.array([x if x is not None else np.nan for x in turns], dtype=float)
    cD = c[-1]
    out = {}

    def ret(k):
        return cD / c[-1 - k] - 1 if (len(c) > k and not math.isnan(c[-1 - k]) and c[-1 - k] > 0) else None
    for k in (5, 10, 20):
        r = ret(k)
        out[f'rev{k}'] = (-r) if r is not None else None
    dr = c[1:] / c[:-1] - 1
    dr = dr[~np.isnan(dr)]
    out['vol20'] = float(np.std(dr)) if len(dr) >= 10 else None
    out['ln_turn'] = float(np.log(v[-1])) if (not math.isnan(v[-1]) and v[-1] > 0) else None
    vt = v[~np.isnan(v)]
    out['ln_turn_avg20'] = float(np.log(vt.mean())) if len(vt) >= 10 and vt.mean() > 0 else None
    out['volsurge'] = float(v[-1] / vt[:-1].mean()) if (len(vt) >= 10 and not math.isnan(v[-1]) and vt[:-1].mean() > 0) else None
    ma5 = np.nanmean(c[-5:]); ma20 = np.nanmean(c[-20:])
    out['dist_ma5'] = cD / ma5 - 1 if ma5 > 0 else None
    out['dist_ma20'] = cD / ma20 - 1 if ma20 > 0 else None
    hi = np.nanmax(c[-20:])
    out['below_high20'] = cD / hi - 1 if hi > 0 else None
    return out


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import time
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        bts = sessionmaker(bind=create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}))()

        all_dates = [str(r[0]) for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        idx = {d: i for i, d in enumerate(all_dates)}
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        maxh = max(HORIZONS)
        eligible = all_dates[LB + 2: len(all_dates) - (maxh + 1)]
        sampled = eligible[::INTERVAL]
        FNAMES = ['rev5', 'rev10', 'rev20', 'vol20', 'ln_turn', 'ln_turn_avg20',
                  'volsurge', 'dist_ma5', 'dist_ma20', 'below_high20']
        print(f"[cfg] interval={INTERVAL} pool={POOL} 采样{len(sampled)}日 recent>={RECENT}", flush=True)

        ic = {f: {h: {'all': [], 'rec': []} for h in HORIZONS} for f in FNAMES}
        # 用 BETWEEN 连续区间(走 (stock_code,trade_date) 唯一索引),比 trade_date IN(...) 快十倍
        wq = text("SELECT stock_code, trade_date, close_price, turnover FROM stock_daily_kline "
                  "WHERE stock_code IN :cs AND trade_date BETWEEN :a AND :b"
                  ).bindparams(bindparam('cs', expanding=True))
        t0 = time.time()
        for k, D in enumerate(sampled):
            bts.rollback()   # 刷新读视图，防长事务 undo 累积导致逐日变慢
            if k % 100 == 0:
                print(f"[prog] {k}/{len(sampled)} {time.time()-t0:.0f}s", flush=True)
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            pool = [c for c, _ in sorted(((c, float(t)) for c, t in rows if c in stock_set),
                                         key=lambda x: -x[1])[:POOL]]
            if len(pool) < MIN_POOL:
                continue
            i0 = idx[D]
            rr = bts.execute(wq, {"cs": pool, "a": all_dates[i0 - LB], "b": all_dates[i0 + maxh]}).fetchall()
            cmap, vmap = {}, {}
            for c, d, cp, tv in rr:
                cmap[(c, str(d))] = float(cp) if cp else None
                vmap[(c, str(d))] = float(tv) if tv else None
            win = [all_dates[j] for j in range(i0 - LB, i0 + 1)]
            fwd_d = {h: all_dates[i0 + h] for h in HORIZONS}
            rec = D >= RECENT
            fvals = {f: [] for f in FNAMES}
            frets = {h: [] for h in HORIZONS}
            for c in pool:
                closes = [cmap.get((c, d)) for d in win]
                turns = [vmap.get((c, d)) for d in win]
                fac = factors_for(closes, turns)
                base = cmap.get((c, D))
                for f in FNAMES:
                    fvals[f].append(fac.get(f) if fac else None)
                for h in HORIZONS:
                    fp = cmap.get((c, fwd_d[h]))
                    frets[h].append((fp / base - 1) if (base and fp) else None)
            for h in HORIZONS:
                for f in FNAMES:
                    r = spearman(fvals[f], frets[h])
                    if r is not None:
                        ic[f][h]['all'].append(r)
                        if rec:
                            ic[f][h]['rec'].append(r)

        print("\n" + "=" * 86)
        print(f"候选因子 IC 扫描  采样{len(sampled)}日  池=Top{POOL}成交额(stock)  全样本 vs 最近一年(>={RECENT})")
        print("=" * 86)
        print(f"{'因子':<14}{'H':>3} | {'IC_全':>8}{'t_全':>7}{'N全':>6} | {'IC_近1y':>9}{'t_近':>7}{'N近':>5}")
        for f in FNAMES:
            for h in HORIZONS:
                na, ma, ta = agg(ic[f][h]['all'])
                nr, mr, tr = agg(ic[f][h]['rec'])
                print(f"{f:<14}{h:>3} | {ma:>8.4f}{ta:>7.2f}{na:>6} | {mr:>9.4f}{tr:>7.2f}{nr:>5}")
        print("\n说明: IC正=该因子值越大未来收益越高(可做多头方向);需全样本与近一年同号且显著才算稳。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
