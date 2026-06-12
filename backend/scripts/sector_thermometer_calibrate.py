"""板块温度计标定（2026-06-13）：读缓存 PX/AMT(申万一级面板) 重算 per行业因子 → 算 μ/σ + AUC权重
+ composite μ/σ + 分级阈值,产硬编码常数。秒级,不碰 DB。
"""
import os, sys, math
import numpy as np, pandas as pd
from app import app
def p(*a): print(*a); sys.stdout.flush()
_OUT = '/app/_bt_results'
SW1 = {'农林牧渔','基础化工','钢铁','有色金属','电子','家用电器','食品饮料','纺织服饰','轻工制造','医药生物',
       '公用事业','交通运输','房地产','商贸零售','社会服务','综合','建筑材料','建筑装饰','电力设备','机械设备',
       '国防军工','汽车','计算机','传媒','通信','银行','非银金融','煤炭','石油石化','环保','美容护理'}
FAC = ['bias20', 'rsi6', 'run5', 'nh_ratio', 'amt_ratio']  # corr/drawdown 弃(顶无效/弱)
NEG = set(FAC)  # 底部全取负向(值越低越偏底)

with app.app_context():
    from extensions import db
    from sqlalchemy import text
    PX = pd.read_pickle(f'{_OUT}/sector_PX.pkl'); AMT = pd.read_pickle(f'{_OUT}/sector_AMT.pkl')
    RET = PX.pct_change()
    rows = db.session.execute(text("SELECT s.sector_name, r.stock_code FROM stock_sector s JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='industry'")).fetchall()
    im = {}
    for nm, c in rows:
        if nm in SW1: im.setdefault(nm, []).append(c)
    im = {k: v for k, v in im.items() if len(v) >= 20}
    p(f"行业 {len(im)} 个")

    def swings(arr, W=20):
        n = len(arr); T = []; B = []
        for i in range(W, n-W):
            w = arr[i-W:i+W+1]
            if arr[i] == np.nanmax(w): T.append(i)
            if arr[i] == np.nanmin(w): B.append(i)
        def dd(a):
            o = []
            for x in a:
                if not o or x-o[-1] > W: o.append(x)
            return o
        return dd(T), dd(B)

    POOL = {f: [] for f in FAC}; YT = []; YB = []
    for nm, members in im.items():
        mem = [c for c in members if c in PX.columns]
        if len(mem) < 20: continue
        px = PX[mem].ffill(); amt = AMT[mem]; rets = RET[mem]
        valid = px.notna().sum(axis=1) >= 10
        px, amt, rets = px[valid], amt[valid], rets[valid]
        if len(px) < 300: continue
        nav = (1 + rets.mean(axis=1).fillna(0)).cumprod(); navs = pd.Series(nav.values)
        ma20 = navs.rolling(20, min_periods=20).mean()
        bias20 = ((navs/ma20-1)*100).values
        delta = navs.diff(); ag = delta.clip(lower=0).ewm(com=5).mean(); al = (-delta).clip(lower=0).ewm(com=5).mean()
        rsi6 = (100-100/(1+ag/al.replace(0, np.nan))).values
        run5 = ((navs/navs.shift(5)-1)*100).values
        roll_h = px.rolling(20, min_periods=10).max()
        nh_ratio = ((px >= roll_h*0.999).mean(axis=1)*100).values
        secamt = amt.sum(axis=1); amt_ratio = (secamt/secamt.rolling(20, min_periods=10).mean()).values
        fv = {'bias20': bias20, 'rsi6': rsi6, 'run5': run5, 'nh_ratio': nh_ratio, 'amt_ratio': amt_ratio}
        T, B = swings(nav.values, 20); n = len(navs); yT = np.zeros(n); yB = np.zeros(n)
        for t in T:
            for j in range(max(0, t-3), min(n, t+4)): yT[j] = 1
        for b in B:
            for j in range(max(0, b-3), min(n, b+4)): yB[j] = 1
        for f in FAC: POOL[f].append(fv[f])
        YT.append(yT); YB.append(yB)
    for f in FAC: POOL[f] = np.concatenate(POOL[f])
    yT = np.concatenate(YT); yB = np.concatenate(YB)
    N = len(yT)

    def auc(s, y):
        m = ~np.isnan(s); s, y = s[m], y[m]; pos = s[y == 1]; neg = s[y == 0]
        if not len(pos) or not len(neg): return np.nan
        r = pd.Series(np.concatenate([pos, neg])).rank().values
        return (r[:len(pos)].sum()-len(pos)*(len(pos)+1)/2)/(len(pos)*len(neg))

    # μ/σ + 权重(∝AUC-0.5)
    stats = {f: (float(np.nanmean(POOL[f])), float(np.nanstd(POOL[f]))) for f in FAC}
    topw = {f: round(max(auc(POOL[f], yT)-0.5, 0), 3) for f in FAC}
    botw = {f: round(max((1-auc(POOL[f], yB))-0.5, 0), 3) for f in FAC}

    def z(f):
        mu, sd = stats[f]; return np.clip((POOL[f]-mu)/sd, -3, 3)
    comp_top = sum(topw[f]*np.nan_to_num(z(f)) for f in FAC)
    comp_bot = sum(botw[f]*(-np.nan_to_num(z(f))) for f in FAC)
    muT, sdT = float(np.mean(comp_top)), float(np.std(comp_top))
    muB, sdB = float(np.mean(comp_bot)), float(np.std(comp_bot))
    def cdf(x, mu, sd): return 0.5*(1+np.vectorize(math.erf)((x-mu)/(sd*1.4142135623730951)))
    top_s = 100*cdf(comp_top, muT, sdT); bot_s = 100*cdf(comp_bot, muB, sdB)
    p(f"\n板块温度计 AUC: 顶score->顶 {auc(top_s, yT):.3f} | 底score->底 {auc(bot_s, yB):.3f}")
    baseT = yT.mean(); baseB = yB.mean()
    p(f"基线: 近顶±3={baseT*100:.0f}% 近底±3={baseB*100:.0f}%")
    p("=== 顶score 阈值 命中率/占比 ===")
    for thr in [60, 70, 80, 90]:
        m = top_s >= thr
        p(f"  ≥{thr}: 触发{m.mean()*100:.0f}% 命中近顶{yT[m].mean()*100:.0f}%")
    p("=== 底score 阈值 命中率/占比 ===")
    for thr in [60, 70, 80, 90]:
        m = bot_s >= thr
        p(f"  ≥{thr}: 触发{m.mean()*100:.0f}% 命中近底{yB[m].mean()*100:.0f}%")
    p("\n=== 硬编码常数 ===")
    p(f"_SEC_FSTAT = {{ {', '.join(f'{repr(k)}: ({v[0]:.4f}, {v[1]:.4f})' for k,v in stats.items())} }}")
    p(f"_SEC_TOPW = {topw}")
    p(f"_SEC_BOTW = {botw}")
    p(f"_SEC_COMP_TOP = ({muT:.4f}, {sdT:.4f})")
    p(f"_SEC_COMP_BOT = ({muB:.4f}, {sdB:.4f})")
    p("DONE")
