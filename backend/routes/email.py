"""邮件相关路由：手动发送复盘邮件 / SMTP 测试。

端点（蓝图前缀 /api/email）：
  POST /send-review/<task_id>   手动给指定复盘任务发邮件
                                Body 可选 {"recipients": ["a@x.com", "b@y.com"]} 覆盖 env 默认
  POST /test                    发一封测试邮件验证 SMTP（不依赖复盘数据）
                                Body 同上可覆盖收件人
"""
import logging

from flask import Blueprint, jsonify, request

from services.email_service import (
    is_review_email_enabled,
    send_daily_review_email,
    send_test_email,
)

logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)


def _parse_recipients(payload: dict):
    """从请求体解析 recipients 字段，兼容 str / list。"""
    if not payload:
        return None
    raw = payload.get('recipients') or payload.get('to')
    if not raw:
        return None
    if isinstance(raw, str):
        return [r.strip() for r in raw.split(',') if r.strip()]
    if isinstance(raw, list):
        return [str(r).strip() for r in raw if str(r).strip()]
    return None


@email_bp.route('/send-review/<int:task_id>', methods=['POST'])
def send_review(task_id: int):
    """手动重发某个复盘任务的邮件。"""
    payload = request.get_json(silent=True) or {}
    recipients = _parse_recipients(payload)
    # 手动调用始终发送（忽略 EMAIL_REVIEW_ENABLED 开关，便于临时关闭自动但手动可用）
    result = send_daily_review_email(task_id, recipients=recipients, skip_if_disabled=False)
    code = 200 if result.get('success') else 400
    return jsonify({'code': code, 'message': '操作成功' if result.get('success') else '发送失败',
                    'data': result}), code


@email_bp.route('/test', methods=['POST'])
def send_test():
    """发一封 SMTP 测试邮件。"""
    payload = request.get_json(silent=True) or {}
    recipients = _parse_recipients(payload)
    result = send_test_email(recipients=recipients)
    code = 200 if result.get('success') else 400
    return jsonify({'code': code, 'message': '操作成功' if result.get('success') else '发送失败',
                    'data': result}), code


@email_bp.route('/status', methods=['GET'])
def status():
    """查询邮件功能状态（是否启用、SMTP 是否配齐、是否有默认收件人），不暴露密码。"""
    import os
    from services.email_service import _default_recipients, _smtp_config
    cfg = _smtp_config()
    return jsonify({
        'code': 200,
        'message': '操作成功',
        'data': {
            'enabled': is_review_email_enabled(),
            'smtp_configured': bool(cfg['host'] and cfg['user'] and cfg['password']),
            'smtp_host': cfg['host'] or None,
            'smtp_port': cfg['port'],
            'smtp_use_ssl': cfg['use_ssl'],
            'from_addr': cfg['from_addr'] or None,
            'default_recipients_count': len(_default_recipients()),
            'public_url': os.getenv('DAYDAYUP_PUBLIC_URL', 'http://192.168.31.123:20080'),
        }
    })
