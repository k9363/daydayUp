#!/usr/bin/env python3
"""
高分池 + 回调 M5 买入 / 跌破 M5 清仓  事件驱动策略回测（2026-06-13）

策略：
- 高分池：每日 total_score Top{TOPN}（成交额前 {POOL} 的 stock_type=stock 池内，生产口径）。
- 观察名单：近 {WATCH_DAYS} 个交易日出现过高分池的票的并集（滚动）。
- 买入：在名单内、空仓、当日收盘价进入 M5±{BAND} 带（回调到 M5 附近）→ 当日收盘等权买入。
- 卖出：持仓股当日收盘 < M5 → 当日收盘清仓。
- M5 = 近 5 日收盘均值（自算）。成本 = 往返 {RT_COST}。执行 = 信号日收盘价（标准简化，偏乐观）。

两阶段（贵的算一次，便宜的可反复重跑）：
  pool 模式（分片并行，慢）：逐日算 Top{TOPN} → /tmp/m5pool_shard_i.pkl
    python stock_pool_m5_strategy_backtest.py pool <start> <end> <i> <N>
  sim 模式（单进程，秒级）：合并池 → 模拟 → 报告
    python stock_pool_m5_strategy_backtest.py sim <start> <end> <shard_total> [band] [rt_cost]
"""
import sys
import math
import pickle

from app import create_app

POOL = 100
TOPN = 10
WATCH_DAYS = 7
BAND = 0.02
RT_COST = 0.002
BENCH = ['sh.000300', 'sh.000001']
POOL_SHARD_F = "/tmp/m5pool_shard_%d.pkl"


def all_trade_dates(bts):
    from sqlalchemy import text
    return [r[0] for r in bts.execute(
        text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]


def worker_pool(start, end, shard_idx, shard_total):
    """逐日算 Top{TOPN}（按 total_score），存 {date_str: [codes]}。"""
    import time
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from services.factor_service import factor_calculator
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        bts = sessionmaker(bind=create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}))()
        factor_calculator._fetch_intraday_deviation = lambda *a, **k: {}

        dates = [d for d in all_trade_dates(bts) if start <= str(d) <= end]
        stock_set = set(r[0] for r in bts.execute(
            text("SELECT stock_code FROM stock_basic WHERE stock_type='stock'")).fetchall())
        mine = dates[shard_idx::shard_total]
        print(f"[pool {shard_idx}/{shard_total}] 区间Top{TOPN} 共{len(dates)}日 本片{len(mine)}", flush=True)
        out = {}
        t0 = time.time()
        for k, D in enumerate(mine):
            bts.rollback()
            if k % 20 == 0:
                print(f"[pool {shard_idx}] {k}/{len(mine)} {time.time()-t0:.0f}s", flush=True)
            rows = bts.execute(text("SELECT stock_code, turnover FROM stock_daily_kline "
                                    "WHERE trade_date=:d AND turnover>0"), {"d": D}).fetchall()
            pool_codes = [c for c, _ in sorted(((c, float(t)) for c, t in rows if c in stock_set),
                                               key=lambda x: -x[1])[:POOL]]
            if len(pool_codes) < 30:
                continue
            try:
                fdf = factor_calculator.calculate_stock_factors(pool_codes, str(D), bts)
            except Exception:
                bts.rollback(); continue
            if fdf is None or fdf.empty or 'total_score' not in fdf.columns:
                continue
            out[str(D)] = list(fdf.nlargest(TOPN, 'total_score')['stock_code'])
        pickle.dump(out, open(POOL_SHARD_F % shard_idx, 'wb'))
        print(f"[pool {shard_idx}] DONE {len(out)}日 -> {POOL_SHARD_F % shard_idx}", flush=True)


