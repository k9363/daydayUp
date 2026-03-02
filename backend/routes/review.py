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
        overwrite = data.get('overwrite', False)  # 是否覆盖
        
        # 数据源信息
        data_source_type = data.get('dataSourceType', 'baostock')
        data_source_name = data.get('dataSourceName', f'复盘数据 {trade_date}')
        data_source_desc = data.get('dataSourceDesc', '')
        
        if not task_name:
            return jsonify({'code': 400, 'message': '请输入任务名称'}), 400
        
        # 检查该交易日是否已存在任务
        from models.reviewtask import ReviewTask
        existing_task = ReviewTask.query.filter(
            ReviewTask.trade_date == trade_date,
            ReviewTask.data_source_type == data_source_type
        ).first()
        
        if existing_task and not overwrite:
            return jsonify({
                'code': 409,
                'message': f'该交易日 {trade_date} 已存在复盘任务',
                'data': {
                    'existingTaskId': existing_task.id,
                    'existingTaskName': existing_task.task_name,
                    'tradeDate': trade_date
                }
            }), 409
        
        # 如果存在且需要覆盖，删除旧任务
        if existing_task and overwrite:
            # 删除旧任务及其结果
            from models.reviewresult import ReviewResult
            ReviewResult.query.filter(ReviewResult.task_id == existing_task.id).delete()
            db.session.delete(existing_task)
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
        stock_filter = data.get('stock_filter', None)  # 股票筛选条件，如 {"type": "top_by_amount", "value": 100}
        overwrite = data.get('overwrite', False)  # 是否覆盖
        
        # 验证日期
        if not trade_date:
            return jsonify({'code': 400, 'message': '请指定交易日期(trade_date)'}), 400
        
        # 检查该交易日是否已存在任务
        from models.reviewtask import ReviewTask
        existing_task = ReviewTask.query.filter(
            ReviewTask.trade_date == trade_date,
            ReviewTask.data_source_type == 'baostock'
        ).first()
        
        if existing_task and not overwrite:
            return jsonify({
                'code': 409,
                'message': f'该交易日 {trade_date} 已存在复盘任务',
                'data': {
                    'existingTaskId': existing_task.id,
                    'existingTaskName': existing_task.task_name,
                    'tradeDate': trade_date
                }
            }), 409
        
        # 如果存在且需要覆盖，删除旧任务
        if existing_task and overwrite:
            from models.reviewresult import ReviewResult
            ReviewResult.query.filter(ReviewResult.task_id == existing_task.id).delete()
            db.session.delete(existing_task)
            db.session.commit()
        
        service = get_review_task_service()
        
        # 直接在任务中设置数据源信息（不再单独创建DataSource）
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
        
        # 获取该任务的所有结果数据
        all_results = ReviewResult.query.filter(
            ReviewResult.task_id == task_id
        ).all()
        
        if not all_results:
            return jsonify({'code': 404, 'message': '图表数据不存在'}), 404
        
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
            if default_expr and default_expr.factors:
                factor_codes_in_expr = default_expr.factors
            elif default_expr and default_expr.expression:
                import re
                # 从表达式中提取因子代码
                var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
                exclude_funcs = {'ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG', 
                               'abs', 'sqrt', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log'}
                matches = re.findall(var_pattern, default_expr.expression)
                factor_codes_in_expr = [m for m in matches if m not in exclude_funcs]
            
            # 只获取表达式中使用的因子定义
            if factor_codes_in_expr:
                stock_factors = FactorDefine.query.filter(
                    FactorDefine.factor_scope == 'stock',
                    FactorDefine.is_active == True,
                    FactorDefine.factor_code.in_(factor_codes_in_expr)
                ).order_by(FactorDefine.factor_code).all()
            else:
                stock_factors = []
            
            factor_columns = [{
                'code': f.factor_code,
                'name': f.factor_name,
                'source': f.source
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


@review_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """获取首页仪表盘数据 - 近10个交易日的板块前10、因子得分Top10和趋势图表"""
    try:
        import json
        from models.reviewtask import ReviewTask
        from models.reviewresult import ReviewResult
        
        # 获取近10个已完成的任务（按交易日期倒序）
        recent_tasks = ReviewTask.query.filter(
            ReviewTask.status == 'completed'
        ).order_by(ReviewTask.trade_date.desc()).limit(10).all()
        
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
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': dashboard_data
        })
        
    except Exception as e:
        import traceback
        logger.error(f"获取仪表盘数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 500, 'message': str(e)}), 500
