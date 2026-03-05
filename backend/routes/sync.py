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

# 在应用工厂中通过 url_prefix='/api/sync' 统一配置前缀
sync_bp = Blueprint('sync', __name__)


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

        # 允许从 stopped 状态继续，或者启动新的任务
        if task.status not in ['pending', 'stopped', 'failed']:
            return jsonify({'code': 400, 'message': f'任务状态为 {task.status}，无法启动'}), 400

        # 立即更新任务状态为 running
        task.status = 'running'
        db.session.commit()

        # 启动异步任务
        from threading import Thread
        from flask import current_app
        service = get_data_sync_service()
        app = current_app._get_current_object()

        def run_task():
            try:
                with app.app_context():
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

        thread = Thread(target=run_task, daemon=True)
        thread.start()

        return jsonify({
            'code': 200,
            'message': '任务已启动',
            'data': task.to_dict()
        })

    except Exception as e:
        logger.exception("启动同步任务失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@sync_bp.route('/task/<int:task_id>/stop', methods=['POST'])
def stop_sync_task(task_id):
    """停止同步任务"""
    try:
        task = DataSyncTask.query.get(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'}), 404

        if task.status != 'running':
            return jsonify({'code': 400, 'message': '任务不在运行中'}), 400

        # 将任务状态设置为 stopped，用户可以继续从断点开始
        task.status = 'stopped'
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '任务已停止，可继续从断点开始',
            'data': task.to_dict()
        })

    except Exception as e:
        logger.exception("停止同步任务失败")
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


@sync_bp.route('/kline/<stock_code>', methods=['GET'])
def get_stock_kline(stock_code):
    """
    获取股票K线数据
    
    请求参数:
        - stock_code: 股票代码 (如 sh.600000)
        - frequency: K线频率 (d=日线, w=周线, m=月线)
        - limit: 返回记录数，默认100
    
    返回:
        K线数据列表，按交易日期倒序
    """
    try:
        frequency = request.args.get('frequency', 'd')
        limit = int(request.args.get('limit', 100))
        
        from models.kline import StockDailyKLine, StockWeeklyKLine, StockMonthlyKLine
        
        # 根据频率获取不同的表
        if frequency == 'w':
            model_class = StockWeeklyKLine
            date_field = StockWeeklyKLine.trade_date
            query = db.session.query(
                model_class.trade_date,
                model_class.open,
                model_class.high,
                model_class.low,
                model_class.close,
                model_class.volume,
                model_class.amount,
                model_class.pct_chg
            ).filter(
                model_class.stock_code == stock_code
            ).order_by(date_field.desc()).limit(limit)
        elif frequency == 'm':
            model_class = StockMonthlyKLine
            date_field = StockMonthlyKLine.trade_date
            query = db.session.query(
                model_class.trade_date,
                model_class.open,
                model_class.high,
                model_class.low,
                model_class.close,
                model_class.volume,
                model_class.amount,
                model_class.pct_chg
            ).filter(
                model_class.stock_code == stock_code
            ).order_by(date_field.desc()).limit(limit)
        else:
            # 日线 - 使用 stock_daily_kline 表 (与数据同步保存的表一致)
            model_class = StockDailyKLine
            date_field = StockDailyKLine.trade_date
            query = db.session.query(
                model_class.trade_date,
                model_class.open_price,
                model_class.high_price,
                model_class.low_price,
                model_class.close_price,
                model_class.volume,
                model_class.turnover,
                model_class.change_percent
            ).filter(
                model_class.stock_code == stock_code
            ).order_by(date_field.desc()).limit(limit)
        
        data = query.all()
        
        # 转换为字典列表
        result = []
        for item in data:
            # 处理元组和对象两种情况
            if isinstance(item, tuple):
                result.append({
                    'trade_date': item[0],
                    'open': float(item[1]) if item[1] else None,
                    'high': float(item[2]) if item[2] else None,
                    'low': float(item[3]) if item[3] else None,
                    'close': float(item[4]) if item[4] else None,
                    'volume': float(item[5]) if item[5] else None,
                    'amount': float(item[6]) if item[6] else None,
                    'pct_chg': float(item[7]) if len(item) > 7 and item[7] else None
                })
            else:
                result.append({
                    'trade_date': item.trade_date,
                    'open': float(item.open_price) if item.open_price else None,
                    'high': float(item.high_price) if item.high_price else None,
                    'low': float(item.low_price) if item.low_price else None,
                    'close': float(item.close_price) if item.close_price else None,
                    'volume': float(item.volume) if item.volume else None,
                    'amount': float(item.turnover) if item.turnover else None,
                    'pct_chg': float(item.change_percent) if item.change_percent else None
                })
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': result
        })
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取K线数据失败: {str(e)}'
        }), 500


def register_sync_blueprint(app):
    """注册同步蓝图（用于非工厂模式）"""
    app.register_blueprint(sync_bp, url_prefix='/api/sync')

