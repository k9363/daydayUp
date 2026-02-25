"""
定时任务管理API
"""
from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)
scheduler_bp = Blueprint('scheduler', __name__)


def get_scheduler_service():
    """延迟导入scheduler_service，避免循环依赖"""
    from services.scheduler_service import scheduler_service as ss
    return ss


@scheduler_bp.route('/status', methods=['GET'])
def get_scheduler_status():
    """获取定时任务状态"""
    scheduler_service = get_scheduler_service()
    
    if scheduler_service is None:
        return jsonify({
            'code': 200,
            'data': {
                'running': False,
                'message': '定时任务调度器未初始化',
                'jobs': []
            }
        })
    
    jobs = scheduler_service.get_jobs()
    return jsonify({
        'code': 200,
        'data': {
            'running': scheduler_service.scheduler.running if scheduler_service.scheduler else False,
            'jobs': jobs
        }
    })


@scheduler_bp.route('/start', methods=['POST'])
def start_scheduler():
    """启动定时任务"""
    scheduler_service = get_scheduler_service()
    
    if scheduler_service is None:
        return jsonify({
            'code': 500,
            'message': '定时任务调度器未安装'
        })
    
    if scheduler_service.scheduler and scheduler_service.scheduler.running:
        return jsonify({
            'code': 200,
            'message': '定时任务已在运行中'
        })
    
    scheduler_service.start()
    return jsonify({
        'code': 200,
        'message': '定时任务已启动'
    })


@scheduler_bp.route('/stop', methods=['POST'])
def stop_scheduler_api():
    """停止定时任务"""
    scheduler_service = get_scheduler_service()
    
    if scheduler_service is None:
        return jsonify({
            'code': 500,
            'message': '定时任务调度器未安装'
        })
    
    if not scheduler_service.scheduler or not scheduler_service.scheduler.running:
        return jsonify({
            'code': 200,
            'message': '定时任务未在运行'
        })
    
    scheduler_service.stop()
    return jsonify({
        'code': 200,
        'message': '定时任务已停止'
    })


@scheduler_bp.route('/trigger', methods=['POST'])
def trigger_review():
    """手动触发复盘任务"""
    scheduler_service = get_scheduler_service()
    
    if scheduler_service is None:
        return jsonify({
            'code': 500,
            'message': '定时任务调度器未安装'
        })
    
    try:
        result = scheduler_service.trigger_now()
        return jsonify({
            'code': 200 if result.get('success') else 500,
            'data': result
        })
    except Exception as e:
        logger.error(f"手动触发复盘任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'执行失败: {str(e)}'
        })
