#!/usr/bin/env python3
"""
daydayUp 选股因子横截面有效性回测（2026-06-13）

目的：用与生产完全相同的 factor_calculator.calculate_stock_factors 计算选股总分及各分项因子，
检验它们在「成交额 Top100（stock_type='stock'）」池内的**横截面预测力**——
按因子排名是否能预测未来 N 日收益。

这与 topbottom_score_backtest.py（时序顶底 AUC）是不同范式：选股是截面排名问题，
评价用 Rank IC / IC_IR / Top10 超额收益 / 分位单调，并按年代分段看稳定性。

口径：
- 池 = 每个采样交易日 stock_type='stock' 的成交额前 POOL 只（与生产 _filter_top_stocks 一致）
- 因子 = calculate_stock_factors 返回的 total_score + 6 个分项
- 远期收益 = close[D+h]/close[D]-1（h∈HORIZONS）；区间内退市/停牌无未来收盘→该股该期剔除
- IC = 每个交易日池内 Spearman(因子, 远期收益)，跨日聚合

用法（容器内）：
  docker exec -w /app -e PYTHONPATH=/app daydayup-backend \
    python scripts/stock_factor_efficacy_backtest.py [interval] [pool] > /tmp/bt.log 2>&1
  interval=采样间隔交易日(默认5=约周频)，pool=池大小(默认100)
"""
import sys
import time
import math

from app import create_app

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 5
POOL = int(sys.argv[2]) if len(sys.argv) > 2 else 100
HORIZONS = [1, 3, 5, 10]
MIN_PAST = 130          # 需足够历史算 120 日新高 / 均线
MIN_POOL = 30           # 池太小当日跳过
FACTORS = ['total_score', 'factor1_rank', 'factor2_ma', 'factor3_vol',
           'factor4_burst', 'remaining_deviation', 'new_high_120_score']


def spearman(a, b):
    import pandas as pd
    s = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(s) < 10 or s['a'].nunique() < 3 or s['b'].nunique() < 3:
        return None
    # Spearman = 排名后的 Pearson（容器无 scipy，不用 method='spearman'）
    return s['a'].rank().corr(s['b'].rank())


