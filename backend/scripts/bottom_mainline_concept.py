#!/usr/bin/env python3
"""
底部后主线(概念层)持续性 + 主题连贯性量化（2026-06-14，v2）

每个近年底部 t0:反弹前 REB 日领涨概念 Top-K → 其后 20/40/60 日相对沪深300 超额。
新增**主题连贯性**:Top-K 概念间成分重叠(平均两两 Jaccard)+ 共享核心股数(出现在≥3个概念)。
检验假设:连贯度高(一簇相关概念同涨=真主线)→ 延续好;散乱→噪声退潮。
⚠️ 概念成分当前快照→轻度前视;样本数个底部=案例非统计。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/bmc.py
"""
from itertools import combinations
from app import create_app

REB = 10
HS = [20, 40, 60]
IDXC = 'sh.000300'
MINN = 20
TOPK = 5
BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
         '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
         '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
         '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格', '超跌']
BOTTOMS = ['2023-06-26', '2024-02-05', '2025-01-02', '2025-04-07', '2025-11-21', '2026-02-02']


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np
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

        def coherence(top_names):
            sets = [concept[n] for n in top_names]
            js = [len(a & b) / len(a | b) for a, b in combinations(sets, 2)]
            from collections import Counter
            cnt = Counter()
            for s in sets:
                for c in s:
                    cnt[c] += 1
            core = sum(1 for c, k in cnt.items() if k >= 3)   # 出现在≥3个概念的股
            return (float(np.mean(js)) if js else 0.0), core

        results = []
        for t0 in BOTTOMS:
            if t0 not in pos:
                continue
            i0 = pos[t0]
            if i0 + REB + max(HS) >= len(dates):
                print(f"\n■ 底 {t0}: 远期不足,跳过"); continue
            d_reb = dates[i0 + REB]; fwd = {h: dates[i0 + REB + h] for h in HS}
            cm = {}
            for c, d, p in bts.execute(q, {"ds": [t0, d_reb] + list(fwd.values())}).fetchall():
                cm.setdefault(c, {})[str(d)] = float(p)

            def ret(code, da, dbb):
                a, b = cm.get(code, {}).get(da), cm.get(code, {}).get(dbb)
                return (b / a - 1) if (a and b) else None

            def cret(mems, da, dbb):
                xs = [x for x in (ret(c, da, dbb) for c in mems) if x is not None]
                return float(np.mean(xs)) if len(xs) >= MINN * 0.5 else None
            reb = sorted([(nm, cret(m, t0, d_reb)) for nm, m in concept.items()],
                         key=lambda x: -(x[1] if x[1] is not None else -9))
            top = [(nm, r) for nm, r in reb if r is not None][:TOPK]
            jac, core = coherence([nm for nm, _ in top])
            exc = {}
            for h in HS:
                grp = [cret(concept[nm], d_reb, fwd[h]) for nm, _ in top]
                grp = [x for x in grp if x is not None]
                idxf = ret(IDXC, d_reb, fwd[h])
                if grp and idxf is not None:
                    exc[h] = float(np.mean(grp)) - idxf
            results.append((t0, top, jac, core, exc))
            print(f"\n■ 底 {t0}  连贯度 Jaccard={jac:.2f} 共享核心股={core}")
            print("   领涨Top5: " + " / ".join(f"{nm}({r*100:+.0f}%)" for nm, r in top))
            print("   后续超额: " + "  ".join(f"{h}日{exc.get(h,0)*100:+.0f}%" for h in HS))

        print(f"\n{'='*72}\n连贯度 vs 延续性(按 Jaccard 高/低分组,中位切)")
        jacs = sorted(r[2] for r in results)
        med = jacs[len(jacs) // 2] if jacs else 0
        for grp_name, cond in [("高连贯(Jaccard≥中位)", lambda j: j >= med), ("低连贯", lambda j: j < med)]:
            sub = [r for r in results if cond(r[2])]
            print(f"\n  【{grp_name}】 n={len(sub)}  底:{[r[0] for r in sub]}")
            for h in HS:
                v = [r[4].get(h) for r in sub if h in r[4]]
                v = [x for x in v if x is not None]
                if v:
                    print(f"    {h}日 超额均值 {np.mean(v)*100:+.0f}%  胜率 {(np.array(v)>0).mean()*100:.0f}%")
        print("\n⚠️ 成分前视 + n=6 案例;连贯度是必要非充分(见2024-02:AI连贯但闪反弹退潮)。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
