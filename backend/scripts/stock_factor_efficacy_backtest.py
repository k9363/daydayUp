#!/usr/bin/env python3
"""
daydayUp 选股因子横截面有效性回测（2026-06-13）

用与生产完全相同的 factor_calculator.calculate_stock_factors 在「成交额 Top100（stock_type='stock'）」
池内检验 total_score 及各分项的横截面预测力。结论：total_score 对未来收益**显著负相关**（短期反转）。

验证项：
  Rank IC / Top10 超额 / 五分位单调 / 年代分段
  (A) new_high_120 分组（二值因子 IC 测不出 → 新高股 vs 非新高股远期均值）
  (B) 取反/反转可交易性：Bottom10 超额 + 多空(Bottom-Top)毛价差
  (C) T+1 隔日入场 + 成本：入场改 close[D+1]，多空扣 2×单边成本
      （对池超额里每仓手续费抵消，故 T+1 超额=纯延迟影响）

分片并行（慢点在 calculate_stock_factors，多进程分片可把墙钟压到 1/N）：
  # 起 N 个 worker（各跑 sampled[i::N]），落 /tmp/sfe_shard_i.pkl
  for i in 0..N-1: python stock_factor_efficacy_backtest.py <interval> <pool> <i> <N> &
  # 全部结束后聚合
  python stock_factor_efficacy_backtest.py agg <N>
单进程：python stock_factor_efficacy_backtest.py <interval> <pool>
"""
import sys
import time
import math
import pickle

from app import create_app

HORIZONS = [1, 3, 5, 10]
MIN_PAST = 130
MIN_POOL = 30
RT_COST = 0.0015
TOPN = 10
FACTORS = ['total_score', 'factor1_rank', 'factor2_ma', 'factor3_vol',
           'factor4_burst', 'remaining_deviation', 'new_high_120_score']
SHARD_F = "/tmp/sfe_shard_%d.pkl"


def new_acc():
    return {
        'ic': {f: {h: [] for h in HORIZONS} for f in FACTORS},
        'ic_era': {f: {h: {'e': [], 'l': []} for h in HORIZONS} for f in FACTORS},
        'top10_exc': {h: [] for h in HORIZONS},
        'bot10_exc': {h: [] for h in HORIZONS},
        'ls_t0': {h: [] for h in HORIZONS},
        'quint': {q: [] for q in range(5)},
        'nh_spread': {h: [] for h in HORIZONS},
        'nh_lvl': {h: {'nh': [], 'non': []} for h in HORIZONS},
        't1_top_exc': {h: [] for h in HORIZONS},
        't1_bot_exc': {h: [] for h in HORIZONS},
        't1_ls_net': {h: [] for h in HORIZONS},
        'n_ok': 0,
    }


def deepmerge(base, add):
    if isinstance(base, list):
        base.extend(add)
    elif isinstance(base, dict):
        for k, v in add.items():
            deepmerge(base[k], v)
    return base


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
        return (len(v), float('nan'), float('nan'), float('nan'), float('nan'))
    m, sd = v.mean(), v.std(ddof=1)
    ir = m / sd if sd > 0 else float('nan')
    t = ir * math.sqrt(len(v)) if sd > 0 else float('nan')
    return (len(v), m, ir, t, (v > 0).mean() * 100)


