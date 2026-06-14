#!/usr/bin/env python3
"""
真·主线持续性验证（2026-06-14）—— 按"持续跑赢+资金聚集"定义主线,非随机短期涨幅

修正前一版的定义错误(随机时点取近20日top=噪声)。主线 = 一段时间持续明显跑赢大盘 + 资金聚集:
  ① 持续跑赢: 近60日 且 近20日 都跑赢沪深300(双窗口确认,排除一日游)
  ② 还在领涨: 近20日超额 > 阈值(仍强,非已熄火)
  ③ 资金聚集: 板块成交额占全市场份额上升(share_now / share_60d > 阈值,增量资金流入)
满足三条 = 合格主线。测其后 FWD 日相对沪深300 超额(是否延续),并和"全概念均值""仅20日top(旧错误定义)"对比。
在 2023+ 每 STEP 交易日滚动。⚠️ 概念成分当前快照→前视;窗口重叠→t偏乐观。

用法: docker exec -w /app -e PYTHONPATH=/app daydayup-backend python /tmp/mpp.py [start] [step]
"""
import sys
from app import create_app

START = sys.argv[1] if len(sys.argv) > 1 else '2023-01-01'
STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 10
LONG, SHORT = 60, 20
FWDS = [20, 60, 120]
IDXC = 'sh.000300'
MINN = 20
EXC_MIN = 0.05      # 超额门槛(跑赢沪深300 ≥5%)
FLOW_MIN = 1.20     # 资金聚集: 份额上升 ≥20%
BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
         '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
         '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
         '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格', '超跌']


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
        rows = bts.execute(text("SELECT s.sector_name, r.stock_code FROM stock_sector s "
                                "JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='concept'")).fetchall()
        concept = {}
        for nm, code in rows:
            if not any(b in nm for b in BLOCK):
                concept.setdefault(nm, set()).add(code)
        concept = {k: v for k, v in concept.items() if len(v) >= MINN}
        q = text("SELECT stock_code, trade_date, close_price, turnover FROM stock_daily_kline "
                 "WHERE trade_date IN :ds").bindparams(bindparam('ds', expanding=True))

        maxf = max(FWDS)
        idxs = [i for i in range(len(dates)) if dates[i] >= START and i - LONG >= 0 and i + maxf < len(dates)]
        sample = idxs[::STEP]
        print(f"[cfg] start={START} step={STEP} 概念{len(concept)} 滚动{len(sample)} 主线门槛:超额≥{EXC_MIN*100:.0f}% 资金聚集≥{FLOW_MIN}", flush=True)

        qual_fwd = {h: [] for h in FWDS}     # 合格主线 后续超额
        all_fwd = {h: [] for h in FWDS}      # 全概念 后续超额(基线)
        top_fwd = {h: [] for h in FWDS}      # 仅20日top5(旧错误定义) 后续超额
        nqual = []
        import time as _t; t0 = _t.time()
        for k, i in enumerate(sample):
            bts.rollback()
            if k % 20 == 0:
                print(f"[prog] {k}/{len(sample)} {_t.time()-t0:.0f}s", flush=True)
            D, dL, dS = dates[i], dates[i - LONG], dates[i - SHORT]
            fwd = {h: dates[i + h] for h in FWDS}
            cm, tv = {}, {}
            mkt = {}   # date -> market total turnover
            for c, d, p, t in bts.execute(q, {"ds": [dL, dS, D] + list(fwd.values())}).fetchall():
                ds = str(d)
                if p:
                    cm.setdefault(c, {})[ds] = float(p)
                if t:
                    tv.setdefault(c, {})[ds] = float(t)
                    mkt[ds] = mkt.get(ds, 0.0) + float(t)

            def ret(code, da, dbb):
                a, b = cm.get(code, {}).get(da), cm.get(code, {}).get(dbb)
                return (b / a - 1) if (a and b) else None

            def cret(mems, da, dbb):
                xs = [x for x in (ret(c, da, dbb) for c in mems) if x is not None]
                return float(np.mean(xs)) if len(xs) >= MINN * 0.5 else None

            def share(mems, d):
                s = sum(tv.get(c, {}).get(d, 0.0) for c in mems)
                return s / mkt[d] if mkt.get(d) else None
            i60 = ret(IDXC, dL, D); i20 = ret(IDXC, dS, D)
            idxf = {h: ret(IDXC, D, fwd[h]) for h in FWDS}
            if i60 is None or i20 is None:
                continue
            qual = []
            for nm, mems in concept.items():
                r60, r20 = cret(mems, dL, D), cret(mems, dS, D)
                sh_now, sh_old = share(mems, D), share(mems, dL)
                if r60 is None or r20 is None or sh_now is None or not sh_old:
                    continue
                exc60, exc20 = r60 - i60, r20 - i20
                flow = sh_now / sh_old
                # 全概念基线 fwd
                for h in FWDS:
                    f = cret(mems, D, fwd[h])
                    if f is not None and idxf[h] is not None:
                        all_fwd[h].append(f - idxf[h])
                # 合格主线
                if exc60 >= EXC_MIN and exc20 >= EXC_MIN and flow >= FLOW_MIN:
                    qual.append((nm, exc60, flow))
                    for h in FWDS:
                        f = cret(mems, D, fwd[h])
                        if f is not None and idxf[h] is not None:
                            qual_fwd[h].append(f - idxf[h])
            nqual.append(len(qual))
            # 旧错误定义: 仅按近20日涨幅 top5
            reb = sorted([(nm, cret(m, dS, D)) for nm, m in concept.items()],
                         key=lambda x: -(x[1] if x[1] is not None else -9))[:5]
            for h in FWDS:
                for nm, _ in reb:
                    f = cret(concept[nm], D, fwd[h])
                    if f is not None and idxf[h] is not None:
                        top_fwd[h].append(f - idxf[h])

        def stat(v):
            a = np.array(v)
            return (len(a), a.mean() * 100, (a > 0).mean() * 100) if len(a) else (0, float('nan'), float('nan'))

        print(f"\n{'='*72}\n真·主线(持续跑赢+资金聚集)持续性  滚动{len(sample)}点, 平均每点合格主线 {np.mean(nqual):.1f} 个")
        for h in FWDS:
            nq, mq, wq = stat(qual_fwd[h])
            na, ma, wa = stat(all_fwd[h])
            nt, mt, wt = stat(top_fwd[h])
            print(f"\n  FWD={h}日 后续相对沪深300超额:")
            print(f"    ✅合格主线   均值{mq:+.1f}% 胜率{wq:.0f}% (n={nq})")
            print(f"    全概念基线   均值{ma:+.1f}% 胜率{wa:.0f}% (n={na})")
            print(f"    仅20日top(旧) 均值{mt:+.1f}% 胜率{wt:.0f}% (n={nt})")
        print("\n⚠️ 成分前视(份额/收益均受)+窗口重叠;结论限2023+谨慎。")
        print("DONE", flush=True)


if __name__ == "__main__":
    main()
