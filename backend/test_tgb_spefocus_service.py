"""
tgb_spefocus_service 单元测试。
"""
import gzip
import io
import json
from unittest.mock import patch

import pytest

from services.tgb_common import CookieExpiredError
from services.tgb_spefocus_service import (
    build_summary,
    fetch_friend_actions,
)


def _make_action(other_id, action_name='R', user='u', obj_name='主题',
                 action_date='2026-05-24 16:00:00', body='正文', object_id=100):
    return {
        'other_id': other_id,
        'action_date': action_date,
        'action_name': action_name,
        'action_label': {'R': '回', 'T': '发', 'Q': '问'}.get(action_name, action_name),
        'user_id': 1,
        'user_name': user,
        'portrait': '',
        'object_id': object_id,
        'object_name': obj_name,
        'new_topic_id': f't{other_id}',
        'body': body,
        'quote_content': '',
        'quote_user_name': None,
        'topic_url': f'https://www.tgb.cn/a/t{other_id}',
        'topic_reply_num': 10,
        'topic_view_num': 100,
        'topic_useful_num': 5,
        'topic_subject': obj_name,
        'topic_author': 'author',
        'topic_post_date': '2026-05-22 10:00:00',
    }


# ---------- build_summary ----------

def test_build_summary_empty():
    result = build_summary([])
    assert result['all_count'] == 0
    assert result['top_actions'] == []
    assert result['report_url'] is None
    assert '暂无动态' in result['summary']


def test_build_summary_renders_timeline():
    actions = [
        _make_action(1, action_name='R', user='熙熙爸比', obj_name='ICU到KTV', body='预期内啊'),
        _make_action(2, action_name='T', user='科比帅', obj_name='周总结', body='反者道之动'),
    ]
    result = build_summary(actions, top_n=10)
    assert result['all_count'] == 2
    assert len(result['top_actions']) == 2
    # 时间线格式：[MM-DD HH:MM] 用户 动作「主题」 — 内容
    assert '熙熙爸比 回「ICU到KTV」' in result['summary']
    assert '科比帅 发「周总结」' in result['summary']
    assert '预期内啊' in result['summary']


def test_build_summary_truncates_long_body():
    long_body = '一' * 100
    actions = [_make_action(1, body=long_body)]
    result = build_summary(actions)
    # body 应被截断到 60 + 省略号
    assert '一' * 60 + '…' in result['summary']
    assert '一' * 100 not in result['summary']


def test_build_summary_hot_objects_threshold():
    """高频主题聚合：单主题 count>=2 才显示"""
    actions = [
        _make_action(1, obj_name='热门主题', object_id=1),
        _make_action(2, obj_name='热门主题', object_id=1),
        _make_action(3, obj_name='热门主题', object_id=1),
        _make_action(4, obj_name='冷门主题', object_id=2),  # 只 1 次，不应出现
    ]
    result = build_summary(actions)
    assert '热门主题' in result['summary'].split('关注流中高频主题')[1]
    cold_section = result['summary'].split('关注流中高频主题')[1] if '关注流中高频主题' in result['summary'] else ''
    assert '冷门主题' not in cold_section


def test_build_summary_no_hot_objects_section_when_all_singles():
    """所有主题都只出现 1 次，不应渲染'高频主题'区块"""
    actions = [
        _make_action(1, object_id=1, obj_name='A'),
        _make_action(2, object_id=2, obj_name='B'),
    ]
    result = build_summary(actions)
    assert '关注流中高频主题' not in result['summary']


def test_build_summary_top_n_cap():
    actions = [_make_action(i) for i in range(50)]
    result = build_summary(actions, top_n=10)
    assert result['all_count'] == 50
    assert len(result['top_actions']) == 10


# ---------- fetch_friend_actions mock ----------

def _gzip_json(payload: dict) -> bytes:
    raw = json.dumps(payload).encode('utf-8')
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(raw)
    return buf.getvalue()


class _FakeResp:
    def __init__(self, body, gzipped=True, final_url='https://www.tgb.cn/super/spefocus/friendActions'):
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


def _make_record(other_id=1, user='u', action_name='R', obj_id=100, obj_name='主题'):
    return {
        'otherID': other_id,
        'actionDate': '2026-05-24 16:00:00',
        'actionName': action_name,
        'userID': 1,
        'userName': user,
        'portrait': 'p.png',
        'objectID': obj_id,
        'objectName': obj_name,
        'newTopicID': f't{other_id}',
        'body': '正文',
        'quoteContent': '',
        'quoteUserName': None,
        'tops': {
            'replyNum': 10, 'viewNum': 100, 'usefulNum': 5,
            'subject': obj_name, 'userName': 'author', 'postDate': '2026-05-22 10:00:00',
        },
    }


def test_fetch_friend_actions_happy_path():
    payload = {
        'status': True, 'errorCode': 0,
        'dto': {'record': [
            _make_record(1, user='熙熙爸比', action_name='R'),
            _make_record(2, user='科比帅', action_name='T'),
        ]}
    }
    with patch('services.tgb_common.urllib.request.urlopen',
               return_value=_FakeResp(_gzip_json(payload))) as mock_open:
        actions = fetch_friend_actions(pages=1, cookie='fake=1')
    assert len(actions) == 2
    assert actions[0]['user_name'] == '熙熙爸比'
    assert actions[0]['action_label'] == '回'
    assert actions[1]['action_label'] == '发'
    # URL 必须是 offset=0
    called_url = mock_open.call_args.args[0].full_url
    assert 'actionID=0' in called_url


def test_fetch_friend_actions_dedupes_across_pages():
    """同一 otherID 跨页出现只算一次"""
    p0 = {'status': True, 'errorCode': 0, 'dto': {'record': [_make_record(1)]}}
    p20 = {'status': True, 'errorCode': 0, 'dto': {'record': [_make_record(1), _make_record(2)]}}
    responses = [_FakeResp(_gzip_json(p0)), _FakeResp(_gzip_json(p20))]
    with patch('services.tgb_common.urllib.request.urlopen', side_effect=responses):
        actions = fetch_friend_actions(pages=2, cookie='fake=1')
    assert {a['other_id'] for a in actions} == {1, 2}


def test_fetch_friend_actions_stops_on_empty_page():
    """空 record 应停止翻页"""
    p0 = {'status': True, 'errorCode': 0, 'dto': {'record': [_make_record(1)]}}
    p20_empty = {'status': True, 'errorCode': 0, 'dto': {'record': []}}
    p40 = {'status': True, 'errorCode': 0, 'dto': {'record': [_make_record(3)]}}
    responses = [_FakeResp(_gzip_json(p0)), _FakeResp(_gzip_json(p20_empty)), _FakeResp(_gzip_json(p40))]
    with patch('services.tgb_common.urllib.request.urlopen', side_effect=responses):
        actions = fetch_friend_actions(pages=3, cookie='fake=1')
    # 应该只拿到 p0 的，p20 空之后停
    assert len(actions) == 1
    assert actions[0]['other_id'] == 1


def test_fetch_friend_actions_detects_sso_redirect():
    fake = _FakeResp(_gzip_json({}), final_url='https://sso.tgb.cn/web/login/index?url=...')
    with patch('services.tgb_common.urllib.request.urlopen', return_value=fake):
        with pytest.raises(CookieExpiredError, match='登录页'):
            fetch_friend_actions(pages=1, cookie='expired=1')


def test_fetch_friend_actions_requires_cookie():
    with patch('services.tgb_spefocus_service.load_cookie', return_value=''):
        with pytest.raises(RuntimeError, match='Cookie 未配置'):
            fetch_friend_actions(pages=1)
