#!/usr/bin/env python3
"""
daydayUp 选股因子横截面有效性回测（2026-06-13）

用与生产完全相同的 factor_calculator.calculate_stock_factors 计算选股总分及各分项因子，
检验它们在「成交额 Top100（stock_type='stock'）」池内的**横截面预测力**。

第一版结论：total_score 对未来收益**显著负相关**（IC −0.04~−0.075，t 到 −8.7），是短期反转信号。
本版追加三项验证：
  (A) new_high_120 分组：新高股 vs 非新高股的远期均值（IC 二值因子测不出，改分组）；
  (B) 取反/反转可交易性：Bottom10（最低分）超额 + 多空(Bottom−Top)价差；
  (C) T+1 延迟稳健 + 成本：入场改 close[D+1]（隔日才能下单），多空价差扣 2×单边成本。
      注：对「池」的超额里每仓手续费抵消，故 T+1 段主要看延迟影响；成本只在多空/绝对口径体现。

口径：
- 池 = 每个采样交易日 stock_type='stock' 的成交额前 POOL 只（与生产 _filter_top_stocks 一致）
- 远期收益 = close[exit]/close[entry]-1；区间内退市/停牌无收盘→该股该期剔除（偏保守）
- IC = 每日池内 Spearman(因子, 远期收益) 跨日聚合

用法（容器内，需 PYTHONPATH=/app）：
  docker exec -d -w /app -e PYTHONPATH=/app daydayup-backend \
    sh -c "python scripts/stock_factor_efficacy_backtest.py [interval] [pool] > /tmp/sfe_full.log 2>&1"
"""
import sys
import time
import math

from app import create_app

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 5
POOL = int(sys.argv[2]) if len(sys.argv) > 2 else 100
HORIZONS = [1, 3, 5, 10]
MIN_PAST = 130
MIN_POOL = 30
RT_COST = 0.0015          # 单边往返成本估计 ~0.15%（佣金+印花+滑点）
TOPN = 10                 # 生产取 Top10
FACTORS = ['total_score', 'factor1_rank', 'factor2_ma', 'factor3_vol',
           'factor4_burst', 'remaining_deviation', 'new_high_120_score']


def spearman(a, b):
    import pandas as pd
    s = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(s) < 10 or s['a'].nunique() < 3 or s['b'].nunique() < 3:
        return None
    return s['a'].rank().corr(s['b'].rank())   # 排名后 Pearson = Spearman（容器无 scipy）


