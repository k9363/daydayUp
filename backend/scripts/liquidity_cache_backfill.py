import warnings, time; warnings.filterwarnings("ignore")
from tradingagents.dataflows.topbottom_dashboard import _api, _mongo
from datetime import datetime, timedelta
api = _api(); db = _mongo()
COLL = 'liquidity_daily'
db[COLL].create_index('date', unique=True)
# 回填近 ~2.6 年 周度换手率(够算2年分位)
ix = api.index_daily(ts_code='000001.SH', start_date='20231001', end_date='20260613').sort_values('trade_date')
days = ix['trade_date'].astype(str).tolist()[::5]   # 周度
have = set(d['date'] for d in db[COLL].find({}, {'date': 1}))
todo = [d for d in days if d not in have]
print(f"[cfg] 需回填 {len(todo)}/{len(days)} 周点", flush=True)
n = 0; t0 = time.time()
for k, d in enumerate(todo):
    if k % 40 == 0: print(f"[prog] {k}/{len(todo)} {time.time()-t0:.0f}s", flush=True)
    for at in range(3):
        try:
            dl = api.daily(trade_date=d, fields='ts_code,amount'); dbb = api.daily_basic(trade_date=d, fields='ts_code,total_mv')
            if dl is not None and not dl.empty and dbb is not None and not dbb.empty:
                amt = float(dl['amount'].astype(float).sum()); mv = float(dbb['total_mv'].astype(float).sum())
                turn = amt/(mv*10)*100
                db[COLL].update_one({'date': d}, {'$set': {'date': d, 'turn': turn, 'amt': amt, 'mv': mv}}, upsert=True)
                n += 1
            break
        except Exception as e:
            if 'minute' in str(e) or '频率' in str(e): time.sleep(8); continue
            break
    time.sleep(0.12)
print(f"[done] 回填 {n} 点, 缓存共 {db[COLL].count_documents({})} 点", flush=True)
print("DONE", flush=True)
