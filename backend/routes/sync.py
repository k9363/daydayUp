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
        # 刷新会话，确保获取最新数据
        db.session.expire_all()
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
        
        # 将任务参数提取到外部变量，避免在新线程中引用外部scope的Flask对象
        task_id = task.id
        task_start_date = task.start_date
        task_end_date = task.end_date
        task_frequency = task.frequency
        task_stock_type = task.stock_type

        def run_task():
            try:
                with app.app_context():
                    # 在新线程中创建独立的数据库会话，避免与主线程的session冲突
                    from sqlalchemy.orm import sessionmaker
                    from extensions import db
                    
                    # 使用 db 的 engine 创建新 session
                    engine = db.engine
                    Session = sessionmaker(bind=engine)
                    local_session = Session()
                    
                    try:
                        service.sync_kline_data(
                            db_session=local_session,
                            task_id=task_id,
                            start_date=task_start_date,
                            end_date=task_end_date,
                            frequency=task_frequency,
                            stock_type=task_stock_type
                        )
                    finally:
                        local_session.close()
            except Exception as e:
                import traceback
                logger.error(f"同步任务执行失败: {e}")
                logger.error(traceback.format_exc())

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

        # 刷新会话，确保获取最新数据
        db.session.expire_all()

        query = DataSyncTask.query
        if status:
            query = query.filter(DataSyncTask.status == status)

        tasks = query.order_by(DataSyncTask.create_time.desc()).limit(limit).all()

        return jsonify({
            'code': 200,
            'message': '操作成功',
            # light=True：列表视图不返回 ~70KB/行的 processed_codes、且只对 running 任务做实时 count，
            #   避免 4.5MB 响应 + 50 次 over 140 万行的 COUNT(*) 拖垮页面
            'data': [task.to_dict(light=True) for task in tasks]
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


@sync_bp.route('/kline/batch_range', methods=['POST'])
def kline_batch_range():
    """批量拉多只股票在指定区间内的首末日 K 线 + 区间汇总。

    用于板块联动分析：一次拿一个板块所有成分股在某交易区间的表现，
    LLM 看到的是"用户那段时间持有时板块的真实样子"，不是当前最新数据。

    Body:
        {
            "stock_codes": ["sh.600000", "sz.000001", ...],
            "start_date": "YYYYMMDD" 或 "YYYY-MM-DD",
            "end_date":   "YYYYMMDD" 或 "YYYY-MM-DD"
        }

    Returns:
        {code: 200, data: {
            "sh.600000": {first_close, last_close, pct_chg, high, low,
                          total_amount, days, first_date, last_date},
            ...
        }}
    """
    try:
        payload = request.get_json() or {}
        codes = payload.get('stock_codes') or []
        start = (payload.get('start_date') or '').replace('-', '')
        end = (payload.get('end_date') or '').replace('-', '')

        if not codes or not isinstance(codes, list):
            return jsonify({'code': 400, 'message': 'stock_codes 必须是非空列表'}), 400
        if not start or not end or len(start) != 8 or len(end) != 8:
            return jsonify({'code': 400, 'message': 'start_date / end_date 必填 YYYYMMDD'}), 400

        # ⚠️ stock_daily_kline.trade_date 存的是 'YYYY-MM-DD'（带横线），
        # 这里把 YYYYMMDD 转成带横线后再用于过滤
        start_iso = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        end_iso = f"{end[:4]}-{end[4:6]}-{end[6:8]}"

        # 去重
        codes = list(set(codes))

        from models.kline import StockDailyKLine

        # 一次性查所有股票的所有 K 线行（区间内）
        rows = db.session.query(
            StockDailyKLine.stock_code,
            StockDailyKLine.trade_date,
            StockDailyKLine.close_price,
            StockDailyKLine.high_price,
            StockDailyKLine.low_price,
            StockDailyKLine.turnover,
        ).filter(
            StockDailyKLine.stock_code.in_(codes),
            StockDailyKLine.trade_date >= start_iso,
            StockDailyKLine.trade_date <= end_iso,
        ).order_by(
            StockDailyKLine.stock_code,
            StockDailyKLine.trade_date,
        ).all()

        from collections import defaultdict
        by_code = defaultdict(list)
        for r in rows:
            by_code[r.stock_code].append(r)

        result = {}
        for code, ks in by_code.items():
            if not ks:
                continue
            first = ks[0]
            last = ks[-1]
            fc = float(first.close_price) if first.close_price is not None else None
            lc = float(last.close_price) if last.close_price is not None else None
            highs = [float(k.high_price) for k in ks if k.high_price is not None]
            lows = [float(k.low_price) for k in ks if k.low_price is not None]
            amts = [float(k.turnover) for k in ks if k.turnover is not None]
            pct = ((lc / fc) - 1) * 100 if (fc and lc) else None
            result[code] = {
                "first_close": fc,
                "last_close": lc,
                "first_date": first.trade_date,
                "last_date": last.trade_date,
                "pct_chg": pct,
                "high": max(highs) if highs else None,
                "low": min(lows) if lows else None,
                "total_amount": sum(amts) if amts else None,
                "avg_amount": (sum(amts) / len(amts)) if amts else None,
                "days": len(ks),
            }

        return jsonify({
            'code': 200,
            'data': result,
            'requested': len(codes),
            'matched': len(result),
            'start_date': start,
            'end_date': end,
        })
    except Exception as e:
        logger.exception("batch_range 失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


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
                model_class.week_open,
                model_class.week_high,
                model_class.week_low,
                model_class.week_close,
                model_class.volume,
                model_class.turnover,
                model_class.change_percent
            ).filter(
                model_class.stock_code == stock_code
            ).order_by(date_field.desc()).limit(limit)
        elif frequency == 'm':
            model_class = StockMonthlyKLine
            date_field = StockMonthlyKLine.trade_date
            query = db.session.query(
                model_class.trade_date,
                model_class.month_open,
                model_class.month_high,
                model_class.month_low,
                model_class.month_close,
                model_class.volume,
                model_class.turnover,
                model_class.change_percent
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


@sync_bp.route('/latest_close_snapshot', methods=['GET'])
def get_latest_close_snapshot():
    """返回最新交易日全市场最新一日 close 快照

    返回:
        {code, trade_date, total: <int>, data: [
          {stock_code, stock_name, close, change_percent, volume, turnover}, ...
        ]}

    供 TA-CN 等外部系统在每日复盘任务跑完后批量同步行情用，避免依赖 akshare
    全市场快照（不稳定且慢）。

    可选 query:
        date=YYYY-MM-DD : 指定日期（不指定 → 数据库里的最新交易日）
        stock_type=stock|etf|index|all（默认 all 但不含 inactive / bond）
    """
    try:
        from flask import request
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy import func

        requested_date = request.args.get('date')
        stock_type = request.args.get('stock_type', 'all')

        # 1. 找最新交易日
        if requested_date:
            trade_date = requested_date
        else:
            row = db.session.query(func.max(StockDailyKLine.trade_date)).first()
            trade_date = row[0] if row and row[0] else None
        if not trade_date:
            return jsonify({'code': 200, 'data': {'trade_date': None, 'total': 0, 'data': []}})

        # 2. 查这一日的全部 K 线 + 名称
        q = db.session.query(
            StockDailyKLine.stock_code,
            StockBasic.stock_name,
            StockBasic.stock_type,
            StockDailyKLine.close_price,
            StockDailyKLine.change_percent,
            StockDailyKLine.volume,
            StockDailyKLine.turnover,
        ).outerjoin(
            StockBasic, StockDailyKLine.stock_code == StockBasic.stock_code
        ).filter(
            StockDailyKLine.trade_date == trade_date
        )
        if stock_type in ('stock', 'etf', 'index'):
            q = q.filter(StockBasic.stock_type == stock_type)
        else:
            # 默认排除 inactive / bond / other
            q = q.filter(StockBasic.stock_type.in_(['stock', 'etf', 'index']))

        rows = q.all()
        data = []
        for r in rows:
            data.append({
                'stock_code': r.stock_code,
                'stock_name': r.stock_name or '',
                'stock_type': r.stock_type or '',
                'close': float(r.close_price) if r.close_price else None,
                'change_percent': float(r.change_percent) if r.change_percent else None,
                'volume': float(r.volume) if r.volume else None,
                'turnover': float(r.turnover) if r.turnover else None,
            })

        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'trade_date': trade_date,
                'total': len(data),
                'data': data,
            }
        })
    except Exception as e:
        logger.error(f"获取最新收盘快照失败: {e}")
        return jsonify({'code': 500, 'message': f'获取最新收盘快照失败: {str(e)}'}), 500


def register_sync_blueprint(app):
    """注册同步蓝图（用于非工厂模式）"""
    app.register_blueprint(sync_bp, url_prefix='/api/sync')