def agg(vals):
    """list -> (n, mean, ic_ir, t, pos%)"""
    import numpy as np
    v = np.array([x for x in vals if x is not None], dtype=float)
    if len(v) < 5:
        return (len(v), float('nan'), float('nan'), float('nan'), float('nan'))
    m, sd = v.mean(), v.std(ddof=1)
    ir = m / sd if sd > 0 else float('nan')
    t = ir * math.sqrt(len(v)) if sd > 0 else float('nan')
    pos = (v > 0).mean() * 100
    return (len(v), m, ir, t, pos)


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        from services.factor_service import factor_calculator
        import pandas as pd
        import numpy as np

        # 回测历史日无分时数据，且 intraday_deviation 不在 total_score 表达式里；
        # 跳过对 TA-CN /api/sync/intraday-deviation 的调用（否则每日 90s 超时 → 不可行）。
        factor_calculator._fetch_intraday_deviation = lambda *a, **k: {}

        uri = app.config['SQLALCHEMY_DATABASE_URI']
        eng = create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30},
                            pool_pre_ping=True)
        bts = sessionmaker(bind=eng)()

        print(f"[cfg] interval={INTERVAL} pool={POOL} horizons={HORIZONS}", flush=True)

        all_dates = [r[0] for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        print(f"[data] {len(all_dates)} 交易日 {all_dates[0]} ~ {all_dates[-1]}", flush=True)
        idx = {d: i for i, d in enumerate(all_dates)}

        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        print(f"[univ] stock_type=stock 共 {len(stock_set)} 只", flush=True)

        maxh = max(HORIZONS)
        eligible = all_dates[MIN_PAST: len(all_dates) - maxh]
        sampled = eligible[::INTERVAL]
        print(f"[plan] 采样 {len(sampled)} 个交易日", flush=True)

        # 累加器
        ic = {f: {h: [] for h in HORIZONS} for f in FACTORS}
        ic_era = {f: {h: {'early': [], 'late': []} for h in HORIZONS} for f in FACTORS}  # <2017 / >=2017
        top10_exc = {h: [] for h in HORIZONS}
        top10_exc_era = {h: {'early': [], 'late': []} for h in HORIZONS}
        quint = {q: [] for q in range(5)}  # total_score 五分位 h=5 远期均值
        n_ok = 0
        t0 = time.time()

        close_q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                       "WHERE trade_date IN :dates AND stock_code IN :codes "
                       "AND close_price IS NOT NULL AND close_price>0"
                       ).bindparams(bindparam('dates', expanding=True),
                                    bindparam('codes', expanding=True))

        for k, D in enumerate(sampled):
            bts.rollback()  # 清 identity map，防跨日累积 ORM 对象拖慢
            if k % 50 == 0:
                print(f"[prog] {k}/{len(sampled)} ok={n_ok} 用时{time.time()-t0:.0f}s", flush=True)
            era = 'early' if str(D)[:4] < '2017' else 'late'
            # 池：当日 stock_type=stock 的成交额前 POOL
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            cand = sorted(((c, float(t)) for c, t in rows if c in stock_set),
                          key=lambda x: -x[1])[:POOL]
            pool_codes = [c for c, _ in cand]
            if len(pool_codes) < MIN_POOL:
                continue
            try:
                fdf = factor_calculator.calculate_stock_factors(pool_codes, str(D), bts)
            except Exception as e:
                bts.rollback()
                if k % 100 == 0:
                    print(f"  [skip] {D} 因子计算异常: {str(e)[:80]}", flush=True)
                continue
            if fdf is None or fdf.empty or 'total_score' not in fdf.columns:
                continue

            future = [all_dates[idx[D] + h] for h in HORIZONS]
            dlist = [D] + future
            cl = bts.execute(close_q, {"dates": dlist, "codes": pool_codes}).fetchall()
            cmap = {(c, d): float(p) for c, d, p in cl}
            base = {c: cmap.get((c, D)) for c in pool_codes}

            fdf = fdf[fdf['stock_code'].isin(pool_codes)].copy()
            valid = n_ok  # placeholder
            any_h = False
            for hi, h in enumerate(HORIZONS):
                fd = future[hi]
                fwd = []
                for c in fdf['stock_code']:
                    b, fut = base.get(c), cmap.get((c, fd))
                    fwd.append((fut / b - 1.0) if (b and fut) else None)
                fdf[f'_fwd{h}'] = fwd
                sub = fdf.dropna(subset=[f'_fwd{h}'])
                if len(sub) < MIN_POOL:
                    continue
                any_h = True
                for f in FACTORS:
                    if f in sub.columns:
                        r = spearman(sub[f].astype(float), sub[f'_fwd{h}'].astype(float))
                        ic[f][h].append(r)
                        ic_era[f][h][era].append(r)
                # Top10（按 total_score）超额
                top = sub.nlargest(10, 'total_score')
                exc = top[f'_fwd{h}'].mean() - sub[f'_fwd{h}'].mean()
                top10_exc[h].append(exc)
                top10_exc_era[h][era].append(exc)
                # 五分位（仅 h=5）
                if h == 5 and len(sub) >= 25:
                    sub2 = sub.copy()
                    sub2['_q'] = pd.qcut(sub2['total_score'].rank(method='first'), 5, labels=False)
                    for q in range(5):
                        quint[q].append(sub2[sub2['_q'] == q][f'_fwd{h}'].mean())
            if any_h:
                n_ok += 1

        # ============ 报告 ============
        print("\n" + "=" * 78, flush=True)
        print(f"daydayUp 选股因子横截面有效性  采样日={n_ok}  池=Top{POOL}成交额(stock)", flush=True)
        print("=" * 78)
        print("\n【Rank IC】（每日池内 Spearman(因子,远期收益) 跨日聚合）")
        print(f"{'因子':<22}{'H':>3} {'N':>5} {'meanIC':>8} {'IC_IR':>7} {'t':>7} {'>0%':>6}")
        for f in FACTORS:
            for h in HORIZONS:
                n, m, ir, t, pos = agg(ic[f][h])
                print(f"{f:<22}{h:>3} {n:>5} {m:>8.4f} {ir:>7.3f} {t:>7.2f} {pos:>6.1f}")
        print("\n【Top10 超额收益】（总分前10 均值 − 池均值，单位 %）")
        print(f"{'H':>3} {'N':>5} {'mean%':>8} {'IR':>7} {'t':>7} {'>0%':>6}")
        for h in HORIZONS:
            n, m, ir, t, pos = agg(top10_exc[h])
            print(f"{h:>3} {n:>5} {m*100:>8.3f} {ir:>7.3f} {t:>7.2f} {pos:>6.1f}")
        print("\n【total_score 五分位远期收益 H=5】（Q0最低分→Q4最高分，单位 %，看单调性）")
        for q in range(5):
            v = np.array([x for x in quint[q] if x is not None and not math.isnan(x)])
            print(f"  Q{q}: {v.mean()*100:>7.3f}%  (n={len(v)})")
        print("\n【年代稳定性】（total_score，early<2017 / late>=2017）")
        print(f"{'指标':<18}{'H':>3} {'early':>9} {'late':>9}")
        for h in HORIZONS:
            ne, me, *_ = agg(ic_era['total_score'][h]['early'])
            nl, ml, *_ = agg(ic_era['total_score'][h]['late'])
            print(f"{'IC':<18}{h:>3} {me:>9.4f} {ml:>9.4f}")
        for h in HORIZONS:
            ne, me, *_ = agg(top10_exc_era[h]['early'])
            nl, ml, *_ = agg(top10_exc_era[h]['late'])
            print(f"{'Top10超额%':<18}{h:>3} {me*100:>9.3f} {ml*100:>9.3f}")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
