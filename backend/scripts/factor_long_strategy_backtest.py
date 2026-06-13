#!/usr/bin/env python3
"""
正向因子组合回测 + 大盘顶底择时（2026-06-13）

在「成交额前 POOL 的 stock_type=stock 池」内，每 REBAL 个交易日换仓：
- A = rev5（5日反转）单因子；B = z(rev5)+z(-vol20)+z(ln_turn_avg20) 等权合成。
- 多头 = 因子最高前 TOPQ 等权持有 REBAL 日；多空 = 前TOPQ−后TOPQ（纯信号，A股难做空仅参考）。
- **大盘顶底择时**：从上证(sh.000001)日线算 MA / RSI6 / bias20，
  风险开(risk_on) = 指数 close ≥ MA{TREND} 且 未超买(bias20≥2.5 或 RSI6≥75 即顶部预警)。
  只在 risk_on 时持有多头，否则空仓(切换收一次成本)。→ 用顶底因子择时 + 正向因子选股。

用法(容器内, PYTHONPATH=/app):
  python factor_long_strategy_backtest.py [rebal] [topq] [pool] [rt_cost] [recent_start]
  env: M5_TREND(默认20) 趋势均线; M5_NO_OB=1 关闭超买退出
"""
import sys
import math
import os

from app import create_app

REBAL = int(sys.argv[1]) if len(sys.argv) > 1 else 5
TOPQ = int(sys.argv[2]) if len(sys.argv) > 2 else 20
POOL = int(sys.argv[3]) if len(sys.argv) > 3 else 100
RT_COST = float(sys.argv[4]) if len(sys.argv) > 4 else 0.002
RECENT = sys.argv[5] if len(sys.argv) > 5 else '2025-06-12'
TREND = int(os.environ.get('M5_TREND', 20))
USE_OB = os.environ.get('M5_NO_OB', '0') != '1'
LB = 20
MIN_POOL = 40
IDX = 'sh.000001'
BENCH = ['sh.000300', 'sh.000001']


def zscore(arr):
    import numpy as np
    a = np.array(arr, dtype=float); m = np.nanmean(a); s = np.nanstd(a)
    return (a - m) / s if s > 0 else a * 0.0


