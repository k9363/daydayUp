"""顶底温度计评分 —— 全周期回测 + 多级标签 + 因子判别力 + 评分标定（2026-06-12）。

用途：基于 stock_daily_kline(2007-2026 全市场含退市股) 算每日因子面板,打三级摆动标签
(阶段W10/中级W20/大级W40),输出 各因子AUC + 合成顶底评分AUC + 阈值标定表,并缓存面板供复用。
运行（daydayup-backend 容器内,约 25-35min,瓶颈是全市场日线分块加载）：
    docker exec daydayup-backend sh -c "cd /app && PYTHONPATH=/app python3 -u scripts/topbottom_score_backtest.py"
缓存输出（持久目录 /app/_bt_results = 宿主 ~/daydayup_docker/backend/_bt_results/）：
    tb_panel.csv  每日因子面板,列: bias20,rsi6,near_high,run5,up_ratio,mean_chg,breadth,lu_pct,ld_pct,limit_up,limit_dn
    tb_meta.npz   dates, closes(上证)
    tb_scores.npz top_score, bot_score, signed
注意：大表无 trade_date 索引,按月分块读 + read_timeout=600 + 重试,避免 MySQL 连接超时(2013)。
配套：scripts/topbottom_score_calibrate.py 从缓存秒级重标定(不碰DB);常数已写入
      TradingAgents tradingagents/dataflows/topbottom_dashboard.py 的 _TB_* 常量。
"""
import os
import logging; logging.disable(logging.CRITICAL)
import numpy as np, pandas as pd, traceback, sys, time
from app import app
_OUT = '/app/_bt_results'
def p(*a):
    print(*a); sys.stdout.flush()
