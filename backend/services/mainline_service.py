"""主线扫描服务(2026-06-14)——复盘在「高流动性牛市」时调用,返回当前高景气主线榜+龙头,
每条主线自带板块「节奏」标签(八态 state + 板块温度计 sec_top/bot_score + 派发风险 dist_risk),
方向(中期景气)× 节奏(短期顶底派发)联动:主线榜回答骑哪条,节奏标签回答此刻能不能上。
口径:概念板块近1年等权收益+相对沪深300超额排序(剔自循环/风格黑名单),标活跃(近60日仍跑赢),每主线列领涨股。
节奏标签复刻 TA-CN topbottom_dashboard 板块状态机:用成分日线合成板块净值,算乖离/RSI6/run5/新高占比/量能比。
⚠️ 概念成分为当前快照→有前视;作主线方向参考,非可交易回测。详见 docs/SYSTEM.md 十五章。"""
import logging
import math
logger = logging.getLogger(__name__)

_IDXC = 'sh.000300'
_MINN = 20
_BLOCK = ['新高', '新低', '百元股', '低价股', '趋势股', '题材股', '热股', '炸板', '连板', '昨日', '涨停',
          '次新', '破净', '送转', '大盘成长', '大盘价值', '中盘', '小盘', '微盘', '机构重仓', '基金重仓',
          '预盈', '预增', '业绩', 'MSCI', '富时', '标普', '沪股通', '深股通', '融资融券', '转融', 'QFII',
          '茅指数', '宁组合', '核心资产', '同花顺', '东方财富', '股权转让', '举牌', '重组', '摘帽', '风格', '超跌']

# ===== 板块温度计常数(复刻 TA-CN topbottom_dashboard,据 30 个申万一级行业 2007-2026 回测标定)=====
# 因子=板块净值形态量(乖离/RSI6/run5/新高占比/量能比),z 标准化×权重→正态CDF→0-100 顶/底分。
_SEC_FSTAT = {'bias20': (0.5777, 5.3292), 'rsi6': (53.2793, 19.4570), 'run5': (0.3897, 4.6708),
              'nh_ratio': (8.8579, 10.3187), 'amt_ratio': (1.0183, 0.3210)}
_SEC_TOPW = {'bias20': 0.24, 'rsi6': 0.196, 'run5': 0.141, 'nh_ratio': 0.172, 'amt_ratio': 0.155}
_SEC_BOTW = {'bias20': 0.356, 'rsi6': 0.32, 'run5': 0.275, 'nh_ratio': 0.224, 'amt_ratio': 0.15}
_SEC_COMP_TOP = (-0.0062, 0.7293)
_SEC_COMP_BOT = (0.0067, 1.0909)


def _sec_z(name, val):
    if val is None:
        return 0.0
    mu, sd = _SEC_FSTAT[name]
    return max(-3.0, min(3.0, (val - mu) / sd))


def _tb_cdf(x, mu, sd):
    return 0.5 * (1 + math.erf((x - mu) / (sd * 1.4142135623730951)))


def _sec_tb_scores(bias20, rsi6, run5, nh_ratio, amt_ratio):
    """板块温度计:板块净值的 0-100 顶/底连续分级。
    分级据标定命中率:底 ≥90强底/≥80中底/≥65阶段底;顶 ≥70警惕/≥60观察(顶噪声大)。"""
    vals = {'bias20': bias20, 'rsi6': rsi6, 'run5': run5, 'nh_ratio': nh_ratio, 'amt_ratio': amt_ratio}
    ct = sum(w * _sec_z(k, vals[k]) for k, w in _SEC_TOPW.items())
    cb = sum(w * (-_sec_z(k, vals[k])) for k, w in _SEC_BOTW.items())
    ts = round(100 * _tb_cdf(ct, *_SEC_COMP_TOP))
    bs = round(100 * _tb_cdf(cb, *_SEC_COMP_BOT))
    tl = "偏强顶(警惕)" if ts >= 70 else ("阶段顶观察" if ts >= 60 else "")
    bl = "强底" if bs >= 90 else ("中底" if bs >= 80 else ("阶段底观察" if bs >= 65 else ""))
    return ts, bs, tl, bl


