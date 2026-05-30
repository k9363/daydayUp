"""
淘股吧特别关注流抓取 + 聚合 service。

数据源：GET https://www.tgb.cn/super/spefocus/friendActions
        ?perPageNum=20&actionID={offset}&type=A

返回登录用户（k9366/8615779）当前关注的那些人最近的动作（发帖/回帖/引用），
时间倒序。跟 tgb_hot_service（全站热度）互补：这个是"我跟的人在说什么"。

字段：
- actionDate: '2026-05-24 16:49:27'
- actionName: 'R'=回帖 / 'T'=主题 / 'Q'=可能是赞或别的
- userID/userName: 动作发起人（你关注的人）
- objectID/objectName: 原主题 ID 和标题
- newTopicID: 主题短码
- body: 这条动作的内容（回复正文 / 主题摘要）
- quoteContent/quoteUserName: 引用的内容和被引用人（仅回帖用）
- tops: 原主题完整元数据（subject/replyNum/viewNum/usefulNum/postDate）

写 external_analysis source=tgb-special-focus, external_id=daily-YYYY-MM-DD。
CLI: `python -m services.tgb_spefocus_service --pages 5 [--dry-run]`
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError

from services.tgb_common import (
    DESKTOP_UA,
    CookieExpiredError,
    http_get_json,
    load_cookie,
)

logger = logging.getLogger(__name__)

SOURCE = 'tgb-special-focus'
BASE_URL = 'https://www.tgb.cn'
ACTION_NAMES = {
    'R': '回',
    'T': '发',
    'Q': '问',
}


def _http_get(url: str, cookie: str) -> dict:
    """桌面端 GET 的薄包装：固定走 DESKTOP_UA + 特别关注页 Referer。"""
    return http_get_json(
        url, cookie, DESKTOP_UA,
        f'{BASE_URL}/user/getMoreListAction',
    )


def fetch_friend_actions(pages: int = 5, cookie: str | None = None) -> list[dict]:
    """抓 actionID=0,20,40,... 共 pages 页，按 actionID（offset）顺序遍历。

    返回字段已扁平化，时间倒序（接口本身就是倒序的，跨页拼接也是倒序）。
    """
    if cookie is None:
        cookie = load_cookie()
    if not cookie:
        raise RuntimeError(
            'Cookie 未配置：请设置环境变量 TGB_COOKIE 或在 backend/.tgb_cookie 写入完整 cookie'
        )

    seen: set[int] = set()
    actions: list[dict] = []
    for i in range(pages):
        offset = i * 20
        url = f'{BASE_URL}/super/spefocus/friendActions?perPageNum=20&actionID={offset}&type=A'
        try:
            payload = _http_get(url, cookie)
        except CookieExpiredError as e:
            logger.error(
                f'[tgb-spefocus] Cookie 失效：{e}\n'
                f'刷新方式见 memory: reference_tgb_cookie_refresh'
            )
            raise
        except (HTTPError, URLError) as e:
            logger.warning(f'[tgb-spefocus] 拉 {url} 失败: {e}')
            break

        if not payload.get('status'):
            logger.warning(f'[tgb-spefocus] 接口返回 status=false: {payload.get("errorMessage")}')
            break
        records = (payload.get('dto') or {}).get('record') or []
        if not records:
            logger.info(f'[tgb-spefocus] offset={offset} 空，停止翻页')
            break

        for r in records:
            other_id = r.get('otherID')  # 本条动作（回帖）的 ID，跨页唯一
            if other_id in seen:
                continue
            seen.add(other_id)
            tops = r.get('tops') or {}
            actions.append({
                'other_id': other_id,
                'action_date': r.get('actionDate'),
                'action_name': r.get('actionName'),
                'action_label': ACTION_NAMES.get(r.get('actionName'), r.get('actionName') or '动'),
                'user_id': r.get('userID'),
                'user_name': r.get('userName'),
                'portrait': r.get('portrait'),
                'object_id': r.get('objectID'),
                'object_name': (r.get('objectName') or '').strip(),
                'new_topic_id': r.get('newTopicID'),
                'body': (r.get('body') or '').strip(),
                'quote_content': (r.get('quoteContent') or '').strip(),
                'quote_user_name': r.get('quoteUserName'),
                'topic_url': (
                    f'{BASE_URL}/a/{r.get("newTopicID")}' if r.get('newTopicID') else None
                ),
                # 原主题元数据（点开看时有用）
                'topic_reply_num': tops.get('replyNum'),
                'topic_view_num': tops.get('viewNum'),
                'topic_useful_num': tops.get('usefulNum'),
                'topic_subject': (tops.get('subject') or '').strip(),
                'topic_author': tops.get('userName'),
                'topic_post_date': tops.get('postDate'),
            })
        logger.info(f'[tgb-spefocus] offset={offset} 取到 {len(records)} 条，累计 {len(actions)}')
    return actions


def build_summary(actions: list[dict], top_n: int = 30) -> dict:
    """按时间倒序取 Top N 条，拼成时间线 summary 文本。"""
    today = datetime.now().strftime('%Y-%m-%d')
    top = actions[:top_n]

    if not top:
        return {
            'trade_date': today,
            'summary': '今日特别关注流暂无动态',
            'top_actions': [],
            'all_count': 0,
            'report_url': None,
        }

    lines: list[str] = [f'特别关注最新动态（共 {len(actions)} 条，列出最近 {len(top)} 条）']
    for a in top:
        # 时间只取 MM-DD HH:MM
        date_short = (a['action_date'] or '')[5:16] if a['action_date'] else ''
        body_short = a['body'][:60] + ('…' if len(a['body']) > 60 else '')
        line = f'[{date_short}] {a["user_name"]} {a["action_label"]}「{a["object_name"][:30]}」'
        if body_short:
            line += f' — {body_short}'
        lines.append(line)

    # 出现频次 Top 关注对象（高频主题）
    obj_counter: dict[int, dict] = {}
    for a in actions:
        oid = a['object_id']
        if not oid:
            continue
        if oid not in obj_counter:
            obj_counter[oid] = {'name': a['object_name'], 'count': 0, 'author': a['topic_author']}
        obj_counter[oid]['count'] += 1
    hot_objects = sorted(obj_counter.values(), key=lambda x: x['count'], reverse=True)
    hot_objects = [o for o in hot_objects if o['count'] >= 2][:5]
    if hot_objects:
        lines.append('')
        lines.append('关注流中高频主题：')
        for o in hot_objects:
            lines.append(f'  - 「{o["name"][:40]}」 ({o["author"]}) ×{o["count"]} 条')

    summary_text = '\n'.join(lines)
    return {
        'trade_date': today,
        'summary': summary_text,
        'top_actions': top,
        'all_count': len(actions),
        'report_url': top[0]['topic_url'] if top else None,
    }


def save_to_db(summary_dict: dict) -> int:
    """增量插入到 external_analysis 表（每次 cron 跑都新增一行，保留历史时点）。

    external_id 格式：snapshot-{YYYY-MM-DD}-{HHMM}
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

    obj.stock_code = '_market_'
    obj.stock_name = '特别关注动态'
    obj.trade_date = trade_date
    obj.summary = summary_dict['summary']
    obj.report_url = summary_dict.get('report_url')
    obj.raw_report = {
        'top_actions': summary_dict['top_actions'],
        'all_count': summary_dict['all_count'],
        'snapshot_time': _dt.now().isoformat(),
    }
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        obj = ExternalAnalysis.query.filter_by(source=SOURCE, external_id=external_id).first()
        obj.summary = summary_dict['summary']
        obj.raw_report = {
            'top_actions': summary_dict['top_actions'],
            'all_count': summary_dict['all_count'],
            'snapshot_time': _dt.now().isoformat(),
        }
        db.session.commit()
    return obj.id


def run_daily(pages: int = 5, dry_run: bool = False) -> dict:
    actions = fetch_friend_actions(pages=pages)
    if not actions:
        logger.warning('[tgb-spefocus] 一条也没抓到，跳过写库')
        return {'success': False, 'count': 0}
    summary_dict = build_summary(actions)
    if dry_run:
        print(summary_dict['summary'])
        return {'success': True, 'count': len(actions), 'dry_run': True}
    new_id = save_to_db(summary_dict)
    logger.info(f'[tgb-spefocus] 已写入 external_analysis id={new_id}, actions={len(actions)}')
    return {'success': True, 'count': len(actions), 'id': new_id}


def _cli():
    parser = argparse.ArgumentParser(description='淘股吧特别关注流抓取器')
    parser.add_argument('--pages', type=int, default=5, help='抓取页数（actionID=0,20,40...），默认 5')
    parser.add_argument('--dry-run', action='store_true', help='只打印结果，不写库')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    if args.dry_run:
        result = run_daily(pages=args.pages, dry_run=True)
    else:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app import create_app
        app = create_app()
        with app.app_context():
            result = run_daily(pages=args.pages, dry_run=False)

    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == '__main__':
    _cli()
