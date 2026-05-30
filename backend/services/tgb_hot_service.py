"""
淘股吧手机端热帖抓取 + 聚合 service。

数据源：GET https://m.tgb.cn/getMZh?pageNo={N}
- 必须手机 UA + 登录 Cookie，否则跳登录或 403
- pageNo=1 是首页 SSR，分页接口从 pageNo=2 开始有数据；这里统一从 2 抓起
- imgurl 字段格式不一致：item[0] 是干净 JSON 数组，item[1+] 可能是
  单元素数组里塞了 `"a.png\",\"b.png"` 这种带转义的字符串，需要兜底

输出：聚合 Top10 文本 summary，写入 external_analysis 表（source=tgb-mobile-hot），
前端 TgbHotPostsSummary.vue 卡片直接消费。

CLI: `python -m services.tgb_hot_service --pages 5 [--dry-run]`
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError

from services.tgb_common import (
    MOBILE_UA,
    CookieExpiredError,
    http_get_json,
    load_cookie as _load_cookie,
)

logger = logging.getLogger(__name__)

SOURCE = 'tgb-mobile-hot'
BASE_URL = 'https://m.tgb.cn'


def parse_imgurl(raw: Any) -> list[str]:
    """imgurl 在 API 里有两种形态：
    - ["img/a.png", "img/b.png"]            # 正常
    - ["img/a.png\",\"img/b.png\",\"..."]  # 单元素里塞了 split 不掉的字符串
    把两种归一化成扁平的图片路径列表。
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        if '","' in item or '\\"' in item:
            # 把转义剥掉后按 "," 分割
            cleaned = item.replace('\\"', '"').strip('"')
            parts = [p.strip('"').strip() for p in cleaned.split('","')]
            out.extend(p for p in parts if p)
        else:
            out.append(item)
    return out


def _http_get(url: str, cookie: str, timeout: int = 15) -> dict:
    """手机端 GET 的薄包装：固定走 MOBILE_UA + m.tgb.cn Referer。"""
    return http_get_json(url, cookie, MOBILE_UA, f'{BASE_URL}/', timeout=timeout)


def fetch_hot_posts(pages: int = 5, cookie: str | None = None) -> list[dict]:
    """抓 pageNo=2..(2+pages-1)，归一化字段。返回去重后的帖子列表。"""
    if cookie is None:
        cookie = _load_cookie()
    if not cookie:
        raise RuntimeError(
            'Cookie 未配置：请设置环境变量 TGB_COOKIE 或在 backend/.tgb_cookie 写入完整 cookie'
        )

    seen: set[int] = set()
    all_posts: list[dict] = []
    for i in range(pages):
        page_no = 2 + i
        url = f'{BASE_URL}/getMZh?pageNo={page_no}'
        try:
            payload = _http_get(url, cookie)
        except CookieExpiredError as e:
            logger.error(
                f'[tgb-hot] Cookie 失效：{e}\n'
                f'刷新方式：用 chrome-devtools MCP 打开 https://sso.tgb.cn/web/login/index '
                f'用 backend/.tgb_credentials 里的账号密码登录（人工过验证码），'
                f'登录后从 m.tgb.cn 抓 cookie 写回 backend/.tgb_cookie'
            )
            raise
        except (HTTPError, URLError) as e:
            logger.warning(f'[tgb-hot] 拉 {url} 失败: {e}')
            break
        if not payload.get('status'):
            logger.warning(f'[tgb-hot] 接口返回 status=false: {payload.get("errorMessage")}')
            break
        items = (payload.get('dto') or {}).get('indexList', {}).get('listData') or []
        if not items:
            logger.info(f'[tgb-hot] pageNo={page_no} 空，停止翻页')
            break
        for raw in items:
            if raw.get('deleteFlag') == 'Y':
                continue
            tid = raw.get('topicID')
            if tid in seen:
                continue
            seen.add(tid)
            all_posts.append({
                'topic_id': tid,
                'new_topic_id': raw.get('newTopicID'),
                'subject': (raw.get('subject') or '').strip(),
                'subinfo': (raw.get('subinfo') or '').strip(),
                'user_id': raw.get('userID'),
                'user_name': raw.get('userName'),
                'portrait': raw.get('portrait'),
                'images': parse_imgurl(raw.get('imgurl')),
                'view_num': int(raw.get('totalViewNum') or 0),
                'reply_num': int(raw.get('replyNum') or 0),
                'post_date': raw.get('postDate'),
                'stock_list': raw.get('stockList') or [],
                'url': f'{BASE_URL}/a/{raw.get("newTopicID")}' if raw.get('newTopicID') else None,
            })
        logger.info(f'[tgb-hot] pageNo={page_no} 取到 {len(items)} 条，累计 {len(all_posts)}')
    return all_posts


def _hotness(post: dict) -> float:
    """热度评分：reply_num + 0.3 * log10(view_num+1)"""
    return post['reply_num'] + 0.3 * math.log10(post['view_num'] + 1)


