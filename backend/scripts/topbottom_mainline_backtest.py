"""主线 ↔ 大盘顶底 关系回测（2026-06-12）。

用途：验证『主线广度(成交额top100 个股 20日新高广度)』与大盘顶底的关系——
T1 广度水平→上证前向收益 / T2 广度对顶底判别AUC / T3 退潮→见顶提前量 / T4 前后半稳定性。
结论已落进 TradingAgents topbottom_dashboard.build_mainline_monitor:
  广度≥40顺风(20年+1.0%/胜62%稳)、低广度=近底(AUC0.73)、退潮不领先顶(AUC0.43已降级)。
运行（daydayup-backend 容器内,约 20-30min,全市场日线分块加载）：
    docker exec daydayup-backend sh -c "cd /app && PYTHONPATH=/app python3 -u scripts/topbottom_mainline_backtest.py"
注意：按月分块读避免 MySQL 连接超时;此脚本未持久化缓存(如需复用面板见 topbottom_score_backtest.py)。
"""
import logging; logging.disable(logging.CRITICAL)
import numpy as np, pandas as pd, traceback, sys
from app import app
def p(*a):
    print(*a); sys.stdout.flush()
try:
  with app.app_context():
    import time
    from extensions import db
    from sqlalchemy import create_engine
    eng = create_engine(db.engine.url.render_as_string(hide_password=False), pool_pre_ping=True,
                        pool_recycle=300, connect_args={"read_timeout": 600, "connect_timeout": 30, "write_timeout": 600})
    idx = pd.read_sql("SELECT trade_date, close_price c FROM stock_daily_kline WHERE stock_code='sh.000001' AND close_price>0 ORDER BY trade_date", eng)
    idx['trade_date'] = idx['trade_date'].astype(str)
    dates = idx['trade_date'].values; closes = idx['c'].values.astype(float); n = len(idx)
    p(f"上证 {n}日 {dates[0]}~{dates[-1]}")
    W = 20
    rawT = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].max()]
    rawB = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].min()]
    def dedup(a):
        o = []
        for x in a:
            if not o or x-o[-1] > W: o.append(x)
        return o
    tops, bots = dedup(rawT), dedup(rawB)
    p(f"阶段顶 {len(tops)} 阶段底 {len(bots)}")
    p("按年分块拉全市场个股日线...")
    pref = "(stock_code LIKE 'sh.60%%' OR stock_code LIKE 'sh.68%%' OR stock_code LIKE 'sz.00%%' OR stock_code LIKE 'sz.30%%' OR stock_code LIKE 'bj.%%')"
    def read_month(yr, mo):
        q = f"SELECT trade_date, stock_code, close_price c, turnover amt FROM stock_daily_kline WHERE trade_date>='{yr}-{mo:02d}-01' AND trade_date<'{yr+(mo//12)}-{(mo%12)+1:02d}-01' AND turnover>0 AND close_price>0 AND {pref}"
        for att in range(3):
            try:
                return pd.read_sql(q, eng)
            except Exception as ex:
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
    p(f"个股日线 {len(df)} 行")
    df['trade_date'] = df['trade_date'].astype(str)
    df['c'] = df['c'].astype('float32'); df['amt'] = df['amt'].astype('float64')
    df = df.sort_values(['stock_code', 'trade_date'])
    df['roll20'] = df.groupby('stock_code', sort=False)['c'].transform(lambda s: s.rolling(20, min_periods=20).max())
    df['nh20'] = (df['c'] >= df['roll20']).astype('float32')
    p("rolling 完成, 算逐日广度...")
    def db_(g):
        t = g.nlargest(100, 'amt'); v = t['nh20'].dropna()
        return v.mean()*100 if len(v) >= 50 else np.nan
    breadth = df.groupby('trade_date', sort=True).apply(db_)
    b = breadth.reindex(dates).values.astype(float)
    p(f"主线广度有效日 {n-int(np.isnan(b).sum())}/{n}")
    np.savez('/tmp/mainline_cache.npz', dates=dates, closes=closes, b=b,
             tops=np.array(tops), bots=np.array(bots))
    p("已缓存 /tmp/mainline_cache.npz")
    cl = pd.Series(closes, index=range(n)); fwd10 = (cl.shift(-10)/cl-1).values
    p("\n=== T1 主线广度水平 -> 上证前向收益(全周期) ===")
    for lo, hi, lab in [(-1, 25, '<25%弱'), (25, 40, '25-40%中'), (40, 200, '>=40%强')]:
        m = (b >= lo) & (b < hi) & ~np.isnan(fwd10); r = fwd10[m]
        p(f"  广度{lab:9s} n={int(m.sum()):4d} | 前10日 均值{r.mean()*100:+.2f}% 胜率{(r>0).mean()*100:.0f}%")
    base = fwd10[~np.isnan(fwd10)]; p(f"  基线全样本   n={len(base)} | 前10日 均值{base.mean()*100:+.2f}% 胜率{(base>0).mean()*100:.0f}%")
    def auc(score, label):
        m = ~np.isnan(score) & ~np.isnan(label); s = score[m]; y = label[m]; pos = s[y == 1]; neg = s[y == 0]
        if len(pos) == 0 or len(neg) == 0: return float('nan')
        r = pd.Series(np.concatenate([pos, neg])).rank().values
        return (r[:len(pos)].sum() - len(pos)*(len(pos)+1)/2) / (len(pos)*len(neg))
    def near(idxs, h=3):
        y = np.zeros(n)
        for pp in idxs:
            for j in range(max(0, pp-h), min(n, pp+h+1)): y[j] = 1
        return y
    yT = near(tops); yB = near(bots)
    bs = pd.Series(b); peak15 = bs.rolling(15, min_periods=8).max().values
    bdraw = 1 - b/np.where(peak15 > 0, peak15, np.nan); bchg5 = bs.diff(5).values
    p("\n=== T2 主线广度对顶/底判别 AUC (近顶/底±3日) ===")
    p(f"  广度水平 -> 底(低广度偏底)  AUC: {1-auc(b, yB):.3f}")
    p(f"  广度水平 -> 顶(高广度偏顶)  AUC: {auc(b, yT):.3f}")
    p(f"  退潮强度 -> 顶(从峰塌缩)    AUC: {auc(bdraw, yT):.3f}")
    p(f"  广度5日变化 -> 顶(走弱偏顶) AUC: {1-auc(bchg5, yT):.3f}")
    p(f"  广度5日变化 -> 底(回升偏底) AUC: {auc(bchg5, yB):.3f}")
    p("\n=== T3 退潮事件(峰>=50且现<峰*0.6) -> 之后见顶提前量 ===")
    ev = dedup([i for i in range(16, n) if (not np.isnan(peak15[i]) and peak15[i] >= 50 and not np.isnan(b[i]) and b[i] < peak15[i]*0.6)])
    topset = np.array(sorted(tops)); hit = 0; leads = []
    for e in ev:
        nxt = topset[topset >= e]
        if len(nxt): ld = int(nxt[0]-e); leads.append(ld); hit += (0 <= ld <= 20)
    p(f"  退潮 {len(ev)}次 | 之后20日内见顶 {hit}次 命中率{hit/max(len(ev),1)*100:.0f}% (基线~{len(tops)/n*21*100:.0f}%)")
    if leads:
        L = np.array([x for x in leads if 0 <= x <= 40]); p(f"  提前量(0-40日 中位/均值): {np.median(L):.0f}/{np.mean(L):.0f}日 n={len(L)}")
    half = n//2
    p("\n=== T4 分前后半 ===")
    for name, sl in [("前半 "+dates[0][:4]+"-"+dates[half][:4], slice(0, half)), ("后半 "+dates[half][:4]+"-"+dates[-1][:4], slice(half, n))]:
        bb = b[sl]; ff = fwd10[sl]; yb = yB[sl]; yt = yT[sl]; bd = bdraw[sl]
        ms = (bb >= 40) & ~np.isnan(ff); mw = (bb < 25) & ~np.isnan(ff)
        p(f"  {name}: >=40前10日{ff[ms].mean()*100:+.2f}%/胜{(ff[ms]>0).mean()*100:.0f}%(n{int(ms.sum())}) | <25 {ff[mw].mean()*100:+.2f}%/{(ff[mw]>0).mean()*100:.0f}%(n{int(mw.sum())}) | 退潮->顶AUC{auc(bd,yt):.3f} | 低广度->底AUC{1-auc(bb,yb):.3f}")
    p("DONE")
except Exception as e:
    p("ERR " + repr(e)); traceback.print_exc(); sys.stdout.flush()
