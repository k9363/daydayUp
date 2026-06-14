"""主线扫描服务(2026-06-14)——复盘在「高流动性牛市」时调用,返回当前高景气主线榜+龙头。
口径:概念板块近1年等权收益+相对沪深300超额排序(剔自循环/风格黑名单),标活跃(近60日仍跑赢),每主线列领涨股。
⚠️ 概念成分为当前快照→有前视;作主线方向参考,非可交易回测。详见 docs/SYSTEM.md 十五章。"""
import logging
logger = logging.getLogger(__name__)

_IDXC = 'sh.000300'
_MINN = 20
_BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
          '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
          '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
          '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格', '超跌']


def scan_mainlines(session, lookback=250, l2=60, top_sec=10, top_stk=5):
    """返回 {'as_of', 'idx_ret_1y', 'sectors':[{name,n,ret_1y,excess,ret_60,active,leaders:[{name,ret}]}]} 或 None。"""
    try:
        from sqlalchemy import text, bindparam
        import numpy as np
        dates = [str(r[0]) for r in session.execute(
            text("SELECT DISTINCT trade_date FROM stock_daily_kline ORDER BY trade_date DESC LIMIT :n"),
            {"n": lookback + 5}).fetchall()][::-1]
        if len(dates) < lookback:
            return None
        d_now, d_L, d_60 = dates[-1], dates[0], dates[-1 - l2]
        rows = session.execute(text(
            "SELECT s.sector_name, r.stock_code FROM stock_sector s "
            "JOIN stock_sector_relation r ON r.sector_id=s.id WHERE s.sector_type='concept'")).fetchall()
        concept = {}
        for nm, code in rows:
            if not any(b in nm for b in _BLOCK):
                concept.setdefault(nm, []).append(code)
        concept = {k: v for k, v in concept.items() if len(v) >= _MINN}
        names = {r[0]: r[1] for r in session.execute(text("SELECT stock_code, stock_name FROM stock_basic")).fetchall()}
        allmem = sorted({c for v in concept.values() for c in v}) + [_IDXC]
        q = text("SELECT stock_code, trade_date, close_price FROM stock_daily_kline "
                 "WHERE trade_date IN :ds AND close_price>0").bindparams(bindparam('ds', expanding=True))
        cm = {}
        for c, d, p in session.execute(q, {"ds": [d_L, d_60, d_now]}).fetchall():
            cm.setdefault(c, {})[str(d)] = float(p)

        def ret(c, a, b):
            x, y = cm.get(c, {}).get(a), cm.get(c, {}).get(b)
            return (y / x - 1) if (x and y) else None
        idx_L = ret(_IDXC, d_L, d_now); idx_60 = ret(_IDXC, d_60, d_now)
        recs = []
        for nm, mems in concept.items():
            rL = [x for x in (ret(c, d_L, d_now) for c in mems) if x is not None]
            r60 = [x for x in (ret(c, d_60, d_now) for c in mems) if x is not None]
            if len(rL) < _MINN * 0.5:
                continue
            recs.append((nm, len(mems), float(np.mean(rL)), float(np.mean(r60)) if r60 else 0.0))
        recs.sort(key=lambda x: -x[2])
        out = []
        for nm, n, rL, r60 in recs[:top_sec]:
            active = (r60 - (idx_60 or 0)) > 0.05
            stk = sorted([(c, ret(c, d_L, d_now)) for c in concept[nm] if ret(c, d_L, d_now) is not None],
                         key=lambda x: -x[1])[:top_stk]
            out.append({'name': nm, 'n': n, 'ret_1y': round(rL * 100, 1),
                        'excess': round((rL - (idx_L or 0)) * 100, 1), 'ret_60': round(r60 * 100, 1),
                        'active': bool(active),
                        'leaders': [{'name': names.get(c, c), 'ret': round(r * 100, 0)} for c, r in stk]})
        return {'as_of': d_now, 'idx_ret_1y': round((idx_L or 0) * 100, 1), 'sectors': out}
    except Exception as e:
        logger.warning(f"主线扫描失败: {e}")
        return None