def sim(start, end, shard_total, band, rt_cost):
    """增强版：真回调入场 + 限仓 + 硬止损 + T+1 执行（参数走环境变量）。"""
    import os
    import numpy as np
    import pandas as pd
    MAXPOS = int(os.environ.get('M5_MAXPOS', 10))
    STOP = float(os.environ.get('M5_STOP', 0.08))         # 从买入价回撤≥此值清仓
    PULL = float(os.environ.get('M5_PULL', 0.03))         # 真回调:近LOOKBACK日曾在M5上方≥此值
    LOOKBACK = int(os.environ.get('M5_LOOKBACK', 3))
    T1 = os.environ.get('M5_T1', '1') == '1'              # 1=信号次日收盘执行
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        bts = sessionmaker(bind=create_engine(uri, connect_args={'read_timeout': 1800, 'connect_timeout': 30}))()

        daily_top = {}
        for i in range(shard_total):
            daily_top.update(pickle.load(open(POOL_SHARD_F % i, 'rb')))   # {date: [codes]}(已按分降序)
        all_dates = [str(d) for d in all_trade_dates(bts)]
        sim_dates = [d for d in all_dates if start <= d <= end]
        cands = sorted({c for codes in daily_top.values() for c in codes})
        i0 = all_dates.index(sim_dates[0])
        px_start = all_dates[max(0, i0 - 15)]
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE stock_code IN :cs AND trade_date BETWEEN :a AND :b AND close_price>0"
                 ).bindparams(bindparam('cs', expanding=True))
        rows = bts.execute(q, {"cs": cands + BENCH, "a": px_start, "b": end}).fetchall()
        close = {}
        for c, d, p in rows:
            close.setdefault(c, {})[str(d)] = float(p)
        full_dates = [d for d in all_dates if px_start <= d <= end]
        m5 = {}
        for c, dmap in close.items():
            m5[c] = pd.Series([dmap.get(d) for d in full_dates], index=full_dates).astype(float).rolling(5).mean()
        fidx = {d: i for i, d in enumerate(full_dates)}

        def watchlist(di):
            wl = set()
            for d in sim_dates[max(0, di - WATCH_DAYS + 1): di + 1]:
                wl.update(daily_top.get(d, []))
            return wl

        def best_rank(c, di):  # 近WATCH_DAYS内在Top10的最佳名次(越小越高分),用于限仓优先
            best = 99
            for d in sim_dates[max(0, di - WATCH_DAYS + 1): di + 1]:
                lst = daily_top.get(d, [])
                if c in lst:
                    best = min(best, lst.index(c))
            return best

        def m5v(c, d):
            v = m5[c].get(d) if c in m5 else None
            return None if (v is None or (isinstance(v, float) and math.isnan(v))) else v

        def was_above(c, d):  # 真回调:近LOOKBACK日曾在 M5 上方≥PULL
            if d not in fidx:
                return False
            for j in range(max(0, fidx[d] - LOOKBACK + 1), fidx[d] + 1):
                dd = full_dates[j]
                cp, mv = close.get(c, {}).get(dd), m5v(c, dd)
                if cp and mv and mv > 0 and cp / mv - 1 >= PULL:
                    return True
            return False

        held = {}                  # code -> entry_close
        pend_buy, pend_sell = [], []
        nav = 1.0
        navs, rets, hold_counts, trades = [], [], [], []
        for di, D in enumerate(sim_dates):
            prevD = sim_dates[di - 1] if di > 0 else None
            # 1) 昨收->今收 组合收益(对昨日收盘持有的票等权)
            if held and prevD:
                rr = [close[c][D] / close[c][prevD] - 1 for c in held
                      if close.get(c, {}).get(D) and close.get(c, {}).get(prevD)]
                day_ret = float(np.mean(rr)) if rr else 0.0
            else:
                day_ret = 0.0
            # 2) 执行昨日信号(T+1: 今收成交)；T1=False 时本段空,信号即时执行在第4步
            n_exec = 0
            for c in pend_sell:
                if c in held and close.get(c, {}).get(D):
                    g = close[c][D] / held.pop(c) - 1
                    trades.append((c, D, g, g - rt_cost)); n_exec += 1
            for c in pend_buy:
                if len(held) >= MAXPOS:
                    break
                if c not in held and close.get(c, {}).get(D):
                    held[c] = close[c][D]; n_exec += 1
            pend_buy, pend_sell = [], []
            n_after = max(len(held), 1)
            cost_drag = (rt_cost / 2) * n_exec / n_after
            nav *= (1 + day_ret - cost_drag)
            navs.append(nav); rets.append(day_ret - cost_drag); hold_counts.append(len(held))
            # 3) 生成今日信号 → 入队(T+1 次日执行；若 T1=False 立即在今收执行)
            sells = []
            for c in list(held.keys()):
                cp, mv = close.get(c, {}).get(D), m5v(c, D)
                if cp is None:
                    continue
                if (mv is not None and cp < mv) or (cp / held[c] - 1 <= -STOP):
                    sells.append(c)
            wl = watchlist(di)
            held_after = set(held.keys()) - set(sells)
            buys = []
            for c in wl:
                if c in held_after:
                    continue
                cp, mv = close.get(c, {}).get(D), m5v(c, D)
                if cp is None or mv is None or mv <= 0:
                    continue
                if abs(cp / mv - 1) <= band and was_above(c, D):
                    buys.append(c)
            buys.sort(key=lambda c: best_rank(c, di))            # 限仓优先:高分先
            slots = MAXPOS - len(held_after)
            buys = buys[:max(0, slots)]
            if T1:
                pend_sell, pend_buy = sells, buys
            else:                                                # 即时(信号日收盘)执行
                for c in sells:
                    if close.get(c, {}).get(D):
                        g = close[c][D] / held.pop(c) - 1
                        trades.append((c, D, g, g - rt_cost))
                for c in buys:
                    if len(held) < MAXPOS and close.get(c, {}).get(D):
                        held[c] = close[c][D]
        for c in list(held.keys()):                              # 末日强平
            if close.get(c, {}).get(sim_dates[-1]):
                g = close[c][sim_dates[-1]] / held[c] - 1
                trades.append((c, sim_dates[-1], g, g - rt_cost))

        rets = np.array(rets); navs_a = np.array(navs)
        ann = navs[-1] ** (242.0 / len(sim_dates)) - 1
        sharpe = (rets.mean() / rets.std() * math.sqrt(242)) if rets.std() > 0 else float('nan')
        mdd = float((navs_a / np.maximum.accumulate(navs_a) - 1).min())
        net = np.array([t[3] for t in trades])
        wins = (net > 0).mean() * 100 if len(net) else float('nan')
        bcode = next((b for b in BENCH if b in close and close[b].get(sim_dates[0]) and close[b].get(sim_dates[-1])), None)
        bench_ret = (close[bcode][sim_dates[-1]] / close[bcode][sim_dates[0]] - 1) if bcode else float('nan')

        print("\n" + "=" * 72)
        print(f"高分池 + 真回调M5买入 / 跌破M5或止损清仓  {sim_dates[0]}~{sim_dates[-1]}")
        print(f"参数: Top{TOPN} 观察{WATCH_DAYS}日 band±{band*100:.2f}% 真回调≥{PULL*100:.0f}%(近{LOOKBACK}日) "
              f"限仓{MAXPOS} 止损{STOP*100:.0f}% 费{rt_cost*100:.2f}% {'T+1' if T1 else '即时'}执行")
        print("=" * 72)
        print(f"  策略总收益:    {(navs[-1]-1)*100:>8.2f}%")
        print(f"  年化:          {ann*100:>8.2f}%")
        print(f"  夏普(年化):     {sharpe:>8.2f}")
        print(f"  最大回撤:      {mdd*100:>8.2f}%")
        print(f"  基准({bcode}) 同期: {bench_ret*100:>8.2f}%   超额: {((navs[-1]-1)-bench_ret)*100:>8.2f}%")
        print(f"  平均/最大 同时持仓: {np.mean(hold_counts):.1f} / {max(hold_counts)}  (上限{MAXPOS})")
        print(f"  在场天数比例:   {sum(1 for h in hold_counts if h>0)/len(sim_dates)*100:>6.1f}%")
        print(f"  完成交易数:     {len(trades)}  胜率(净): {wins:.1f}%")
        if len(net):
            print(f"  单笔净收益 均值/中位: {net.mean()*100:.2f}% / {np.median(net)*100:.2f}%")
            print(f"  单笔 最好/最差: {net.max()*100:.2f}% / {net.min()*100:.2f}%")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "pool":
        worker_pool(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
    elif mode == "sim":
        st = int(sys.argv[4])
        band = float(sys.argv[5]) if len(sys.argv) > 5 else BAND
        rt = float(sys.argv[6]) if len(sys.argv) > 6 else RT_COST
        sim(sys.argv[2], sys.argv[3], st, band, rt)
