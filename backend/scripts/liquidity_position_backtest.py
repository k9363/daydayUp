import warnings, time, math; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from tradingagents.dataflows.topbottom_dashboard import _api
api = _api()
def idx(code):
    df = api.index_daily(ts_code=code, start_date='20080101', end_date='20260613').sort_values('trade_date')
    return pd.Series(df['close'].astype(float).values, index=df['trade_date'].astype(str)), \
           pd.Series(df['amount'].astype(float).values, index=df['trade_date'].astype(str))
shc, sha = idx('000001.SH')
days = list(shc.index)
ma60 = shc.rolling(60).mean(); ma120 = shc.rolling(120).mean()
expand = sha.rolling(20).mean()/sha.rolling(120).mean()
# 周度换手率
samp = days[::5]; turn = {}; t0 = time.time()
for k, d in enumerate(samp):
    if k % 80 == 0: print(f"[prog] {k}/{len(samp)} {time.time()-t0:.0f}s", flush=True)
    for at in range(3):
        try:
            dl = api.daily(trade_date=d, fields='ts_code,amount'); db = api.daily_basic(trade_date=d, fields='ts_code,total_mv')
            if dl is not None and not dl.empty and db is not None and not db.empty:
                turn[d] = float(dl['amount'].astype(float).sum())/(float(db['total_mv'].astype(float).sum())*10)*100
            break
        except Exception as e:
            if 'minute' in str(e) or '频率' in str(e): time.sleep(8); continue
            break
    time.sleep(0.12)
ts = pd.Series(turn).sort_index(); tp = ts.rolling(104, min_periods=40).apply(lambda x:(x<=x.iloc[-1]).mean(), raw=False)
sd = list(ts.index)
import bisect
def turn_pct(d):
    j = bisect.bisect_right(sd, d)-1
    return tp.iloc[j] if j >= 0 else np.nan
print("[pull done] 回测...", flush=True)
def metrics(rets, ppy=242):
    r = np.array(rets); nav = np.cumprod(1+r)
    ann = nav[-1]**(ppy/len(r))-1; vol = r.std()*math.sqrt(ppy)
    sh = (r.mean()*ppy)/vol if vol>0 else float('nan')
    mdd = float((nav/np.maximum.accumulate(nav)-1).min())
    return ann*100, sh, mdd*100, (ann/abs(mdd) if mdd<0 else float('nan')), nav[-1]-1
COST = 0.0005
for bname, bcode in [('中证1000','000852.SH'),('上证','000001.SH'),('中证500','000905.SH')]:
    bc, _ = idx(bcode); bd = [d for d in days if d in bc.index and d>=bc.index[0]]
    def runpos(scheme):
        pr, ex = [], []
        for i in range(1, len(bd)):
            d0, d1 = bd[i-1], bd[i]
            if d0 not in shc.index: continue
            br = bc[d1]/bc[d0]-1
            def P(d):
                c, m60, m120 = shc.get(d), ma60.get(d), ma120.get(d)
                if c is None or pd.isna(m60): return 1.0
                if scheme=='full': return 1.0
                bull = c>=m60
                if scheme=='ma60':
                    return 1.0 if bull else (0.3 if (not pd.isna(m120) and c>=m120) else 0.0)
                if scheme=='liq':
                    hl = (turn_pct(d)>=0.5) and (expand.get(d,0)>=1.05) if not pd.isna(turn_pct(d)) else False
                    if bull: return 1.0 if hl else 0.5
                    return 0.3 if (not pd.isna(m120) and c>=m120) else 0.0
                return 1.0
            e0, e1 = P(d0), P(d1)
            pr.append(e0*br - COST*abs(e1-e0)); ex.append(e0)
        return metrics(pr), np.mean(ex)*100
    print(f"\n=== {bname} (2008-2026) ===")
    print(f"{'方案':<10}{'年化%':>7}{'Sharpe':>8}{'回撤%':>7}{'Calmar':>8}{'总收益%':>9}{'平均仓%':>8}")
    for sc, lbl in [('full','满仓'),('ma60','MA60阶梯'),('liq','流动性阶梯')]:
        (ann, sh, mdd, cal, tot), avg = runpos(sc)
        print(f"{lbl:<10}{ann:>7.1f}{sh:>8.2f}{mdd:>7.0f}{cal:>8.2f}{tot*100:>9.0f}{avg:>8.0f}")
print("\nDONE", flush=True)