def _board_state(px, amt, pct):
    """成分日线(close/turnover/pct DataFrame, index=日期 × columns=代码)→ 板块净值八态+温度计+派发风险。
    复刻 TA-CN _sector_state_one 的相位/派发/温度计部分(去掉 yy_ratio/高位爆量等需 low 的闪信号)。"""
    import numpy as np
    import pandas as pd
    keep = px.columns[px.notna().mean() > 0.8]
    if len(keep) < 10:
        return None
    px = px[keep].ffill()
    amt = amt.reindex(columns=keep)
    pct = pct.reindex(columns=keep)
    dts = px.index.tolist()
    rets = px.pct_change()
    nav = (1 + rets.mean(axis=1).fillna(0)).cumprod()
    i_top = int(np.argmax(nav.values))
    drawdown = (nav.iloc[-1] / nav.iloc[i_top] - 1) * 100
    days_since_top = len(dts) - 1 - i_top
    # 连续主升天数: nav 处于自身运行峰值 3% 以内的尾部天数(回撤超3%清零)
    healthy = (nav >= nav.cummax() * 0.97).values
    up_streak = 0
    for v in healthy[::-1]:
        if v:
            up_streak += 1
        else:
            break
    # 新高占比(20日)
    roll_high = px.rolling(20, min_periods=5).max()
    nh_ratio = (px >= roll_high * 0.999).mean(axis=1) * 100
    nh_now = float(nh_ratio.iloc[-1])
    nh_peak60 = float(nh_ratio.iloc[-60:].max())
    # 量能比: 今日板块成交额 / 前20日均
    sec_amt = amt.sum(axis=1)
    amt_ratio = None
    if len(sec_amt) >= 21:
        base = float(sec_amt.iloc[-21:-1].mean())
        amt_ratio = float(sec_amt.iloc[-1]) / base if base > 0 else None
    # 共振: corr20 相对 60 日;当日跌5%家数占比
    crash_now = float((pct.iloc[-1] < -5).mean() * 100)
    samp = list(keep[:25])
    rv = rets[samp]

    def _corr_at(i):
        sub = rv.iloc[max(0, i - 19):i + 1].dropna(axis=1)
        if sub.shape[1] < 5:
            return np.nan
        cm = np.corrcoef(sub.values.T)
        return cm[np.triu_indices_from(cm, 1)].mean()
    corr_now = _corr_at(len(dts) - 1)
    corr_60max = max((x for x in (_corr_at(i) for i in range(max(20, len(dts) - 60), len(dts))) if not np.isnan(x)),
                     default=np.nan)
    corr_is_60d_high = (not np.isnan(corr_now)) and (not np.isnan(corr_60max)) and corr_now >= corr_60max * 0.98
    # 派发风险(0~3): 缩量(无承接) + 抱团共振(corr创60日新高) + 新高占比从60日峰腰斩
    dist_flags = []
    if amt_ratio is not None and amt_ratio < 1.0:
        dist_flags.append("缩量")
    if corr_is_60d_high:
        dist_flags.append("抱团")
    if nh_peak60 > 0 and nh_now < nh_peak60 * 0.5:
        dist_flags.append("衰减")
    dist_risk = len(dist_flags)
    # 板块温度计: 板块净值的 乖离/RSI6/run5 + 新高占比/量能比 → 0-100
    _navs = pd.Series(nav.values)
    _ma20 = _navs.rolling(20, min_periods=20).mean()
    _bias20 = float((_navs.iloc[-1] / _ma20.iloc[-1] - 1) * 100) if not pd.isna(_ma20.iloc[-1]) else None
    if len(_navs) >= 7:
        _d = _navs.diff(); _ag = _d.clip(lower=0).ewm(com=5).mean(); _al = (-_d).clip(lower=0).ewm(com=5).mean()
        _rsi6 = float((100 - 100 / (1 + _ag / _al.replace(0, np.nan))).iloc[-1])
    else:
        _rsi6 = None
    _run5 = float((_navs.iloc[-1] / _navs.iloc[-6] - 1) * 100) if len(_navs) >= 6 else None
    sec_top, sec_bot, tb_top, tb_bot = _sec_tb_scores(_bias20, _rsi6, _run5, nh_now, amt_ratio)
    # 状态机(复刻 TA-CN,去掉高位爆量闪信号)
    if crash_now > 50 and drawdown < -12 and corr_is_60d_high:
        state = "🔴 最后一跌(低吸窗口)"
    elif days_since_top <= 2 and nh_now > 25:
        state = "🟢 主升(创新高中)"
    elif -8 < drawdown < -3 and dist_risk >= 2:
        state = "🟠 派发风险偏高(%d/3:%s)" % (dist_risk, "·".join(dist_flags))
    elif 0 < days_since_top <= 25 and drawdown > -8:
        state = "🟡 顶后回落观察(派发%d/3%s)" % (dist_risk, "·" + "·".join(dist_flags) if dist_flags else "")
    elif nh_peak60 > 50 and nh_now < 25 and days_since_top <= 5:
        state = "🟡 动能顶预备(新高占比%d%%→%d%%衰竭)" % (nh_peak60, nh_now)
    elif drawdown < -15:
        state = "⚫ 深度调整(等共振下杀的最后一跌)"
    elif drawdown <= -8 and nh_now < max(nh_peak60 * 0.5, 1):
        state = "🟠 退潮调整(回撤%.0f%%、新高占比%d%%已从峰%d%%腰斩)" % (drawdown, nh_now, nh_peak60)
    else:
        state = "⚪ 常态"
    return {'state': state, 'sec_top_score': sec_top, 'sec_bot_score': sec_bot,
            'sec_tb_top': tb_top, 'sec_tb_bot': tb_bot,
            'dist_risk': dist_risk, 'dist_flags': dist_flags,
            'drawdown': round(float(drawdown), 1), 'nh_now': round(nh_now),
            'amt_ratio': round(amt_ratio, 2) if amt_ratio is not None else None,
            'up_streak': int(up_streak)}


