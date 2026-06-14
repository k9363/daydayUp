#!/usr/bin/env python3
"""
两层条件化控仓回测（2026-06-14）—— 趋势看MA60 / 大回调看超卖 / 大涨看顶背离

修正"一刀切MA60"过糙:同一信号按趋势语境反向解读(位置感知)。
- 上升趋势(上证 close>MA60) + 超卖(RSI6≤25 或 bias20≤-3) → 加到满仓(买回调=机会)
- 下降趋势(close<MA60) + 顶背离(创10日新高但 MACD-DIF 弱于10日前且回落) → 减到地板(减反弹顶)
- 其余 = 该趋势基础仓(上升BASE_UP / 下降BASE_DN)
对比 满仓 / 纯趋势MA60(1.0上/0.3下) / 条件化(cond)。4基准 × 全程/前后半,比 Sharpe·Calmar。
顶背离为标准近似(非严格波段配对),已标明。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/rc.py
"""
import math
from app import create_app

IDX = 'sh.000001'
SPLIT = '2016-09-01'
COST = 0.0005
BASE_UP = 0.7
BASE_DN = 0.4
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
        ma60 = ic.rolling(60).mean()
        bias20 = (ic / ic.rolling(20).mean() - 1) * 100
        delta = ic.diff()
        ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean()
        al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
        rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))
        dif = ic.ewm(span=12, adjust=False).mean() - ic.ewm(span=26, adjust=False).mean()
        nh10 = ic >= ic.rolling(10).max()
        topdiv = nh10 & (dif < dif.shift(10)) & (dif < dif.shift(1))   # 价新高但DIF走弱回落=顶背离近似

        def expo(scheme, d):
            up = (d in ma60.index and not math.isnan(ma60[d]) and ic[d] >= ma60[d])
            if scheme == 'trend':
                return 1.0 if up else 0.3
            if scheme == 'cond':
                if up:
                    ov = (rsi6.get(d, 50) <= 25) or (bias20.get(d, 0) <= -3)
                    return 1.0 if ov else BASE_UP
                else:
                    return 0.2 if bool(topdiv.get(d, False)) else BASE_DN
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

        periods = [('全程', '1900', '9999'), ('前半', '1900', SPLIT), ('后半', SPLIT, '9999')]
        schemes = [('满仓100%', None), ('纯趋势MA60', 'trend'), ('条件化cond', 'cond')]
        for nm, code in BASKETS:
            bk = series(code); bkd = [d for d in dates if d in bk]
            if len(bkd) < 200:
                print(f"\n=== {nm}: 无数据 ==="); continue
            print(f"\n{'='*96}\n=== 基准 {nm} ({bkd[0]}~{bkd[-1]}) ===")
            print(f"{'方案':<12}{'区间':<6}{'年化%':>7}{'波动%':>7}{'Sharpe':>8}{'回撤%':>7}{'Calmar':>8}{'平均仓%':>8}{'总收益%':>9}")
            for sn, sc in schemes:
                for pn, lo, hi in periods:
                    pr, ex = [], []
                    for i in range(1, len(bkd)):
                        d0, d1 = bkd[i - 1], bkd[i]
                        if not (lo <= d1 < hi):
                            continue
                        bret = bk[d1] / bk[d0] - 1
                        e0 = 1.0 if sc is None else expo(sc, d0)
                        e1 = 1.0 if sc is None else expo(sc, d1)
                        pr.append(e0 * bret - COST * abs(e1 - e0)); ex.append(e0)
                    m = metrics(pr)
                    if m:
                        print(f"{sn:<12}{pn:<6}{m['ann']*100:>7.1f}{m['vol']*100:>7.1f}{m['sharpe']:>8.2f}"
                              f"{m['mdd']*100:>7.0f}{m['calmar']:>8.2f}{np.mean(ex)*100:>8.0f}{m['tot']*100:>9.0f}")
        print("\n注: 比 Sharpe/Calmar(风险调整),非总收益。cond=上升趋势超卖加仓/下降趋势顶背离减仓。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
