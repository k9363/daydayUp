#!/usr/bin/env python3
"""
主线扫描器 v2（2026-06-14）—— 框架读数: 仓位档 + 当前活跃主线 + 主线领涨股

清洗: 剔除"自循环/风格/指数/资金"类非题材概念(新高/百元股/趋势股/热股/炸板/MSCI/沪股通…)。
框架: 顶部输出当前仓位档(上证 MA60/MA120 趋势,镜像 TA-CN position_ladder);
      主线榜按近1年超额排序、标"活跃(近60日仍强)/熄火";每条主线列领涨股。
⚠️ 概念成分为当前快照,回看过去板块收益偏高(前视),作主线复盘+当下方向用,非可交易回测。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/ms.py [lookback]
"""
import sys
from app import create_app

L = int(sys.argv[1]) if len(sys.argv) > 1 else 250
L2 = 60
IDXC = 'sh.000300'
SH = 'sh.000001'
MINN = 20
TOPSEC = 15
TOPSTK = 6
# 非题材概念黑名单(子串匹配): 价格/动量/风格/指数/资金 类,不是可操作主线
BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
         '次新', '破净', '高送转', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓',
         '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
         '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽']


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
        d_now, d_L, d_60 = dates[-1], dates[-1 - L], dates[-1 - L2]

        # 仓位档(上证趋势,镜像 TA-CN position_ladder)
        shc = {str(r[0]): float(r[1]) for r in bts.execute(text(
            "SELECT trade_date, close_price FROM stock_daily_kline WHERE stock_code=:c AND close_price>0 "
            "ORDER BY trade_date DESC LIMIT 130"), {"c": SH}).fetchall()}
        shd = sorted(shc); c = [shc[d] for d in shd]
        ma60 = np.mean(c[-60:]); ma120 = np.mean(c[-120:]); cl = c[-1]
        if cl >= ma60:
            pos = "上升趋势 → 满仓(顶背离时减半)"
        elif cl >= ma120:
            pos = "下降·守MA120 → 轻仓 0.3"
        else:
            pos = "破位(跌破MA120) → 空仓 0"

        rows = bts.execute(text("SELECT s.sector_name, r.stock_code FROM stock_sector s "
                                "JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='concept'")).fetchall()
        concept = {}
        for nm, code in rows:
            if any(b in nm for b in BLOCK):
                continue
            concept.setdefault(nm, []).append(code)
        concept = {k: v for k, v in concept.items() if len(v) >= MINN}
        allmem = sorted({c2 for v in concept.values() for c2 in v})
        names = {r[0]: r[1] for r in bts.execute(text("SELECT stock_code, stock_name FROM stock_basic")).fetchall()}
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE trade_date IN :ds AND close_price>0").bindparams(bindparam('ds', expanding=True))
        cm = {}
        for code, d, p in bts.execute(q, {"ds": [d_L, d_60, d_now]}).fetchall():
            cm.setdefault(code, {})[str(d)] = float(p)

        def ret(code, da, db):
            a, b = cm.get(code, {}).get(da), cm.get(code, {}).get(db)
            return (b / a - 1) if (a and b) else None
        idx_L, idx_60 = ret(IDXC, d_L, d_now), ret(IDXC, d_60, d_now)

        recs = []
        for nm, mems in concept.items():
            rL = [x for x in (ret(c2, d_L, d_now) for c2 in mems) if x is not None]
            r60 = [x for x in (ret(c2, d_60, d_now) for c2 in mems) if x is not None]
            if len(rL) < MINN * 0.5:
                continue
            recs.append((nm, len(mems), float(np.mean(rL)), float(np.mean(r60)) if r60 else 0.0))
        recs.sort(key=lambda x: -x[2])

        print(f"\n{'='*90}")
        print(f"【框架读数】 {d_now}")
        print(f"  当前仓位档: {pos}  (上证{cl:.0f} / MA60 {ma60:.0f} / MA120 {ma120:.0f})")
        print(f"  基准沪深300: 近{L}日{idx_L*100:+.0f}% / 近{L2}日{idx_60*100:+.0f}%")
        print(f"{'='*90}")
        print(f"【主线榜】近{L}日超额排序(已剔自循环/风格类)  活跃=近60日仍跑赢")
        print(f"{'主线':<14}{'成分':>5}{'近1年%':>8}{'超额%':>7}{'近60日%':>8}{'状态':>8}")
        for nm, n, rL, r60 in recs[:TOPSEC]:
            active = '🔥活跃' if (r60 - idx_60) > 0.05 else ('熄火' if r60 < idx_60 else '走平')
            print(f"{nm:<14}{n:>5}{rL*100:>8.0f}{(rL-idx_L)*100:>7.0f}{r60*100:>8.0f}{active:>8}")

        print(f"\n{'─'*90}\n【主线领涨股】Top 主线的领涨个股(近{L}日):\n{'─'*90}")
        for nm, n, rL, r60 in recs[:8]:
            stk = sorted([(c2, ret(c2, d_L, d_now)) for c2 in concept[nm]
                          if ret(c2, d_L, d_now) is not None], key=lambda x: -x[1])[:TOPSTK]
            print(f"■ {nm}({rL*100:+.0f}%): " + "  ".join(f"{names.get(c2,c2)}{r*100:+.0f}%" for c2, r in stk))
        print("\n⚠️ 当前成分回看=板块历史收益偏高(前视);此为主线复盘+当下方向,非可交易回测。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
