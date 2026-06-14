#!/usr/bin/env python3
"""
底部后主线(概念层)持续性 —— 近年底部案例（2026-06-14）

接 Phase 1,但下沉到概念层、且只用近年底部(2023-06起,概念成分大致有效):
每个底部 t0,反弹前 REB 日领涨概念 Top-K,看其后 [t0+REB, +H] 相对沪深300 超额(是否延续领涨)。
回答"框架下能否在底部后早点识别主线并骑乘"。
⚠️ 概念成分当前快照→仍有轻度前视(新近入选的票);样本仅数个底部=案例非统计。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/bmc.py
"""
from app import create_app

REB = 10
HS = [20, 40, 60]
IDXC = 'sh.000300'
MINN = 20
TOPK = 5
BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
         '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
         '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
         '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格']
# 近年底部首确认日(成分大致有效;需 +REB+max(H) 有数据)
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
                concept.setdefault(nm, []).append(code)
        concept = {k: v for k, v in concept.items() if len(v) >= MINN}
        allmem = sorted({c for v in concept.values() for c in v})
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE trade_date IN :ds AND close_price>0").bindparams(bindparam('ds', expanding=True))

        agg_exc = {h: [] for h in HS}   # 跨底部: 早期领涨概念组的后续超额
        for t0 in BOTTOMS:
            if t0 not in pos:
                continue
            i0 = pos[t0]
            if i0 + REB + max(HS) >= len(dates):
                print(f"\n■ 底 {t0}: 远期数据不足,跳过"); continue
            d_reb = dates[i0 + REB]
            fwd = {h: dates[i0 + REB + h] for h in HS}
            need = [t0, d_reb] + list(fwd.values())
            cm = {}
            for c, d, p in bts.execute(q, {"ds": need}).fetchall():
                cm.setdefault(c, {})[str(d)] = float(p)

            def ret(code, da, dbb):
                a, b = cm.get(code, {}).get(da), cm.get(code, {}).get(dbb)
                return (b / a - 1) if (a and b) else None

            def cret(mems, da, dbb):
                xs = [x for x in (ret(c, da, dbb) for c in mems) if x is not None]
                return float(np.mean(xs)) if len(xs) >= MINN * 0.5 else None
            # 反弹前REB日各概念领涨
            reb = [(nm, cret(m, t0, d_reb)) for nm, m in concept.items()]
            reb = sorted([(nm, r) for nm, r in reb if r is not None], key=lambda x: -x[1])
            top = reb[:TOPK]
            idxf = {h: ret(IDXC, d_reb, fwd[h]) for h in HS}
            print(f"\n■ 底 {t0}  反弹前{REB}日领涨概念Top{TOPK}:")
            print("   " + " / ".join(f"{nm}({r*100:+.0f}%)" for nm, r in top))
            line = "   后续超额(领涨组 vs 沪深300): "
            for h in HS:
                grp = [cret(concept[nm], d_reb, fwd[h]) for nm, _ in top]
                grp = [x for x in grp if x is not None]
                if grp and idxf[h] is not None:
                    e = float(np.mean(grp)) - idxf[h]
                    agg_exc[h].append(e)
                    line += f"{h}日{e*100:+.0f}%  "
            print(line)

        print(f"\n{'='*70}\n汇总: 各底部'早期领涨概念组'后续相对沪深300超额 均值(n={len(agg_exc[20])})")
        for h in HS:
            v = np.array(agg_exc[h])
            if len(v):
                print(f"  {h}日: 均值{v.mean()*100:+.1f}%  胜率{(v>0).mean()*100:.0f}%  (各底:{['%+.0f'%(x*100) for x in v]})")
        print("\n⚠️ 概念成分前视 + 样本仅数个底部=案例洞察,非统计结论。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
