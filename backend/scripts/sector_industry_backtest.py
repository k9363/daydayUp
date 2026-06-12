"""行业板块顶底回测 v2 提纯版（2026-06-13）：只用申万一级(去嵌套) + 前后半稳定性 + 缓存 PX/AMT。
运行: docker exec daydayup-backend sh -c "cd /app && PYTHONPATH=/app python3 -u scripts/sector_industry_backtest.py"
"""
import os, logging, sys, time, traceback
logging.disable(logging.CRITICAL)
import numpy as np, pandas as pd
from app import app
def p(*a): print(*a); sys.stdout.flush()
_OUT = '/app/_bt_results'
os.makedirs(_OUT, exist_ok=True)
# 申万一级 31(2021)白名单 —— 只留一级,排除二级/三级(半导体/汽车零部件/通用设备/IT服务/电网设备/电力/电池...)
SW1 = {'农林牧渔','基础化工','钢铁','有色金属','电子','家用电器','食品饮料','纺织服饰','轻工制造','医药生物',
       '公用事业','交通运输','房地产','商贸零售','社会服务','综合','建筑材料','建筑装饰','电力设备','机械设备',
       '国防军工','汽车','计算机','传媒','通信','银行','非银金融','煤炭','石油石化','环保','美容护理'}
SPLIT = '2016-09-01'

