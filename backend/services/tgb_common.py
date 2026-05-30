"""
淘股吧抓取相关 service 的共用工具：cookie 加载、带失效检测的 JSON GET。
被 tgb_hot_service / tgb_spefocus_service 复用。
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import urllib.request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

MOBILE_UA = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
    'Mobile/15E148 Safari/604.1'
)
DESKTOP_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
)


class CookieExpiredError(RuntimeError):
    """Cookie 失效（被 302 跳 sso 或返回非 JSON）。捕获方应触发刷新流程。"""


def load_cookie() -> str:
    """优先 env TGB_COOKIE，其次 backend/.tgb_cookie 文件。"""
    env_v = os.environ.get('TGB_COOKIE', '').strip()
    if env_v:
        return env_v
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(backend_dir, '.tgb_cookie')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ''


def http_get_json(
    url: str,
    cookie: str,
    user_agent: str,
    referer: str,
    timeout: int = 15,
) -> dict:
    """带 gzip 兜底 + cookie 失效检测的 JSON GET。

    cookie 失效时服务器会 302 跳 sso.tgb.cn 或返回登录页 HTML，
    两种情况都抛 CookieExpiredError 让上游统一处理。
    """
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': user_agent,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': referer,
            'Cookie': cookie,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        if 'sso.tgb.cn' in final_url or '/login' in final_url:
            raise CookieExpiredError(f'被重定向到登录页：{final_url}')
        body = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        text = body.decode('utf-8', errors='replace')
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            head = text[:120].replace('\n', ' ')
            raise CookieExpiredError(
                f'响应不是 JSON（cookie 可能已失效）：{head}'
            ) from e
