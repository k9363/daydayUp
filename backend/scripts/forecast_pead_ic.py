#!/usr/bin/env python3
"""
业绩预告 surprise / PEAD 因子 IC 测试（2026-06-14）—— 业绩拐点能否事前捕捉(CPO类驱动)

数据: TA-CN tushare forecast(业绩预告 净利同比变动幅度) 2023-2025 → /tmp/forecasts.json。
因子: 预告净利同比变动中值 pchg=(pmin+pmax)/2(预增幅度)。事件=预告公告日 ann。
检验: 公告后 T+1 入场,持有 20/60 交易日,相对沪深300超额;Spearman(pchg,超额)+ 分组。
      并核对: 光模块/CPO 龙头(中际旭创/新易盛/源杰...)当年是否大幅预增且后续正超额(因子能否早flag)。
口径: T+1 可实现;预告同期取最早 ann 去重。⚠ 仅2023+;预告滞后真实。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/fpic.py
"""
import json
from app import create_app

FWDS = [20, 60]
IDXC = 'sh.000300'
NAMED = {'sz.300308': '中际旭创', 'sz.300502': '新易盛', 'sh.688498': '源杰科技',
         'sz.002463': '沪电股份', 'sz.300394': '天孚通信', 'sh.688516': '奥特维'}


def to_ddu(ts):
    num, suf = ts.split('.')
    return {'SZ': 'sz', 'SH': 'sh', 'BJ': 'bj'}.get(suf, suf.lower()) + '.' + num


def main():
    fc = json.load(open('/tmp/forecasts.json'))
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np, pandas as pd
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 1200})) ()
        dates = [str(r[0]) for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        dpos = {d: i for i, d in enumerate(dates)}

        # 去重:每 (ts,end) 取最早 ann;因子=pchg中值(需 pmin/pmax 数值)
        best = {}
        for o in fc:
            pmin, pmax = o.get('pmin'), o.get('pmax')
            if pmin is None or pmax is None:
                continue
            ann = o['ann']
            # ann(YYYYMMDD) → 'YYYY-MM-DD'
            annd = f"{ann[:4]}-{ann[4:6]}-{ann[6:8]}"
            k = (o['ts'], o['end'])
            if k not in best or annd < best[k][0]:
                best[k] = (annd, (float(pmin) + float(pmax)) / 2, o['ts'])
        events = []  # (ddu_code, ann_date, pchg)
        for (ts, end), (annd, pchg, _) in best.items():
            events.append((to_ddu(ts), annd, pchg))
        print(f"[cfg] 预告事件(去重){len(events)} 覆盖股票{len(set(e[0] for e in events))}", flush=True)

        # 入场=ann后第一个交易日;需要 close 的日期集合
        def next_td_idx(annd):
            # 第一个 >= annd 的交易日
            import bisect
            i = bisect.bisect_left(dates, annd)
            return i if i < len(dates) else None
        need_dates = set()
        ev2 = []
        for code, annd, pchg in events:
            i = next_td_idx(annd)
            if i is None or i + max(FWDS) >= len(dates):
                continue
            entry = dates[i]; exits = {h: dates[i + h] for h in FWDS}
            ev2.append((code, entry, exits, pchg))
            need_dates.add(entry); [need_dates.add(x) for x in exits.values()]
        codes = set(e[0] for e in ev2) | {IDXC}
        # 拉 close: 按日期集合(分块)
        nd = sorted(need_dates)
        cm = {}
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE trade_date IN :ds AND close_price>0").bindparams(bindparam('ds', expanding=True))
        for j in range(0, len(nd), 60):
            for c, d, p in bts.execute(q, {"ds": nd[j:j + 60]}).fetchall():
                if c in codes:
                    cm.setdefault(c, {})[str(d)] = float(p)

        def excess(code, entry, exitd):
            a, b = cm.get(code, {}).get(entry), cm.get(code, {}).get(exitd)
            ia, ib = cm.get(IDXC, {}).get(entry), cm.get(IDXC, {}).get(exitd)
            if a and b and ia and ib:
                return (b / a - 1) - (ib / ia - 1)
            return None

        rows = {h: [] for h in FWDS}   # (pchg, excess)
        for code, entry, exits, pchg in ev2:
            for h in FWDS:
                e = excess(code, entry, exits[h])
                if e is not None:
                    rows[h].append((pchg, e))

        print(f"\n{'='*70}\n业绩预告 surprise → PEAD  (事件n≈{len(ev2)})")
        for h in FWDS:
            v = rows[h]
            pc = np.array([x[0] for x in v]); ex = np.array([x[1] for x in v])
            sp = pd.Series(pc).rank().corr(pd.Series(ex).rank())
            # 分组: 大幅预增(>100%) / 预增(0~100) / 预减(<0)
            big = ex[pc > 100]; mid = ex[(pc > 0) & (pc <= 100)]; neg = ex[pc <= 0]
            print(f"\n  FWD={h}日 (n={len(v)}):  Spearman(预增幅度,后续超额)={sp:+.3f}")
            print(f"    大幅预增>100%: 超额均值{big.mean()*100:+.1f}% 胜率{(big>0).mean()*100:.0f}% (n={len(big)})")
            print(f"    预增 0~100%:   超额均值{mid.mean()*100:+.1f}% 胜率{(mid>0).mean()*100:.0f}% (n={len(mid)})")
            print(f"    预减 <0%:      超额均值{neg.mean()*100:+.1f}% 胜率{(neg>0).mean()*100:.0f}% (n={len(neg)})")

        print(f"\n{'─'*70}\n光模块/CPO 龙头 当年预告事件(因子能否早flag):")
        for code, entry, exits, pchg in sorted([e for e in ev2 if e[0] in NAMED], key=lambda x: x[1]):
            e60 = excess(code, entry, exits.get(60, exits[FWDS[-1]]))
            print(f"  {NAMED[code]} {entry} 预增中值{pchg:+.0f}% → 后续60日超额{(e60*100 if e60 is not None else 0):+.0f}%")
        print("\n⚠️ 仅2023+;预告净利同比为口径;成分/退市未特殊处理。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