def agg(vals):
    import numpy as np
    v = np.array([x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))], dtype=float)
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

        uri = app.config['SQLALCHEMY_DATABASE_URI']
        eng = create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}, pool_pre_ping=True)
        bts = sessionmaker(bind=eng)()
        # 历史无分时数据、且 intraday_deviation 不在 total_score 表达式里 → 跳过外部调用（否则每日 90s 超时）
        factor_calculator._fetch_intraday_deviation = lambda *a, **k: {}

        print(f"[cfg] interval={INTERVAL} pool={POOL} horizons={HORIZONS} RT_COST={RT_COST}", flush=True)
        all_dates = [r[0] for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        print(f"[data] {len(all_dates)} 交易日 {all_dates[0]} ~ {all_dates[-1]}", flush=True)
        idx = {d: i for i, d in enumerate(all_dates)}
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        print(f"[univ] stock_type=stock 共 {len(stock_set)} 只", flush=True)

        maxh = max(HORIZONS)
        eligible = all_dates[MIN_PAST: len(all_dates) - (1 + maxh)]   # 留 T+1 入场 + maxh 持有
        sampled = eligible[::INTERVAL]
        print(f"[plan] 采样 {len(sampled)} 个交易日", flush=True)

        ic = {f: {h: [] for h in HORIZONS} for f in FACTORS}
        ic_era = {f: {h: {'e': [], 'l': []} for h in HORIZONS} for f in FACTORS}
        top10_exc = {h: [] for h in HORIZONS}
        bot10_exc = {h: [] for h in HORIZONS}                 # (B) 反转：最低分超额
        ls_t0 = {h: [] for h in HORIZONS}                     # (B) 多空 Bottom-Top (T0, 毛)
        quint = {q: [] for q in range(5)}
        nh_spread = {h: [] for h in HORIZONS}                 # (A) 新高 - 非新高
        nh_lvl = {h: {'nh': [], 'non': []} for h in HORIZONS}
        t1_top_exc = {h: [] for h in HORIZONS}                # (C) T+1 入场
        t1_bot_exc = {h: [] for h in HORIZONS}
        t1_ls_net = {h: [] for h in HORIZONS}                 # (C) 多空净成本 = (bot-top) - 2*RT
        n_ok = 0
        t0 = time.time()

        close_q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                       "WHERE trade_date IN :dates AND stock_code IN :codes "
                       "AND close_price IS NOT NULL AND close_price>0"
                       ).bindparams(bindparam('dates', expanding=True), bindparam('codes', expanding=True))

        for k, D in enumerate(sampled):
            bts.rollback()
            if k % 50 == 0:
                print(f"[prog] {k}/{len(sampled)} ok={n_ok} 用时{time.time()-t0:.0f}s", flush=True)
            era = 'e' if str(D)[:4] < '2017' else 'l'
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            cand = sorted(((c, float(t)) for c, t in rows if c in stock_set), key=lambda x: -x[1])[:POOL]
            pool_codes = [c for c, _ in cand]
            if len(pool_codes) < MIN_POOL:
                continue
            try:
                fdf = factor_calculator.calculate_stock_factors(pool_codes, str(D), bts)
            except Exception as e:
                bts.rollback()
                continue
            if fdf is None or fdf.empty or 'total_score' not in fdf.columns:
                continue
            fdf = fdf[fdf['stock_code'].isin(pool_codes)].copy()

            i0 = idx[D]
            d1 = all_dates[i0 + 1]                                  # T+1 入场日
            exit_t0 = {h: all_dates[i0 + h] for h in HORIZONS}
            exit_t1 = {h: all_dates[i0 + 1 + h] for h in HORIZONS}
            dset = list({D, d1, *exit_t0.values(), *exit_t1.values()})
            cl = bts.execute(close_q, {"dates": dset, "codes": pool_codes}).fetchall()
            cmap = {(c, d): float(p) for c, d, p in cl}
            base0 = {c: cmap.get((c, D)) for c in pool_codes}
            base1 = {c: cmap.get((c, d1)) for c in pool_codes}

            any_h = False
            for h in HORIZONS:
                # ---- T0 远期收益 ----
                r0 = []
                for c in fdf['stock_code']:
                    b, x = base0.get(c), cmap.get((c, exit_t0[h]))
                    r0.append((x / b - 1.0) if (b and x) else None)
                fdf[f'_r0_{h}'] = r0
                sub = fdf.dropna(subset=[f'_r0_{h}'])
                if len(sub) < MIN_POOL:
                    continue
                any_h = True
                col0 = f'_r0_{h}'
                # IC
                for f in FACTORS:
                    if f in sub.columns:
                        r = spearman(sub[f].astype(float), sub[col0].astype(float))
                        ic[f][h].append(r)
                        ic_era[f][h][era].append(r)
                top = sub.nlargest(TOPN, 'total_score')
                bot = sub.nsmallest(TOPN, 'total_score')
                pm = sub[col0].mean()
                top10_exc[h].append(top[col0].mean() - pm)
                bot10_exc[h].append(bot[col0].mean() - pm)
                ls_t0[h].append(bot[col0].mean() - top[col0].mean())
                if h == 5 and len(sub) >= 25:
                    sub2 = sub.copy()
                    sub2['_q'] = pd.qcut(sub2['total_score'].rank(method='first'), 5, labels=False)
                    for q in range(5):
                        quint[q].append(sub2[sub2['_q'] == q][col0].mean())
                # ---- (A) 新高分组 ----
                if 'new_high_120_score' in sub.columns:
                    nh = sub[sub['new_high_120_score'] > 0]
                    non = sub[sub['new_high_120_score'] <= 0]
                    if len(nh) >= 3 and len(non) >= 3:
                        nh_spread[h].append(nh[col0].mean() - non[col0].mean())
                        nh_lvl[h]['nh'].append(nh[col0].mean())
                        nh_lvl[h]['non'].append(non[col0].mean())
                # ---- (C) T+1 入场 ----
                r1 = []
                for c in fdf['stock_code']:
                    b, x = base1.get(c), cmap.get((c, exit_t1[h]))
                    r1.append((x / b - 1.0) if (b and x) else None)
                fdf[f'_r1_{h}'] = r1
                sub1 = fdf.dropna(subset=[f'_r1_{h}'])
                if len(sub1) >= MIN_POOL:
                    col1 = f'_r1_{h}'
                    top1 = sub1.nlargest(TOPN, 'total_score')
                    bot1 = sub1.nsmallest(TOPN, 'total_score')
                    pm1 = sub1[col1].mean()
                    t1_top_exc[h].append(top1[col1].mean() - pm1)
                    t1_bot_exc[h].append(bot1[col1].mean() - pm1)
                    # 多空净成本：long bottom / short top，各付一次往返
                    t1_ls_net[h].append((bot1[col1].mean() - top1[col1].mean()) - 2 * RT_COST)
            if any_h:
                n_ok += 1

        # ===================== 报告 =====================
        def line(name, h, tup, scale=1.0):
            n, m, ir, t, pos = tup
            print(f"{name:<20}{h:>3} {n:>5} {m*scale:>9.4f} {ir:>7.3f} {t:>7.2f} {pos:>6.1f}")

        print("\n" + "=" * 80, flush=True)
        print(f"daydayUp 选股因子横截面有效性  采样日={n_ok}  池=Top{POOL}成交额(stock)  2007-2026")
        print("=" * 80)

        print("\n【Rank IC】每日池内 Spearman(因子,远期收益) 跨日聚合")
        print(f"{'因子':<20}{'H':>3} {'N':>5} {'meanIC':>9} {'IC_IR':>7} {'t':>7} {'>0%':>6}")
        for f in FACTORS:
            for h in HORIZONS:
                line(f, h, agg(ic[f][h]))

        print("\n【(A) new_high_120 分组远期收益 %】（IC 二值测不出，用分组均值）")
        print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
        for h in HORIZONS:
            line('新高-非新高 spread', h, agg(nh_spread[h]), 100)
        for h in HORIZONS:
            ne = agg(nh_lvl[h]['nh']); nn = agg(nh_lvl[h]['non'])
            print(f"  H={h}: 新高组均值 {ne[1]*100:>7.3f}%  非新高组 {nn[1]*100:>7.3f}%")

        print("\n【(B) 取反/反转可交易性 %】（T0 收盘入场，超额=对池均值）")
        print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
        for h in HORIZONS:
            line('Top10超额', h, agg(top10_exc[h]), 100)
        for h in HORIZONS:
            line('Bottom10超额', h, agg(bot10_exc[h]), 100)
        for h in HORIZONS:
            line('多空(Bot-Top)毛', h, agg(ls_t0[h]), 100)

        print("\n【total_score 五分位远期收益 H=5 %】（Q0最低→Q4最高，看单调性）")
        for q in range(5):
            v = np.array([x for x in quint[q] if x is not None and not math.isnan(x)])
            print(f"  Q{q}: {v.mean()*100:>7.3f}%  (n={len(v)})")

        print("\n【(C) T+1 隔日入场 + 成本 %】（成本在对池超额里抵消，故超额=延迟稳健性；多空为净成本）")
        print(f"{'指标':<20}{'H':>3} {'N':>5} {'mean%':>9} {'IR':>7} {'t':>7} {'>0%':>6}")
        for h in HORIZONS:
            line('T+1 Top10超额', h, agg(t1_top_exc[h]), 100)
        for h in HORIZONS:
            line('T+1 Bottom10超额', h, agg(t1_bot_exc[h]), 100)
        for h in HORIZONS:
            line('T+1 多空净(扣2×费)', h, agg(t1_ls_net[h]), 100)

        print("\n【年代稳定性 total_score】（e<2017 / l>=2017）")
        for h in HORIZONS:
            _, me, *_ = agg(ic_era['total_score'][h]['e'])
            _, ml, *_ = agg(ic_era['total_score'][h]['l'])
            print(f"  IC  H={h:>2}: early {me:>8.4f}  late {ml:>8.4f}")

        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
