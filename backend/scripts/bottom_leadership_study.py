#!/usr/bin/env python3
"""
Phase 1: 底部主线领涨延续性研究（2026-06-13）

命门验证:大盘底部后,反弹头 REB 日相对最强的行业(主线),在随后上升段是否持续跑赢大盘?
- 底部事件 = bottom_events_reconstruct.py 跑出的 57 个底部低点日(下方硬编码,来源见该脚本)。
- 行业 = 申万一级(去嵌套白名单),等权合成成分股收益。
- 每个底 t0: 底后[t0, t0+REB]日各行业反弹收益排名 → 前3=主线 / 后3=垫底。
  测 [t0+REB, t0+REB+H] 行业相对上证超额(H=20/40/60),主线 vs 全行业均值 vs 垫底,跨事件聚合+胜率。
口径诚实: 用当前成分(有漂移/幸存者偏差,行业比概念稳);事件少(薄样本只给方向);等权行业 vs 上证。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/bl.py
"""
import math
from app import create_app

IDX = 'sh.000001'
REB = 5                 # 反弹观察窗(识别主线)
HORIZONS = [20, 40, 60]
TOPK = 3                # 取前/后 K 个行业
SW1 = {'农林牧渔', '基础化工', '钢铁', '有色金属', '电子', '家用电器', '食品饮料', '纺织服饰', '轻工制造', '医药生物',
       '公用事业', '交通运输', '房地产', '商贸零售', '社会服务', '综合', '建筑材料', '建筑装饰', '电力设备', '机械设备',
       '国防军工', '汽车', '计算机', '传媒', '通信', '银行', '非银金融', '煤炭', '石油石化', '环保', '美容护理'}
# 57 个底部低点日(来自 bottom_events_reconstruct.py)
BOTTOMS = ['2007-02-02', '2007-06-04', '2007-07-05', '2007-11-22', '2008-04-18', '2008-06-27', '2008-10-29',
           '2008-12-23', '2009-02-27', '2009-08-31', '2009-09-28', '2009-11-27', '2010-05-17', '2010-06-29',
           '2010-11-17', '2011-01-20', '2011-05-27', '2011-08-08', '2011-11-30', '2012-01-05', '2012-03-28',
           '2012-07-16', '2013-03-04', '2013-06-24', '2014-03-10', '2014-04-28', '2015-02-02', '2015-05-07',
           '2015-08-26', '2015-11-27', '2016-01-28', '2016-02-29', '2016-05-09', '2017-05-08', '2017-08-11',
           '2018-02-09', '2018-03-23', '2018-06-19', '2018-08-03', '2018-10-18', '2019-05-06', '2020-02-03',
           '2020-03-23', '2020-09-10', '2021-03-09', '2021-07-27', '2022-01-25', '2022-03-15', '2022-04-26',
           '2023-06-26', '2024-02-05', '2025-01-03', '2025-04-07', '2025-11-21', '2026-02-02', '2026-03-23',
           '2026-06-08']


