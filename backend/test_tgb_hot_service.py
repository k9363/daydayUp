"""
tgb_hot_service 单元测试：
- imgurl 双格式清洗
- 聚合排序公式
- fetch_hot_posts 端到端（mock urlopen）
"""
import gzip
import io
import json
import math
from unittest.mock import patch, MagicMock

import pytest

from services.tgb_common import CookieExpiredError
from services.tgb_hot_service import (
    parse_imgurl,
    build_summary,
    fetch_hot_posts,
    _hotness,
)


# ---------- parse_imgurl ----------

def test_parse_imgurl_empty():
    assert parse_imgurl(None) == []
    assert parse_imgurl([]) == []
    assert parse_imgurl('not a list') == []


def test_parse_imgurl_clean_format():
    """正常的多元素数组"""
    raw = ['img/2026/05/22/a.png', 'img/2026/05/22/b.png']
    assert parse_imgurl(raw) == ['img/2026/05/22/a.png', 'img/2026/05/22/b.png']


def test_parse_imgurl_dirty_format():
    """淘股吧的奇葩格式：单元素里塞了带 \\" 的字符串"""
    raw = ['img/a.png","img/b.png","img/c.png']
    out = parse_imgurl(raw)
    assert out == ['img/a.png', 'img/b.png', 'img/c.png']


def test_parse_imgurl_mixed():
    """两个 item，一个干净一个脏"""
    raw = ['img/clean.png', 'img/dirty1.png","img/dirty2.png']
    out = parse_imgurl(raw)
    assert out == ['img/clean.png', 'img/dirty1.png', 'img/dirty2.png']


# ---------- 聚合 ----------

def _make_post(tid, reply, view, subject='主题', stock_list=None, post_date='2026-05-24T00:00:00.000+00:00'):
    return {
        'topic_id': tid,
        'new_topic_id': f't{tid}',
        'subject': subject,
        'subinfo': 's',
        'user_id': 1,
        'user_name': 'u',
        'portrait': '',
        'images': [],
        'view_num': view,
        'reply_num': reply,
        'post_date': post_date,
        'stock_list': stock_list or [],
        'url': f'https://m.tgb.cn/a/t{tid}',
    }


def test_hotness_orders_correctly():
    """reply 优先，view 作为对数加权小补丁"""
    high_reply = _make_post(1, reply=100, view=1000)
    low_reply_huge_view = _make_post(2, reply=10, view=10_000_000)
    # log10(1e7) ≈ 7, * 0.3 = 2.1，仍然 << 100 - 10 = 90 的差距
    assert _hotness(high_reply) > _hotness(low_reply_huge_view)


def test_build_summary_top_n_and_format():
    posts = [_make_post(i, reply=100 - i, view=1000) for i in range(20)]
    result = build_summary(posts, top_n=5)
    assert result['all_count'] == 20
    assert len(result['top_posts']) == 5
    # Top 1 应该是 reply 最大的（i=0）
    assert result['top_posts'][0]['topic_id'] == 0
    # 文本里能看到 5 行 Top 帖
    assert 'Top5' in result['summary']
    assert result['summary'].count('. [u]') == 5


def test_build_summary_aggregates_stock_codes():
    """stockList 出现频次应聚合"""
    posts = [
        _make_post(1, 10, 100, stock_list=[{'stockCode': 'sh600000'}, {'stockCode': 'sz000001'}]),
        _make_post(2, 20, 200, stock_list=[{'stockCode': 'sh600000'}]),
        _make_post(3, 5, 50, stock_list=[]),
    ]
    result = build_summary(posts)
    assert 'sh600000×2' in result['summary']
    assert 'sz000001×1' in result['summary']


def test_build_summary_handles_empty():
    result = build_summary([])
    assert result['all_count'] == 0
    assert result['top_posts'] == []
    assert result['report_url'] is None


