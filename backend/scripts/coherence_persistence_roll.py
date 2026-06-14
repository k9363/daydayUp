#!/usr/bin/env python3
"""
主题连贯性 → 延续性 月度滚动验证（2026-06-14）—— 把 n=6 案例扩成统计样本

一般化假设(不限底部):任意时点取近 LB 日领涨 Top-K 概念,算连贯度(成分重叠 Jaccard),
看其后 FWD 日是否相对沪深300 跑赢。在成分大致有效期(默认 2023+)每 STEP 交易日滚一次。
检验:连贯度高(一簇相关概念同涨)→ 后续延续更好? 看 高/低连贯分组 + Spearman 相关。
⚠️ 概念成分当前快照→前视(越往前越重);重叠窗口→t偏乐观。结论限近年、谨慎。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/cpr.py [start] [step]
"""
import sys
from itertools import combinations
from app import create_app

START = sys.argv[1] if len(sys.argv) > 1 else '2023-01-01'
STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 10
LB = 20          # 近20日定"领涨"
FWDS = [20, 40]
IDXC = 'sh.000300'
MINN = 20
TOPK = 5
BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
         '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
         '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
         '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格', '超跌']


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np, pandas as pd
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 600})) ()
        dates = [str(r[0]) for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        pos = {d: i for i, d in enumerate(dates)}
        rows = bts.execute(text("SELECT s.sector_name, r.stock_code FROM stock_sector s "
                                "JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='concept'")).fetchall()
        concept = {}
        for nm, code in rows:
            if not any(b in nm for b in BLOCK):
                concept.setdefault(nm, set()).add(code)
        concept = {k: v for k, v in concept.items() if len(v) >= MINN}
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE trade_date IN :ds AND close_price>0").bindparams(bindparam('ds', expanding=True))

        maxf = max(FWDS)
        idxs = [i for i, d in enumerate(dates) if d >= START and i - LB >= 0 and i + maxf < len(dates)]
        sample_idx = idxs[::STEP]
        print(f"[cfg] start={START} step={STEP} 概念{len(concept)} 滚动点{len(sample_idx)} LB={LB} FWD={FWDS}", flush=True)

        recs = []  # (date, jaccard, {fwd: excess})
        import time as _t; t0 = _t.time()
        for k, i in enumerate(sample_idx):
            bts.rollback()
            if k % 20 == 0:
                print(f"[prog] {k}/{len(sample_idx)} {_t.time()-t0:.0f}s", flush=True)
            D = dates[i]; d_lb = dates[i - LB]
            fwd_d = {h: dates[i + h] for h in FWDS}
            cm = {}
            for c, d, p in bts.execute(q, {"ds": [d_lb, D] + list(fwd_d.values())}).fetchall():
                cm.setdefault(c, {})[str(d)] = float(p)

            def ret(code, da, dbb):
                a, b = cm.get(code, {}).get(da), cm.get(code, {}).get(dbb)
                return (b / a - 1) if (a and b) else None

            def cret(mems, da, dbb):
                xs = [x for x in (ret(c, da, dbb) for c in mems) if x is not None]
                return float(np.mean(xs)) if len(xs) >= MINN * 0.5 else None
            reb = sorted([(nm, cret(m, d_lb, D)) for nm, m in concept.items()],
                         key=lambda x: -(x[1] if x[1] is not None else -9))
            top = [nm for nm, r in reb if r is not None][:TOPK]
            if len(top) < TOPK:
                continue
            js = [len(concept[a] & concept[b]) / len(concept[a] | concept[b]) for a, b in combinations(top, 2)]
            jac = float(np.mean(js)) if js else 0.0
            exc = {}
            for h in FWDS:
                grp = [cret(concept[nm], D, fwd_d[h]) for nm in top]
                grp = [x for x in grp if x is not None]
                idxf = ret(IDXC, D, fwd_d[h])
                if grp and idxf is not None:
                    exc[h] = float(np.mean(grp)) - idxf
            if exc:
                recs.append((D, jac, exc))

        print(f"\n{'='*72}\n连贯度→延续性  滚动样本 n={len(recs)} ({START}起)")
        for h in FWDS:
            v = [(r[1], r[2][h]) for r in recs if h in r[2]]
            jacv = np.array([x[0] for x in v]); exv = np.array([x[1] for x in v])
            # Spearman(连贯度, 后续超额)
            sp = pd.Series(jacv).rank().corr(pd.Series(exv).rank())
            med = np.median(jacv)
            hi = exv[jacv >= med]; lo = exv[jacv < med]
            print(f"\n  FWD={h}日 (n={len(v)}):")
            print(f"    Spearman(连贯度, 后续超额) = {sp:+.2f}")
            print(f"    高连贯组(Jaccard≥{med:.3f}) 后续超额 均值{hi.mean()*100:+.1f}% 胜率{(hi>0).mean()*100:.0f}% (n={len(hi)})")
            print(f"    低连贯组             后续超额 均值{lo.mean()*100:+.1f}% 胜率{(lo>0).mean()*100:.0f}% (n={len(lo)})")
            print(f"    高−低 差 = {(hi.mean()-lo.mean())*100:+.1f}pp")
        print("\n⚠️ 成分前视(越早越重)+窗口重叠→t偏乐观;结论限 2023+ 谨慎。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