def main():
    app = create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine, text, bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np
        bts = sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                              connect_args={'read_timeout': 600, 'connect_timeout': 30}))()
        all_dates = [str(r[0]) for r in bts.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        idx = {d: i for i, d in enumerate(all_dates)}
        irows = bts.execute(text("SELECT trade_date, close_price FROM stock_daily_kline "
                                 "WHERE stock_code=:c ORDER BY trade_date"), {"c": IDX}).fetchall()
        iclose = {str(d): float(p) for d, p in irows if p}
        # 行业成分(申万一级)
        rows = bts.execute(text("SELECT s.sector_name, r.stock_code FROM stock_sector s "
                                "JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='industry'")).fetchall()
        ind = {}
        for nm, code in rows:
            if nm in SW1:
                ind.setdefault(nm, []).append(code)
        ind = {k: v for k, v in ind.items() if len(v) >= 20}
        allmembers = sorted({c for v in ind.values() for c in v})
        print(f"[cfg] 申万一级 {len(ind)} 个行业, 成分合计 {len(allmembers)}; 底部事件 {len(BOTTOMS)}", flush=True)

        mset = set(allmembers)
        # 只按 trade_date IN(几日)拉(走trade_date索引,快),成分在Python侧筛;
        # 避免 stock_code IN(5588)的巨型 IN(优化器易选错索引,极慢)
        cq = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                  "WHERE trade_date IN :ds AND close_price>0"
                  ).bindparams(bindparam('ds', expanding=True))

        # 累加: 每事件每H的 top3/all/bottom3 行业相对上证超额
        acc = {h: {'top': [], 'all': [], 'bot': []} for h in HORIZONS}
        used = 0
        detail = []
        import time as _t; _t0 = _t.time()
        for _i, t0 in enumerate(BOTTOMS):
            bts.rollback()
            print(f"[prog] {_i}/{len(BOTTOMS)} used={used} {_t.time()-_t0:.0f}s", flush=True)
            if t0 not in idx:
                continue
            i0 = idx[t0]
            if i0 + REB + max(HORIZONS) >= len(all_dates):
                continue   # 远期不够
            d_reb = all_dates[i0 + REB]
            fwd_d = {h: all_dates[i0 + REB + h] for h in HORIZONS}
            need = [t0, d_reb] + list(fwd_d.values())
            rr = bts.execute(cq, {"ds": need}).fetchall()
            cm = {}
            for c, d, p in rr:
                if c in mset:
                    cm.setdefault(c, {})[str(d)] = float(p)

            def ind_ret(members, da, db):
                rs = [cm[c][db] / cm[c][da] - 1 for c in members if cm.get(c, {}).get(da) and cm.get(c, {}).get(db)]
                return float(np.mean(rs)) if len(rs) >= 5 else None

            reb = {nm: ind_ret(ms, t0, d_reb) for nm, ms in ind.items()}
            reb = {k: v for k, v in reb.items() if v is not None}
            if len(reb) < 10:
                continue
            ranked = sorted(reb, key=lambda k: -reb[k])
            top, bot = ranked[:TOPK], ranked[-TOPK:]
            used += 1
            row = {'t0': t0}
            for h in HORIZONS:
                de = fwd_d[h]
                if d_reb not in iclose or de not in iclose:
                    continue
                idx_fwd = iclose[de] / iclose[d_reb] - 1
                exc = {}
                for grp, names in (('top', top), ('all', list(reb.keys())), ('bot', bot)):
                    fr = [ind_ret(ind[nm], d_reb, de) for nm in names]
                    fr = [x for x in fr if x is not None]
                    if fr:
                        e = float(np.mean(fr)) - idx_fwd
                        acc[h][grp].append(e); exc[grp] = e
                if 'top' in exc:
                    row[h] = exc['top']
            detail.append(row)

        def stat(v):
            v = [x for x in v if x is not None and not math.isnan(x)]
            if len(v) < 3:
                return (len(v), float('nan'), float('nan'), float('nan'))
            a = np.array(v)
            t = (a.mean() / a.std(ddof=1) * math.sqrt(len(a))) if a.std(ddof=1) > 0 else float('nan')
            return (len(a), a.mean() * 100, (a > 0).mean() * 100, t)

        print(f"\n{'='*78}\nPhase 1 底部主线领涨延续性  有效事件 {used}\n{'='*78}")
        print("主线=底后5日反弹最强前3行业;超额=该组行业 vs 上证(底后5日起算,单位%)")
        print(f"{'组别':<10}{'H':>4} {'N':>4} {'平均超额%':>10} {'胜率%':>7} {'t':>6}")
        for grp, lbl in (('top', '主线前3'), ('all', '全行业均值'), ('bot', '垫底3')):
            for h in HORIZONS:
                n, m, w, t = stat(acc[h][grp])
                print(f"{lbl:<10}{h:>4} {n:>4} {m:>10.2f} {w:>7.1f} {t:>6.2f}")
        print("\n判读: 若'主线前3'超额显著>0 且 > 全行业均值 → 底部领涨可延续(选主线加价值);")
        print("      若 ≈ 全行业均值或不显著 → 主线只是噪声,这套思路的②不成立。")
        print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
