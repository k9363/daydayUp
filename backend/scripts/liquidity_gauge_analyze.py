import json, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
J = json.load(open('/tmp/liq_series.json'))
days = J['daily_sh']['days']; close = J['daily_sh']['close']; amt = J['daily_sh']['amt']
c = pd.Series({d: close[d] for d in days}).sort_index()
a = pd.Series({d: amt[d] for d in days}).sort_index()
ma60 = c.rolling(60).mean()
expand = a.rolling(20).mean() / a.rolling(120).mean()    # 上证成交额 放量倍数
# 周度 换手率(成交额/总市值): amt千元*1000 / mv万元*10000 = amt_k/(mv_w*10)
W = pd.DataFrame(J['weekly'])
W = W[W['mkt_amt_k'].notna() & W['mkt_mv_w'].notna()].copy()
W['turn'] = W['mkt_amt_k'] / (W['mkt_mv_w'] * 10) * 100   # 日换手率 %
W = W.set_index('d').sort_index()
W['turn_pct'] = W['turn'].rolling(104, min_periods=40).apply(lambda x: (x <= x.iloc[-1]).mean(), raw=False)  # 2yr分位
W['expand'] = [expand.get(d, np.nan) for d in W.index]
W['bull'] = [bool(close.get(d, 0) >= (ma60.get(d) if not pd.isna(ma60.get(d, np.nan)) else 9e9)) for d in W.index]
# 高流动性 = 换手率分位≥0.5 且 放量≥1.05; 高流动性牛市=再叠 bull
W['hiliq'] = (W['turn_pct'] >= 0.5) & (W['expand'] >= 1.05)
W['hlb'] = W['hiliq'] & W['bull']
W['yr'] = [d[:4] for d in W.index]
print("=== 年度: 平均换手率% / 平均放量 / 高流动性牛市周占比 ===")
for yr, g in W.groupby('yr'):
    print(f"  {yr}: 换手{g['turn'].mean():.2f}% 放量{g['expand'].mean():.2f} 高流动性牛市占比{g['hlb'].mean()*100:.0f}%")
print("\n=== 高流动性牛市 区间(连续周) ===")
prev = False; start = None
idx = list(W.index)
for i, d in enumerate(idx):
    h = bool(W.loc[d, 'hlb'])
    if h and not prev: start = d
    if prev and not h:
        print(f"  {start} ~ {idx[i-1]}")
    prev = h
if prev: print(f"  {start} ~ {idx[-1]}(至今)")
print("\nDONE")
