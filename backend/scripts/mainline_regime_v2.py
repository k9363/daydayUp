#!/usr/bin/env python3
"""主线持续性 × 升级版流动性regime(2026-06-14 v2)—— 读 TA-CN 生成的 /tmp/regime.json
regime = 高流动性牛市(市场换手率2年分位≥0.5 + 上证成交额放量≥1.05 + 上证>MA60),20年口径。
合格主线(持续跑赢60d+20d超额≥5% + 资金聚集份额↑20%)后续超额,按 regime 切。"""
import json
from app import create_app
START='2023-01-01'; STEP=8; LONG,SHORT=60,20; FWDS=[20,60]; IDXC='sh.000300'
MINN=20; EXC_MIN=0.05; FLOW_MIN=1.20
BLOCK=['新高','新低','百元股','低价股','趋势股','题材股','热股','炸板','连板','昨日','涨停','次新','破净','送转','大盘成长','大盘价值','中盘','小盘','微盘','机构重仓','基金重仓','预盈','预增','业绩','MSCI','富时','标普','沪股通','深股通','融资融券','转融','QFII','茅指数','宁组合','核心资产','同花顺','东方财富','股权转让','举牌','重组','摘帽','风格','超跌']
def main():
    regime = json.load(open('/tmp/regime.json'))
    app=create_app("development")
    with app.app_context():
        from sqlalchemy import create_engine,text,bindparam
        from sqlalchemy.orm import sessionmaker
        import numpy as np
        bts=sessionmaker(bind=create_engine(app.config['SQLALCHEMY_DATABASE_URI'],connect_args={'read_timeout':1200}))()
        dates=[str(r[0]) for r in bts.execute(text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date ASC")).fetchall()]
        dpos={d:i for i,d in enumerate(dates)}
        rows=bts.execute(text("SELECT s.sector_name,r.stock_code FROM stock_sector s JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='concept'")).fetchall()
        concept={}
        for nm,code in rows:
            if not any(b in nm for b in BLOCK): concept.setdefault(nm,set()).add(code)
        concept={k:v for k,v in concept.items() if len(v)>=MINN}
        q=text("SELECT stock_code,trade_date,close_price,turnover FROM stock_daily_kline WHERE trade_date IN :ds").bindparams(bindparam('ds',expanding=True))
        maxf=max(FWDS)
        sample=[dates[i] for i in range(len(dates)) if dates[i]>=START and i-LONG>=0 and i+maxf<len(dates)][::STEP]
        QF={h:{'hlb':[],'other':[]} for h in FWDS}; BASE={h:{'hlb':[],'other':[]} for h in FWDS}; nhlb=0
        for D in sample:
            bts.rollback()
            tag='hlb' if regime.get(D.replace('-',''),0)==1 else 'other'
            if tag=='hlb': nhlb+=1
            i=dpos[D]; dL,dS=dates[i-LONG],dates[i-SHORT]; fwd={h:dates[i+h] for h in FWDS}
            cm,tv,mkt={},{},{}
            for c,d,p,t in bts.execute(q,{"ds":[dL,dS,D]+list(fwd.values())}).fetchall():
                ds=str(d)
                if p: cm.setdefault(c,{})[ds]=float(p)
                if t: tv.setdefault(c,{})[ds]=float(t); mkt[ds]=mkt.get(ds,0.0)+float(t)
            def ret(c,a,b):
                x,y=cm.get(c,{}).get(a),cm.get(c,{}).get(b); return (y/x-1) if (x and y) else None
            def cret(m,a,b):
                xs=[v for v in (ret(c,a,b) for c in m) if v is not None]; return float(np.mean(xs)) if len(xs)>=MINN*0.5 else None
            def share(m,dd):
                s=sum(tv.get(c,{}).get(dd,0.0) for c in m); return s/mkt[dd] if mkt.get(dd) else None
            i60,i20=ret(IDXC,dL,D),ret(IDXC,dS,D); idxf={h:ret(IDXC,D,fwd[h]) for h in FWDS}
            if i60 is None or i20 is None: continue
            for nm,m in concept.items():
                r60,r20,shn,sho=cret(m,dL,D),cret(m,dS,D),share(m,D),share(m,dL)
                if None in (r60,r20,shn) or not sho: continue
                for h in FWDS:
                    f=cret(m,D,fwd[h])
                    if f is not None and idxf[h] is not None: BASE[h][tag].append(f-idxf[h])
                if r60-i60>=EXC_MIN and r20-i20>=EXC_MIN and shn/sho>=FLOW_MIN:
                    for h in FWDS:
                        f=cret(m,D,fwd[h])
                        if f is not None and idxf[h] is not None: QF[h][tag].append(f-idxf[h])
        def st(v):
            a=np.array(v); return (len(a),a.mean()*100,(a>0).mean()*100) if len(a) else (0,float('nan'),float('nan'))
        print(f"\n{'='*72}\n合格主线后续超额 × 升级流动性regime  (高流动性牛市点 {nhlb}/{len(sample)})")
        for h in FWDS:
            print(f"\n  FWD={h}日:")
            for tag,lbl in [('hlb','🐂高流动性牛市'),('other','其余')]:
                nq,mq,wq=st(QF[h][tag]); nb,mb,wb=st(BASE[h][tag])
                print(f"    {lbl}: 合格主线 {mq:+.1f}%/胜{wq:.0f}%(n={nq}) | 基线 {mb:+.1f}%/{wb:.0f}% | 主线−基线 {mq-mb:+.1f}pp")
        print("\nDONE",flush=True)
if __name__=="__main__": main()