try:
  with app.app_context():
    from extensions import db
    from sqlalchemy import create_engine, text
    eng = create_engine(db.engine.url.render_as_string(hide_password=False), pool_pre_ping=True,
                        pool_recycle=300, connect_args={"read_timeout": 600, "connect_timeout": 30, "write_timeout": 600})
    rows = db.session.execute(text("""
        SELECT s.sector_name, r.stock_code FROM stock_sector s
        JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='industry'""")).fetchall()
    ind_members = {}
    for nm, code in rows:
        if nm in SW1:
            ind_members.setdefault(nm, []).append(code)
    ind_members = {k: v for k, v in ind_members.items() if len(v) >= 20}
    p(f"申万一级行业 {len(ind_members)} 个: {sorted(ind_members)}")

    pref = "(stock_code LIKE 'sh.60%%' OR stock_code LIKE 'sh.68%%' OR stock_code LIKE 'sz.00%%' OR stock_code LIKE 'sz.30%%' OR stock_code LIKE 'bj.%%')"
    def read_month(yr, mo):
        q = f"SELECT trade_date, stock_code, close_price c, turnover amt FROM stock_daily_kline WHERE trade_date>='{yr}-{mo:02d}-01' AND trade_date<'{yr+(mo//12)}-{(mo%12)+1:02d}-01' AND turnover>0 AND close_price>0 AND {pref}"
        for att in range(3):
            try: return pd.read_sql(q, eng)
            except Exception:
                if att == 2: raise
                eng.dispose(); time.sleep(3)
    frames = []
    for yr in range(2007, 2027):
        ny = 0
        for mo in range(1, 13):
            if yr == 2026 and mo > 6: break
            d = read_month(yr, mo)
            if len(d):
                d['c'] = d['c'].astype('float32'); d['amt'] = d['amt'].astype('float64')
                frames.append(d); ny += len(d)
        p(f"  {yr}: {ny}")
    df = pd.concat(frames, ignore_index=True); frames = None
    df['trade_date'] = df['trade_date'].astype(str)
    p(f"个股日线 {len(df)} 行,透视...")
    PX = df.pivot_table(index='trade_date', columns='stock_code', values='c').sort_index()
    AMT = df.pivot_table(index='trade_date', columns='stock_code', values='amt').sort_index()
    df = None
    RET = PX.pct_change()
    PX.to_pickle(f'{_OUT}/sector_PX.pkl'); AMT.to_pickle(f'{_OUT}/sector_AMT.pkl')
    p(f"透视完成 {PX.shape}, 已缓存 PX/AMT")
    dates_all = np.array(PX.index.tolist())

    def auc(score, label):
        m = ~np.isnan(score) & ~np.isnan(label); s = np.asarray(score)[m]; y = np.asarray(label)[m]
        pos = s[y == 1]; neg = s[y == 0]
        if len(pos) == 0 or len(neg) == 0: return np.nan
        r = pd.Series(np.concatenate([pos, neg])).rank().values
        return (r[:len(pos)].sum() - len(pos)*(len(pos)+1)/2) / (len(pos)*len(neg))
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

    FAC = ['bias20', 'rsi6', 'run5', 'drawdown', 'nh_ratio', 'amt_ratio', 'corr']
    NEG = {'bias20', 'rsi6', 'run5', 'nh_ratio', 'amt_ratio'}  # 底部取负向
    agg = {f: {'v': [], 'yT': [], 'yB': [], 'h': []} for f in FAC}
    nT = nB = 0
    for ii, (nm, members) in enumerate(ind_members.items(), 1):
        mem = [c for c in members if c in PX.columns]
        if len(mem) < 20: continue
        px = PX[mem].ffill(); amt = AMT[mem]; rets = RET[mem]
        valid = px.notna().sum(axis=1) >= 10
        px, amt, rets = px[valid], amt[valid], rets[valid]
        if len(px) < 300: continue
        d_idx = np.array(px.index.tolist())
        half = (d_idx >= SPLIT).astype(int)
        nav = (1 + rets.mean(axis=1).fillna(0)).cumprod(); navv = nav.values; navs = pd.Series(navv)
        ma20 = navs.rolling(20, min_periods=20).mean()
        bias20 = ((navs/ma20-1)*100).values
        delta = navs.diff(); ag = delta.clip(lower=0).ewm(com=5).mean(); al = (-delta).clip(lower=0).ewm(com=5).mean()
        rsi6 = (100-100/(1+ag/al.replace(0, np.nan))).values
        run5 = ((navs/navs.shift(5)-1)*100).values
        drawdown = ((navs/navs.cummax()-1)*100).values
        roll_h = px.rolling(20, min_periods=10).max()
        nh_ratio = ((px >= roll_h*0.999).mean(axis=1)*100).values
        secamt = amt.sum(axis=1)
        amt_ratio = (secamt/secamt.rolling(20, min_periods=10).mean()).values
        samp = mem[:25]; rv = rets[samp].values; corr_arr = np.full(len(px), np.nan)
        for i in range(20, len(px)):
            sub = rv[i-19:i+1]; colok = ~np.all(np.isnan(sub), axis=0); sub2 = sub[:, colok]
            if sub2.shape[1] >= 5:
                cm = np.corrcoef(np.nan_to_num(sub2).T); corr_arr[i] = cm[np.triu_indices_from(cm, 1)].mean()
        T, B = swings(navv, 20); nT += len(T); nB += len(B)
        n = len(navv); yT = np.zeros(n); yB = np.zeros(n)
        for t in T:
            for j in range(max(0, t-3), min(n, t+4)): yT[j] = 1
        for b in B:
            for j in range(max(0, b-3), min(n, b+4)): yB[j] = 1
        fv = {'bias20': bias20, 'rsi6': rsi6, 'run5': run5, 'drawdown': drawdown, 'nh_ratio': nh_ratio, 'amt_ratio': amt_ratio, 'corr': corr_arr}
        for f in FAC:
            agg[f]['v'].append(fv[f]); agg[f]['yT'].append(yT); agg[f]['yB'].append(yB); agg[f]['h'].append(half)
    p(f"\n申万一级 阶段顶 {nT} / 阶段底 {nB}（池化）")

    def rep(side, ydir):
        p(f"\n=== 行业级『{side}』判别 AUC（全周期 | 前半 | 后半）{'(取负向)' if ydir=='neg-aware' else ''} ===")
        for f in FAC:
            v = np.concatenate(agg[f]['v']); y = np.concatenate(agg[f]['yT' if side=='顶' else 'yB']); h = np.concatenate(agg[f]['h'])
            def a1(mask):
                a = auc(v[mask], y[mask])
                if side == '底' and f in NEG and not np.isnan(a): a = 1-a
                return a
            full = a1(np.ones(len(v), bool)); h0 = a1(h==0); h1 = a1(h==1)
            p(f"  {f:10s}: {full:.3f} | {h0:.3f} | {h1:.3f}")
    rep('顶', 'raw'); rep('底', 'neg-aware')
    p("DONE")
except Exception as e:
    p("ERR " + repr(e)); traceback.print_exc(); sys.stdout.flush()