def sampled_dates(bts, interval):
    import os
    from sqlalchemy import text
    all_dates = [r[0] for r in bts.execute(
        text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
    maxh = max(HORIZONS)
    eligible = all_dates[MIN_PAST: len(all_dates) - (1 + maxh)]
    samp = eligible[::interval]
    start = os.environ.get('SFE_START')   # 可选：只回测 >= 该日（如 '2025-06-12'）
    if start:
        samp = [d for d in samp if str(d) >= start]
    return all_dates, samp


def worker(interval, pool, shard_idx, shard_total):
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        from services.factor_service import factor_calculator
        import pandas as pd

        uri = app.config['SQLALCHEMY_DATABASE_URI']
        eng = create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}, pool_pre_ping=True)
        bts = sessionmaker(bind=eng)()
        factor_calculator._fetch_intraday_deviation = lambda *a, **k: {}   # 历史无分时,跳过(且不在总分里)

        all_dates, sampled = sampled_dates(bts, interval)
        idx = {d: i for i, d in enumerate(all_dates)}
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        mine = sampled[shard_idx::shard_total]
        print(f"[shard {shard_idx}/{shard_total}] 总采样{len(sampled)} 本片{len(mine)} 池{pool}", flush=True)

        A = new_acc()
        close_q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                       "WHERE trade_date IN :dates AND stock_code IN :codes "
                       "AND close_price IS NOT NULL AND close_price>0"
                       ).bindparams(bindparam('dates', expanding=True), bindparam('codes', expanding=True))
        t0 = time.time()
        for k, D in enumerate(mine):
            bts.rollback()
            if k % 25 == 0:
                print(f"[shard {shard_idx}] {k}/{len(mine)} ok={A['n_ok']} {time.time()-t0:.0f}s", flush=True)
            era = 'e' if str(D)[:4] < '2017' else 'l'
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            cand = sorted(((c, float(t)) for c, t in rows if c in stock_set), key=lambda x: -x[1])[:pool]
            pool_codes = [c for c, _ in cand]
            if len(pool_codes) < MIN_POOL:
                continue
            try:
                fdf = factor_calculator.calculate_stock_factors(pool_codes, str(D), bts)
            except Exception:
                bts.rollback()
                continue
            if fdf is None or fdf.empty or 'total_score' not in fdf.columns:
                continue
            fdf = fdf[fdf['stock_code'].isin(pool_codes)].copy()

            i0 = idx[D]
            d1 = all_dates[i0 + 1]
            exit_t0 = {h: all_dates[i0 + h] for h in HORIZONS}
            exit_t1 = {h: all_dates[i0 + 1 + h] for h in HORIZONS}
            dset = list({D, d1, *exit_t0.values(), *exit_t1.values()})
            cl = bts.execute(close_q, {"dates": dset, "codes": pool_codes}).fetchall()
            cmap = {(c, d): float(p) for c, d, p in cl}
            base0 = {c: cmap.get((c, D)) for c in pool_codes}
            base1 = {c: cmap.get((c, d1)) for c in pool_codes}

            any_h = False
            for h in HORIZONS:
                r0 = [(cmap.get((c, exit_t0[h])) / base0[c] - 1.0)
                      if (base0.get(c) and cmap.get((c, exit_t0[h]))) else None for c in fdf['stock_code']]
                fdf[f'_r0_{h}'] = r0
                sub = fdf.dropna(subset=[f'_r0_{h}'])
                if len(sub) < MIN_POOL:
                    continue
                any_h = True
                c0 = f'_r0_{h}'
                for f in FACTORS:
                    if f in sub.columns:
                        r = spearman(sub[f].astype(float), sub[c0].astype(float))
                        A['ic'][f][h].append(r)
                        A['ic_era'][f][h][era].append(r)
                top = sub.nlargest(TOPN, 'total_score'); bot = sub.nsmallest(TOPN, 'total_score')
                pm = sub[c0].mean()
                A['top10_exc'][h].append(top[c0].mean() - pm)
                A['bot10_exc'][h].append(bot[c0].mean() - pm)
                A['ls_t0'][h].append(bot[c0].mean() - top[c0].mean())
                if h == 5 and len(sub) >= 25:
                    s2 = sub.copy()
                    s2['_q'] = pd.qcut(s2['total_score'].rank(method='first'), 5, labels=False)
                    for q in range(5):
                        A['quint'][q].append(s2[s2['_q'] == q][c0].mean())
                if 'new_high_120_score' in sub.columns:
                    nh = sub[sub['new_high_120_score'] > 0]; non = sub[sub['new_high_120_score'] <= 0]
                    if len(nh) >= 3 and len(non) >= 3:
                        A['nh_spread'][h].append(nh[c0].mean() - non[c0].mean())
                        A['nh_lvl'][h]['nh'].append(nh[c0].mean())
                        A['nh_lvl'][h]['non'].append(non[c0].mean())
                r1 = [(cmap.get((c, exit_t1[h])) / base1[c] - 1.0)
                      if (base1.get(c) and cmap.get((c, exit_t1[h]))) else None for c in fdf['stock_code']]
                fdf[f'_r1_{h}'] = r1
                sub1 = fdf.dropna(subset=[f'_r1_{h}'])
                if len(sub1) >= MIN_POOL:
                    c1 = f'_r1_{h}'
                    top1 = sub1.nlargest(TOPN, 'total_score'); bot1 = sub1.nsmallest(TOPN, 'total_score')
                    pm1 = sub1[c1].mean()
                    A['t1_top_exc'][h].append(top1[c1].mean() - pm1)
                    A['t1_bot_exc'][h].append(bot1[c1].mean() - pm1)
                    A['t1_ls_net'][h].append((bot1[c1].mean() - top1[c1].mean()) - 2 * RT_COST)
            if any_h:
                A['n_ok'] += 1
        pickle.dump(A, open(SHARD_F % shard_idx, 'wb'))
        print(f"[shard {shard_idx}] DONE ok={A['n_ok']} 用时{time.time()-t0:.0f}s -> {SHARD_F % shard_idx}", flush=True)


