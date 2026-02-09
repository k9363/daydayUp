"""
复盘任务API路由
"""
import logging
from flask import Blueprint, request, jsonify
from services.review_service import get_review_task_service
from extensions import db

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

review_bp = Blueprint('review', __name__)


@review_bp.route('/task', methods=['POST'])
def create_task():
    """创建复盘任务"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'code': 400, 'message': '请求数据不能为空'}), 400
        
        task_name = data.get('taskName')
        trade_date = data.get('tradeDate')  # 直接使用交易日期
        review_type = data.get('reviewType', 'custom')
        dimensions = data.get('dimensions', [])
        rules = data.get('rules', [])
        
        # 数据源信息
        data_source_type = data.get('dataSourceType', 'baostock')
        data_source_name = data.get('dataSourceName', f'复盘数据 {trade_date}')
        data_source_desc = data.get('dataSourceDesc', '')
        
        if not task_name:
            return jsonify({'code': 400, 'message': '请输入任务名称'}), 400
        
        service = get_review_task_service()
        task = service.create_task(
            task_name=task_name,
            trade_date=trade_date,
            review_type=review_type,
            dimensions=dimensions,
            rules=rules,
            data_source_type=data_source_type,
            data_source_name=data_source_name,
            data_source_desc=data_source_desc
        )
        
        return jsonify({
            'code': 200,
            'message': '创建成功',
            'data': task.to_dict()
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """执行复盘任务"""
    try:
        service = get_review_task_service()
        task = service.execute_task(task_id)
        
        return jsonify({
            'code': 200,
            'message': '执行成功',
            'data': task.to_dict()
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/list', methods=['GET'])
def task_list():
    """获取任务列表"""
    try:
        include_completed = request.args.get('includeCompleted', 'false').lower() == 'true'
        
        service = get_review_task_service()
        tasks = service.get_task_list(include_completed)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': [t.to_dict_with_summary() for t in tasks]
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>', methods=['GET'])
def task_detail(task_id):
    """获取任务详情"""
    try:
        service = get_review_task_service()
        task = service.get_task(task_id)
        
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': task.to_dict()
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>/results', methods=['GET'])
def task_results(task_id):
    """获取任务结果"""
    try:
        service = get_review_task_service()
        results = service.get_task_results(task_id)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': [r.to_dict() for r in results]
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>/report', methods=['GET'])
def task_report(task_id):
    """获取分析报告"""
    try:
        service = get_review_task_service()
        report = service.get_report(task_id)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': report
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    try:
        service = get_review_task_service()
        success = service.delete_task(task_id)
        
        if not success:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404
        
        return jsonify({
            'code': 200,
            'message': '删除成功',
            'data': True
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/baostock', methods=['POST'])
def create_baostock_task():
    """创建Baostock复盘任务 - 获取指定日期全A股市场股票信息"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'code': 400, 'message': '请求数据不能为空'}), 400
        
        from datetime import datetime
        task_name = data.get('task_name', f"A股市场复盘 {datetime.now().strftime('%Y-%m-%d')}")
        trade_date = data.get('trade_date')  # 交易日期，YYYY-MM-DD格式
        review_type = data.get('review_type', 'daily')
        dimensions = data.get('dimensions', [])
        rules = data.get('rules', [])
        
        # 验证日期
        if not trade_date:
            return jsonify({'code': 400, 'message': '请指定交易日期(trade_date)'}), 400
        
        service = get_review_task_service()
        
        # 直接在任务中设置数据源信息（不再单独创建DataSource）
        task = service.create_task(
            task_name=task_name,
            trade_date=trade_date,
            review_type=review_type,
            dimensions=dimensions,
            rules=rules,
            data_source_type='baostock',
            data_source_name=f"Baostock A股数据 {trade_date}",
            data_source_desc=f"获取{trade_date}日全A股市场股票列表"
        )
        
        # 执行任务
        task = service.execute_baostock_task(task.id)
        
        return jsonify({
            'code': 200,
            'message': '创建成功',
            'data': task.to_dict_with_summary()
        })
        
    except Exception as e:
        import traceback
        logger.error(f"创建Baostock复盘任务失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 500, 'message': str(e)}), 500


@review_bp.route('/task/<int:task_id>/chart', methods=['GET'])
def task_chart_data(task_id):
    """获取任务图表数据"""
    try:
        from models.reviewresult import ReviewResult
        import json
        
        # 获取图表数据
        chart_result = ReviewResult.query.filter(
            ReviewResult.task_id == task_id,
            ReviewResult.dimension == '图表数据'
        ).first()
        
        if not chart_result or not chart_result.detail_data:
            return jsonify({'code': 404, 'message': '图表数据不存在'}), 404
        
        chart_data = json.loads(chart_result.detail_data)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': chart_data
        })
        
    except Exception as e:
        import traceback
        logger.error(f"获取图表数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 500, 'message': str(e)}), 500