def scan_mainlines(session, lookback=250, l2=60, top_sec=10, top_stk=5):
    """返回 {'as_of','idx_ret_1y','sectors':[{name,n,ret_1y,excess,ret_60,active,leaders,
    state,sec_top_score,sec_bot_score,dist_risk,...}]} 或 None。"""
    try:
        from sqlalchemy import text, bindparam
        import numpy as np
        import pandas as pd
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
        top = recs[:top_sec]

        # ===== B: 给 top 主线算板块节奏(合成净值→八态/温度计/派发风险)=====
        # 只为 top 主线拉 ~110 日成分日线(close/high/turnover/pct),按板块合成净值
        state_dates = dates[-110:]
        d_s0 = state_dates[0]
        top_members = sorted({c for nm, _, _, _ in top for c in concept[nm]})
        board_states = {}
        if top_members:
            qs = text("SELECT stock_code, trade_date, close_price, turnover, change_percent "
                      "FROM stock_daily_kline WHERE trade_date BETWEEN :a AND :b "
                      "AND stock_code IN :cs AND close_price>0").bindparams(bindparam('cs', expanding=True))
            srecs = session.execute(qs, {"a": d_s0, "b": d_now, "cs": top_members}).fetchall()
            if srecs:
                sdf = pd.DataFrame(srecs, columns=['code', 'date', 'close', 'amt', 'pct'])
                sdf['date'] = sdf['date'].astype(str)
                px_all = sdf.pivot_table(index='date', columns='code', values='close').sort_index()
                amt_all = sdf.pivot_table(index='date', columns='code', values='amt').sort_index()
                pct_all = sdf.pivot_table(index='date', columns='code', values='pct').sort_index()
                for nm, _, _, _ in top:
                    cols = [c for c in concept[nm] if c in px_all.columns]
                    if len(cols) < 10:
                        continue
                    try:
                        st = _board_state(px_all[cols], amt_all[cols], pct_all[cols])
                        if st:
                            board_states[nm] = st
                    except Exception as e:
                        logger.warning(f"主线[{nm}]节奏计算失败: {e}")

        out = []
        for nm, n, rL, r60 in top:
            active = (r60 - (idx_60 or 0)) > 0.05
            stk = sorted([(c, ret(c, d_L, d_now)) for c in concept[nm] if ret(c, d_L, d_now) is not None],
                         key=lambda x: -x[1])[:top_stk]
            rec = {'name': nm, 'n': n, 'ret_1y': round(rL * 100, 1),
                   'excess': round((rL - (idx_L or 0)) * 100, 1), 'ret_60': round(r60 * 100, 1),
                   'active': bool(active),
                   'leaders': [{'name': names.get(c, c), 'ret': round(r * 100, 0)} for c, r in stk]}
            st = board_states.get(nm)
            if st:
                rec.update(st)
            out.append(rec)
        return {'as_of': d_now, 'idx_ret_1y': round((idx_L or 0) * 100, 1), 'sectors': out}
    except Exception as e:
        logger.warning(f"主线扫描失败: {e}")
        return None
