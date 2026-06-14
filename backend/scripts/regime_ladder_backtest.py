#!/usr/bin/env python3
"""
4档仓位阶梯回测（2026-06-14）—— 上升满仓/严格顶背离降仓/下降轻仓/破位空仓

- 上升趋势(上证 close≥MA60) → 满仓1.0;触发严格顶背离 → 降到 DIV_CUT(0.5)
- 下降但守MA120(MA120≤close<MA60) → 轻仓 0.3
- 破位(close<MA120) → 空仓 0
严格顶背离: 摆动高点配对(close在±W内为局部高),相邻两高点 价更高但 DIF更低 = 熊背离,
            确认滞后 W 日(无未来函数),激活 ACTIVE 个交易日。
对比 满仓 / 纯趋势MA60(1.0上/0.3下) / 阶梯ladder。4基准×全程/前后半,比 Sharpe·Calmar。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/rl.py
"""
import math
from app import create_app

IDX = 'sh.000001'
SPLIT = '2016-09-01'
COST = 0.0005
W = 5          # 摆动高点半窗
ACTIVE = 10    # 顶背离激活天数
DIV_CUT = 0.5  # 顶背离降仓档
BASKETS = [('中证1000', 'sh.000852'), ('中证500', 'sh.000905'), ('沪深300', 'sh.000300'), ('上证', 'sh.000001')]


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
        dates = list(ic.index)
        cl = ic.values
        ma60 = ic.rolling(60).mean(); ma120 = ic.rolling(120).mean()
        dif = (ic.ewm(span=12, adjust=False).mean() - ic.ewm(span=26, adjust=False).mean()).values

        # 严格顶背离: 摆动高点配对
        topdiv = [False] * len(dates)
        swings = []  # (i, close, dif) 局部高点
        for i in range(W, len(dates) - W):
            if cl[i] == max(cl[i - W:i + W + 1]) and cl[i] > cl[i - 1]:
                swings.append((i, cl[i], dif[i]))
        for k in range(1, len(swings)):
            ip, cp, dp = swings[k - 1]
            ic_, cc, dc = swings[k]
            if cc > cp and dc < dp:        # 价更高、DIF更低 = 熊背离
                start = ic_ + W            # 确认滞后 W 日(无未来函数)
                for j in range(start, min(start + ACTIVE, len(dates))):
                    topdiv[j] = True
        n_div = sum(topdiv)
        print(f"[cfg] 顶背离激活日 {n_div}/{len(dates)}; 摆动高点 {len(swings)}", flush=True)

        def expo(scheme, i):
            d = dates[i]
            m60 = ma60.iloc[i]; m120 = ma120.iloc[i]
            if math.isnan(m60):
                return 1.0
            up = cl[i] >= m60
            if scheme == 'trend':
                return 1.0 if up else 0.3
            if scheme == 'ladder':
                if up:
                    return DIV_CUT if topdiv[i] else 1.0
                if not math.isnan(m120) and cl[i] >= m120:
                    return 0.3          # 下降守MA120 轻仓
                return 0.0              # 破位空仓
            return 1.0

        def metrics(rets, ppy=242):
            r = np.array(rets)
            if len(r) < 50:
                return None
            nav = np.cumprod(1 + r)
            ann = nav[-1] ** (ppy / len(r)) - 1
            vol = r.std() * math.sqrt(ppy)
            sh = (r.mean() * ppy) / vol if vol > 0 else float('nan')
            mdd = float((nav / np.maximum.accumulate(nav) - 1).min())
            return dict(tot=nav[-1] - 1, ann=ann, vol=vol, sharpe=sh, mdd=mdd,
                        calmar=(ann / abs(mdd) if mdd < 0 else float('nan')))

        di = {d: i for i, d in enumerate(dates)}
        periods = [('全程', '1900', '9999'), ('前半', '1900', SPLIT), ('后半', SPLIT, '9999')]
        schemes = [('满仓100%', None), ('纯趋势MA60', 'trend'), ('阶梯ladder', 'ladder')]
        for nm, code in BASKETS:
            bk = series(code); bkd = [d for d in dates if d in bk]
            if len(bkd) < 200:
                print(f"\n=== {nm}: 无数据 ==="); continue
            print(f"\n{'='*96}\n=== 基准 {nm} ({bkd[0]}~{bkd[-1]}) ===")
            print(f"{'方案':<12}{'区间':<6}{'年化%':>7}{'波动%':>7}{'Sharpe':>8}{'回撤%':>7}{'Calmar':>8}{'平均仓%':>8}{'总收益%':>9}")
            for sn, sc in schemes:
                for pn, lo, hi in periods:
                    pr, ex = [], []
                    for a in range(1, len(bkd)):
                        d0, d1 = bkd[a - 1], bkd[a]
                        if not (lo <= d1 < hi):
                            continue
                        bret = bk[d1] / bk[d0] - 1
                        e0 = 1.0 if sc is None else expo(sc, di[d0])
                        e1 = 1.0 if sc is None else expo(sc, di[d1])
                        pr.append(e0 * bret - COST * abs(e1 - e0)); ex.append(e0)
                    m = metrics(pr)
                    if m:
                        print(f"{sn:<12}{pn:<6}{m['ann']*100:>7.1f}{m['vol']*100:>7.1f}{m['sharpe']:>8.2f}"
                              f"{m['mdd']*100:>7.0f}{m['calmar']:>8.2f}{np.mean(ex)*100:>8.0f}{m['tot']*100:>9.0f}")
        print("\n注: 比 Sharpe/Calmar(风险调整)。ladder=上升满仓/顶背离降0.5/下降守MA120轻0.3/破MA120空仓。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
