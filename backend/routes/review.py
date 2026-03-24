"""
复盘任务API路由
"""
import logging
from flask import Blueprint, request, current_app
from services.review_service import get_review_task_service
from extensions import db
from utils.api_response import ApiResponse, validate_required

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

review_bp = Blueprint('review', __name__)


@review_bp.route('/task', methods=['POST'])
def create_task():
    """创建复盘任务"""
    try:
        data = request.get_json()

        if not data:
            return ApiResponse.bad_request('请求数据不能为空')

        # 验证必填字段
        error = validate_required(data, 'taskName', 'tradeDate')
        if error:
            return ApiResponse.bad_request(error)

        task_name = data.get('taskName')
        trade_date = data.get('tradeDate')
        review_type = data.get('reviewType', 'custom')
        dimensions = data.get('dimensions', [])
        rules = data.get('rules', [])
        overwrite = data.get('overwrite', False)

        data_source_type = data.get('dataSourceType', 'baostock')
        data_source_name = data.get('dataSourceName', f'复盘数据 {trade_date}')
        data_source_desc = data.get('dataSourceDesc', '')

        # 检查该交易日是否已存在任务
        from models.reviewtask import ReviewTask
        existing_task = ReviewTask.query.filter(
            ReviewTask.trade_date == trade_date,
            ReviewTask.data_source_type == data_source_type
        ).first()

        if existing_task and not overwrite:
            return ApiResponse.conflict(
                f'该交易日 {trade_date} 已存在复盘任务',
            )

        # 如果存在且需要覆盖，删除旧任务
        if existing_task and overwrite:
            # 先保存旧任务的笔记（基于交易日期）
            from models.dailynote import DailyNote
            old_note = DailyNote.query.filter_by(trade_date=trade_date).first()
            saved_market_analysis = old_note.market_analysis if old_note else None
            saved_next_action = old_note.next_action if old_note else None

            # 删除旧任务及其结果
            from models.reviewresult import ReviewResult
            ReviewResult.query.filter(ReviewResult.task_id == existing_task.id).delete()
            db.session.delete(existing_task)
            db.session.commit()

            # 恢复笔记
            if saved_market_analysis is not None or saved_next_action is not None:
                note = DailyNote.query.filter_by(trade_date=trade_date).first()
                if note:
                    if saved_market_analysis is not None:
                        note.market_analysis = saved_market_analysis
                    if saved_next_action is not None:
                        note.next_action = saved_next_action
                else:
                    note = DailyNote(
                        trade_date=trade_date,
                        market_analysis=saved_market_analysis,
                        next_action=saved_next_action
                    )
                    db.session.add(note)
                db.session.commit()

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

        return ApiResponse.success(task.to_dict(), '创建成功')

    except Exception as e:
        logger.exception(f"创建复盘任务失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>', methods=['GET'])
def get_task_detail(task_id):
    """获取任务详情"""
    try:
        service = get_review_task_service()
        task = service.get_task(task_id)

        if not task:
            return ApiResponse.not_found('任务不存在')

        return ApiResponse.success(task.to_dict())

    except Exception as e:
        logger.exception(f"获取任务详情失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """执行复盘任务"""
    try:
        service = get_review_task_service()
        task = service.execute_task(task_id)

        if not task:
            return ApiResponse.not_found('任务不存在')

        return ApiResponse.success(task.to_dict(), '执行成功')

    except Exception as e:
        logger.exception(f"执行复盘任务失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/list', methods=['GET'])
def task_list():
    """获取任务列表"""
    try:
        include_completed = request.args.get('includeCompleted', 'false').lower() == 'true'
        trade_date = request.args.get('tradeDate', '').strip() or None
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 20, type=int)

        page_size = min(page_size, 100)

        service = get_review_task_service()
        result = service.get_task_list(include_completed, trade_date, page, page_size)

        return ApiResponse.success({
            'items': [t.to_dict_with_summary() for t in result['items']],
            'total': result['total'],
            'page': result['page'],
            'page_size': result['page_size'],
            'total_pages': result['total_pages']
        })

    except Exception as e:
        logger.exception(f"获取任务列表失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>', methods=['GET'])
def task_detail(task_id):
    """获取任务详情"""
    try:
        service = get_review_task_service()
        task = service.get_task(task_id)

        if not task:
            return ApiResponse.not_found('任务不存在')

        return ApiResponse.success(task.to_dict())

    except Exception as e:
        logger.exception(f"获取任务详情失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>/results', methods=['GET'])
def task_results(task_id):
    """获取任务结果"""
    try:
        service = get_review_task_service()
        results = service.get_task_results(task_id)

        return ApiResponse.success([r.to_dict() for r in results])

    except Exception as e:
        logger.exception(f"获取任务结果失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>/report', methods=['GET'])
def task_report(task_id):
    """获取分析报告"""
    try:
        service = get_review_task_service()
        report = service.get_report(task_id)

        return ApiResponse.success(report)

    except Exception as e:
        logger.exception(f"获取分析报告失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    try:
        service = get_review_task_service()
        success = service.delete_task(task_id)

        if not success:
            return ApiResponse.not_found('任务不存在')

        return ApiResponse.success(True, '删除成功')

    except Exception as e:
        logger.exception(f"删除任务失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/baostock', methods=['POST'])
def create_baostock_task():
    """创建Baostock复盘任务 - 获取指定日期全A股市场股票信息"""
    try:
        data = request.get_json()

        if not data:
            return ApiResponse.bad_request('请求数据不能为空')

        from datetime import datetime
        task_name = data.get('task_name', f"A股市场复盘 {datetime.now().strftime('%Y-%m-%d')}")
        trade_date = data.get('trade_date')
        review_type = data.get('review_type', 'daily')
        dimensions = data.get('dimensions', [])
        rules = data.get('rules', [])
        stock_filter = data.get('stock_filter', None)
        overwrite = data.get('overwrite', False)

        if not trade_date:
            return ApiResponse.bad_request('请指定交易日期(trade_date)')

        from models.reviewtask import ReviewTask
        existing_task = ReviewTask.query.filter(
            ReviewTask.trade_date == trade_date,
            ReviewTask.data_source_type == 'baostock'
        ).first()

        if existing_task and not overwrite:
            return ApiResponse.conflict(f'该交易日 {trade_date} 已存在复盘任务')

        # 如果存在且需要覆盖，删除旧任务
        if existing_task and overwrite:
            from models.dailynote import DailyNote
            old_note = DailyNote.query.filter_by(trade_date=trade_date).first()
            saved_market_analysis = old_note.market_analysis if old_note else None
            saved_next_action = old_note.next_action if old_note else None

            from models.reviewresult import ReviewResult
            ReviewResult.query.filter(ReviewResult.task_id == existing_task.id).delete()
            db.session.delete(existing_task)
            db.session.commit()

            if saved_market_analysis is not None or saved_next_action is not None:
                note = DailyNote.query.filter_by(trade_date=trade_date).first()
                if note:
                    if saved_market_analysis is not None:
                        note.market_analysis = saved_market_analysis
                    if saved_next_action is not None:
                        note.next_action = saved_next_action
                else:
                    note = DailyNote(
                        trade_date=trade_date,
                        market_analysis=saved_market_analysis,
                        next_action=saved_next_action
                    )
                    db.session.add(note)
                db.session.commit()

        service = get_review_task_service()

        task = service.create_task(
            task_name=task_name,
            trade_date=trade_date,
            review_type=review_type,
            dimensions=dimensions,
            rules=rules,
            stock_filter=stock_filter,
            data_source_type='baostock',
            data_source_name=f"Baostock A股数据 {trade_date}",
            data_source_desc=f"获取{trade_date}日全A股市场股票列表"
        )

        task_response = task.to_dict_with_summary()
        task_id = task.id

        def run_baostock_task(task_id, app_instance):
            from extensions import db
            from services.review_service import ReviewTaskService

            with app_instance.app_context():
                service = ReviewTaskService()
                try:
                    service.execute_baostock_task(task_id)
                except Exception as e:
                    logger.error(f"Baostock复盘任务执行失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

        from threading import Thread
        app = current_app._get_current_object()
        thread = Thread(target=run_baostock_task, args=(task_id, app))
        thread.daemon = True
        thread.start()

        return ApiResponse.success(task_response, '任务已创建，正在后台执行')

    except Exception as e:
        logger.exception(f"创建Baostock任务失败: {e}")
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/baostock/batch', methods=['POST'])
def create_baostock_batch_tasks():
    """按日期范围批量创建Baostock复盘任务，每个交易日（周一至周五）各建一个任务并顺序异步执行"""
    try:
        from datetime import datetime, timedelta
        from models.reviewtask import ReviewTask

        data = request.get_json()
        if not data:
            return ApiResponse.bad_request('请求数据不能为空')

        start_date = data.get('start_date')
        end_date   = data.get('end_date')
        stock_filter = data.get('stock_filter', None)
        overwrite  = data.get('overwrite', False)

        if not start_date or not end_date:
            return ApiResponse.bad_request('请指定 start_date 和 end_date')

        # 生成范围内所有工作日
        try:
            d_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            d_end   = datetime.strptime(end_date,   '%Y-%m-%d').date()
        except ValueError:
            return ApiResponse.bad_request('日期格式错误，请使用 YYYY-MM-DD')

        if d_start > d_end:
            return ApiResponse.bad_request('开始日期不能晚于结束日期')

        # 调用 baostock 查询范围内实际交易日
        import baostock as bs
        try:
            rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
            trade_dates = []
            while (rs.error_code == '0') and rs.next():
                row = rs.get_row_data()
                # row[0]=calendar_date, row[1]=is_trading_day ('1'=交易日)
                if str(row[1]) == '1':
                    trade_dates.append(row[0])
        except Exception as e:
            logger.warning(f"baostock query_trade_dates 失败，降级为工作日过滤: {e}")
            # 降级：用工作日过滤
            cur = d_start
            trade_dates = []
            while cur <= d_end:
                if cur.weekday() < 5:
                    trade_dates.append(cur.strftime('%Y-%m-%d'))
                cur += timedelta(days=1)

        if not trade_dates:
            return ApiResponse.bad_request('所选范围内无交易日')

        service = get_review_task_service()
        created_tasks = []
        skipped_dates = []

        for td in trade_dates:
            existing = ReviewTask.query.filter_by(trade_date=td, data_source_type='baostock').first()
            if existing and not overwrite:
                skipped_dates.append(td)
                continue
            if existing and overwrite:
                from models.reviewresult import ReviewResult
                ReviewResult.query.filter_by(task_id=existing.id).delete()
                db.session.delete(existing)
                db.session.commit()

            task = service.create_task(
                task_name=f"{td} 日复盘",
                trade_date=td,
                review_type='daily',
                dimensions=[],
                rules=[],
                stock_filter=stock_filter,
                data_source_type='baostock',
                data_source_name=f"Baostock A股数据 {td}",
                data_source_desc=f"获取{td}日全A股市场股票列表"
            )
            created_tasks.append(task.id)

        # 顺序执行所有新建任务（单个后台线程，避免并发 Baostock 连接冲突）
        def run_batch(task_ids, app_obj):
            from services.review_service import ReviewTaskService
            from models.reviewtask import ReviewTask
            import time
            with app_obj.app_context():
                svc = ReviewTaskService()
                for tid in task_ids:
                    try:
                        svc.execute_baostock_task(tid)
                        
                        # 如果任务进入 waiting_for_sync 状态，等待同步完成后再继续
                        # 需要重新查询任务状态，而不是使用已缓存的对象
                        task = ReviewTask.query.get(tid)
                        wait_count = 0
                        max_wait_count = 300  # 最多等待10分钟（300 * 2秒）
                        while task and task.status == 'waiting_for_sync':
                            wait_count += 1
                            if wait_count % 15 == 0:  # 每30秒打印一次日志
                                logger.info(f"等待数据同步完成: task_id={tid}, 已等待 {wait_count * 2} 秒")
                            if wait_count >= max_wait_count:
                                logger.error(f"等待数据同步超时: task_id={tid}, 跳过此任务")
                                break
                            time.sleep(2)  # 每2秒检查一次
                            # 重新查询以获取最新状态
                            db.session.expire(task)
                            task = ReviewTask.query.get(tid)
                            
                        # 如果任务已完成或失败，记录日志
                        if task:
                            if task.status == 'completed':
                                logger.info(f"复盘任务 {tid} 已完成")
                            elif task.status == 'failed':
                                logger.error(f"复盘任务 {tid} 失败: {task.error_message}")
                            elif task.status == 'waiting_for_sync':
                                logger.error(f"复盘任务 {tid} 等待同步超时，跳过")
                                
                    except Exception as e:
                        logger.error(f"批量复盘任务 {tid} 执行失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

        if created_tasks:
            from threading import Thread
            app = current_app._get_current_object()
            Thread(target=run_batch, args=(created_tasks, app), daemon=True).start()

        return ApiResponse.success({
                'created': len(created_tasks),
                'skipped': skipped_dates,
                'task_ids': created_tasks
            }, f'成功创建 {len(created_tasks)} 个任务，跳过 {len(skipped_dates)} 个已存在日期')

    except Exception as e:
        import traceback
        logger.error(f"批量创建复盘任务失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))


@review_bp.route('/task/<int:task_id>/chart', methods=['GET'])
def task_chart_data(task_id):
    """获取任务图表数据"""
    try:
        from models.reviewresult import ReviewResult
        from models.reviewtask import ReviewTask
        import json
        
        # 获取该任务的所有结果数据
        all_results = ReviewResult.query.filter(
            ReviewResult.task_id == task_id
        ).all()
        
        if not all_results:
            return ApiResponse.not_found('图表数据不存在')
        
        # 整合数据为图表格式
        chart_data = {
            'summary': {},
            'sectors': [],
            'top100Detail': [],
            'indexData': [],
            'charts': {
                'sectorPie': {'labels': [], 'data': []},
                'sectorBar': {'labels': [], 'data': []},
                'amountTop10': {'labels': [], 'data': []}
            }
        }
        
        # 处理所有结果
        for result in all_results:
            if result.dimension == '总体统计' and result.detail_data:
                try:
                    summary_data = json.loads(result.detail_data)
                    chart_data['summary']['totalStocks'] = summary_data.get('totalStocks', 0)
                    chart_data['summary']['top100Count'] = summary_data.get('top100Count', 0)
                    chart_data['summary']['tradeDate'] = summary_data.get('tradeDate', '')
                    chart_data['summary']['获取股票数'] = result.metric_value
                except:
                    pass
            
            # 处理成交额排名数据
            elif result.dimension == '成交额排名' and result.detail_data:
                try:
                    detail = json.loads(result.detail_data)
                    # 提取 totalAmount 和 avgAmount
                    chart_data['summary']['totalAmount'] = detail.get('totalTurnover', detail.get('totalAmount', 0))
                    chart_data['summary']['avgAmount'] = detail.get('avgTurnover', detail.get('avgAmount', 0))
                    
                    # 前端期望 'stocks' 字段
                    chart_data['top100Detail'] = detail.get('stocks', detail.get('top10', []))
                except:
                    chart_data['top100Detail'] = []
            
            # 处理因子分析数据 - 合并到top100Detail中
            elif result.dimension == '因子分析' and result.detail_data:
                try:
                    detail = json.loads(result.detail_data)
                    factor_stocks = detail.get('stocks', [])
                    # 如果已有top100Detail，将因子数据合并进去
                    if chart_data.get('top100Detail'):
                        # 创建stock_code到因子数据的映射
                        factor_map = {s['code']: s for s in factor_stocks}
                        # 为已有的股票添加因子数据
                        for stock in chart_data['top100Detail']:
                            code = stock.get('code')
                            if code in factor_map:
                                factor_data = factor_map[code]
                                stock['totalScore'] = factor_data.get('totalScore', 0)
                                stock['factor1Rank'] = factor_data.get('factor1Rank', 0)
                                stock['factor2MA'] = factor_data.get('factor2MA', 0)
                                stock['factor3Vol'] = factor_data.get('factor3Vol', 0)
                                stock['factor4Amt'] = factor_data.get('factor4Amt', 0)
                    # 保存因子分析的top10股票用于展示
                    chart_data['top10FactorStocks'] = factor_stocks
                except Exception as e:
                    logger.warning(f"处理因子分析数据失败: {e}")
            
            # 处理指数行情数据
            elif result.dimension == '指数行情' and result.detail_data:
                try:
                    detail = json.loads(result.detail_data)
                    chart_data['indexData'] = detail.get('indexes', [])
                except:
                    pass
            
            # 处理板块得分数据
            elif result.dimension == '板块得分' and result.detail_data:
                try:
                    sector_scores = json.loads(result.detail_data)
                    # 兼容字典和列表格式 - 前端期望 'sectors' 字段
                    if isinstance(sector_scores, dict):
                        chart_data['sectors'] = sector_scores.get('sectors', [])
                    elif isinstance(sector_scores, list):
                        chart_data['sectors'] = sector_scores
                    else:
                        chart_data['sectors'] = []
                except:
                    pass
            
            # 处理因子体系数据（因子树）
            elif result.dimension == '因子体系' and result.detail_data:
                try:
                    factor_tree_data = json.loads(result.detail_data)
                    chart_data['factorTree'] = factor_tree_data
                except:
                    pass
            
            # 处理市场/大盘指数数据
            elif result.dimension == '市场':
                try:
                    # 检查是否有 detail_data（树状结构）
                    if result.detail_data:
                        detail = json.loads(result.detail_data)
                        if detail.get('type') == 'market_overview':
                            # 新的树状结构
                            chart_data['marketDetail'] = detail
                            chart_data['market'] = {
                                '大盘综合得分': result.metric_value,
                                # 从 factors 中提取
                                **{name: info.get('value', 0) for name, info in detail.get('factors', {}).items()}
                            }
                        else:
                            # 旧的扁平结构
                            if 'market' not in chart_data:
                                chart_data['market'] = {}
                            chart_data['market'][result.metric_name] = result.metric_value
                    else:
                        # 没有 detail_data，使用旧的扁平结构
                        if 'market' not in chart_data:
                            chart_data['market'] = {}
                        chart_data['market'][result.metric_name] = result.metric_value
                except:
                    pass
        
        # 如果有 top100Detail，更新 Top10 图表（数据已除以10000）
        if chart_data.get('top100Detail') and isinstance(chart_data['top100Detail'], list):
            top10 = chart_data['top100Detail'][:10]
            # 前端期望的字段名: code, name, amount
            chart_data['charts']['amountTop10']['labels'] = [f"{s.get('code', '')} {s.get('name', '')}" for s in top10]
            chart_data['charts']['amountTop10']['data'] = [s.get('amount', 0) for s in top10]
        
        # 更新板块饼图和柱状图数据
        sectors_list = chart_data.get('sectors', [])
        if isinstance(sectors_list, list) and len(sectors_list) > 0:
            # 前端期望的字段名: sector, count, totalAmount, avgPctChg
            chart_data['charts']['sectorPie']['labels'] = [s.get('sector', s.get('name', '')) for s in sectors_list[:10]]
            chart_data['charts']['sectorPie']['data'] = [s.get('score', s.get('count', 0)) for s in sectors_list[:10]]
            chart_data['charts']['sectorBar']['labels'] = [s.get('sector', s.get('name', '')) for s in sectors_list[:10]]
            chart_data['charts']['sectorBar']['data'] = [s.get('count', s.get('stockCount', 0)) for s in sectors_list[:10]]
        
        # 如果 summary 中没有交易日期，则从任务表中补充
        if not chart_data['summary'].get('tradeDate'):
            task = ReviewTask.query.get(task_id)
            if task and task.trade_date:
                chart_data['summary']['tradeDate'] = task.trade_date
        
        # 如果 summary 中有数据总量，使用它
        if '数据总量' in chart_data['summary']:
            chart_data['summary']['totalStocks'] = int(chart_data['summary'].get('数据总量', 0))
        
        # 设置默认值
        chart_data['summary'].setdefault('totalAmount', 0)
        chart_data['summary'].setdefault('avgAmount', 0)
        
        # ========== 获取因子定义信息 ==========
        try:
            from models.factor import FactorDefine
            from models.expression import ScoreExpression
            
            # 获取默认表达式
            default_expr = ScoreExpression.query.filter(
                ScoreExpression.scope == 'stock',
                ScoreExpression.is_default == True,
                ScoreExpression.is_active == True
            ).first()
            
            # 从表达式中提取使用的因子代码
            factor_codes_in_expr = []
            import re
            var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
            exclude_funcs = {'ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG', 
                           'abs', 'sqrt', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log', 'AND', 'OR', 'NOT'}
            if default_expr and default_expr.factors:
                factor_codes_in_expr = default_expr.factors
            elif default_expr and default_expr.expression:
                # 从表达式中提取因子代码
                matches = re.findall(var_pattern, default_expr.expression)
                factor_codes_in_expr = [m for m in matches if m not in exclude_funcs]
            
            # 排除 Python 代码计算的因子（这些因子的依赖在代码内处理，不需要展示）
            python_factors = [f.factor_code for f in FactorDefine.query.filter(
                FactorDefine.calculation_method == 'python',
                FactorDefine.factor_code.in_(factor_codes_in_expr)
            ).all()]
            factor_codes_in_expr = [f for f in factor_codes_in_expr if f not in python_factors]
            logger.info(f"📊 初始因子列表（排除Python因子）: {factor_codes_in_expr}")
            
            # 递归查找所有依赖的因子（包括表达式因子的依赖）
            def find_all_dependencies(factor_codes, visited=None):
                if visited is None:
                    visited = set(factor_codes)
                else:
                    visited.update(factor_codes)
                
                # 查找这些因子的表达式依赖
                new_deps = set()
                sub_factors = FactorDefine.query.filter(
                    FactorDefine.factor_code.in_(factor_codes),
                    FactorDefine.expression.isnot(None),
                    FactorDefine.calculation_method != 'python'  # 排除 Python 代码计算的因子
                ).all()
                
                for sf in sub_factors:
                    if sf.expression:
                        matches = re.findall(var_pattern, sf.expression)
                        deps = {m for m in matches if m not in exclude_funcs and m not in visited}
                        new_deps.update(deps)
                
                if new_deps:
                    find_all_dependencies(new_deps, visited)
                
                return visited
            
            all_needed_factors = find_all_dependencies(factor_codes_in_expr)
            logger.info(f"📊 表达式因子及其依赖: {all_needed_factors}")
            
            # 只获取表达式中使用的因子定义（包括依赖的原子因子）
            if all_needed_factors:
                stock_factors = FactorDefine.query.filter(
                    FactorDefine.factor_scope == 'stock',
                    FactorDefine.is_active == True,
                    FactorDefine.factor_code.in_(all_needed_factors)
                ).order_by(FactorDefine.factor_code).all()
            else:
                stock_factors = []
            
            factor_columns = [{
                'code': f.factor_code,
                'name': f.factor_name,
                'source': f.source,
                'expression': f.expression,
                'calculation_method': f.calculation_method
            } for f in stock_factors]
            
            chart_data['factorConfig'] = {
                'columns': factor_columns,
                'expression': default_expr.expression if default_expr else '',
                'expressionName': default_expr.expression_name if default_expr else ''
            }
        except Exception as e:
            import traceback
            logger.warning(f"获取因子配置信息失败: {e}")
            logger.warning(traceback.format_exc())
            chart_data['factorConfig'] = {
                'columns': [],
                'expression': '',
                'expressionName': ''
            }
        
        return ApiResponse.success(chart_data)
        
    except Exception as e:
        import traceback
        logger.error(f"获取图表数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))


@review_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """获取首页仪表盘数据 - 支持选择交易日时间范围，默认近10个交易日"""
    try:
        import json
        from models.reviewtask import ReviewTask
        from models.reviewresult import ReviewResult
        
        # 获取查询参数
        from flask import request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        days = request.args.get('days', 10, type=int)
        
        # 构建查询条件
        query = ReviewTask.query.filter(ReviewTask.status == 'completed')
        
        if start_date and end_date:
            # 如果提供了日期范围，按范围查询
            query = query.filter(
                ReviewTask.trade_date >= start_date,
                ReviewTask.trade_date <= end_date
            ).order_by(ReviewTask.trade_date.desc())
        elif start_date:
            # 只提供开始日期，获取从该日期到当前的所有数据
            query = query.filter(
                ReviewTask.trade_date >= start_date
            ).order_by(ReviewTask.trade_date.desc())
        elif end_date:
            # 只提供结束日期，获取从最早到该日期的数据
            query = query.filter(
                ReviewTask.trade_date <= end_date
            ).order_by(ReviewTask.trade_date.desc())
        else:
            # 默认获取近10个交易日
            query = query.order_by(ReviewTask.trade_date.desc())
        
        # 如果没有指定日期范围，则限制数量
        if not start_date and not end_date:
            recent_tasks = query.limit(days).all()
        else:
            # 如果指定了日期范围，获取所有符合条件的数据
            recent_tasks = query.all()
        
        dashboard_data = []
        
        for task in recent_tasks:
            task_info = {
                'taskId': task.id,
                'taskName': task.task_name,
                'tradeDate': task.trade_date,
                'sectors': [],  # 板块前10
                'factorStocks': [],  # 因子得分Top10
                'marketScore': None,  # 大盘综合得分
                'topStockScore': None  # 因子Top10股票得分
            }
            
            # 获取板块得分数据
            sector_result = ReviewResult.query.filter(
                ReviewResult.task_id == task.id,
                ReviewResult.dimension == '板块得分'
            ).first()
            
            if sector_result and sector_result.detail_data:
                try:
                    sector_data = json.loads(sector_result.detail_data)
                    sectors_list = sector_data.get('sectors', [])
                    # 取前10个板块
                    task_info['sectors'] = [
                        {
                            'name': s.get('name', s.get('sector', '')),
                            'score': s.get('score', 0)
                        }
                        for s in sectors_list[:10]
                    ]
                    # 板块得分列表（按名次排序）
                    task_info['sectorScores'] = [s.get('score', 0) for s in sectors_list[:10]]
                except:
                    pass
            
            # 获取因子分析数据
            factor_result = ReviewResult.query.filter(
                ReviewResult.task_id == task.id,
                ReviewResult.dimension == '因子分析'
            ).first()
            
            if factor_result and factor_result.detail_data:
                try:
                    factor_data = json.loads(factor_result.detail_data)
                    factor_stocks = factor_data.get('stocks', [])
                    # 取前10只股票
                    top_stocks = [
                        {
                            'code': s.get('code', ''),
                            'name': s.get('name', ''),
                            'totalScore': s.get('totalScore', 0)
                        }
                        for s in factor_stocks[:10]
                    ]
                    task_info['factorStocks'] = top_stocks
                    # Top10股票得分列表（按名次排序）
                    task_info['topStockScores'] = [s.get('totalScore', 0) for s in top_stocks]
                    # 每只股票对应的名次
                    task_info['stockRanks'] = [{'name': s.get('name', ''), 'rank': idx + 1} for idx, s in enumerate(top_stocks)]
                except:
                    pass
            
            # 获取大盘综合得分
            market_result = ReviewResult.query.filter(
                ReviewResult.task_id == task.id,
                ReviewResult.dimension == '市场',
                ReviewResult.metric_name == '大盘综合得分'
            ).first()
            
            if market_result and market_result.metric_value:
                try:
                    task_info['marketScore'] = float(market_result.metric_value)
                except:
                    pass
            
            dashboard_data.append(task_info)
        
        return ApiResponse.success(dashboard_data)
        
    except Exception as e:
        import traceback
        logger.error(f"获取仪表盘数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))


# ==================== 每日笔记 API ====================

@review_bp.route('/note/<string:trade_date>', methods=['GET'])
def get_daily_note(trade_date):
    """获取指定交易日的笔记"""
    try:
        from models.dailynote import DailyNote
        
        note = DailyNote.query.filter_by(trade_date=trade_date).first()
        
        if not note:
            return ApiResponse.success(None)
        
        return ApiResponse.success(note.to_dict())
        
    except Exception as e:
        import traceback
        logger.error(f"获取每日笔记失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))


@review_bp.route('/note', methods=['POST'])
def save_daily_note():
    """保存每日笔记"""
    try:
        from models.dailynote import DailyNote
        
        data = request.get_json()
        
        if not data:
            return ApiResponse.bad_request('请求数据不能为空')
        
        trade_date = data.get('tradeDate') or data.get('trade_date')
        market_analysis = data.get('marketAnalysis') or data.get('market_analysis')
        next_action = data.get('nextAction') or data.get('next_action')
        
        if not trade_date:
            return ApiResponse.bad_request('请指定交易日期')
        
        # 查询是否已存在
        note = DailyNote.query.filter_by(trade_date=trade_date).first()
        
        if note:
            # 更新
            if market_analysis is not None:
                note.market_analysis = market_analysis
            if next_action is not None:
                note.next_action = next_action
        else:
            # 创建新记录
            note = DailyNote(
                trade_date=trade_date,
                market_analysis=market_analysis,
                next_action=next_action
            )
            db.session.add(note)
        
        db.session.commit()
        
        return ApiResponse.success(note.to_dict(), '保存成功')
        
    except Exception as e:
        import traceback
        logger.error(f"保存每日笔记失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))


@review_bp.route('/note/latest', methods=['GET'])
def get_latest_note():
    """获取最近有笔记的交易日信息"""
    try:
        from models.dailynote import DailyNote
        
        note = DailyNote.query.order_by(DailyNote.trade_date.desc()).first()
        
        if not note:
            return ApiResponse.success(None)
        
        return ApiResponse.success(note.to_dict())
        
    except Exception as e:
        import traceback
        logger.error(f"获取最新笔记失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse.server_error(str(e))
