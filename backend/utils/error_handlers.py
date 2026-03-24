"""
全局错误处理器
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from utils.api_response import ApiResponse
import logging

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """
    注册全局错误处理器

    Args:
        app: Flask 应用实例
    """

    @app.errorhandler(400)
    def bad_request(e):
        return ApiResponse.bad_request(str(e.description) if hasattr(e, 'description') else '请求参数错误')

    @app.errorhandler(401)
    def unauthorized(e):
        return ApiResponse.unauthorized('请先登录')

    @app.errorhandler(403)
    def forbidden(e):
        return ApiResponse.forbidden('权限不足')

    @app.errorhandler(404)
    def not_found(e):
        # API 路由返回 JSON，其他返回 HTML
        if request.path.startswith('/api/'):
            return ApiResponse.not_found('接口不存在')
        return e

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.path.startswith('/api/'):
            return ApiResponse.error('不支持的请求方法', 405)
        return e

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.exception(f"服务器内部错误: {e}")
        if request.path.startswith('/api/'):
            return ApiResponse.server_error('服务器内部错误')
        return e

    @app.errorhandler(Exception)
    def handle_exception(e):
        # 捕获所有 HTTP 异常
        if isinstance(e, HTTPException):
            if request.path.startswith('/api/'):
                return ApiResponse.error(e.description, e.code)
            return e

        # 其他异常
        logger.exception(f"未处理的异常: {e}")
        if request.path.startswith('/api/'):
            return ApiResponse.server_error('服务器内部错误')
        return e
