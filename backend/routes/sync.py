"""
数据同步API路由
提供数据补充任务的创建、查询和管理功能
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
from services.data_sync_service import get_data_sync_service
from extensions import db
from models.kline import DataSyncTask

logger = logging.getLogger(__name__)

sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')


@sync_bp.route('/task', methods=['POST'])
def create_sync_task():
    """
    创建数据同步任务

    请求参数:
        - task_name: 任务名称
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        - frequency: K线频率 (daily, weekly, monthly, 5, 15, 30, 60)
        - stock_type: 股票类型 (all, sh, sz)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'message': '请求数据不能为空'}), 400

        task_name = data.get('task_name')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        frequency = data.get('frequency', 'daily')
        stock_type = data.get('stock_type', 'all')

        # 参数验证
        if not start_date:
            return jsonify({'code': 400, 'message': '请指定开始日期(start_date)'}), 400
        if not end_date:
            return jsonify({'code': 400, 'message': '请指定结束日期(end_date)'}), 400

        # 验证日期格式
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'code': 400, 'message': '日期格式错误，请使用 YYYY-MM-DD 格式'}), 400

        # 验证频率
        valid_frequencies = ['daily', 'weekly', 'monthly', '5', '15', '30', '60']
        if frequency not in valid_frequencies:
            return jsonify({
                'code': 400,
                'message': f'无效的频率，有效值: {", ".join(valid_frequencies)}'
            }), 400

        # 验证股票类型
        valid_stock_types = ['all', 'sh', 'sz']
        if stock_type not in valid_stock_types:
            return jsonify({
                'code': 400,
                'message': f'无效的股票类型，有效值: {", ".join(valid_stock_types)}'
            }), 400

        # 创建任务
        task = DataSyncTask()
        task.task_name = task_name or f"数据同步 {start_date} ~ {end_date} ({frequency})"
        task.start_date = start_date
        task.end_date = end_date
        task.frequency = frequency
        task.stock_type = stock_type
        task.status = 'pending'

        db.session.add(task)
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '任务创建成功',
            'data': task.to_dict()
        })

    except Exception as e:
        logger.exception("创建同步任务失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/task/<int:task_id>', methods=['GET'])
def get_sync_task(task_id):
    """获取同步任务详情"""
    try:
        task = DataSyncTask.query.get(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404

        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': task.to_dict()
        })

    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/task/<int:task_id>/start', methods=['POST'])
def start_sync_task(task_id):
    """启动同步任务"""
    try:
        from flask import current_app
        task = DataSyncTask.query.get(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404

        if task.status == 'running':
            return jsonify({'code': 400, 'message': '任务已在运行中'}), 400

        # 启动异步任务
        from threading import Thread
        service = get_data_sync_service()

        def run_task(app_ctx):
            try:
                with app_ctx:
                    service.sync_kline_data(
                        db_session=db.session,
                        task_id=task.id,
                        start_date=task.start_date,
                        end_date=task.end_date,
                        frequency=task.frequency,
                        stock_type=task.stock_type
                    )
            except Exception as e:
                logger.error(f"同步任务执行失败: {e}")

        from flask import Flask
        app = Flask(__name__)
        thread = Thread(target=run_task, args=(app.app_context(),))
        thread.start()

        return jsonify({
            'code': 200,
            'message': '任务已启动',
            'data': task.to_dict()
        })

    except Exception as e:
        logger.exception("启动同步任务失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_sync_task(task_id):
    """删除同步任务"""
    try:
        task = DataSyncTask.query.get(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404

        if task.status == 'running':
            return jsonify({'code': 400, 'message': '无法删除运行中的任务'}), 400

        db.session.delete(task)
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '删除成功'
        })

    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/tasks', methods=['GET'])
def get_sync_tasks():
    """获取同步任务列表"""
    try:
        status = request.args.get('status')
        limit = request.args.get('limit', 20, type=int)

        query = DataSyncTask.query
        if status:
            query = query.filter(DataSyncTask.status == status)

        tasks = query.order_by(DataSyncTask.create_time.desc()).limit(limit).all()

        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': [task.to_dict() for task in tasks]
        })

    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/frequency/options', methods=['GET'])
def get_frequency_options():
    """获取K线频率选项"""
    options = [
        {'value': 'daily', 'label': '日线', 'description': '每日K线数据'},
        {'value': 'weekly', 'label': '周线', 'description': '每周K线数据'},
        {'value': 'monthly', 'label': '月线', 'description': '每月K线数据'},
        {'value': '5', 'label': '5分钟', 'description': '5分钟K线数据'},
        {'value': '15', 'label': '15分钟', 'description': '15分钟K线数据'},
        {'value': '30', 'label': '30分钟', 'description': '30分钟K线数据'},
        {'value': '60', 'label': '60分钟', 'description': '60分钟K线数据'}
    ]

    return jsonify({
        'code': 200,
        'message': '操作成功',
        'data': options
    })


@sync_bp.route('/stock-type/options', methods=['GET'])
def get_stock_type_options():
    """获取股票类型选项"""
    options = [
        {'value': 'all', 'label': '全部A股', 'description': '上海和深圳交易所的全部A股'},
        {'value': 'sh', 'label': '上海A股', 'description': '上海交易所的A股'},
        {'value': 'sz', 'label': '深圳A股', 'description': '深圳交易所的A股'}
    ]

    return jsonify({
        'code': 200,
        'message': '操作成功',
        'data': options
    })


def register_sync_blueprint(app):
    """注册同步蓝图"""
    app.register_blueprint(sync_bp)