def report(shard_total, pool):
    import numpy as np
    A = new_acc()
    A['n_ok'] = 0
    for i in range(shard_total):
        s = pickle.load(open(SHARD_F % i, 'rb'))
        n = s.pop('n_ok')
        deepmerge(A, s)
        A['n_ok'] += n
    n_ok = A['n_ok']

    def line(name, h, tup, sc=1.0):
        n, m, ir, t, pos = tup
        print(f"{name:<20}{h:>3} {n:>5} {m*sc:>9.4f} {ir:>7.3f} {t:>7.2f} {pos:>6.1f}")

    print("\n" + "=" * 80)
    print(f"daydayUp 选股因子横截面有效性  采样日={n_ok}  池=Top{pool}成交额(stock)  2007-2026")
    print("=" * 80)
    print("\n【Rank IC】每日池内 Spearman(因子,远期收益) 跨日聚合")
    print(f"{'因子':<20}{'H':>3} {'N':>5} {'meanIC':>9} {'IC_IR':>7} {'t':>7} {'>0%':>6}")
    for f in FACTORS:
        for h in HORIZONS:
            line(f, h, agg(A['ic'][f][h]))
    print("\n【(A) new_high_120 分组远期收益 %】(IC二值测不出,用分组均值)")
    print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
    for h in HORIZONS:
        line('新高-非新高 spread', h, agg(A['nh_spread'][h]), 100)
    for h in HORIZONS:
        ne = agg(A['nh_lvl'][h]['nh']); nn = agg(A['nh_lvl'][h]['non'])
        print(f"  H={h}: 新高组 {ne[1]*100:>7.3f}%  非新高组 {nn[1]*100:>7.3f}%")
    print("\n【(B) 取反/反转可交易性 %】(T0收盘入场,超额=对池均值)")
    print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
    for h in HORIZONS:
        line('Top10超额', h, agg(A['top10_exc'][h]), 100)
    for h in HORIZONS:
        line('Bottom10超额', h, agg(A['bot10_exc'][h]), 100)
    for h in HORIZONS:
        line('多空(Bot-Top)毛', h, agg(A['ls_t0'][h]), 100)
    print("\n【total_score 五分位远期收益 H=5 %】(Q0最低->Q4最高,看单调)")
    for q in range(5):
        v = np.array([x for x in A['quint'][q] if x is not None and not math.isnan(x)])
        print(f"  Q{q}: {v.mean()*100:>7.3f}%  (n={len(v)})")
    print("\n【(C) T+1隔日入场+成本 %】(超额里费用抵消=延迟稳健;多空为净成本)")
    print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
    for h in HORIZONS:
        line('T+1 Top10超额', h, agg(A['t1_top_exc'][h]), 100)
    for h in HORIZONS:
        line('T+1 Bottom10超额', h, agg(A['t1_bot_exc'][h]), 100)
    for h in HORIZONS:
        line('T+1 多空净(扣2×费)', h, agg(A['t1_ls_net'][h]), 100)
    print("\n【年代稳定性 total_score】(e<2017 / l>=2017)")
    for h in HORIZONS:
        _, me, *_ = agg(A['ic_era']['total_score'][h]['e'])
        _, ml, *_ = agg(A['ic_era']['total_score'][h]['l'])
        print(f"  IC H={h:>2}: early {me:>8.4f}  late {ml:>8.4f}")
    print("\nDONE", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "agg":
        report(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 100)
    else:
        interval = int(sys.argv[1]); pool = int(sys.argv[2])
        si = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        st = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        worker(interval, pool, si, st)