try:
  with app.app_context():
    from extensions import db
    from sqlalchemy import create_engine
    eng = create_engine(db.engine.url.render_as_string(hide_password=False), pool_pre_ping=True,
                        pool_recycle=300, connect_args={"read_timeout": 600, "connect_timeout": 30, "write_timeout": 600})
    # ===== 上证 =====
    idx = pd.read_sql("SELECT trade_date, close_price c FROM stock_daily_kline WHERE stock_code='sh.000001' AND close_price>0 ORDER BY trade_date", eng)
    idx['trade_date'] = idx['trade_date'].astype(str)
    dates = idx['trade_date'].values; closes = idx['c'].values.astype(float); n = len(idx)
    p(f"上证 {n}日 {dates[0]}~{dates[-1]}")
    # ===== 全市场个股(按月分块) -> 每日聚合 + 主线广度 =====
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
    p(f"个股日线 {len(df)} 行")
    df['trade_date'] = df['trade_date'].astype(str)
    df = df.sort_values(['stock_code', 'trade_date'])
    g = df.groupby('stock_code', sort=False)
    df['prevc'] = g['c'].shift(1)
    df['pct'] = (df['c'] / df['prevc'] - 1) * 100
    df['roll20'] = g['c'].transform(lambda s: s.rolling(20, min_periods=20).max())
    df['nh20'] = (df['c'] >= df['roll20']).astype('float32')
    p("个股派生完成, 聚合每日因子...")
    # 每日全市场聚合
    def agg_day(gg):
        pc = gg['pct'].dropna()
        top = gg.nlargest(100, 'amt')
        nhv = top['nh20'].dropna()
        return pd.Series({
            'up_ratio': (pc > 0).mean() * 100 if len(pc) else np.nan,
            'limit_up': int((pc >= 9.7).sum()),
            'limit_dn': int((pc <= -9.7).sum()),
            'mean_chg': pc.mean() if len(pc) else np.nan,
            'breadth': nhv.mean() * 100 if len(nhv) >= 50 else np.nan,
        })
    daily = df.groupby('trade_date', sort=True).apply(agg_day)
    daily = daily.reindex(dates)
    p(f"每日因子聚合完成 {daily['up_ratio'].notna().sum()}/{n}")
    # ===== 上证派生因子 =====
    cl = pd.Series(closes)
    ma20 = cl.rolling(20, min_periods=20).mean()
    bias20 = (cl / ma20 - 1) * 100
    delta = cl.diff()
    ag = delta.clip(lower=0).ewm(com=5, adjust=True).mean(); al = (-delta).clip(lower=0).ewm(com=5, adjust=True).mean()
    rsi6 = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    roll20i = cl.rolling(20, min_periods=20).max()
    near_high = (cl >= roll20i * 0.999)
    run5 = (cl / cl.shift(5) - 1) * 100
    # 涨跌停 250日滚动分位
    lu = daily['limit_up'].reset_index(drop=True); ld = daily['limit_dn'].reset_index(drop=True)
    lu_pct = lu.rolling(250, min_periods=60).apply(lambda w: (w.iloc[-1] >= w).mean(), raw=False)
    ld_pct = ld.rolling(250, min_periods=60).apply(lambda w: (w.iloc[-1] >= w).mean(), raw=False)
    F = pd.DataFrame({
        'bias20': bias20.values, 'rsi6': rsi6.values, 'near_high': near_high.values.astype(float),
        'run5': run5.values, 'up_ratio': daily['up_ratio'].values, 'mean_chg': daily['mean_chg'].values,
        'breadth': daily['breadth'].values, 'lu_pct': lu_pct.values, 'ld_pct': ld_pct.values,
        'limit_up': daily['limit_up'].values, 'limit_dn': daily['limit_dn'].values,
    })
    os.makedirs(_OUT, exist_ok=True)
    F.to_csv(f'{_OUT}/tb_panel.csv', index=False)
    np.savez(f'{_OUT}/tb_meta.npz', dates=dates, closes=closes)
    p(f"已缓存 {_OUT}/tb_panel.csv + tb_meta.npz")
    # ===== 多级摆动标签 =====
    def swings(W):
        T = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].max()]
        B = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].min()]
        def dd(a):
            o = []
            for x in a:
                if not o or x-o[-1] > W: o.append(x)
            return o
        return dd(T), dd(B)
    tiers = {'阶段W10': 10, '中级W20': 20, '大级W40': 40}
    lab = {}
    for nm, W in tiers.items():
        T, B = swings(W); lab[nm] = (T, B)
        p(f"  {nm}: 顶{len(T)} 底{len(B)}")
    def near(idxs, h=3):
        y = np.zeros(n)
        for pp in idxs:
            for j in range(max(0, pp-h), min(n, pp+h+1)): y[j] = 1
        return y
    def auc(score, label):
        m = ~np.isnan(score) & ~np.isnan(label); s = np.asarray(score)[m]; y = np.asarray(label)[m]
        pos = s[y == 1]; neg = s[y == 0]
        if len(pos) == 0 or len(neg) == 0: return float('nan')
        r = pd.Series(np.concatenate([pos, neg])).rank().values
        return (r[:len(pos)].sum() - len(pos)*(len(pos)+1)/2) / (len(pos)*len(neg))
    # ===== 各因子在各级别的判别力 AUC =====
    p("\n=== 各因子对『顶』判别 AUC (按级别; >0.5=值大偏顶) ===")
    topfac = ['bias20', 'rsi6', 'run5', 'lu_pct', 'up_ratio']
    for nm in tiers:
        yT = near(lab[nm][0]); row = " ".join(f"{f}={auc(F[f].values, yT):.2f}" for f in topfac)
        p(f"  {nm}: {row}")
    p("=== 各因子对『底』判别 AUC (已按方向, >0.5=偏底) ===")
    botfac = [('bias20', -1), ('rsi6', -1), ('ld_pct', 1), ('up_ratio', -1), ('mean_chg', -1), ('breadth', -1)]
    for nm in tiers:
        yB = near(lab[nm][1]); row = " ".join(f"{f}={auc(s*F[f].values, yB):.2f}" for f, s in botfac)
        p(f"  {nm}: {row}")
    # ===== 合成温度计: 因子百分位 × (权重∝中级AUC-0.5) =====
    def pctrank(x):
        s = pd.Series(x); return s.rank(pct=True).values
    yT20 = near(lab['中级W20'][0]); yB20 = near(lab['中级W20'][1])
    topw = {f: max(auc(F[f].values, yT20)-0.5, 0) for f in topfac}
    botw = {f: max(auc(s*F[f].values, yB20)-0.5, 0) for f, s in botfac}
    p(f"\n顶权重(∝中级AUC-0.5): {{ {', '.join(f'{k}:{v:.2f}' for k,v in topw.items())} }}")
    p(f"底权重: {{ {', '.join(f'{k}:{v:.2f}' for k,v in botw.items())} }}")
    pr = {f: pctrank(F[f].values) for f in topfac}
    prb = {f: pctrank(s*F[f].values) for f, s in botfac}
    tw = sum(topw.values()); bw = sum(botw.values())
    top_score = sum(topw[f]*pr[f] for f in topfac)/tw*100
    bot_score = sum(botw[f]*prb[f] for f, s in botfac)/bw*100
    signed = top_score - bot_score
    p("\n=== 合成评分 AUC (顶score->顶 / 底score->底, 各级别) ===")
    for nm in tiers:
        yT = near(lab[nm][0]); yB = near(lab[nm][1])
        p(f"  {nm}: 顶score->顶 {auc(top_score, yT):.3f} | 底score->底 {auc(bot_score, yB):.3f} | signed->顶 {auc(signed, yT):.3f}")
    # ===== 标定: 阈值 -> 命中率 + 密度(次/年) 对『阶段级』 =====
    yrs = n/243.0
    p("\n=== 标定 顶score 阈值 -> 命中阶段顶±3 / 密度 ===")
    yT10 = near(lab['阶段W10'][0])
    def dedup_days(mask):
        idxs = np.where(mask)[0]; o = []
        for x in idxs:
            if not o or x-o[-1] > 5: o.append(x)
        return o
    for thr in [60, 70, 80, 90]:
        m = top_score >= thr; ev = dedup_days(m & ~np.isnan(top_score))
        hit = np.mean([yT10[e] for e in ev]) if ev else float('nan')
        p(f"  顶score>={thr}: 触发日{int(np.nansum(m))} 事件{len(ev)}(~{len(ev)/yrs:.1f}/年) 命中阶段顶±3 {hit*100:.0f}%")
    p("=== 标定 底score 阈值 -> 命中阶段底±3 / 密度 ===")
    yB10 = near(lab['阶段W10'][1])
    for thr in [60, 70, 80, 90]:
        m = bot_score >= thr; ev = dedup_days(m & ~np.isnan(bot_score))
        hit = np.mean([yB10[e] for e in ev]) if ev else float('nan')
        p(f"  底score>={thr}: 触发日{int(np.nansum(m))} 事件{len(ev)}(~{len(ev)/yrs:.1f}/年) 命中阶段底±3 {hit*100:.0f}%")
    np.savez(f'{_OUT}/tb_scores.npz', top_score=top_score, bot_score=bot_score, signed=signed)
    p(f"已缓存 {_OUT}/tb_scores.npz")
    p("DONE")
except Exception as e:
    p("ERR " + repr(e)); traceback.print_exc(); sys.stdout.flush()
