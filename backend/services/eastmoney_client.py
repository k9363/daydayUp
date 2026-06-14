"""东财（eastmoney）数据统一收口（2026-06-14）。

⚠️ 项目内所有「东财直连」必须走本模块，不要再各处手搓 requests / 复制浏览器 UA。
背景：akshare 1.18.x 的东财 **board/sector/fund_flow/分时** 系列接口
（stock_*_fund_flow_rank / stock_board_*_em / stock_zh_a_hist_min_em 等）在服务器被
东财 UA 反爬（RemoteDisconnected）；**端点本身正常，浏览器 UA + Referer 直连即可**。
故东财的板块/资金流/分时数据一律走这里，**严禁改回 akshare 的上述接口**。
（akshare 仍可正常用的 stock_zh_a_spot_em 全市场快照 / stock_individual_info_em 等
非 board/fund_flow 端点不在此列，保持现状。）

与 TA-CN `tradingagents/dataflows/eastmoney_client.py` 同源（两 repo 各一份、逻辑保持一致）。
"""
import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}
CLIST_HOSTS = ("push2delay.eastmoney.com", "push2.eastmoney.com", "82.push2.eastmoney.com")
KLINE_HOSTS = ("push2his.eastmoney.com", "push2.eastmoney.com")


def _em_get(host, path, params, max_retry=4):
    """单 host GET + 退避重试（东财对密集请求会临时 RemoteDisconnected）。失败抛异常。"""
    import requests
    last = None
    for attempt in range(max_retry):
        try:
            r = requests.get("http://%s%s" % (host, path), params=params, headers=EM_HEADERS, timeout=12)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            if attempt == max_retry - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last


def em_clist(fs, fields="f12,f14", fid="f3", page_size=100, max_retry=4):
    """东财 clist 列表/排名（/api/qt/clist/get），自动分页 + 多 host 退避。返回 list[dict]。
    fs 示例：m:90+t:2(行业板块) / m:90+t:3(概念) / b:BKxxxx+f:!50(板块成分)；
    fields 取 f12 代码/f14 名称/f3 涨跌幅/f62 主力净流入/f184 净占比等；fid 为排序字段。"""
    for host in CLIST_HOSTS:
        try:
            out = []
            pn = 1
            while True:
                r = _em_get(host, "/api/qt/clist/get",
                            {"pn": pn, "pz": page_size, "po": 1, "np": 1,
                             "fs": fs, "fields": fields, "fid": fid}, max_retry)
                data = (r.json() or {}).get("data") or {}
                diff = data.get("diff") or []
                if isinstance(diff, dict):
                    diff = list(diff.values())
                out.extend(diff)
                total = data.get("total") or 0
                if not diff or len(out) >= total:
                    break
                pn += 1
                time.sleep(0.5)
            return out
        except Exception as e:
            logger.warning("东财 clist 失败 host=%s fs=%s: %s" % (host, fs, e))
            continue
    return []


def em_kline_close(secid, trade_date, klt="5", lookback_days=10, max_retry=4):
    """东财 K 线（push2his /api/qt/stock/kline/get）。
    返回 [(date 'YYYY-MM-DD', time 'HH:MM', close float), ...]。
    secid：个股 '1.600000'(沪)/'0.000001'(深)；指数见调用方映射。trade_date 为 YYYYMMDD。"""
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(trade_date, "%Y%m%d")
    except Exception:
        return []
    params = {"secid": secid, "klt": klt, "fqt": "0",
              "beg": (d - timedelta(days=lookback_days)).strftime("%Y%m%d"),
              "end": trade_date, "lmt": "1000", "fields1": "f1", "fields2": "f51,f53"}
    for host in KLINE_HOSTS:
        try:
            r = _em_get(host, "/api/qt/stock/kline/get", params, max_retry)
            klines = ((r.json() or {}).get("data") or {}).get("klines") or []
            recs = []
            for k in klines:
                parts = str(k).split(",")
                if len(parts) < 2 or len(parts[0]) < 16:
                    continue
                try:
                    recs.append((parts[0][:10], parts[0][11:16], float(parts[1])))
                except ValueError:
                    continue
            return recs
        except Exception as e:
            logger.warning("东财 kline 失败 host=%s secid=%s: %s" % (host, secid, e))
            continue
    return []


def em_kline_pct(secid, trade_date, klt="5"):
    """当日 5min 相对昨收累计涨跌幅 {t(HH:MM): pct}。昨收取区间内前一交易日最后一根 close。"""
    recs = em_kline_close(secid, trade_date, klt=klt)
    if not recs:
        return {}
    td_dash = "%s-%s-%s" % (trade_date[:4], trade_date[4:6], trade_date[6:8])
    prev = [c for (dd, _t, c) in recs if dd < td_dash]
    today = [(t, c) for (dd, t, c) in recs if dd == td_dash]
    if not today:
        return {}
    pc = prev[-1] if prev else today[0][1]
    if not pc:
        return {}
    return {t: (c / pc - 1.0) * 100.0 for (t, c) in today}