def metrics(period_rets, ppy):
    import numpy as np
    r = np.array([x for x in period_rets if x is not None and not math.isnan(x)], dtype=float)
    if len(r) < 3:
        return (float('nan'),) * 5
    nav = np.cumprod(1 + r)
    return (nav[-1] - 1, nav[-1] ** (ppy / len(r)) - 1,
            (r.mean() / r.std() * math.sqrt(ppy)) if r.std() > 0 else float('nan'),
            float((nav / np.maximum.accumulate(nav) - 1).min()), (r > 0).mean() * 100)


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np
        import pandas as pd
        import time
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        bts = sessionmaker(bind=create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}))()

        all_dates = [str(r[0]) for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        idx = {d: i for i, d in enumerate(all_dates)}
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())

        # 预算指数序列(择时) + 基准序列(对比) —— 各一次查询,免循环内反复查
        def series(code):
            rows = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                    "WHERE stock_code=:c AND close_price>0 ORDER BY trade_date"), {"c": code}).fetchall()
            return pd.Series({str(d): float(p) for d, p in rows})
        ic = series(IDX)
        ma = ic.rolling(TREND).mean()
        bias20 = (ic / ic.rolling(20).mean() - 1) * 100
        delta = ic.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
        rsi6 = 100 - 100 / (1 + gain.ewm(com=5, adjust=False).mean() / loss.ewm(com=5, adjust=False).mean())
        bench_s = next((series(b) for b in BENCH if len(series(b)) > 100), ic)

        MODE = os.environ.get('M5_MODE', 'trend')   # trend=趋势上行且不超买 / avoidtop=只躲顶(反转友好)
        def risk_on(D):
            if D not in ic or math.isnan(ma.get(D, float('nan'))):
                return True
            ob = bias20.get(D, 0) >= 2.5 or rsi6.get(D, 0) >= 75      # 顶部预警(超买门控)
            if MODE == 'avoidtop':
                return not ob                                         # 只在顶空仓,超卖/正常都持有反转多头
            return bool((ic[D] >= ma[D]) and (not ob if USE_OB else True))

        rebal_idx = list(range(LB + 2, len(all_dates) - REBAL - 1, REBAL))
        rebal_dates = [all_dates[i] for i in rebal_idx]
        print(f"[cfg] rebal={REBAL} topq={TOPQ} pool={POOL} cost={RT_COST} 趋势MA{TREND} 超买退出={USE_OB} 换仓点={len(rebal_dates)}", flush=True)

        wq = text("SELECT stock_code, trade_date, close_price, turnover FROM stock_daily_kline "
                  "WHERE stock_code IN :cs AND trade_date BETWEEN :a AND :b"
                  ).bindparams(bindparam('cs', expanding=True))

        recs = []  # (date, A_long, B_long, A_timed, B_timed, A_ls, B_ls, bench, ison)
        prevA = prevB = prevAt = prevBt = set()
        prev_on = True
        t0 = time.time()
        for n, D in enumerate(rebal_dates):
            bts.rollback()
            if n % 50 == 0:
                print(f"[prog] {n}/{len(rebal_dates)} {time.time()-t0:.0f}s", flush=True)
            i0 = idx[D]; exitD = all_dates[i0 + REBAL]
            ison = risk_on(D)
            bench = (bench_s[exitD] / bench_s[D] - 1) if (D in bench_s and exitD in bench_s) else None
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            pool = [c for c, _ in sorted(((c, float(t)) for c, t in rows if c in stock_set),
                                         key=lambda x: -x[1])[:POOL]]
            if len(pool) < MIN_POOL:
                recs.append((D, None, None, None, None, None, None, bench, ison)); continue
            rr = bts.execute(wq, {"cs": pool, "a": all_dates[i0 - LB], "b": exitD}).fetchall()
            cmap = {}
            for c, d, cp, tv in rr:
                cmap.setdefault(c, {})[str(d)] = (float(cp) if cp else None, float(tv) if tv else None)
            win = [all_dates[j] for j in range(i0 - LB, i0 + 1)]
            codes, rev5, vol20, lnturn, fwd = [], [], [], [], []
            for c in pool:
                dm = cmap.get(c, {})
                closes = [dm.get(d, (None, None))[0] for d in win]
                turns = [dm.get(d, (None, None))[1] for d in win]
                cD = closes[-1]; ce = dm.get(exitD, (None, None))[0]
                if cD is None or closes[-6] is None or ce is None:
                    continue
                ca = np.array([x if x is not None else np.nan for x in closes], dtype=float)
                dr = ca[1:] / ca[:-1] - 1; dr = dr[~np.isnan(dr)]
                tv = np.array([x for x in turns if x is not None], dtype=float)
                if len(dr) < 10 or len(tv) < 10 or tv.mean() <= 0:
                    continue
                codes.append(c); rev5.append(-(cD / ca[-6] - 1)); vol20.append(float(np.std(dr)))
                lnturn.append(float(np.log(tv.mean()))); fwd.append(ce / cD - 1)
            if len(codes) < MIN_POOL:
                recs.append((D, None, None, None, None, None, None, bench, ison)); continue
            fwd = np.array(fwd); sA = np.array(rev5)
            sB = zscore(rev5) + zscore([-x for x in vol20]) + zscore(lnturn)

            def topset(score, top):
                o = np.argsort(-score)
                return set(codes[i] for i in (o[:TOPQ] if top else o[-TOPQ:]))

            def long_ret(sel, prev):
                r = float(np.mean([fwd[codes.index(c)] for c in sel]))
                return r - RT_COST * (len(sel - prev) / len(sel)), sel

            At = topset(sA, True); Ab = topset(sA, False); Bt = topset(sB, True); Bb = topset(sB, False)
            aL, prevA = long_ret(At, prevA); bL, prevB = long_ret(Bt, prevB)
            # 择时版:risk_on 才持多头,否则空仓;状态翻转收一次成本
            if ison:
                aT, prevAt = long_ret(At, prevAt if prev_on else set())
                bT, prevBt = long_ret(Bt, prevBt if prev_on else set())
            else:
                aT = bT = (0.0 - (RT_COST if prev_on else 0.0)); prevAt = prevBt = set()
            prev_on = ison
            als = float(np.mean([fwd[codes.index(c)] for c in At]) - np.mean([fwd[codes.index(c)] for c in Ab])) - RT_COST * 2
            bls = float(np.mean([fwd[codes.index(c)] for c in Bt]) - np.mean([fwd[codes.index(c)] for c in Bb])) - RT_COST * 2
            recs.append((D, aL, bL, aT, bT, als, bls, bench, ison))

        ppy = 242.0 / REBAL

        def col(i, recent):
            return [r[i] for r in recs if r[i] is not None and (not recent or r[0] >= RECENT)]
        on_frac = np.mean([1 if r[8] else 0 for r in recs]) * 100
        on_frac_r = np.mean([1 if r[8] else 0 for r in recs if r[0] >= RECENT]) * 100

        def show(label, i):
            f = metrics(col(i, False), ppy); r = metrics(col(i, True), ppy)
            print(f"{label:<18} 全: 收益{f[0]*100:>8.1f}% 年化{f[1]*100:>6.1f}% 夏普{f[2]:>5.2f} 回撤{f[3]*100:>6.1f}% 胜{f[4]:>3.0f}% "
                  f"| 近1y: 收益{r[0]*100:>6.1f}% 夏普{r[2]:>5.2f} 回撤{r[3]*100:>6.1f}%")
        print("\n" + "=" * 100)
        print(f"正向因子 + 大盘顶底择时  换仓{REBAL}日 前{TOPQ}/池{POOL} 费{RT_COST*100:.2f}% 趋势MA{TREND}+超买退出={USE_OB}")
        print(f"风险开仓位占比: 全{on_frac:.0f}% / 近1y {on_frac_r:.0f}%")
        print("=" * 100)
        show("A rev5 多头(裸)", 1)
        show("B 合成 多头(裸)", 2)
        show("A rev5 多头(择时)", 3)
        show("B 合成 多头(择时)", 4)
        show("A rev5 多空(纸面)", 5)
        show("B 合成 多空(纸面)", 6)
        bf = metrics(col(7, False), ppy); br = metrics(col(7, True), ppy)
        print(f"{'基准 沪深300':<18} 全: 收益{bf[0]*100:>8.1f}% 年化{bf[1]*100:>6.1f}% 夏普{bf[2]:>5.2f} 回撤{bf[3]*100:>6.1f}%      "
              f"| 近1y: 收益{br[0]*100:>6.1f}% 夏普{br[2]:>5.2f} 回撤{br[3]*100:>6.1f}%")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
