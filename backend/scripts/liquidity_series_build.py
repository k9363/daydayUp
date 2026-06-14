import warnings, json, time; warnings.filterwarnings("ignore")
from tradingagents.dataflows.topbottom_dashboard import _api
api = _api()
ix = api.index_daily(ts_code='000001.SH', start_date='20080101', end_date='20260613').sort_values('trade_date')
days = ix['trade_date'].astype(str).tolist()
sh_close = dict(zip(ix['trade_date'].astype(str), ix['close'].astype(float)))
sh_amt = dict(zip(ix['trade_date'].astype(str), ix['amount'].astype(float)))
print(f"[cfg] 上证 {len(days)}日 {days[0]}~{days[-1]}", flush=True)
samp = days[::5]
out = []; t0 = time.time()
for k, d in enumerate(samp):
    if k % 50 == 0:
        print(f"[prog] {k}/{len(samp)} {time.time()-t0:.0f}s", flush=True)
    mkt_amt = mkt_mv = None
    for attempt in range(3):
        try:
            dl = api.daily(trade_date=d, fields='ts_code,amount')
            db = api.daily_basic(trade_date=d, fields='ts_code,total_mv')
            if dl is not None and not dl.empty:
                mkt_amt = float(dl['amount'].astype(float).sum())
            if db is not None and not db.empty:
                mkt_mv = float(db['total_mv'].astype(float).sum())
            break
        except Exception as e:
            if 'minute' in str(e) or '频率' in str(e):
                time.sleep(8); continue
            break
    out.append({'d': d, 'sh_close': sh_close.get(d), 'sh_amt': sh_amt.get(d),
                'mkt_amt_k': mkt_amt, 'mkt_mv_w': mkt_mv})
    time.sleep(0.12)
json.dump({'daily_sh': {'days': days, 'close': sh_close, 'amt': sh_amt}, 'weekly': out},
          open('/tmp/liq_series.json', 'w'))
print(f"[落库] 周度{len(out)}点 -> /tmp/liq_series.json", flush=True)
print("DONE", flush=True)