def build_summary(posts: list[dict], top_n: int = 10, recent_days: int = 3) -> dict:
    """聚合 Top N，拼成纯文本 summary。返回 dict 可直接喂给 external_analysis。

    recent_days: 只保留 post_date 在最近 N 天内的帖子。/getMZh 返回的是淘股吧全站
    长期热度榜（混入历年老帖），不过滤的话 Top10 会被 2023 年的"百万阅读"老帖占满。
    传 0 关闭过滤，看全部。post_date 是 ISO 字符串 '2026-05-24T04:30:10.000+00:00'，
    比较取前 10 位日期部分（按发帖人本地日期，可接受 ±1 天偏差）。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    if recent_days > 0:
        cutoff = (datetime.now() - timedelta(days=recent_days)).strftime('%Y-%m-%d')
        filtered = [p for p in posts if p['post_date'] and p['post_date'][:10] >= cutoff]
    else:
        filtered = list(posts)

    sorted_posts = sorted(filtered, key=_hotness, reverse=True)
    top = sorted_posts[:top_n]

    if recent_days > 0:
        header = f'淘股吧手机端热帖 Top{len(top)}（近 {recent_days} 日 {len(filtered)}/{len(posts)} 条）'
    else:
        header = f'淘股吧手机端热帖 Top{len(top)}（采集 {len(posts)} 条）'
    lines: list[str] = [header]
    for idx, p in enumerate(top, 1):
        lines.append(
            f'{idx:>2}. [{p["user_name"]}] {p["subject"]}  '
            f'(回{p["reply_num"]} / 看{p["view_num"]})'
        )

    # 关联个股汇总（用过滤后的，跟 Top 列表语义保持一致）
    stock_counter: dict[str, int] = {}
    for p in filtered:
        for st in p['stock_list']:
            code = st.get('stockCode') if isinstance(st, dict) else None
            if code:
                stock_counter[code] = stock_counter.get(code, 0) + 1
    if stock_counter:
        hot_stocks = sorted(stock_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        lines.append('')
        lines.append('关联个股出现频次 Top10：' + ', '.join(f'{c}×{n}' for c, n in hot_stocks))

    summary_text = '\n'.join(lines)
    return {
        'trade_date': today,
        'summary': summary_text,
        'top_posts': top,
        'all_count': len(posts),         # 原始采集量
        'filtered_count': len(filtered), # 过滤后参与排序的量
        'recent_days': recent_days,
        'report_url': top[0]['url'] if top else None,
    }


def save_to_db(summary_dict: dict) -> int:
    """增量插入到 external_analysis 表（每次 cron 跑都新增一行，保留历史时点）。

    external_id 格式：snapshot-{YYYY-MM-DD}-{HHMM}（精确到分钟，避免同分钟冲突）
    同分钟内重复跑（极少）会触发 UniqueConstraint 冲突 → 兜底 update 该行。

    返回 external_analysis.id。**调用方需已建立 Flask app context。**
    """
    from extensions import db
    from models.external_analysis import ExternalAnalysis
    from datetime import datetime as _dt
    from sqlalchemy.exc import IntegrityError

    trade_date = summary_dict['trade_date']
    now_hhmm = _dt.now().strftime('%H%M')
    external_id = f'snapshot-{trade_date}-{now_hhmm}'

    obj = ExternalAnalysis.query.filter_by(source=SOURCE, external_id=external_id).first()
    if obj is None:
        obj = ExternalAnalysis(source=SOURCE, external_id=external_id, stock_code='_market_')
        db.session.add(obj)

    obj.stock_code = '_market_'  # 占位：全市场聚合无单一股票
    obj.stock_name = '淘股吧热帖'
    obj.trade_date = trade_date
    obj.summary = summary_dict['summary']
    obj.report_url = summary_dict.get('report_url')
    obj.raw_report = {
        'top_posts': summary_dict['top_posts'],
        'all_count': summary_dict['all_count'],
        'filtered_count': summary_dict.get('filtered_count'),
        'recent_days': summary_dict.get('recent_days'),
        'snapshot_time': _dt.now().isoformat(),
    }
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # 同 source+external_id 冲突 → 重读后 update
        obj = ExternalAnalysis.query.filter_by(source=SOURCE, external_id=external_id).first()
        obj.summary = summary_dict['summary']
        obj.raw_report = {
            'top_posts': summary_dict['top_posts'],
            'all_count': summary_dict['all_count'],
            'filtered_count': summary_dict.get('filtered_count'),
            'recent_days': summary_dict.get('recent_days'),
            'snapshot_time': _dt.now().isoformat(),
        }
        db.session.commit()
    return obj.id


def run_daily(pages: int = 5, dry_run: bool = False, recent_days: int = 3) -> dict:
    """完整流程：抓 → 过滤近 recent_days 天 → 聚合 → 写库。CLI 和 scheduler 都走这里。"""
    posts = fetch_hot_posts(pages=pages)
    if not posts:
        logger.warning('[tgb-hot] 一条也没抓到，跳过写库')
        return {'success': False, 'count': 0}
    summary_dict = build_summary(posts, recent_days=recent_days)
    if dry_run:
        print(summary_dict['summary'])
        return {
            'success': True, 'count': len(posts),
            'filtered': summary_dict['filtered_count'], 'dry_run': True,
        }
    new_id = save_to_db(summary_dict)
    logger.info(
        f'[tgb-hot] 已写入 external_analysis id={new_id}, '
        f'posts={len(posts)} filtered={summary_dict["filtered_count"]}'
    )
    return {
        'success': True, 'count': len(posts),
        'filtered': summary_dict['filtered_count'], 'id': new_id,
    }


def _cli():
    parser = argparse.ArgumentParser(description='淘股吧手机端热帖抓取器')
    parser.add_argument('--pages', type=int, default=5, help='抓取页数（pageNo=2 起算），默认 5')
    parser.add_argument('--recent-days', type=int, default=3,
                        help='只保留发帖时间在最近 N 天内的，默认 3。传 0 关闭过滤看全部。')
    parser.add_argument('--dry-run', action='store_true', help='只打印结果，不写库')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    if args.dry_run:
        # dry-run 不需要 Flask context
        result = run_daily(pages=args.pages, dry_run=True, recent_days=args.recent_days)
    else:
        # 写库需要 app context
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app import create_app
        app = create_app()
        with app.app_context():
            result = run_daily(pages=args.pages, dry_run=False, recent_days=args.recent_days)

    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == '__main__':
    _cli()
