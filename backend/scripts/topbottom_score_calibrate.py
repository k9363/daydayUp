"""顶底温度计评分 —— 落地版标定（从缓存面板,秒级,不碰DB；2026-06-12）。

用途：读 topbottom_score_backtest.py 产出的缓存面板,按『落地版』公式(只用 gauge 自有因子
bias20/rsi6/run5/涨跌停分位,不含主线广度;z标准化→正态CDF)重算 top/bot_score 的 AUC + 阈值标定表,
并打印硬编码常数(FACTOR_STATS / TOPW / BOTW / COMP_TOP / COMP_BOT)。
这些常数已写入 TradingAgents tradingagents/dataflows/topbottom_dashboard.py 的 _TB_* 常量;
调权重/阈值后重跑本脚本拿新常数回填即可,无需重跑 25min 的全量回测。
运行（秒级）：
    docker exec daydayup-backend python3 /app/scripts/topbottom_score_calibrate.py
    # 读 /app/_bt_results/tb_panel.csv(优先) 或 /tmp/tb_panel.csv
"""
import numpy as np, pandas as pd, math, sys
def p(*a): print(*a); sys.stdout.flush()
# 读缓存面板(优先持久化目录)
import os
base = '/app/_bt_results' if os.path.exists('/app/_bt_results/tb_panel.csv') else '/tmp'
F = pd.read_csv(f'{base}/tb_panel.csv')
meta = np.load(f'{base}/tb_meta.npz', allow_pickle=True)
closes = meta['closes'].astype(float); n = len(closes)
p(f"面板 {len(F)}行, 上证 {n}日")

# 多级标签
def swings(W):
    T = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].max()]
    B = [i for i in range(W, n-W) if closes[i] == closes[i-W:i+W+1].min()]
    def dd(a):
        o = []
        for x in a:
            if not o or x-o[-1] > W: o.append(x)
        return o
    return dd(T), dd(B)
T10, B10 = swings(10); T20, B20 = swings(20)
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

# ===== 落地版评分(只用 gauge 现有因子, 不含 breadth/mean_chg) =====
# z 标准化(固定 μ/σ 取自全样本面板), 权重取自回测中级AUC-0.5
def musd(col):
    v = F[col].astype(float); return float(v.mean()), float(v.std())
stats = {c: musd(c) for c in ['bias20', 'rsi6', 'run5', 'lu_pct', 'ld_pct']}
def z(col):
    mu, sd = stats[col]; return ((F[col].astype(float)-mu)/sd).clip(-3, 3).values
TOPW = {'bias20': 0.27, 'rsi6': 0.24, 'run5': 0.17, 'lu_pct': 0.08}
BOTW = {'bias20': 0.29, 'rsi6': 0.25, 'ld_pct': 0.11}  # 去breadth后略提 bias/rsi(原0.33/0.29按比例)
comp_top = sum(w*z(c) for c, w in TOPW.items())
comp_bot = (BOTW['bias20']*(-z('bias20')) + BOTW['rsi6']*(-z('rsi6')) + BOTW['ld_pct']*z('ld_pct'))
muT, sdT = float(np.nanmean(comp_top)), float(np.nanstd(comp_top))
muB, sdB = float(np.nanmean(comp_bot)), float(np.nanstd(comp_bot))
def cdf(x, mu, sd): return 0.5*(1+math.erf((x-mu)/(sd*math.sqrt(2))))
top_score = np.array([100*cdf(x, muT, sdT) if not np.isnan(x) else np.nan for x in comp_top])
bot_score = np.array([100*cdf(x, muB, sdB) if not np.isnan(x) else np.nan for x in comp_bot])

p("\n=== 落地版评分 AUC ===")
for nm, (T, B) in [('阶段W10', (T10, B10)), ('中级W20', (T20, B20))]:
    p(f"  {nm}: 顶score->顶 {auc(top_score, near(T)):.3f} | 底score->底 {auc(bot_score, near(B)):.3f}")
yrs = n/243.0
def dedup_days(mask):
    idxs = np.where(mask)[0]; o = []
    for x in idxs:
        if not o or x-o[-1] > 5: o.append(x)
    return o
p("\n=== 标定 顶score (命中阶段顶±3 / 密度) ===")
yT10 = near(T10); base_t = yT10.mean()
for thr in [60, 70, 75, 80, 85, 90]:
    m = top_score >= thr; ev = dedup_days(m & ~np.isnan(top_score))
    hit = np.mean([yT10[e] for e in ev]) if ev else float('nan')
    p(f"  顶>={thr}: 事件{len(ev)}(~{len(ev)/yrs:.1f}/年) 命中{hit*100:.0f}% (基线{base_t*100:.0f}%)")
p("=== 标定 底score (命中阶段底±3 / 密度) ===")
yB10 = near(B10); base_b = yB10.mean()
for thr in [60, 70, 75, 80, 85, 90]:
    m = bot_score >= thr; ev = dedup_days(m & ~np.isnan(bot_score))
    hit = np.mean([yB10[e] for e in ev]) if ev else float('nan')
    p(f"  底>={thr}: 事件{len(ev)}(~{len(ev)/yrs:.1f}/年) 命中{hit*100:.0f}% (基线{base_b*100:.0f}%)")
p("\n=== 落地常数(硬编码用) ===")
p(f"FACTOR_STATS = {{ {', '.join(f'{repr(k)}: ({v[0]:.4f}, {v[1]:.4f})' for k,v in stats.items())} }}")
p(f"TOPW = {TOPW}")
p(f"BOTW = {BOTW}")
p(f"COMP_TOP = ({muT:.4f}, {sdT:.4f})")
p(f"COMP_BOT = ({muB:.4f}, {sdB:.4f})")
p("DONE")
