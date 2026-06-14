#!/usr/bin/env python3
"""
4档阶梯 参数敏感性检验（2026-06-14）—— 确认是稳健山头还是刀尖拟合

固定: 趋势MA60 / 摆动半窗W=5 / 上升满仓 / 下降守破位线轻仓0.3 / 破位空仓。
扫描: 顶背离降仓档 DIV_CUT∈{0.4,0.5,0.6} × 激活窗 ACTIVE∈{5,10,15} × 破位线 BREAK_MA∈{100,120,150}
共27组,基准 中证1000 + 中证500,全程 Sharpe/Calmar/回撤。Sharpe 全程在窄带内=稳健。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/rls.py
"""
import math
from app import create_app

IDX = 'sh.000001'
COST = 0.0005
W = 5
BASKETS = [('中证1000', 'sh.000852'), ('中证500', 'sh.000905')]


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
        ic = series(IDX); dates = list(ic.index); cl = ic.values
        ma60 = ic.rolling(60).mean().values
        mas = {m: ic.rolling(m).mean().values for m in (100, 120, 150)}
        dif = (ic.ewm(span=12, adjust=False).mean() - ic.ewm(span=26, adjust=False).mean()).values
        # 摆动高点 + 熊背离配对(确认点 = 高点+W)
        div_starts = []
        sw = []
        for i in range(W, len(dates) - W):
            if cl[i] == max(cl[i - W:i + W + 1]) and cl[i] > cl[i - 1]:
                sw.append((i, cl[i], dif[i]))
        for k in range(1, len(sw)):
            if sw[k][1] > sw[k - 1][1] and sw[k][2] < sw[k - 1][2]:
                div_starts.append(sw[k][0] + W)

        def topdiv_arr(active):
            t = [False] * len(dates)
            for s in div_starts:
                for j in range(s, min(s + active, len(dates))):
                    t[j] = True
            return t

        def metrics(rets):
            r = np.array(rets); nav = np.cumprod(1 + r)
            ann = nav[-1] ** (242.0 / len(r)) - 1
            vol = r.std() * math.sqrt(242)
            sh = (r.mean() * 242) / vol if vol > 0 else float('nan')
            mdd = float((nav / np.maximum.accumulate(nav) - 1).min())
            return sh, (ann / abs(mdd) if mdd < 0 else float('nan')), mdd * 100, (nav[-1] - 1) * 100, np.mean

        di = {d: i for i, d in enumerate(dates)}
        for nm, code in BASKETS:
            bk = series(code); bkd = [d for d in dates if d in bk]
            if len(bkd) < 200:
                continue
            # 基准
            bnav = np.array([bk[d] for d in bkd]) / bk[bkd[0]]
            br = np.diff(bnav) / bnav[:-1]
            bsh = (br.mean() * 242) / (br.std() * math.sqrt(242))
            print(f"\n{'='*78}\n=== {nm}  (满仓 Sharpe {bsh:.2f}) ===")
            print(f"{'降仓':>5}{'激活':>5}{'破位MA':>7} | {'Sharpe':>7}{'Calmar':>7}{'回撤%':>7}{'总收益%':>9}{'平均仓%':>8}")
            shs = []
            for cut in (0.4, 0.5, 0.6):
                for active in (5, 10, 15):
                    td = topdiv_arr(active)
                    for bm in (100, 120, 150):
                        ma_b = mas[bm]
                        pr, ex = [], []
                        for a in range(1, len(bkd)):
                            i0 = di[bkd[a - 1]]; i1 = di[bkd[a]]
                            bret = bk[bkd[a]] / bk[bkd[a - 1]] - 1

                            def e(i):
                                m6 = ma60[i]
                                if math.isnan(m6):
                                    return 1.0
                                if cl[i] >= m6:
                                    return cut if td[i] else 1.0
                                if not math.isnan(ma_b[i]) and cl[i] >= ma_b[i]:
                                    return 0.3
                                return 0.0
                            e0, e1 = e(i0), e(i1)
                            pr.append(e0 * bret - COST * abs(e1 - e0)); ex.append(e0)
                        r = np.array(pr); nav = np.cumprod(1 + r)
                        ann = nav[-1] ** (242.0 / len(r)) - 1
                        vol = r.std() * math.sqrt(242)
                        sh = (r.mean() * 242) / vol if vol > 0 else float('nan')
                        mdd = float((nav / np.maximum.accumulate(nav) - 1).min())
                        cal = ann / abs(mdd) if mdd < 0 else float('nan')
                        shs.append(sh)
                        print(f"{cut:>5}{active:>5}{bm:>7} | {sh:>7.2f}{cal:>7.2f}{mdd*100:>7.0f}{(nav[-1]-1)*100:>9.0f}{np.mean(ex)*100:>8.0f}")
            print(f"  → Sharpe 全网格 min/中位/max = {min(shs):.2f}/{sorted(shs)[len(shs)//2]:.2f}/{max(shs):.2f} (满仓{bsh:.2f})")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
