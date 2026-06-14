#!/usr/bin/env python3
"""
分级控仓(仓位拨盘)回测 —— 比风险调整收益（2026-06-14）

把大盘 regime(顶底温度的主成分:上证 bias20/RSI6/MA)映射到每日 0-100% 仓位,
日频应用到基准收益,对比"一直满仓(100%)买入持有"。目标不是跑赢总收益,
而是 **同等收益下更低回撤 / 更高 Sharpe / 更高 Calmar**(验证"风控工具"该看的指标)。

仓位映射(几种对比):
  temp   连续温度计近似: expo=clip(0.6-0.06*bias20,0.2,1); RSI6≥75 封顶0.3 / ≤25 保底0.95; 跌破MA60 ×0.5
  3state 三态: 超卖1.0 / 正常0.6 / 超买0.3; 跌破MA60 ×0.6
  trend  纯趋势: 在MA60上方1.0 否则0.3
基准: 中证1000/中证500/沪深300/上证。换仓成本=0.05%×|Δ仓位|。区间: 全程/前半<2016-09/后半。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/ge.py
"""
import math
from app import create_app

IDX = 'sh.000001'
SPLIT = '2016-09-01'
COST = 0.0005   # 每单位仓位变动成本
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
        ma20 = ic.rolling(20).mean(); ma60 = ic.rolling(60).mean(); ma120 = ic.rolling(120).mean()
        bias20 = (ic / ma20 - 1) * 100
        delta = ic.diff()
        ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean()
        al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
        rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))

        def expo(scheme, d):
            b = bias20.get(d, 0.0); r = rsi6.get(d, 50.0)
            below60 = (d in ma60.index and not math.isnan(ma60[d]) and ic[d] < ma60[d])
            if math.isnan(b):
                b = 0.0
            if math.isnan(r):
                r = 50.0
            if scheme == 'temp':
                e = min(1.0, max(0.2, 0.6 - 0.06 * b))
                if r >= 75:
                    e = min(e, 0.3)
                if r <= 25:
                    e = max(e, 0.95)
                if below60:
                    e *= 0.5
                return e
            if scheme == '3state':
                ov = (b <= -3) or (r <= 25); ob = (b >= 2.5) or (r >= 75)
                e = 1.0 if ov else (0.3 if ob else 0.6)
                return e * (0.6 if below60 else 1.0)
            if scheme == 'trend':
                return 1.0 if not below60 else 0.3
            if scheme in ('trend20', 'trend60', 'trend120'):
                msel = {'trend20': ma20, 'trend60': ma60, 'trend120': ma120}[scheme]
                mv = msel.get(d, float('nan'))
                return 0.3 if (not math.isnan(mv) and ic[d] < mv) else 1.0
            if scheme == 'combo':   # 趋势MA60为基 + 顶底极值微调
                ob = (b >= 2.5) or (r >= 75); ov = (b <= -3) or (r <= 25)
                if not below60:
                    return 0.7 if ob else 1.0      # 上升趋势中超买→适度减
                else:
                    return 0.5 if ov else 0.3      # 下降趋势中超卖→适度加(博反弹)
            return 1.0

        def metrics(rets, ppy=242):
            r = np.array(rets)
            if len(r) < 50:
                return None
            nav = np.cumprod(1 + r)
            ann = nav[-1] ** (ppy / len(r)) - 1
            vol = r.std() * math.sqrt(ppy)
            sharpe = (r.mean() * ppy) / vol if vol > 0 else float('nan')
            mdd = float((nav / np.maximum.accumulate(nav) - 1).min())
            calmar = ann / abs(mdd) if mdd < 0 else float('nan')
            return dict(tot=nav[-1] - 1, ann=ann, vol=vol, sharpe=sharpe, mdd=mdd, calmar=calmar)

        periods = [('全程', '1900', '9999'), ('前半', '1900', SPLIT), ('后半', SPLIT, '9999')]
        for nm, code in BASKETS:
            bk = series(code)
            bkd = [d for d in dates if d in bk]
            if len(bkd) < 200:
                print(f"\n=== {nm}: 无数据 ==="); continue
            # 日收益 + 各方案日仓位
            print(f"\n{'='*104}\n=== 基准 {nm} ({bkd[0]}~{bkd[-1]}) ===")
            print(f"{'方案':<10}{'区间':<6}{'年化%':>7}{'波动%':>7}{'Sharpe':>8}{'回撤%':>7}{'Calmar':>8}{'平均仓%':>8}{'总收益%':>9}")
            schemes = [('满仓100%', None), ('trend20', 'trend20'), ('trend60', 'trend60'),
                       ('trend120', 'trend120'), ('combo趋势+顶底', 'combo'), ('temp温度计', 'temp')]
            for sn, sc in schemes:
                for pn, lo, hi in periods:
                    pr = []; expos = []
                    for i in range(1, len(bkd)):
                        d0, d1 = bkd[i - 1], bkd[i]
                        if not (lo <= d1 < hi):
                            continue
                        bret = bk[d1] / bk[d0] - 1
                        if sc is None:
                            e0 = e1 = 1.0
                        else:
                            e0 = expo(sc, d0); e1 = expo(sc, d1)
                        c = COST * abs(e1 - e0)
                        pr.append(e0 * bret - c); expos.append(e0)
                    m = metrics(pr)
                    if m:
                        print(f"{sn:<10}{pn:<6}{m['ann']*100:>7.1f}{m['vol']*100:>7.1f}{m['sharpe']:>8.2f}"
                              f"{m['mdd']*100:>7.0f}{m['calmar']:>8.2f}{np.mean(expos)*100:>8.0f}{m['tot']*100:>9.0f}")
        print("\n注: 目标=同等收益更低回撤/更高Sharpe·Calmar(风控),非比总收益。Calmar=年化/|最大回撤|。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
