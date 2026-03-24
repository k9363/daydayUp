"""
统一 API 响应工具
提供标准化的成功/错误响应格式
"""
from flask import jsonify
from typing import Any, Optional, Dict
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class ApiResponse:
    """API 响应构建器"""

    # 响应码定义
    CODE_SUCCESS = 200
    CODE_CREATED = 201
    CODE_BAD_REQUEST = 400
    CODE_UNAUTHORIZED = 401
    CODE_FORBIDDEN = 403
    CODE_NOT_FOUND = 404
    CODE_CONFLICT = 409
    CODE_SERVER_ERROR = 500

    @staticmethod
    def success(data: Any = None, message: str = '操作成功', code: int = None) -> tuple:
        """
        成功响应

        Args:
            data: 响应数据
            message: 成功消息
            code: 自定义响应码（可选）

        Returns:
            (response, status_code)
        """
        response = {
            'code': code or ApiResponse.CODE_SUCCESS,
            'message': message,
            'data': data
        }
        return jsonify(response), response['code']

    @staticmethod
    def created(data: Any = None, message: str = '创建成功') -> tuple:
        """创建成功响应"""
        return ApiResponse.success(data, message, ApiResponse.CODE_CREATED)

    @staticmethod
    def error(message: str, code: int = None, errors: Any = None) -> tuple:
        """
        错误响应

        Args:
            message: 错误消息
            code: 错误码
            errors: 详细错误信息（可选）

        Returns:
            (response, status_code)
        """
        status_code = code or ApiResponse.CODE_SERVER_ERROR
        response = {
            'code': code or ApiResponse.CODE_SERVER_ERROR,
            'message': message
        }
        if errors is not None:
            response['errors'] = errors
        return jsonify(response), status_code

    @staticmethod
    def bad_request(message: str = '请求参数错误', errors: Any = None) -> tuple:
        """400 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_BAD_REQUEST, errors)

    @staticmethod
    def unauthorized(message: str = '未授权访问') -> tuple:
        """401 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_UNAUTHORIZED)

    @staticmethod
    def forbidden(message: str = '权限不足') -> tuple:
        """403 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_FORBIDDEN)

    @staticmethod
    def not_found(message: str = '资源不存在') -> tuple:
        """404 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_NOT_FOUND)

    @staticmethod
    def conflict(message: str = '资源冲突') -> tuple:
        """409 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_CONFLICT)

    @staticmethod
    def server_error(message: str = '服务器内部错误', errors: Any = None) -> tuple:
        """500 错误响应"""
        return ApiResponse.error(message, ApiResponse.CODE_SERVER_ERROR, errors)


def handle_api_error(func):
    """
    API 错误处理装饰器
    自动捕获异常并返回统一格式的错误响应
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"参数错误: {e}")
            return ApiResponse.bad_request(str(e))
        except PermissionError as e:
            logger.warning(f"权限错误: {e}")
            return ApiResponse.forbidden(str(e))
        except FileNotFoundError as e:
            logger.warning(f"文件未找到: {e}")
            return ApiResponse.not_found(str(e))
        except Exception as e:
            logger.exception(f"API 错误: {e}")
            return ApiResponse.server_error(str(e))
    return wrapper


def validate_required(data: Dict, *fields, message: str = None) -> Optional[str]:
    """
    验证必填字段

    Args:
        data: 待验证的数据字典
        *fields: 必填字段名
        message: 自定义错误消息

    Returns:
        错误消息字符串，如果有错误；否则返回 None
    """
    missing = [f for f in fields if not data.get(f)]
    if missing:
        field_names = '、'.join(missing)
        return message or f"缺少必填字段: {field_names}"
    return None