def test_build_summary_recent_days_filters_old_posts():
    """recent_days=3 应过滤掉发帖超过 3 天的老帖（典型场景：2023 年的"百万阅读"老帖）"""
    from datetime import datetime, timedelta
    today = datetime.now()
    fresh = today.strftime('%Y-%m-%dT%H:%M:%S.000+00:00')
    two_days_ago = (today - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%S.000+00:00')
    five_days_ago = (today - timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S.000+00:00')
    very_old = '2023-12-11T10:33:19.000+00:00'

    posts = [
        _make_post(1, reply=10, view=100, post_date=fresh),
        _make_post(2, reply=20, view=200, post_date=two_days_ago),
        _make_post(3, reply=30, view=300, post_date=five_days_ago),       # 应被过滤
        _make_post(4, reply=99999, view=1_000_000, post_date=very_old),   # 千帖之王也应被过滤
    ]
    result = build_summary(posts, recent_days=3)
    assert result['all_count'] == 4
    assert result['filtered_count'] == 2
    assert {p['topic_id'] for p in result['top_posts']} == {1, 2}
    # Top1 应该是 tid=2（reply 更高）而不是 tid=4（被过滤掉了）
    assert result['top_posts'][0]['topic_id'] == 2
    assert '近 3 日 2/4 条' in result['summary']


def test_build_summary_recent_days_zero_disables_filter():
    """recent_days=0 应保留所有帖子（含老帖）"""
    posts = [
        _make_post(1, reply=10, view=100, post_date='2026-05-24T00:00:00.000+00:00'),
        _make_post(2, reply=99999, view=1_000_000, post_date='2023-01-01T00:00:00.000+00:00'),
    ]
    result = build_summary(posts, recent_days=0)
    assert result['filtered_count'] == 2
    assert result['top_posts'][0]['topic_id'] == 2  # 老帖热度高，没过滤会排第一
    assert '采集 2 条' in result['summary']
    assert '近' not in result['summary'].split('\n')[0]  # 标题里不应出现"近 N 日"


def test_build_summary_stock_aggregation_uses_filtered_only():
    """关联个股聚合应只统计过滤后参与排序的帖子，避免老帖污染"""
    from datetime import datetime, timedelta
    today = datetime.now()
    fresh = today.strftime('%Y-%m-%dT%H:%M:%S.000+00:00')
    very_old = '2023-01-01T00:00:00.000+00:00'

    posts = [
        _make_post(1, 10, 100, post_date=fresh, stock_list=[{'stockCode': 'sh600000'}]),
        _make_post(2, 10, 100, post_date=very_old, stock_list=[{'stockCode': 'sh999999'}]),
    ]
    result = build_summary(posts, recent_days=3)
    assert 'sh600000' in result['summary']
    assert 'sh999999' not in result['summary']  # 老帖关联股被过滤掉


# ---------- fetch_hot_posts mock ----------

def _gzip_json(payload: dict) -> bytes:
    raw = json.dumps(payload).encode('utf-8')
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(raw)
    return buf.getvalue()


class _FakeResp:
    def __init__(self, body, gzipped=True, final_url='https://m.tgb.cn/getMZh?pageNo=2'):
        self.body = body
        self.headers = {'Content-Encoding': 'gzip' if gzipped else ''}
        self._final_url = final_url

    def read(self):
        return self.body

    def geturl(self):
        return self._final_url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_hot_posts_happy_path():
    payload = {
        'status': True,
        'errorCode': 0,
        'dto': {
            'indexList': {
                'listData': [
                    {
                        'topicID': 1, 'newTopicID': 'a1', 'subject': 'S1', 'subinfo': '',
                        'userID': 100, 'userName': 'U1', 'portrait': 'p.png',
                        'imgurl': ['img/a.png'], 'totalViewNum': 500, 'replyNum': 30,
                        'postDate': '2026-05-24T00:00:00.000+00:00',
                        'stockList': [{'stockCode': 'sh600000'}],
                        'deleteFlag': 'N',
                    },
                    {
                        'topicID': 2, 'newTopicID': 'a2', 'subject': 'S2', 'subinfo': '',
                        'userID': 101, 'userName': 'U2', 'portrait': '',
                        'imgurl': None, 'totalViewNum': 200, 'replyNum': 5,
                        'postDate': '2026-05-24T00:00:00.000+00:00',
                        'stockList': [],
                        'deleteFlag': 'N',
                    },
                ]
            }
        }
    }
    fake_body = _gzip_json(payload)
    with patch('services.tgb_common.urllib.request.urlopen', return_value=_FakeResp(fake_body)) as mock_open:
        posts = fetch_hot_posts(pages=1, cookie='fake=1')
    assert len(posts) == 2
    assert posts[0]['topic_id'] == 1
    assert posts[0]['url'] == 'https://m.tgb.cn/a/a1'
    assert posts[0]['images'] == ['img/a.png']
    assert posts[1]['images'] == []
    # URL 必须是 pageNo=2 起
    called_url = mock_open.call_args.args[0].full_url
    assert 'pageNo=2' in called_url


def test_fetch_hot_posts_dedupes_across_pages():
    """同一帖跨页出现应只算一次"""
    payload_p2 = {
        'status': True, 'errorCode': 0,
        'dto': {'indexList': {'listData': [
            {'topicID': 1, 'newTopicID': 'a1', 'subject': 'S1', 'subinfo': '',
             'userID': 1, 'userName': 'U', 'portrait': '', 'imgurl': [],
             'totalViewNum': 100, 'replyNum': 10, 'postDate': '2026-05-24T00:00:00.000+00:00',
             'stockList': [], 'deleteFlag': 'N'},
        ]}}
    }
    payload_p3 = {
        'status': True, 'errorCode': 0,
        'dto': {'indexList': {'listData': [
            {'topicID': 1, 'newTopicID': 'a1', 'subject': 'S1', 'subinfo': '',
             'userID': 1, 'userName': 'U', 'portrait': '', 'imgurl': [],
             'totalViewNum': 100, 'replyNum': 10, 'postDate': '2026-05-24T00:00:00.000+00:00',
             'stockList': [], 'deleteFlag': 'N'},
            {'topicID': 2, 'newTopicID': 'a2', 'subject': 'S2', 'subinfo': '',
             'userID': 1, 'userName': 'U', 'portrait': '', 'imgurl': [],
             'totalViewNum': 100, 'replyNum': 10, 'postDate': '2026-05-24T00:00:00.000+00:00',
             'stockList': [], 'deleteFlag': 'N'},
        ]}}
    }
    responses = [_FakeResp(_gzip_json(payload_p2)), _FakeResp(_gzip_json(payload_p3))]
    with patch('services.tgb_common.urllib.request.urlopen', side_effect=responses):
        posts = fetch_hot_posts(pages=2, cookie='fake=1')
    assert {p['topic_id'] for p in posts} == {1, 2}


def test_fetch_hot_posts_skips_deleted():
    payload = {
        'status': True, 'errorCode': 0,
        'dto': {'indexList': {'listData': [
            {'topicID': 1, 'newTopicID': 'a1', 'subject': 'S1', 'subinfo': '',
             'userID': 1, 'userName': 'U', 'portrait': '', 'imgurl': [],
             'totalViewNum': 100, 'replyNum': 10, 'postDate': '',
             'stockList': [], 'deleteFlag': 'Y'},
            {'topicID': 2, 'newTopicID': 'a2', 'subject': 'S2', 'subinfo': '',
             'userID': 1, 'userName': 'U', 'portrait': '', 'imgurl': [],
             'totalViewNum': 100, 'replyNum': 10, 'postDate': '',
             'stockList': [], 'deleteFlag': 'N'},
        ]}}
    }
    with patch('services.tgb_common.urllib.request.urlopen', return_value=_FakeResp(_gzip_json(payload))):
        posts = fetch_hot_posts(pages=1, cookie='fake=1')
    assert len(posts) == 1
    assert posts[0]['topic_id'] == 2


def test_fetch_hot_posts_detects_sso_redirect():
    """Cookie 失效会被 302 跳 sso.tgb.cn，应抛 CookieExpiredError 让上游告警"""
    fake = _FakeResp(_gzip_json({}), final_url='https://sso.tgb.cn/web/login/index?url=...')
    with patch('services.tgb_common.urllib.request.urlopen', return_value=fake):
        with pytest.raises(CookieExpiredError, match='登录页'):
            fetch_hot_posts(pages=1, cookie='expired=1')


def test_fetch_hot_posts_detects_non_json_response():
    """有些站点 cookie 失效返回登录页 HTML 而不 302，json 解析失败也应抛 CookieExpiredError"""
    html_body = gzip.compress(b'<html><body>please login</body></html>')
    fake = _FakeResp(html_body)
    with patch('services.tgb_common.urllib.request.urlopen', return_value=fake):
        with pytest.raises(CookieExpiredError, match='不是 JSON'):
            fetch_hot_posts(pages=1, cookie='expired=1')


def test_fetch_hot_posts_requires_cookie():
    with patch.dict('os.environ', {}, clear=False):
        # 确保 env 干净 + 临时项目里没有 .tgb_cookie
        import os
        # mock _load_cookie 返回空
        with patch('services.tgb_hot_service._load_cookie', return_value=''):
        # 注意：tgb_hot_service 里 _load_cookie 是从 tgb_common.load_cookie 重命名 import 进来的
            with pytest.raises(RuntimeError, match='Cookie 未配置'):
                fetch_hot_posts(pages=1)
