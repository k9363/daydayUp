"""
复盘任务服务 - 核心分析引擎
"""
import json
import logging
import re
from datetime import datetime
from collections import defaultdict
from extensions import db
from models.reviewtask import ReviewTask
from models.reviewresult import ReviewResult
from services.baostock_service import get_baostock_service
from services.factor_service import factor_calculator
from services.review_result_builder import ReviewResultBuilder
from utils.excel_utils import read_excel
from config import (
    MARKET_INDEX_CODES, STOCK_TYPE_STOCK,
    EXPR_BUILTINS, EXPR_FUNCTION_NAMES,
    CALCULATION_METHOD_MAP, FACTOR_DEPENDENCIES,
    FACTOR_NAME_MAP
)

logger = logging.getLogger(__name__)


def trigger_tacn_batch_analysis(trade_date=None):
    """复盘成功后 HTTP 触发 TA-CN 全市场综合分析。

    放在「复盘真正完成」处统一触发，覆盖所有入口（定时 / 手动重跑 / 异步回调完成）——
    之前触发只挂在 scheduler 的 18:00 cron 路径，手动重跑/异步完成都不会触发。
    非阻塞（5s timeout），失败只 log，不影响复盘成功状态。

    Args:
        trade_date: 'YYYY-MM-DD'，传给 TA-CN 让其分析同一交易日；None=TA-CN 取最新交易日
    """
    import os
    import requests
    tacn_base = os.getenv('TACN_API_BASE', 'http://host.docker.internal:8000')
    token = os.getenv('INTERNAL_TRIGGER_TOKEN', '')
    date_param = trade_date.replace('-', '') if trade_date else None  # YYYY-MM-DD → YYYYMMDD
    try:
        resp = requests.post(
            f'{tacn_base}/api/analysis/index/batch/internal/trigger',
            json={'date': date_param, 'model': 'deepseek-v4-pro'},
            headers={'X-Internal-Token': token} if token else {},
            timeout=5,
        )
        if resp.status_code == 200:
            logger.info(f"🌐 已触发 TA-CN 全市场综合分析 task_id={resp.json().get('task_id')} (date={date_param})")
        else:
            logger.warning(f"⚠️ TA-CN 触发返回 HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"⚠️ 触发 TA-CN 全市场分析失败（不影响复盘）: {e}")


def _wait_for_market_report(trade_date, timeout_s=720, interval_s=20):
    """复盘发邮件前，轮询等待 TA-CN 当日全市场综合分析就绪。

    TA-CN 全市场分析是上面 trigger_tacn_batch_analysis 异步触发的（HTTP fire-and-forget），
    LLM 跑 1.6W 字需数分钟；不等待会导致复盘邮件赶在分析完成前发出、缺「全市场综合分析」段
    （实测 387：复盘 18:55 发邮件，全市场分析 19:01 才就绪）。

    就绪（external_analysis 出现当日 batch 记录且含全文）返回 True；超时返回 False
    （调用方仍照常发邮件，只是可能不含全市场分析，不阻断复盘）。
    """
    import time
    import json as _json
    from models.external_analysis import ExternalAnalysis
    if not trade_date:
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            db.session.expire_all()
            ext = (ExternalAnalysis.query
                   .filter(ExternalAnalysis.trade_date == trade_date)
                   .filter(ExternalAnalysis.source.like('%batch%'))
                   .order_by(ExternalAnalysis.id.desc()).first())
            if ext:
                raw = ext.raw_report
                if isinstance(raw, str):
                    try:
                        raw = _json.loads(raw)
                    except Exception:
                        raw = {}
                rep = ''
                if isinstance(raw, dict):
                    node = raw.get('result') if isinstance(raw.get('result'), dict) else raw
                    rep = node.get('report') or raw.get('report') or ''
                if isinstance(rep, str) and len(rep) > 2000:
                    logger.info(f"✅ 全市场分析已就绪（{len(rep)} 字），开始发复盘邮件 (date={trade_date})")
                    return True
        except Exception as e:
            logger.warning(f"等待全市场分析轮询出错（继续等待）: {e}")
        time.sleep(interval_s)
    logger.warning(f"⚠️ 等待全市场分析超时（{timeout_s}s, date={trade_date}），照常发邮件（可能不含全市场分析）")
    return False


def _build_factor_tree(factor_definitions):
    """
    构建因子依赖树
    
    Args:
        factor_definitions: FactorDefine 模型列表
    
    Returns:
        树形结构的因子列表
    """
    # 定义因子分类和层级
    factor_categories = {
        'kline_field': {'name': 'K线原始字段', 'level': 0, 'children': []},
        'rank': {'name': '排名因子', 'level': 1, 'children': []},
        'avg': {'name': '历史平均因子', 'level': 1, 'children': []},
        'expression': {'name': '计算得分因子', 'level': 2, 'children': []},
    }

    # 从常量配置读取
    calculation_method_map = CALCULATION_METHOD_MAP
    factor_dependencies = FACTOR_DEPENDENCIES
    
    def parse_dependencies_from_expression(expr):
        if not expr or not expr.strip():
            return None
        var_names = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr)
        deps = [v for v in var_names if v not in EXPR_BUILTINS]
        return deps if deps else None
    
    # 因子中文名映射
    factor_name_map = {
        'close_price': '收盘价',
        'volume': '成交量',
        'turnover': '成交额',
        'pct_change': '涨跌幅',
        'ma5': '5日均线',
        'ma10': '10日均线',
        'ma20': '20日均线',
        'ma20_y1': '昨日20日均线',
        'volume_y1': '昨日成交量',
        'turnover_y1': '昨日成交额',
        'amount_rank': '成交额排名',
        'avg_amount_3d': '近3日平均成交额',
        'avg_amount_5d': '近5日平均成交额',
        'avg_amount_10d': '近10日平均成交额',
        'avg_amount_20d': '近20日平均成交额',
        'avg_amount_4_20d': '4-20日平均成交额',
        'avg_amount_11_30d': '11-30日平均成交额',
        'avg_amount_4_120d': '4-120日平均成交额',
        'price_ma5_diff': '股价与5日线差值',
        'price_ma10_diff': '股价与10日线差值',
        'factor1_rank': '成交额权重',
        'factor2_ma': '短线趋势',
        'factor3_vol': '昨日同比',
        'factor4_burst': '爆量',
        'factor5_extreme': '极限量',
        'factor6_trend': '多头趋势',

        # 偏离值因子
        'deviation_10d': '10日偏离值累计',
        'deviation_30d': '30日偏离值累计',
        'remaining_deviation': '剩余偏离值',
    }
    
    # 分类因子
    categorized_factors = defaultdict(list)
    factor_info_map = {}
    
    for f in factor_definitions:
        code = f.factor_code
        method = f.calculation_method
        
        # 获取分类
        if code in calculation_method_map:
            category = calculation_method_map[code]
        else:
            category = method if method else 'expression'
        
        # 依赖：有表达式则从表达式解析，否则用默认映射
        deps = parse_dependencies_from_expression(f.expression)
        if deps is not None:
            dependencies = deps
        else:
            dependencies = factor_dependencies.get(code, [])
        
        factor_info = {
            'code': code,
            'name': f.factor_name or factor_name_map.get(code, code),
            'method': method,
            'expression': f.expression,
            'description': f.description,
            'dependencies': dependencies,
            'children': []
        }
        
        categorized_factors[category].append(factor_info)
        factor_info_map[code] = factor_info
    
    # 构建树形结构
    # 1. K线原始字段（叶子节点）
    kline_fields = categorized_factors.get('kline_field', [])
    
    # 2. 历史平均因子（依赖K线字段）
    avg_factors = categorized_factors.get('avg', [])
    for af in avg_factors:
        af['dependencies'] = [d for d in af['dependencies'] if d in factor_info_map]
    
    # 3. 排名因子
    rank_factors = categorized_factors.get('rank', [])
    
    # 4. 中间表达式因子
    expr_factors = categorized_factors.get('expression', [])
    # 过滤掉得分因子（factor1-6）
    intermediate_expr = [f for f in expr_factors if not f['code'].startswith('factor')]
    # 表达式因子的依赖只保留已定义的因子
    for ef in expr_factors:
        ef['dependencies'] = [d for d in ef['dependencies'] if d in factor_info_map]
    
    # 5. 最终得分因子
    score_factors = [f for f in expr_factors if f['code'].startswith('factor')]
    
    # 构建层级结构
    tree = []
    
    # 第一层：K线原始字段
    level1 = {
        'level': 1,
        'levelName': '数据源',
        'description': '来自股票行情的原始数据',
        'factors': []
    }
    for f in kline_fields:
        level1['factors'].append({
            'code': f['code'],
            'name': f['name'],
            'description': f.get('description', ''),
            'method': f['method'],
            'children': []
        })
    if level1['factors']:
        tree.append(level1)
    
    # 第二层：中间计算因子
    level2 = {
        'level': 2,
        'levelName': '中间计算因子',
        'description': '基于原始数据计算的中间指标',
        'factors': []
    }
    # 历史平均因子
    for f in avg_factors:
        deps = f.get('dependencies', [])
        dep_names = [factor_name_map.get(d, d) for d in deps]
        level2['factors'].append({
            'code': f['code'],
            'name': f['name'],
            'description': f.get('description', ''),
            'method': f['method'],
            'dependencies': deps,
            'dependenciesName': dep_names,
            'children': []
        })
    # 排名因子
    for f in rank_factors:
        deps = f.get('dependencies', [])
        dep_names = [factor_name_map.get(d, d) for d in deps]
        level2['factors'].append({
            'code': f['code'],
            'name': f['name'],
            'description': f.get('description', ''),
            'method': f['method'],
            'dependencies': deps,
            'dependenciesName': dep_names,
            'children': []
        })
    # 中间表达式因子
    for f in intermediate_expr:
        deps = f.get('dependencies', [])
        dep_names = [factor_name_map.get(d, d) for d in deps]
        level2['factors'].append({
            'code': f['code'],
            'name': f['name'],
            'description': f.get('description', ''),
            'method': f['method'],
            'expression': f.get('expression', ''),
            'dependencies': deps,
            'dependenciesName': dep_names,
            'children': []
        })
    if level2['factors']:
        tree.append(level2)
    
    # 第三层：最终得分因子
    level3 = {
        'level': 3,
        'levelName': '综合得分因子',
        'description': '用于股票排序和选股的最终因子',
        'factors': []
    }
    for f in score_factors:
        deps = f.get('dependencies', [])
        dep_names = [factor_name_map.get(d, d) for d in deps]
        level3['factors'].append({
            'code': f['code'],
            'name': f['name'],
            'description': f.get('description', ''),
            'method': f['method'],
            'expression': f.get('expression', ''),
            'dependencies': deps,
            'dependenciesName': dep_names,
            'children': []
        })
    if level3['factors']:
        tree.append(level3)
    
    return tree


class ReviewTaskService:
    """复盘任务服务类"""
    
    def create_task(self, task_name, review_type, dimensions=None, rules=None,
                    trade_date=None, data_source_type='baostock',
                    data_source_name=None, data_source_desc=None, stock_filter=None):
        """
        创建复盘任务

        Args:
            task_name: 任务名称
            review_type: 复盘类型
            dimensions: 分析维度列表
            rules: 复盘规则列表
            trade_date: 交易日期
            data_source_type: 数据源类型
            data_source_name: 数据源名称
            data_source_desc: 数据源描述
            stock_filter: 股票筛选条件，如 {"type": "top_by_amount", "value": 100}

        Returns:
            ReviewTask: 创建的任务
        """
        task = ReviewTask()
        task.task_name = task_name
        task.review_type = review_type
        task.dimensions = json.dumps(dimensions, ensure_ascii=False) if dimensions else None
        task.rules = json.dumps(rules, ensure_ascii=False) if rules else None
        task.stock_filter = json.dumps(stock_filter, ensure_ascii=False) if stock_filter else None
        task.status = 'pending'

        # 数据源信息
        task.trade_date = trade_date
        task.data_source_type = data_source_type
        task.data_source_name = data_source_name or f'复盘数据 {trade_date}'
        task.data_source_desc = data_source_desc

        db.session.add(task)
        db.session.commit()

        return task
    
    def execute_task(self, task_id):
        """
        执行复盘任务

        Args:
            task_id: 任务ID

        Returns:
            ReviewTask: 执行后的任务
        """
        task = ReviewTask.query.get(task_id)

        if not task:
            raise Exception("任务不存在")

        task.status = 'running'
        task.start_time = datetime.now()
        db.session.commit()

        try:
            # 根据数据源类型执行不同的逻辑
            data_source_type = task.data_source_type

            if data_source_type == 'baostock':
                # 使用 Baostock 数据源
                return self.execute_baostock_task(task_id)
            elif data_source_type == 'excel' and task.file_path:
                # 使用 Excel 文件（原有逻辑）
                return self._execute_excel_task(task)
            else:
                raise Exception(f"不支持的数据源类型({data_source_type})")
            
        except Exception as e:
            task.status = 'failed'
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.session.commit()
            logger.error(f"❌ 复盘任务执行失败: {e}")
            raise Exception(f"复盘执行失败: {str(e)}")
    
    def _execute_excel_task(self, task):
        """执行Excel文件类型的任务"""
        try:
            # 读取数据
            file_path = task.file_path
            data = read_excel(file_path)
            
            if not data:
                raise Exception("数据为空")
            
            # 执行分析
            results = self._analyze_data(task, data)
            
            # 批量保存结果
            if results:
                # 使用bulk_insert_mappings批量插入
                from models.reviewresult import ReviewResult
                mappings = []
                for r in results:
                    mappings.append({
                        'task_id': r.task_id,
                        'dimension': r.dimension,
                        'metric_name': r.metric_name,
                        'metric_value': r.metric_value,
                        'compare_value': r.compare_value,
                        'change_rate': r.change_rate,
                        'status': r.status,
                        'suggestion': r.suggestion,
                        'detail_data': r.detail_data
                    })
                db.session.bulk_insert_mappings(ReviewResult, mappings)
            
            # 更新任务状态
            task.status = 'completed'
            task.end_time = datetime.now()
            abnormal_count = sum(1 for r in results if r.status != 'normal')
            task.result_summary = f"分析了 {len(data)} 条数据，发现 {abnormal_count} 个指标异常"
            
            db.session.commit()
            
            return task
            
        except Exception as e:
            task.status = 'failed'
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.session.commit()
            raise Exception(f"Excel任务执行失败: {str(e)}")
    
    def _analyze_data(self, task, data):
        """
        核心数据分析引擎
        
        Args:
            task: 复盘任务
            data: 数据列表
        
        Returns:
            list: 分析结果列表
        """
        results = []
        
        # 解析维度和规则
        dimensions = json.loads(task.dimensions) if task.dimensions else []
        rules = json.loads(task.rules) if task.rules else []
        
        # 如果没有指定维度，执行总体分析
        if not dimensions:
            results.extend(self._calculate_summary(task.id, data))
        else:
            # 按维度分组分析
            for dimension in dimensions:
                results.extend(self._analyze_dimension(task.id, dimension, data, rules))
            
            # 计算统计摘要
            results.extend(self._calculate_summary(task.id, data))
        
        return results
    
    def _analyze_dimension(self, task_id, dimension, data, rules):
        """
        分析单个维度
        
        Args:
            task_id: 任务ID
            dimension: 维度名
            data: 数据
            rules: 规则列表
        
        Returns:
            list: 分析结果
        """
        results = []
        
        # 按维度值分组
        grouped_data = defaultdict(list)
        for item in data:
            key = str(item.get(dimension, '未知'))
            grouped_data[key].append(item)
        
        for dim_value, group_data in grouped_data.items():
            for rule in rules:
                result = self._analyze_rule(task_id, dimension, dim_value, group_data, rule)
                if result:
                    results.append(result)
        
        return results
    
    def _analyze_rule(self, task_id, dimension, dim_value, group_data, rule):
        """
        分析单个规则
        
        Args:
            task_id: 任务ID
            dimension: 维度名
            dim_value: 维度值
            group_data: 分组数据
            rule: 规则
        
        Returns:
            ReviewResult: 分析结果
        """
        try:
            result = ReviewResult()
            result.task_id = task_id
            result.dimension = f"{dimension}: {dim_value}"
            result.metric_name = rule.get('ruleName', rule.get('field', '未命名'))
            
            # 计算聚合值
            field = rule.get('field')
            aggregation = rule.get('aggregation', 'sum')
            
            if field:
                aggregated_value = self._aggregate(group_data, field, aggregation)
                result.metric_value = self._format_value(aggregated_value)
            
            # 阈值检查
            threshold = rule.get('threshold')
            if threshold is not None:
                result.compare_value = str(threshold)
                change_rate = self._calculate_change_rate(aggregated_value, threshold)
                result.change_rate = change_rate
                result.status = self._determine_status(change_rate, rule.get('level', 'warning'))
                result.suggestion = self._generate_suggestion(rule, result.status)
            else:
                result.status = 'normal'
            
            result.create_time = datetime.now()
            
            # 保存详细数据
            detail_data = {
                'count': len(group_data),
                'aggregation': aggregation,
                'field': field
            }
            result.detail_data = json.dumps(detail_data, ensure_ascii=False)
            
            return result
            
        except Exception as e:
            return None
    
    def _aggregate(self, data, field, aggregation):
        """
        聚合计算
        
        Args:
            data: 数据列表
            field: 字段名
            aggregation: 聚合方式
        
        Returns:
            float: 聚合结果
        """
        values = []
        for item in data:
            val = item.get(field)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
        
        if not values:
            return 0.0
        
        if aggregation.lower() == 'sum':
            return sum(values)
        elif aggregation.lower() == 'avg':
            return sum(values) / len(values)
        elif aggregation.lower() == 'count':
            return len(values)
        elif aggregation.lower() == 'max':
            return max(values)
        elif aggregation.lower() == 'min':
            return min(values)
        else:
            return sum(values)
    
    def _calculate_summary(self, task_id, data):
        """
        计算统计摘要
        
        Args:
            task_id: 任务ID
            data: 数据列表
        
        Returns:
            list: 摘要结果
        """
        results = []
        
        if not data:
            return results
        
        from models.reviewresult import ReviewResult
        
        # 数据总量
        total_result = ReviewResult()
        total_result.task_id = task_id
        total_result.dimension = '总体统计'
        total_result.metric_name = '数据总量'
        total_result.metric_value = str(len(data))
        total_result.status = 'normal'
        total_result.create_time = datetime.now()
        results.append(total_result)
        
        # 各字段统计
        if data:
            first_row = data[0]
            for field in first_row.keys():
                if self._is_numeric_field(data, field):
                    field_result = ReviewResult()
                    field_result.task_id = task_id
                    field_result.dimension = '字段分析'
                    field_result.metric_name = f'{field}_总和'
                    
                    sum_value = sum(
                        float(item.get(field, 0)) 
                        for item in data 
                        if item.get(field) is not None
                    )
                    
                    field_result.metric_value = self._format_value(sum_value)
                    field_result.status = 'normal'
                    field_result.create_time = datetime.now()
                    results.append(field_result)
        
        return results
    
    def _is_numeric_field(self, data, field):
        """
        判断是否为数值字段
        
        Args:
            data: 数据列表
            field: 字段名
        
        Returns:
            bool: 是否为数值字段
        """
        return all(
            item.get(field) is None or self._is_numeric(item.get(field))
            for item in data
        )
    
    def _is_numeric(self, value):
        """
        判断是否为数值
        
        Args:
            value: 值
        
        Returns:
            bool: 是否为数值
        """
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _calculate_change_rate(self, current, baseline):
        """
        计算变化率
        
        Args:
            current: 当前值
            baseline: 基准值
        
        Returns:
            float: 变化率
        """
        if baseline == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - baseline) / baseline) * 100
    
    def _determine_status(self, change_rate, level):
        """
        确定状态
        
        Args:
            change_rate: 变化率
            level: 告警级别
        
        Returns:
            str: 状态
        """
        if change_rate is None:
            return 'normal'
        
        abs_rate = abs(change_rate)
        
        if level == 'critical':
            if abs_rate > 50:
                return 'critical'
            elif abs_rate > 30:
                return 'warning'
        elif level == 'warning':
            if abs_rate > 30:
                return 'warning'
            elif abs_rate > 15:
                return 'normal'
        
        return 'warning' if abs_rate > 20 else 'normal'
    
    def _generate_suggestion(self, rule, status):
        """
        生成建议
        
        Args:
            rule: 规则
            status: 状态
        
        Returns:
            str: 建议
        """
        if status == 'normal':
            return '指标正常，无需处理'
        
        suggestion = rule.get('suggestion', '')
        
        if status == 'warning':
            return f"{suggestion} 建议关注当前变化趋势，进行进一步分析"
        else:
            return f"{suggestion} 需要立即处理"
    
    def _format_value(self, value):
        """
        格式化数值
        
        Args:
            value: 数值
        
        Returns:
            str: 格式化后的字符串
        """
        if value is None:
            return '0'
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        elif isinstance(value, float):
            return f"{value:.2f}"
        return str(value)
    
    def get_task_list(self, include_completed=False, trade_date=None, page=1, page_size=20):
        """
        获取任务列表

        Args:
            include_completed: 是否包含已完成的任务
            trade_date: 筛选特定日期的任务，格式 YYYY-MM-DD
            page: 页码，从 1 开始
            page_size: 每页数量

        Returns:
            dict: 包含 items 和 total
        """
        query = ReviewTask.query

        if not include_completed:
            query = query.filter(ReviewTask.status != 'completed')

        # 按日期筛选
        if trade_date:
            query = query.filter(ReviewTask.trade_date == trade_date)

        # 获取总数
        total = query.count()

        # 分页
        offset = (page - 1) * page_size
        tasks = query.order_by(ReviewTask.create_time.desc()).offset(offset).limit(page_size).all()

        return {
            'items': tasks,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    def get_task(self, task_id):
        """
        获取任务详情
        
        Args:
            task_id: 任务ID
        
        Returns:
            ReviewTask: 任务
        """
        return ReviewTask.query.get(task_id)
    
    def get_task_results(self, task_id):
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
        
        Returns:
            list: 结果列表
        """
        return ReviewResult.query.filter(
            ReviewResult.task_id == task_id
        ).order_by(ReviewResult.create_time.desc()).all()
    
    def get_report(self, task_id):
        """
        获取分析报告
        
        Args:
            task_id: 任务ID
        
        Returns:
            dict: 报告数据
        """
        task = self.get_task(task_id)
        
        if not task:
            raise Exception("任务不存在")
        
        results = self.get_task_results(task_id)
        
        report = {
            'task': task.to_dict(),
            'results': [r.to_dict() for r in results]
        }
        
        # 统计摘要
        total = len(results)
        normal = sum(1 for r in results if r.status == 'normal')
        warning = sum(1 for r in results if r.status == 'warning')
        critical = sum(1 for r in results if r.status == 'critical')
        
        report['summary'] = {
            'total': total,
            'normal': normal,
            'warning': warning,
            'critical': critical
        }
        
        return report
    
    def delete_task(self, task_id):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否成功
        """
        task = self.get_task(task_id)
        
        if not task:
            return False
        
        db.session.delete(task)
        db.session.commit()
        
        return True
    
    def execute_baostock_task(self, task_id):
        """
        执行Baostock复盘任务 - 核心分析引擎

        任务流程：
        1. 根据复盘类型获取对应K线数据（日K/周K/月K）
        2. 筛选出成交金额前100的股票
        3. 筛选出成交金额前100的股票所属的板块，按照股票数量排序

        Args:
            task_id: 任务ID

        Returns:
            ReviewTask: 执行后的任务
        """
        import pandas as pd
        from services.metadata_config import is_auto_supplement_enabled

        task = ReviewTask.query.get(task_id)

        if not task:
            raise Exception("任务不存在")

        task.status = 'running'
        task.start_time = datetime.now()
        db.session.commit()

        try:
            trade_date = task.trade_date
            review_type = task.review_type or 'daily'
            logger.info(f"📊 ========== 开始执行复盘任务: {trade_date} ({review_type}) ==========")

            # ========== 步骤1: 获取日K线数据 ==========
            baostock_service = get_baostock_service()

            logger.info(f"📊 步骤1: 获取 {trade_date} 的日K线数据")
            
            # 传入 create_sync_task=True 和 review_task_id，允许创建同步任务并等待回调
            all_stocks_df = self._fetch_daily_data(trade_date, db.session, create_sync_task=True, review_task_id=task_id)
            kline_type = '日K'

            # 如果返回空 DataFrame 且任务状态是 waiting_for_sync，说明已创建同步任务等待回调
            if all_stocks_df.empty and task.status == 'waiting_for_sync':
                logger.info(f"📊 已创建数据同步任务，等待同步完成...")
                return task

            if all_stocks_df.empty:
                raise Exception(f"未能获取到 {trade_date} 的{kline_type}数据")

            logger.info(f"✅ 步骤1完成: 获取到 {len(all_stocks_df)} 只股票的{kline_type}数据")

            # ========== 步骤2: 根据筛选条件过滤股票 ==========
            # 解析 stock_filter，默认为成交金额前100
            stock_filter = None
            if task.stock_filter:
                try:
                    stock_filter = json.loads(task.stock_filter)
                except:
                    stock_filter = None
            
            filter_type = stock_filter.get('type', 'top_by_amount') if stock_filter else 'top_by_amount'
            filter_value = stock_filter.get('value', 100) if stock_filter else 100
            
            logger.info(f"📊 步骤2: 筛选股票 - 类型: {filter_type}, 值: {filter_value}")
            
            if filter_type == 'top_by_amount':
                top100_df = self._filter_top_stocks(all_stocks_df, top_n=filter_value)
                filter_desc = f"成交金额前{filter_value}"
            elif filter_type == 'all':
                top100_df = all_stocks_df.copy()
                filter_desc = "全部A股"
            else:
                top100_df = self._filter_top_stocks(all_stocks_df, top_n=100)
                filter_desc = "成交金额前100"

            if top100_df.empty:
                raise Exception(f"未能筛选出股票: {filter_desc}")

            logger.info(f"✅ 步骤2完成: 筛选出 {len(top100_df)} 只股票 ({filter_desc})")

            # ========== 步骤3: 计算因子并排名 ==========
            logger.info(f"📊 步骤3: 计算因子得分")
            # 获取前100只股票的历史数据（用于计算因子）
            stock_pool = top100_df['stock_code'].tolist()
            factors_df = factor_calculator.calculate_stock_factors(stock_pool, trade_date, db.session)

            if factors_df.empty:
                raise Exception("未能计算因子得分")

            logger.info(f"✅ 步骤3完成: 计算了 {len(factors_df)} 只股票的因子得分")

            # ========== 步骤4: 选出前10只股票 ==========
            top10_stocks = factors_df.nlargest(10, 'total_score')
            logger.info(f"✅ 步骤4完成: 选出前10只股票: {top10_stocks[['stock_code', 'stock_name', 'total_score']].to_dict('records')}")

            # ========== 步骤5: 计算板块得分 ==========
            sector_scores = factor_calculator.calculate_sector_factors(factors_df, db.session)
            logger.info(f"✅ 步骤5完成: 计算了 {len(sector_scores)} 个板块的得分")

            # ========== 步骤6: 生成并保存分析结果 ==========
            logger.info(f"📊 步骤6: 保存分析结果")
            self._save_review_results(task, all_stocks_df, top100_df, factors_df, sector_scores, trade_date)
            logger.info(f"✅ 步骤6完成: 分析结果已保存")

            # 更新任务状态
            task.status = 'completed'
            task.end_time = datetime.now()

            # 安全获取前10股票和板块名称（使用按总分排序的前10）
            top10_stock_names = top10_stocks['stock_name'].head(3).tolist() if not top10_stocks.empty else []
            top10_sector_names = sector_scores['sector_name'].head(3).tolist() if not sector_scores.empty else []

            task.result_summary = (
                f"{trade_date}日: "
                f"获取{len(all_stocks_df)}只A股，"
                f"前100成交额{top100_df['turnover'].sum():.2f}，"
                f"前10股票: {', '.join(top10_stock_names)}，"
                f"前10板块: {', '.join(top10_sector_names)}"
            )

            db.session.commit()

            logger.info(f"📊 ========== 复盘任务完成: {trade_date} ==========")
            # 复盘成功 → 触发 TA-CN 全市场综合分析（覆盖手动重跑/同步完成路径）
            trigger_tacn_batch_analysis(trade_date)
            # 复盘成功 → 仅【定时任务】触发的复盘自动发邮件（task_name 带 [定时] 标记）；
            # 手动重跑/Excel 任务等不自动发，用户可在报告页通过「发送邮件」按钮手动发
            # （/api/email/send-review/<task_id>）。失败只 warn 不影响复盘成功状态。
            if '[定时]' in (task.task_name or ''):
                try:
                    # 等 TA-CN 全市场分析就绪再发，避免邮件赶在分析完成前发出（缺全市场分析段）
                    _wait_for_market_report(trade_date)
                    from services.email_service import send_daily_review_email
                    _res = send_daily_review_email(task.id)
                    if not _res.get('success') and not _res.get('skipped'):
                        logger.warning(f"⚠️ 复盘邮件未发出: {_res.get('error')}")
                except Exception as _ee:
                    logger.warning(f"⚠️ 复盘邮件发送异常（不影响复盘）: {_ee}")
            return task

        except Exception as e:
            # 先 rollback 清掉可能失效的事务，否则标 failed 的写入也会失败 → 僵尸 running
            try:
                db.session.rollback()
            except Exception:
                pass
            try:
                t = db.session.get(ReviewTask, task.id) if getattr(task, 'id', None) else task
                if t is not None:
                    t.status = 'failed'
                    t.end_time = datetime.now()
                    t.error_message = str(e)[:1000]
                    db.session.commit()
            except Exception as e2:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                logger.error(f"❌ 标记复盘失败状态时再次出错: {e2}")
            logger.error(f"❌ 复盘任务失败: {e}")
            raise Exception(f"复盘执行失败: {str(e)}")

    def execute_baostock_task_continue(self, task_id):
        """
        继续执行被数据同步打断的复盘任务（跳过数据获取步骤）

        Args:
            task_id: 任务ID

        Returns:
            ReviewTask: 执行后的任务
        """
        import pandas as pd
        from services.metadata_config import is_auto_supplement_enabled

        task = ReviewTask.query.get(task_id)

        if not task:
            raise Exception("任务不存在")

        if task.status != 'running':
            logger.info(f"任务状态不是 running，跳过继续执行: {task.status}")
            return task

        try:
            trade_date = task.trade_date
            review_type = task.review_type or 'daily'
            logger.info(f"📊 ========== 继续执行复盘任务: {trade_date} ({review_type}) ==========")

            # ========== 步骤1: 直接获取已同步的数据 ==========
            from models.kline import StockDailyKLine
            
            logger.info(f"📊 步骤1: 获取已同步的 {trade_date} 日K线数据")
            stock_records = db.session.query(StockDailyKLine).filter(
                StockDailyKLine.trade_date == trade_date
            ).all()
            
            if not stock_records:
                raise Exception(f"数据同步后仍未能获取到 {trade_date} 的日K数据")
            
            stock_data = [record.to_dict() for record in stock_records]
            all_stocks_df = pd.DataFrame(stock_data)
            kline_type = '日K'

            logger.info(f"✅ 步骤1完成: 获取到 {len(all_stocks_df)} 只股票的{kline_type}数据")

            # 后续步骤与主流程相同...
            # ========== 步骤2: 根据筛选条件过滤股票 ==========
            stock_filter = None
            if task.stock_filter:
                try:
                    stock_filter = json.loads(task.stock_filter)
                except:
                    stock_filter = None
            
            filter_type = stock_filter.get('type', 'top_by_amount') if stock_filter else 'top_by_amount'
            filter_value = stock_filter.get('value', 100) if stock_filter else 100
            
            logger.info(f"📊 步骤2: 筛选股票 - 类型: {filter_type}, 值: {filter_value}")
            
            if filter_type == 'top_by_amount':
                top100_df = self._filter_top_stocks(all_stocks_df, top_n=filter_value)
                filter_desc = f"成交金额前{filter_value}"
            elif filter_type == 'all':
                top100_df = all_stocks_df.copy()
                filter_desc = "全部A股"
            else:
                top100_df = self._filter_top_stocks(all_stocks_df, top_n=100)
                filter_desc = "成交金额前100"

            if top100_df.empty:
                raise Exception(f"未能筛选出股票: {filter_desc}")

            logger.info(f"✅ 步骤2完成: 筛选出 {len(top100_df)} 只股票 ({filter_desc})")

            # ========== 步骤3: 计算因子并排名 ==========
            logger.info(f"📊 步骤3: 计算因子得分")
            from services.factor_service import factor_calculator
            stock_pool = top100_df['stock_code'].tolist()
            factors_df = factor_calculator.calculate_stock_factors(stock_pool, trade_date, db.session)

            if factors_df.empty:
                raise Exception("未能计算因子得分")

            # ========== 步骤4: 计算板块得分 ==========
            logger.info(f"📊 步骤4: 计算板块得分")
            sector_scores = factor_calculator.calculate_sector_factors(factors_df, db.session)

            # ========== 步骤5: 保存结果 ==========
            logger.info(f"📊 步骤5: 保存分析结果")
            # _save_review_results(self, task, all_df, top_df, factors_df, sector_scores, trade_date)
            # top100_df 包含股票代码、名称、成交额等信息，可以用作 top_df
            # all_stocks_df 包含所有股票数据，用于获取指数行情
            self._save_review_results(task, all_stocks_df, top100_df, factors_df, sector_scores, trade_date)

            # ========== 步骤6: 更新任务状态 ==========
            task.status = 'completed'
            task.end_time = datetime.now()
            task.row_count = len(factors_df)

            # 生成结果摘要
            score_col = 'total_score' if 'total_score' in factors_df.columns else 'composite_score'
            top10_stocks = factors_df.nlargest(10, score_col)[['stock_code', 'stock_name', score_col]] if not factors_df.empty else pd.DataFrame()
            top10_sector_names = sector_scores['sector_name'].head(10).tolist() if not sector_scores.empty else []
            top10_stock_names = top10_stocks['stock_name'].head(3).tolist() if not top10_stocks.empty else []

            task.result_summary = (
                f"{trade_date}日: "
                f"获取{len(all_stocks_df)}只A股，"
                f"前100成交额{top100_df['turnover'].sum():.2f}，"
                f"前10股票: {', '.join(top10_stock_names)}，"
                f"前10板块: {', '.join(top10_sector_names[:3])}"
            )

            db.session.commit()

            logger.info(f"📊 ========== 复盘任务完成(继续执行): {trade_date} ==========")
            # 复盘成功 → 触发 TA-CN 全市场综合分析（覆盖异步回调完成路径）
            trigger_tacn_batch_analysis(trade_date)
            # 复盘成功 → 仅【定时任务】触发的复盘自动发邮件（task_name 带 [定时] 标记）；
            # 手动重跑/Excel 任务等不自动发，用户可在报告页通过「发送邮件」按钮手动发
            # （/api/email/send-review/<task_id>）。失败只 warn 不影响复盘成功状态。
            if '[定时]' in (task.task_name or ''):
                try:
                    # 等 TA-CN 全市场分析就绪再发，避免邮件赶在分析完成前发出（缺全市场分析段）
                    _wait_for_market_report(trade_date)
                    from services.email_service import send_daily_review_email
                    _res = send_daily_review_email(task.id)
                    if not _res.get('success') and not _res.get('skipped'):
                        logger.warning(f"⚠️ 复盘邮件未发出: {_res.get('error')}")
                except Exception as _ee:
                    logger.warning(f"⚠️ 复盘邮件发送异常（不影响复盘）: {_ee}")
            return task

        except Exception as e:
            # session 可能因前序查询失败而处于 invalid-transaction 状态，
            # 必须先 rollback 清掉失效事务，否则标 failed 的写入本身也会失败 → 任务卡在 running（僵尸）
            try:
                db.session.rollback()
            except Exception:
                pass
            try:
                t = db.session.get(ReviewTask, task.id) if getattr(task, 'id', None) else task
                if t is not None:
                    t.status = 'failed'
                    t.end_time = datetime.now()
                    t.error_message = str(e)[:1000]
                    db.session.commit()
            except Exception as e2:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                logger.error(f"❌ 标记复盘失败状态时再次出错: {e2}")
            logger.error(f"❌ 复盘任务继续执行失败: {e}")
            raise Exception(f"复盘继续执行失败: {str(e)}")

    def _fetch_daily_data(self, trade_date, db_session, create_sync_task=False, review_task_id=None):
        """
        获取指定日期的全部日K数据

        Args:
            trade_date: 交易日期
            db_session: 数据库会话
            create_sync_task: 是否创建同步任务（用于等待回调）
            review_task_id: 复盘任务ID（用于回调）

        Returns:
            pd.DataFrame: 包含所有股票日K数据的DataFrame
        """
        import pandas as pd
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic

        logger.info(f"📊 正在获取 {trade_date} 的日K线数据...")

        # 1. 从元数据获取所有股票列表（获取股票、ETF、指数类型）
        all_stocks = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
            StockBasic.stock_type.in_(['stock', 'etf', 'index'])
        ).all()
        expected_stock_codes = [s.stock_code for s in all_stocks]
        stock_name_map = {s.stock_code: s.stock_name for s in all_stocks}
        logger.info(f"从元数据获取到 {len(expected_stock_codes)} 只股票/ETF/指数 (stock_type in ['stock', 'etf', 'index'])")
        
        # 检查其他类型的数量
        other_count = db_session.query(StockBasic).filter(
            StockBasic.stock_type != 'stock'
        ).count()
        logger.info(f"元数据中非股票类型数量: {other_count}")
        
        # 调试：打印前后10个股票代码
        logger.info(f"=== DEBUG: expected_stock_codes前10: {expected_stock_codes[:10]}")
        logger.info(f"=== DEBUG: expected_stock_codes后10: {expected_stock_codes[-10:]}")
        
        # （已移除一条仅用于 debug 日志的 `SELECT DISTINCT stock_code FROM stock_daily_kline`，
        #   它对 140 万行做全表去重耗时 ~12s 且不参与任何逻辑；真正判断用下方按 trade_date 分批查询）

        if not expected_stock_codes:
            raise Exception("元数据表中没有找到股票列表，请先进行元数据初始化")

        # 2. 批量查询数据库中已有该日期数据的股票
        existing_codes = set()
        batch_size = 1000
        for i in range(0, len(expected_stock_codes), batch_size):
            batch_codes = expected_stock_codes[i:i+batch_size]
            existing = db_session.query(StockDailyKLine.stock_code).filter(
                StockDailyKLine.trade_date == trade_date,
                StockDailyKLine.stock_code.in_(batch_codes)
            ).distinct().all()
            existing_codes.update([e.stock_code for e in existing])

        logger.info(f"数据库中已有 {len(existing_codes)} 只股票的 {trade_date} 日K数据")
        logger.info(f"=== DEBUG: existing_codes前10: {list(existing_codes)[:10]}")
        logger.info(f"=== DEBUG: existing_codes后10: {list(existing_codes)[-10:]}")

        # 3. 找出缺失的股票
        missing_codes = [code for code in expected_stock_codes if code not in existing_codes]
        # 排除停牌/退市/次新无数据股：最近 K 线远早于复盘日（或无 K 线）的不算缺失，否则会为
        # 停牌股反复触发同步、baostock 兜底失败导致复盘卡死（如 *ST 停牌股，本就没有当日数据）
        if missing_codes:
            from sqlalchemy import func as _sqlfunc
            from datetime import datetime as _dt, timedelta as _td
            _last_map = dict(db_session.query(StockDailyKLine.stock_code, _sqlfunc.max(StockDailyKLine.trade_date))
                             .filter(StockDailyKLine.stock_code.in_(missing_codes))
                             .group_by(StockDailyKLine.stock_code).all())
            try:
                _cut = (_dt.strptime(str(trade_date)[:10], '%Y-%m-%d') - _td(days=10)).strftime('%Y-%m-%d')
            except Exception:
                _cut = None
            if _cut:
                _suspended = [c for c in missing_codes if (not _last_map.get(c)) or str(_last_map[c])[:10] < _cut]
                if _suspended:
                    logger.info(f"跳过 {len(_suspended)} 只停牌/退市/次新股(最近K线早于{_cut}或无K线): {_suspended[:8]}")
                missing_codes = [c for c in missing_codes if c not in _suspended]
        logger.info(f"缺失 {len(missing_codes)} 只股票的 {trade_date} 日K数据(已排除停牌/退市)")
        logger.info(f"=== DEBUG: missing_codes前10: {missing_codes[:10]}")

        # 4. 如果全部存在，直接返回
        if not missing_codes:
            logger.info(f"数据库中已存在 {trade_date} 的完整股票数据")
            existing_data = db_session.query(StockDailyKLine).filter(
                StockDailyKLine.trade_date == trade_date
            ).all()
            stock_data = [record.to_dict() for record in existing_data]
            df = pd.DataFrame(stock_data)
            logger.info(f"✅ 获取到 {len(df)} 只股票的日K数据")
            return df

        # 5. 直接复用 DataSyncService.sync_kline_data 批量获取和保存数据
        from services.data_sync_service import DataSyncService
        from models.kline import DataSyncTask
        import json
        
        data_sync_service = DataSyncService()
        
        # 判断是否需要创建同步任务并等待回调
        if create_sync_task and review_task_id and missing_codes:
            # 创建数据同步任务
            sync_task = DataSyncTask(
                task_name=f"复盘任务自动同步 {trade_date}",
                start_date=trade_date,
                end_date=trade_date,
                frequency='daily',
                stock_type='all',
                status='pending',
                callback_type='review_task',
                callback_params=json.dumps({'review_task_id': review_task_id})
            )
            db_session.add(sync_task)
            db_session.commit()
            sync_task_id = sync_task.id
            
            # 更新复盘任务状态
            from models.reviewtask import ReviewTask
            review_task = db_session.query(ReviewTask).get(review_task_id)
            if review_task:
                review_task.status = 'waiting_for_sync'
                review_task.waiting_for_sync = True
                review_task.sync_task_id = sync_task_id
                db_session.commit()
            
            logger.info(f"创建数据同步任务: {sync_task_id}, 等待回调复盘任务: {review_task_id}")
            
            # 启动同步任务（在后台线程中执行）
            from threading import Thread
            from flask import current_app
            from sqlalchemy.orm import sessionmaker
            
            # 获取 app 实例
            app = current_app._get_current_object()
            
            # 将参数提取到外部变量，避免在新线程中引用 Flask 对象
            task_id = sync_task_id
            start_date = trade_date
            end_date = trade_date
            missing_codes_list = missing_codes
            
            def run_sync_task():
                try:
                    with app.app_context():
                        # 在新线程中创建独立的数据库会话，避免与主线程的session冲突
                        engine = db.engine
                        Session = sessionmaker(bind=engine)
                        local_session = Session()
                        
                        from services.data_sync_service import DataSyncService
                        sync_service = DataSyncService()
                        try:
                            sync_service.sync_kline_data(
                                db_session=local_session,
                                task_id=task_id,
                                start_date=start_date,
                                end_date=end_date,
                                frequency='daily',
                                stock_codes=missing_codes_list,
                                batch_size=100,
                                request_interval=0
                            )
                        except Exception as e:
                            logger.error(f"同步任务执行失败: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                        finally:
                            local_session.close()
                except Exception as e:
                    logger.error(f"同步任务线程执行失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            thread = Thread(target=run_sync_task)
            thread.start()
            
            logger.info(f"已启动同步任务线程 (task_id={task_id}), 主线程返回，任务将通过回调继续...")
            
            # 返回空 DataFrame，表示需要等待
            return pd.DataFrame()
        
        # 使用 sync_kline_data 批量处理，设置 request_interval=0 加快速度
        total_stock, processed_stock, total_records, saved_records = data_sync_service.sync_kline_data(
            db_session=db_session,
            task_id=0,  # 0 表示不保存进度
            start_date=trade_date,
            end_date=trade_date,
            frequency='daily',
            stock_codes=missing_codes,  # 只处理缺失的股票
            batch_size=100,
            request_interval=0
        )
        
        logger.info(f"共补充 {saved_records} 条数据")

        # 6. 返回所有数据
        stock_records = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.trade_date == trade_date
        ).all()

        if not stock_records:
            logger.warning(f"⚠️ 数据库中未找到 {trade_date} 的日线数据")
            return pd.DataFrame()

        stock_data = [record.to_dict() for record in stock_records]
        df = pd.DataFrame(stock_data)

        logger.info(f"✅ 获取到 {len(df)} 只股票的日K数据")
        return df

    def _convert_weekly_to_df(self, weekly_records):
        """
        将周K线记录转换为DataFrame

        Args:
            weekly_records: 周K线记录列表

        Returns:
            pd.DataFrame: 包含周K线数据的DataFrame
        """
        import pandas as pd

        if not weekly_records:
            logger.warning("⚠️ 没有周K线数据")
            return pd.DataFrame()

        # 转换为字典列表
        stock_data = []
        for record in weekly_records:
            stock_data.append({
                'stock_code': record.stock_code,
                'stock_name': record.stock_name,
                'trade_date': record.trade_date,
                'open': float(record.week_open) if record.week_open else 0,
                'high': float(record.week_high) if record.week_high else 0,
                'low': float(record.week_low) if record.week_low else 0,
                'close': float(record.week_close) if record.week_close else 0,
                'volume': float(record.volume) if record.volume else 0,
                'amount': float(record.amount) if record.amount else 0,
                'turnover': float(record.amount) if record.amount else 0,  # 使用amount作为成交额
                'pct_chg': float(record.pct_chg) if record.pct_chg else 0
            })

        df = pd.DataFrame(stock_data)
        logger.info(f"✅ 转换得到 {len(df)} 只股票的周K数据")
        return df

    def _convert_monthly_to_df(self, monthly_records):
        """
        将月K线记录转换为DataFrame

        Args:
            monthly_records: 月K线记录列表

        Returns:
            pd.DataFrame: 包含月K线数据的DataFrame
        """
        import pandas as pd

        if not monthly_records:
            logger.warning("⚠️ 没有月K线数据")
            return pd.DataFrame()

        # 转换为字典列表
        stock_data = []
        for record in monthly_records:
            stock_data.append({
                'stock_code': record.stock_code,
                'stock_name': record.stock_name,
                'trade_date': record.trade_date,
                'open': float(record.month_open) if record.month_open else 0,
                'high': float(record.month_high) if record.month_high else 0,
                'low': float(record.month_low) if record.month_low else 0,
                'close': float(record.month_close) if record.month_close else 0,
                'volume': float(record.volume) if record.volume else 0,
                'amount': float(record.amount) if record.amount else 0,
                'turnover': float(record.amount) if record.amount else 0,
                'pct_chg': float(record.pct_chg) if record.pct_chg else 0
            })

        df = pd.DataFrame(stock_data)
        logger.info(f"✅ 转换得到 {len(df)} 只股票的月K数据")
        return df

    def _filter_top_stocks(self, df, top_n=100):
        """
        筛选成交金额前N的股票（只包含A股股票，排除ETF、指数等）

        Args:
            df: 包含所有股票数据的DataFrame
            top_n: 筛选前N只股票

        Returns:
            pd.DataFrame: 成交额前N的股票
        """
        import pandas as pd

        if df.empty:
            logger.warning("⚠️ 传入的DataFrame为空")
            return pd.DataFrame()

        # 确保turnover字段存在
        if 'turnover' not in df.columns:
            logger.warning("⚠️ 数据中缺少成交额(turnover)字段")
            return pd.DataFrame()

        # 转换为数值类型
        df = df.copy()
        df['turnover'] = pd.to_numeric(df['turnover'], errors='coerce').fillna(0)

        logger.info(f"📊 筛选前原始股票数量: {len(df)}")

        # 使用数据库的 stock_type 进行过滤
        if 'stock_code' in df.columns:
            from models.stockbasic import StockBasic
            
            # 获取所有股票代码对应的类型
            stock_codes = df['stock_code'].unique().tolist()
            logger.info(f"📊 待查询stock_type的股票代码数量: {len(stock_codes)}")
            
            stock_types = db.session.query(StockBasic.stock_code, StockBasic.stock_type).filter(
                StockBasic.stock_code.in_(stock_codes)
            ).all()
            
            logger.info(f"📊 查询到stock_type的股票数量: {len(stock_types)}")
            
            if not stock_types:
                logger.warning("⚠️ stock_basic表中没有找到任何股票类型数据")
            
            # 创建类型映射
            type_map = {st.stock_code: st.stock_type for st in stock_types}
            
            # 添加类型列
            df['stock_type'] = df['stock_code'].map(type_map).fillna('')
            
            logger.info(f"📊 stock_type分布: {df['stock_type'].value_counts().to_dict()}")
            
            # 只保留stock类型（排除ETF、指数、债券）
            # stock_type 值为: 'stock', 'etf', 'index', 'bond'
            df = df[df['stock_type'] == 'stock']
            
            logger.info(f"按stock_type过滤后剩余 {len(df)} 只股票")

        # 筛选成交额前N
        top_df = df.nlargest(top_n, 'turnover').copy()

        logger.info(f"成交额前{top_n}股票总成交额: {top_df['turnover'].sum():.2f}")
        return top_df

    def _calculate_factors(self, stock_codes, trade_date, db_session):
        """
        计算因子得分 - 使用数据库中的 expression 配置

        Args:
            stock_codes: 股票代码列表
            trade_date: 交易日期
            db_session: 数据库会话

        Returns:
            pd.DataFrame: 包含因子得分的DataFrame
        """
        import pandas as pd
        from datetime import datetime, timedelta
        from models.kline import StockDailyKLine
        from models.factor import FactorDefine
        from services.factor_service import FactorCalculator

        # 获取所有因子定义
        all_factors = FactorDefine.query.filter(
            FactorDefine.is_active == True
        ).all()
        
        # 构建因子信息字典
        factor_defs = {f.factor_code: f for f in all_factors}
        
        # 分类因子：数据源字段、中间因子、得分因子
        kline_fields = ['close_price', 'volume', 'turnover', 'pct_change', 
                       'open_price', 'high_price', 'low_price']

        # 获取历史交易日 - 需要从数据库查询实际存在的交易日
        trading_dates = db_session.query(StockDailyKLine.trade_date).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date <= trade_date
        ).distinct().order_by(StockDailyKLine.trade_date.desc()).limit(60).all()
        
        # 提取日期列表
        all_dates = [t[0] for t in trading_dates]
        
        if len(all_dates) < 30:
            logger.warning(f"⚠️ 历史交易日不足30天，仅有{len(all_dates)}天，无法计算因子5")
            return pd.DataFrame()
        
        # 取前45个交易日（包括当天），确保有足够数据计算 ma20_y1
        dates_needed = all_dates[:45]
        logger.info(f"🔍 实际交易日范围: {dates_needed[-1]} ~ {dates_needed[0]} (共{len(dates_needed)}天)")

        # 查询历史数据
        historical_data = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date.in_(dates_needed),
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).order_by(StockDailyKLine.trade_date.desc()).all()

        if not historical_data:
            logger.warning("⚠️ 未获取到历史数据，无法计算因子")
            return pd.DataFrame()

        # 转换为DataFrame
        hist_list = []
        for record in historical_data:
            hist_list.append({
                'stock_code': record.stock_code,
                'stock_name': record.stock_name,
                'trade_date': record.trade_date,
                'close': float(record.close_price) if record.close_price else 0,
                'volume': float(record.volume) if record.volume else 0,
                'turnover': float(record.turnover) if record.turnover else 0,
                'open': float(record.open_price) if record.open_price else 0,
                'high': float(record.high_price) if record.high_price else 0,
                'low': float(record.low_price) if record.low_price else 0,
                'close_price': float(record.close_price) if record.close_price else 0,
                'open_price': float(record.open_price) if record.open_price else 0,
                'high_price': float(record.high_price) if record.high_price else 0,
                'low_price': float(record.low_price) if record.low_price else 0
            })

        hist_df = pd.DataFrame(hist_list)

        # 获取当天的数据
        today_data = hist_df[hist_df['trade_date'] == trade_date]
        
        # 构建当天成交额的字典，方便快速查找
        today_turnover_map = dict(zip(today_data['stock_code'], today_data['turnover']))
        today_volume_map = dict(zip(today_data['stock_code'], today_data['volume']))
        today_close_map = dict(zip(today_data['stock_code'], today_data['close']))

        # 按股票分组，获取最近几天的数据
        # 使用数据库的 expression 来计算因子
        
        results = []
        for stock_code in stock_codes:
            stock_hist = hist_df[hist_df['stock_code'] == stock_code].sort_values('trade_date', ascending=False)

            if stock_hist.empty:
                continue

            # 获取股票名称
            stock_name = stock_hist.iloc[0]['stock_name'] if 'stock_name' in stock_hist.columns else ''

            # 构建该股票的所有因子值
            stock_factors = {}
            
            # 1. K线原始字段（叶子节点）
            current_row = stock_hist.iloc[0] if len(stock_hist) >= 1 else None
            if current_row is not None:
                stock_factors['close_price'] = float(current_row['close_price']) if current_row['close_price'] else 0
                stock_factors['volume'] = float(current_row['volume']) if current_row['volume'] else 0
                stock_factors['turnover'] = float(current_row['turnover']) if current_row['turnover'] else 0
                stock_factors['open_price'] = float(current_row['open_price']) if current_row['open_price'] else 0
                stock_factors['high_price'] = float(current_row['high_price']) if current_row['high_price'] else 0
                stock_factors['low_price'] = float(current_row['low_price']) if current_row['low_price'] else 0
                stock_factors['pct_change'] = float(current_row.get('pct_change', 0)) if current_row.get('pct_change') else 0
            
            # 2. 昨日成交量/成交额
            if len(stock_hist) >= 2:
                stock_factors['volume_y1'] = float(stock_hist.iloc[1]['volume']) if stock_hist.iloc[1]['volume'] else 0
                stock_factors['turnover_y1'] = float(stock_hist.iloc[1]['turnover']) if stock_hist.iloc[1]['turnover'] else 0
            
            # 3. 中间因子：直接从 DataFrame 计算
            stock_hist_asc = stock_hist.sort_values('trade_date', ascending=True)
            
            # 计算需要的均线（使用 close_price 列）
            if len(stock_hist) >= 5:
                close_5 = stock_hist.head(5)['close_price']
                ma5_val = close_5.mean()
                stock_factors['ma5'] = ma5_val
            if len(stock_hist) >= 10:
                stock_factors['ma10'] = stock_hist.head(10)['close_price'].mean()
            if len(stock_hist) >= 20:
                stock_factors['ma20'] = stock_hist.head(20)['close_price'].mean()
                # ma20_y1: 昨日20日均线（从昨天开始往前20天，不包含今天）
                # 需要21天数据: head(21).iloc[1:21] = 昨天到第20天前 = 20条数据
                if len(stock_hist) >= 21:
                    ma20_y1_data = stock_hist.head(21).iloc[1:21]
                    stock_factors['ma20_y1'] = ma20_y1_data['close_price'].mean()
                    logger.info(f"股票 {stock_code}: len={len(stock_hist)}, ma20={stock_factors['ma20']:.2f}, ma20_y1={stock_factors['ma20_y1']:.2f}, ma20_y1数据条数={len(ma20_y1_data)}")
            
            # 计算 amount_rank（成交额排名）
            today_turnovers = today_data.set_index('stock_code')['turnover'].to_dict()
            rank = sorted(today_turnovers.items(), key=lambda x: x[1], reverse=True)
            rank_map = {code: i+1 for i, (code, _) in enumerate(rank)}
            stock_factors['amount_rank'] = rank_map.get(stock_code, 999)
            
            # 计算中间因子：直接从 DataFrame 计算
            stock_hist_asc = stock_hist.sort_values('trade_date', ascending=True)
            
            # 通用动态计算 avg_amount_* 系列因子
            # 匹配模式: avg_amount_3d (最近3天), avg_amount_4_20d (第4-20天)
            for factor_code, factor_def in factor_defs.items():
                if factor_code.startswith('avg_amount_'):
                    # 首先尝试使用 days_range 字段（如果存在）
                    days_range = getattr(factor_def, 'days_range', None)
                    calculation_method = getattr(factor_def, 'calculation_method', None)
                    
                    if days_range and calculation_method == 'turnover_ma':
                        # 使用 days_range 字段解析天数区间
                        try:
                            if '_' in days_range:
                                parts = days_range.split('_')
                                start_day = int(parts[0])
                                end_day = int(parts[1])
                            else:
                                start_day = 1
                                end_day = int(days_range)
                            days_needed = end_day
                        except (ValueError, IndexError):
                            # 回退到从因子代码解析
                            match = re.match(r'avg_amount_(\d+)(?:_(\d+))?d', factor_code)
                            if match:
                                if match.group(2):
                                    start_day = int(match.group(1))
                                    end_day = int(match.group(2))
                                    days_needed = end_day
                                else:
                                    start_day = 1
                                    end_day = int(match.group(1))
                                    days_needed = end_day
                            else:
                                continue
                    else:
                        # 从因子代码解析天数区间（兼容旧逻辑）
                        match = re.match(r'avg_amount_(\d+)(?:_(\d+))?d', factor_code)
                        if match:
                            if match.group(2):  # 如 avg_amount_4_20d -> (4, 20)
                                start_day = int(match.group(1))
                                end_day = int(match.group(2))
                                days_needed = end_day
                            else:  # 如 avg_amount_3d -> (1, 3)
                                start_day = 1
                                end_day = int(match.group(1))
                                days_needed = end_day
                        else:
                            continue
                    
                    # 计算
                    if len(stock_hist_asc) >= days_needed:
                        if start_day == 1:
                            # 最近N天: avg_amount_3d, avg_amount_5d, avg_amount_120d
                            stock_factors[factor_code] = stock_hist_asc.tail(end_day)['turnover'].mean()
                        else:
                            # 区间: avg_amount_4_20d, avg_amount_11_30d
                            stock_factors[factor_code] = stock_hist_asc.iloc[start_day-1:end_day]['turnover'].mean()
            
            # 计算价格均线差值
            for factor_code in ['price_ma5_diff', 'price_ma10_diff']:
                try:
                    factor_def = factor_defs.get(factor_code)
                    if factor_def and factor_def.expression:
                        # 使用 simpleeval 计算
                        import simpleeval
                        context = {
                            'close_price': stock_factors.get('close_price', 0),
                            'ma5': stock_factors.get('ma5', 0),
                            'ma10': stock_factors.get('ma10', 0),
                            'ma20': stock_factors.get('ma20', 0),
                            'ma20_y1': stock_factors.get('ma20_y1', 0),
                        }
                        result_val = simpleeval.simple_eval(factor_def.expression, names=context)
                        stock_factors[factor_code] = result_val
                except Exception as e:
                    logger.warning(f"计算因子 {factor_code} 失败: {e}")
                    stock_factors[factor_code] = 0

            # 4. 综合得分因子：使用 expression 计算
            score_factors_expr = {
                'factor1_rank': 'IF(amount_rank <= 50, 10 - (amount_rank - 1) * 0.2, 0)',
                # 短线趋势新逻辑：
                # 1. MA5 > MA10 > MA20 (短期均线在中期均线上方) → +2，否则 -0.5
                # 2. Pt > MA5 (价格在短期均线上方) → +2，否则 -0.5
                # 3. MA20(t) > MA20(t-1) (中长期均线向上) → +2，否则 -0.5
                # 注意：simpleeval 使用 Python 语法，需要用小写 and/or
                'factor2_ma': 'IF(ma5 > ma10 and ma10 > ma20, 2, -0.5) + IF(close_price > ma5, 2, -0.5) + IF(ma20 > ma20_y1, 2, -0.5)',
                'factor3_vol': 'IF(volume >= volume_y1, 3, -1)',
                'factor4_burst': '(avg_amount_3d / avg_amount_4_20d) * 2',
                'factor5_extreme': '(avg_amount_10d / avg_amount_11_30d) * 3',
            }
            
            # 计算得分因子
            for factor_code, expression in score_factors_expr.items():
                try:
                    factor_def = factor_defs.get(factor_code)
                    if factor_def and factor_def.expression:
                        expr = factor_def.expression
                    else:
                        expr = expression
                    context = {
                        'amount_rank': stock_factors.get('amount_rank', 999),
                        'close_price': stock_factors.get('close_price', 0),
                        'ma5': stock_factors.get('ma5', 0),
                        'ma10': stock_factors.get('ma10', 0),
                        'ma20': stock_factors.get('ma20', 0),
                        'ma20_y1': stock_factors.get('ma20_y1', 0),
                        'volume': stock_factors.get('volume', 0),
                        'volume_y1': stock_factors.get('volume_y1', 0),
                        'avg_amount_3d': stock_factors.get('avg_amount_3d', 0),
                        'avg_amount_4_20d': stock_factors.get('avg_amount_4_20d', 0),
                        'avg_amount_10d': stock_factors.get('avg_amount_10d', 0),
                        'avg_amount_11_30d': stock_factors.get('avg_amount_11_30d', 0),
                    }
                    result_val = simpleeval.simple_eval(expr, names=context)
                    stock_factors[factor_code] = result_val
                except Exception as e:
                    logger.warning(f"计算因子 {factor_code} 失败: {e}")
                    stock_factors[factor_code] = 0
            
            # 计算多头趋势（特殊逻辑）
            if len(stock_hist) >= 16:
                hist_15d = stock_hist.iloc[1:16]
                trend_score = 0
                for i in range(len(hist_15d)):
                    if i + 5 <= len(hist_15d):
                        ma5_i = hist_15d.iloc[i:i+5]['close_price'].mean()
                        if hist_15d.iloc[i]['close_price'] >= ma5_i:
                            trend_score += 0.2
                    if i + 10 <= len(hist_15d):
                        ma10_i = hist_15d.iloc[i:i+10]['close_price'].mean()
                        if hist_15d.iloc[i]['close_price'] >= ma10_i:
                            trend_score += 0.1
                stock_factors['factor6_trend'] = trend_score

            # 计算总分
            total_score = (stock_factors.get('factor1_rank', 0) + 
                          stock_factors.get('factor2_ma', 0) + 
                          stock_factors.get('factor3_vol', 0) + 
                          stock_factors.get('factor4_burst', 0) + 
                          stock_factors.get('factor5_extreme', 0) + 
                          stock_factors.get('factor6_trend', 0))

            results.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'factor1_rank': stock_factors.get('factor1_rank', 0),
                'factor2_ma': stock_factors.get('factor2_ma', 0),
                'factor3_vol': stock_factors.get('factor3_vol', 0),
                'factor4_burst': stock_factors.get('factor4_burst', 0),
                'factor5_extreme': stock_factors.get('factor5_extreme', 0),
                'factor6_trend': stock_factors.get('factor6_trend', 0),

                # 偏离值因子
                'deviation_10d': stock_factors.get('deviation_10d', 0),
                'deviation_30d': stock_factors.get('deviation_30d', 0),
                'remaining_deviation': stock_factors.get('remaining_deviation', 0),

                'total_score': total_score,
                'close': stock_factors.get('close_price', 0),
                'volume': stock_factors.get('volume', 0),
                'turnover': stock_factors.get('turnover', 0),
                # 详细计算数据
                'current_price': round(stock_factors.get('close_price', 0), 2) if stock_factors.get('close_price') else None,
                'ma5': round(stock_factors.get('ma5', 0), 2) if stock_factors.get('ma5') else None,
                'ma10': round(stock_factors.get('ma10', 0), 2) if stock_factors.get('ma10') else None,
                'ma20': round(stock_factors.get('ma20', 0), 2) if stock_factors.get('ma20') else None,
                'ma20_y1': round(stock_factors.get('ma20_y1', 0), 2) if stock_factors.get('ma20_y1') else None,
                'volume_y1': round(stock_factors.get('volume_y1', 0), 2) if stock_factors.get('volume_y1') else None,
                'turnover_y1': round(stock_factors.get('turnover_y1', 0), 2) if stock_factors.get('turnover_y1') else None,
                'amount_rank': stock_factors.get('amount_rank', 999),
                'avg_3d_turnover': round(stock_factors.get('avg_amount_3d', 0), 2) if stock_factors.get('avg_amount_3d') else None,
                'avg_5d_turnover': round(stock_factors.get('avg_amount_5d', 0), 2) if stock_factors.get('avg_amount_5d') else None,
                'avg_10d_turnover': round(stock_factors.get('avg_amount_10d', 0), 2) if stock_factors.get('avg_amount_10d') else None,
                'avg_20d_turnover': round(stock_factors.get('avg_amount_20d', 0), 2) if stock_factors.get('avg_amount_20d') else None,
                'avg_5_20d_turnover': round(stock_factors.get('avg_amount_4_20d', 0), 2) if stock_factors.get('avg_amount_4_20d') else None,
                'avg_11_30d_turnover': round(stock_factors.get('avg_amount_11_30d', 0), 2) if stock_factors.get('avg_amount_11_30d') else None,
            })
            
            # 调试日志 - 打印中间因子计算结果
            if stock_code == 'sz.300476':
                logger.info(f"🔍 FACTOR_CALC: {stock_code}, ma5={stock_factors.get('ma5')}, ma10={stock_factors.get('ma10')}, avg_3d={stock_factors.get('avg_amount_3d')}, len_hist={len(stock_hist)}")

        if not results:
            return pd.DataFrame()

        result_df = pd.DataFrame(results)
        
        # 计算因子1：根据成交额排名（成交额权重）
        # 第一名得10分，每少一名减0.2分，最低为0
        result_df = result_df.sort_values('turnover', ascending=False).reset_index(drop=True)
        result_df['factor1_rank'] = [10 - x * 0.2 if (10 - x * 0.2) > 0 else 0 for x in range(len(result_df))]

        # 打印调试信息：检查成交额前10的股票
        top10_by_turnover = result_df.head(10)
        logger.info(f"🔍 成交额前10股票: {top10_by_turnover[['stock_code', 'stock_name', 'turnover', 'factor1_rank']].to_dict('records')}")

        # 重新计算总分（包含所有6个因子）
        result_df['total_score'] = (result_df['factor1_rank'] + result_df['factor2_ma'] + 
                                    result_df['factor3_vol'] + result_df['factor4_burst'] + 
                                    result_df['factor5_extreme'] + result_df['factor6_trend'])

        # 按总分排序（factor1_rank 保持不变，仍然是成交额排名时的得分）
        result_df = result_df.sort_values('total_score', ascending=False).reset_index(drop=True)

        # 打印调试信息：检查利欧股份的数据
        lj_stock = result_df[result_df['stock_code'].str.contains('002131|利欧', na=False)]
        if not lj_stock.empty:
            logger.info(f"🔍 利欧股份因子数据: {lj_stock[['stock_code', 'stock_name', 'turnover', 'factor1_rank', 'total_score']].to_dict('records')}")

        logger.info(f"✅ 因子计算完成: {len(result_df)} 只股票")
        logger.info(f"前5只股票得分: {result_df[['stock_code', 'stock_name', 'total_score']].head().to_dict('records')}")

        return result_df

    def _calculate_sector_scores(self, factors_df, db_session, trade_date):
        """
        根据因子得分计算板块得分
        选取前30只股票，按排名给所属板块加分（第1名加30分，每少1名少1分）

        Args:
            factors_df: 包含因子得分的DataFrame
            db_session: 数据库会话
            trade_date: 交易日期

        Returns:
            pd.DataFrame: 板块得分排名
        """
        import pandas as pd
        from models.kline import StockSectorRelation, StockSector, StockDailyKLine

        # 选取前30只股票
        top30_stocks = factors_df.head(30)

        if top30_stocks.empty:
            return pd.DataFrame()

        stock_codes = top30_stocks['stock_code'].tolist()

        # 查询这些股票的板块关联
        sector_relations = db_session.query(
            StockSectorRelation.stock_code,
            StockSector.id,
            StockSector.sector_name,
            StockSector.sector_code
        ).join(
            StockSector, StockSector.id == StockSectorRelation.sector_id
        ).filter(
            StockSectorRelation.stock_code.in_(stock_codes)
        ).all()

        # 查询股票元数据（补充名称）
        stock_name_map = {}
        try:
            from models.stockbasic import StockBasic
            stock_metadatas = db_session.query(
                StockBasic.stock_code,
                StockBasic.stock_name
            ).filter(
                StockBasic.stock_code.in_(stock_codes)
            ).all()
            stock_name_map = {sm.stock_code: sm.stock_name if sm.stock_name and sm.stock_name != '1' else sm.stock_code 
                            for sm in stock_metadatas}
        except Exception as e:
            logger.warning(f"获取股票元数据失败: {e}")

        # 构建板块得分
        sector_scores = {}
        for rank, (_, row) in enumerate(top30_stocks.iterrows(), 1):
            stock_code = row['stock_code']
            stock_name = row.get('stock_name', '')
            # 补充股票名称
            if not stock_name or stock_name == '1':
                stock_name = stock_name_map.get(stock_code, stock_code)
            score = 31 - rank  # 第1名30分，第2名29分，...
            total_score = row.get('total_score', 0)  # 该股票的总得分

            # 查找该股票所属的所有板块
            stock_sectors = [rel for rel in sector_relations if rel.stock_code == stock_code]
            logger.info(f"🔍 股票 {stock_code} 所属板块: {[(rel.sector_code, rel.sector_name) for rel in stock_sectors]}")
            
            for rel in stock_sectors:
                    key = rel.sector_code
                    if key not in sector_scores:
                        sector_scores[key] = {
                            'sector_code': rel.sector_code,
                            'sector_name': rel.sector_name,
                            'score': 0,
                            'stock_count': 0,
                            'top_stocks': []  # 前30股票中该板块的股票列表
                        }
                    sector_scores[key]['score'] += score
                    sector_scores[key]['stock_count'] += 1
                    # 添加股票信息到列表
                    sector_scores[key]['top_stocks'].append({
                        'code': stock_code,
                        'name': stock_name,
                        'totalScore': total_score,
                        'rank': rank
                    })

        # 转换为DataFrame并排序
        if not sector_scores:
            return pd.DataFrame()

        sector_df = pd.DataFrame(list(sector_scores.values()))
        sector_df = sector_df.sort_values('score', ascending=False).reset_index(drop=True)

        logger.info(f"✅ 板块得分计算完成: {len(sector_df)} 个板块")
        logger.info(f"前5个板块: {sector_df[['sector_name', 'score', 'stock_count', 'top_stocks']].head().to_dict('records')}")

        return sector_df

    def _get_sector_stats(self, top_df):
        """
        获取前N股票所属板块统计

        Args:
            top_df: 成交额前N的股票DataFrame

        Returns:
            pd.DataFrame: 板块统计数据，按股票数量降序排序
        """
        import pandas as pd

        if top_df.empty:
            return pd.DataFrame()

        # 获取板块信息并添加到数据中
        from models.kline import StockSectorRelation, StockSector

        stock_codes = top_df['stock_code'].unique().tolist()

        sector_relations = db.session.query(
            StockSectorRelation.stock_code,
            StockSector.sector_name
        ).join(
            StockSector, StockSector.id == StockSectorRelation.sector_id
        ).filter(
            StockSectorRelation.stock_code.in_(stock_codes)
        ).all()

        # 创建股票代码到板块名称的映射
        stock_sector_map = {rel.stock_code: rel.sector_name for rel in sector_relations}

        # 添加板块信息
        top_df = top_df.copy()
        top_df['sector'] = top_df['stock_code'].map(stock_sector_map).fillna('未分类')

        # 按板块分组统计
        if 'change_percent' in top_df.columns:
            sector_stats = top_df.groupby('sector').agg({
                'stock_code': 'count',
                'turnover': 'sum',
                'change_percent': 'mean'
            }).reset_index()
        else:
            sector_stats = top_df.groupby('sector').agg({
                'stock_code': 'count',
                'turnover': 'sum'
            }).reset_index()
            sector_stats['change_percent'] = 0

        # 重命名列
        sector_stats.columns = ['sector', 'stock_count', 'total_turnover', 'avg_change_percent']

        # 按股票数量降序排序
        sector_stats = sector_stats.sort_values('stock_count', ascending=False)

        logger.info(f"板块统计: {len(sector_stats)} 个板块")
        return sector_stats

    def _save_review_results(self, task, all_df, top_df, factors_df, sector_scores, trade_date):
        """
        保存复盘分析结果（使用 ReviewResultBuilder 拆分的独立方法）
        """
        # 使用 ReviewResultBuilder 构建各种结果
        builder = ReviewResultBuilder(db.session)

        # 1. 构建指数行情结果
        results = builder.build_index_results(task, all_df)

        # 2. 构建成交额排名结果
        results.extend(builder.build_top_stocks_result(task, top_df))

        # 3. 构建因子分析结果
        results.extend(builder.build_factor_analysis_result(task, factors_df, top_df))

        # 4. 构建板块得分结果
        results.extend(builder.build_sector_score_result(task, factors_df, sector_scores))

        # 5. 构建因子树形结构结果
        results.extend(builder.build_factor_tree_result(task))

        # 6. 构建大盘指数计算结果
        results.extend(builder.build_market_analysis_result(task, trade_date))

        # 批量保存所有结果
        if results:
            from models.reviewresult import ReviewResult
            mappings = []
            for r in results:
                mappings.append({
                    'task_id': r.task_id,
                    'dimension': r.dimension,
                    'metric_name': r.metric_name,
                    'metric_value': r.metric_value,
                    'compare_value': r.compare_value,
                    'change_rate': r.change_rate,
                    'status': r.status,
                    'suggestion': r.suggestion,
                    'detail_data': r.detail_data
                })
            db.session.bulk_insert_mappings(ReviewResult, mappings)

        db.session.commit()
        logger.info(f"✅ 保存了 {len(results)} 条分析结果")

        return results
        
        # 从 all_df 中获取指数数据
        if all_df is not None and not all_df.empty:
            index_data = all_df[all_df['stock_code'].isin(INDEX_CODES)]
        else:
            index_data = pd.DataFrame()
        
        # 批量查询指数元数据（补充名称为1的）
        index_codes = index_data['stock_code'].tolist() if not index_data.empty else []
        index_metadata_map = {}
        try:
            from models.stockbasic import StockBasic
            index_metadatas = db.session.query(
                StockBasic.stock_code,
                StockBasic.stock_name
            ).filter(
                StockBasic.stock_code.in_(index_codes)
            ).all()
            index_metadata_map = {im.stock_code: im.stock_name for im in index_metadatas}
        except Exception as e:
            logger.warning(f"获取指数元数据失败: {e}")
        
        # 转换指数数据格式
        index_list = []
        for _, row in index_data.iterrows():
            stock_code = row.get('stock_code', '')
            stock_name = row.get('stock_name', '')
            # 如果名称为1，从元数据补充
            if not stock_name or stock_name == '1':
                stock_name = index_metadata_map.get(stock_code, stock_code)
            
            index_list.append({
                'code': stock_code,
                'name': stock_name,
                'close': float(row.get('close_price', 0)) if pd.notna(row.get('close_price', 0)) else 0,
                'changePercent': float(row.get('change_percent', 0)) if pd.notna(row.get('change_percent', 0)) else 0,
                'amount': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'turnover': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'volume': float(row.get('volume', 0)) if pd.notna(row.get('volume', 0)) else 0
            })
        
        # 保存指数数据
        if index_list:
            from models.reviewresult import ReviewResult
            index_result = ReviewResult()
            index_result.task_id = task.id
            index_result.dimension = '指数行情'
            index_result.metric_name = '主要指数'
            index_result.metric_value = str(len(index_list))
            index_result.status = 'normal'
            index_result.detail_data = json.dumps({
                'type': 'index_data',
                'indexes': index_list
        }, ensure_ascii=False)
            results.append(index_result)

        # 2. 成交额前100统计（仅保留详细数据，移除汇总指标）
        from models.reviewresult import ReviewResult
        top_result = ReviewResult()
        top_result.task_id = task.id
        top_result.dimension = '成交额排名'
        top_result.metric_name = '前100股票明细'
        top_result.metric_value = str(len(top_df))
        top_result.status = 'normal'

        # 批量获取所有100只股票的板块信息
        stock_codes = top_df['stock_code'].tolist()  # 获取全部100只
        sector_map = {}  # stock_code -> sector_names
        try:
            from models.kline import StockSectorRelation, StockSector
            relations = db.session.query(
                StockSectorRelation.stock_code, StockSectorRelation.priority,
                StockSector.sector_name, StockSector.sector_type, StockSector.sector_code
            ).join(
                StockSector, StockSector.id == StockSectorRelation.sector_id
            ).filter(StockSectorRelation.stock_code.in_(stock_codes)).all()
            for stock_code, priority, sector_name, sector_type, sector_code in relations:
                if stock_code not in sector_map:
                    sector_map[stock_code] = []
                sector_map[stock_code].append({
                    'sector_name': sector_name,
                    'sector_type': sector_type,
                    'sector_code': sector_code,
                    'priority': priority or 0,
                })
            # 每只股票的板块按人工优先级降序（与元数据/个股板块关联一致）
            for _c in sector_map:
                sector_map[_c].sort(key=lambda x: -(x.get('priority') or 0))
        except Exception as e:
            logger.warning(f"获取板块信息失败: {e}")

        # Top 100 详细信息 - 转换格式以匹配前端
        top100_detail = []
        
        # 直接使用 K 线数据中的股票名称
        stock_name_map_from_kline = dict(zip(top_df['stock_code'], top_df['stock_name']))
        
        for _, row in top_df.iterrows():  # 遍历全部100只
            stock_code = row.get('stock_code', '')
            sector_info = ','.join([_s['sector_name'] for _s in sector_map.get(stock_code, [])])

            # 直接使用 K 线数据中的股票名称
            stock_name = stock_name_map_from_kline.get(stock_code, '')
            # 如果名称为1，从元数据表补充
            if not stock_name or stock_name == '1':
                stock_name = stock_code  # 临时使用代码，后续批量查询补充
            
            # 获取市值信息
            total_mv = 0
            circulate_mv = 0
            industry = ''
            
            top100_detail.append({
                'code': stock_code,
                'name': stock_name,
                'sector': sector_info,
                'sectors': sector_map.get(stock_code, []),
                'industry': industry,
                'amount': float(row['turnover']) / 100000000 if pd.notna(row['turnover']) else 0,
                'turnover': float(row['turnover']) / 100000000 if pd.notna(row['turnover']) else 0,
                'changePercent': float(row.get('change_percent', 0)) if pd.notna(row.get('change_percent', 0)) else 0,
                'totalMarketValue': total_mv,
                'circulateMarketValue': circulate_mv
            })
        
        # 批量查询股票元数据（名称和市值）
        stock_codes = [item['code'] for item in top100_detail]
        try:
            from models.stockbasic import StockBasic
            stock_metadatas = db.session.query(
                StockBasic.stock_code, 
                StockBasic.stock_name,
                StockBasic.industry,
                StockBasic.total_market_value,
                StockBasic.circulate_market_value
            ).filter(
                StockBasic.stock_code.in_(stock_codes)
            ).all()
            stock_metadata_map = {sm.stock_code: {
                'stock_name': sm.stock_name if sm.stock_name and sm.stock_name != '1' else sm.stock_code,
                'industry': sm.industry or '',
                'total_market_value': float(sm.total_market_value) if sm.total_market_value else 0,
                'circulate_market_value': float(sm.circulate_market_value) if sm.circulate_market_value else 0
            } for sm in stock_metadatas}
            
            # 更新 top100_detail
            for item in top100_detail:
                metadata = stock_metadata_map.get(item['code'], {})
                item['name'] = metadata.get('stock_name', item['code'])
                item['industry'] = metadata.get('industry', '')
                item['totalMarketValue'] = metadata.get('total_market_value', 0)
                item['circulateMarketValue'] = metadata.get('circulate_market_value', 0)
        except Exception as e:
            logger.warning(f"批量获取股票元数据失败: {e}")

        top_result.detail_data = json.dumps({
            'count': len(top_df),
            'totalTurnover': float(top_df['turnover'].sum()) / 100000000,
            'avgTurnover': float(top_df['turnover'].mean()) / 100000000,
            'maxTurnover': float(top_df['turnover'].max()) / 100000000,
            'minTurnover': float(top_df['turnover'].min()) / 100000000,
            'stocks': top100_detail,  # 保存完整的100只股票
            'top10': top100_detail[:10]  # 前10只
        }, ensure_ascii=False)
        results.append(top_result)

        # 3. 因子分析结果 - 前10只股票
        from models.reviewresult import ReviewResult
        top10_result = ReviewResult()
        top10_result.task_id = task.id
        top10_result.dimension = '因子分析'
        top10_result.metric_name = '前10股票'
        top10_result.status = 'normal'

        # 获取股票名称映射（从top_df - K线数据）
        stock_name_map = dict(zip(top_df['stock_code'], top_df['stock_name']))

        # 批量查询股票元数据（名称和市值）- 用于补充名称为1的股票
        factor_stock_codes = factors_df.head(10)['stock_code'].tolist()
        stock_metadata_map = {}
        try:
            from models.stockbasic import StockBasic
            stock_metadatas = db.session.query(
                StockBasic.stock_code, 
                StockBasic.stock_name,
                StockBasic.total_market_value,
                StockBasic.circulate_market_value
            ).filter(
                StockBasic.stock_code.in_(factor_stock_codes)
            ).all()
            stock_metadata_map = {sm.stock_code: {
                'stock_name': sm.stock_name if sm.stock_name and sm.stock_name != '1' else sm.stock_code,
                'total_market_value': float(sm.total_market_value) if sm.total_market_value else 0,
                'circulate_market_value': float(sm.circulate_market_value) if sm.circulate_market_value else 0
            } for sm in stock_metadatas}
        except Exception as e:
            logger.warning(f"获取因子分析元数据失败: {e}")

        # 转换数据格式以匹配前端 - 使用完整的100只股票的因子数据
        # factors_df 已经按 total_score 排序，取前10只保存
        top10_factors_detail = []
        for _, row in factors_df.head(10).iterrows():
            stock_code = row.get('stock_code', '')
            sector_info = ','.join([_s['sector_name'] for _s in sector_map.get(stock_code, [])])
            
            # 依次尝试从 K线数据、factors_df、元数据表获取名称
            stock_name = stock_name_map.get(stock_code, '')
            if not stock_name or stock_name == '1':
                stock_name = row.get('stock_name', '')
            if not stock_name or stock_name == '1':
                metadata = stock_metadata_map.get(stock_code, {})
                stock_name = metadata.get('stock_name', stock_code)
            
            # 获取市值信息
            metadata = stock_metadata_map.get(stock_code, {})
            total_mv = metadata.get('total_market_value', 0)
            circulate_mv = metadata.get('circulate_market_value', 0)

            # ========== 动态获取因子列 ==========
            # 只获取表达式中使用的因子，而不是所有 active 的因子
            try:
                from models.expression import ScoreExpression
                score_expr = ScoreExpression.query.filter_by(
                    scope='stock',
                    is_default=True,
                    is_active=True
                ).first()
                if score_expr and score_expr.factors:
                    factor_codes = score_expr.factors
                else:
                    factor_codes = []
                logger.info(f"🔍 表达式使用的因子: {factor_codes}")
                logger.info(f"🔍 factors_df 列: {list(factors_df.columns)}")
                logger.info(f"🔍 factors_df 前3行: {factors_df.head(3)[['stock_code', 'factor1_rank', 'factor2_ma', 'factor3_vol', 'factor4_burst']].to_dict()}")
            except Exception as e:
                logger.warning(f"获取表达式因子失败: {e}")
                factor_codes = []
            
            # 构建动态因子数据
            stock_data = {
                'code': stock_code,
                'name': stock_name,
                'sector': sector_info,
                'sectors': sector_map.get(stock_code, []),
                'industry': '',
                'amount': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'changePercent': float(row.get('change_percent', 0)),
                'totalScore': float(row.get('total_score', 0)),
                'close': float(row.get('close', 0)),
                'turnover': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'totalMarketValue': total_mv,
                'circulateMarketValue': circulate_mv,
            }
            
            # 添加因子详情需要的字段（与 factorTree 中的字段名对应）
            
            stock_data['close'] = float(row.get('close_price', 0))
            stock_data['close_price'] = float(row.get('close_price', 0))
            stock_data['volume'] = float(row.get('volume', 0)) if pd.notna(row.get('volume', 0)) else 0
            stock_data['turnover'] = float(row.get('turnover', 0)) if pd.notna(row.get('turnover', 0)) else 0
            stock_data['volume_y1'] = float(row.get('volume_y1', 0)) if pd.notna(row.get('volume_y1', 0)) else 0
            stock_data['turnover_y1'] = float(row.get('turnover_y1', 0)) if pd.notna(row.get('turnover_y1', 0)) else 0
            stock_data['ma5'] = float(row.get('ma5', 0)) if pd.notna(row.get('ma5', 0)) else 0
            stock_data['ma10'] = float(row.get('ma10', 0)) if pd.notna(row.get('ma10', 0)) else 0
            stock_data['ma20'] = float(row.get('ma20', 0)) if pd.notna(row.get('ma20', 0)) else 0
            stock_data['amount_rank'] = float(row.get('amount_rank', 999)) if pd.notna(row.get('amount_rank', 999)) else 999
            stock_data['turnover_rank'] = float(row.get('turnover_rank', 999)) if pd.notna(row.get('turnover_rank', 999)) else 999
            stock_data['avg_amount_3d'] = float(row.get('avg_3d_turnover', 0)) if pd.notna(row.get('avg_3d_turnover', 0)) else 0
            stock_data['avg_amount_5d'] = float(row.get('avg_5d_turnover', 0)) if pd.notna(row.get('avg_5d_turnover', 0)) else 0
            stock_data['avg_amount_10d'] = float(row.get('avg_10d_turnover', 0)) if pd.notna(row.get('avg_10d_turnover', 0)) else 0
            stock_data['avg_amount_20d'] = float(row.get('avg_20d_turnover', 0)) if pd.notna(row.get('avg_20d_turnover', 0)) else 0
            stock_data['avg_amount_4_20d'] = float(row.get('avg_5_20d_turnover', 0)) if pd.notna(row.get('avg_5_20d_turnover', 0)) else 0
            stock_data['avg_amount_11_30d'] = float(row.get('avg_11_30d_turnover', 0)) if pd.notna(row.get('avg_11_30d_turnover', 0)) else 0
            
            # 添加动态因子列 - 包括所有依赖的原子因子
            # 从因子表达式依赖中获取所有需要的因子
            all_needed_factors = set(factor_codes)
            
            # 添加所有在 factors_df 中的因子列（除了基础字段）
            kline_fields = {'stock_code', 'stock_name', 'close_price', 'volume', 'turnover', 
                          'pct_change', 'change_percent', 'close', 'total_score'}
            for col in factors_df.columns:
                if col not in kline_fields:
                    all_needed_factors.add(col)
            
            # 保存所有需要的因子
            for fc in all_needed_factors:
                if fc in row.index:
                    val = row.get(fc, 0)
                    stock_data[fc] = float(val) if pd.notna(val) else 0
                else:
                    stock_data[fc] = 0
            
            # 调试日志
            logger.info(f"🔍 因子数据: fc={factor_codes[:3]}, row_cols={list(row.index[:10])}, close_price_val={stock_data.get('close_price', 'NOT_FOUND')}, ma5={stock_data.get('ma5', 'NOT_FOUND')}")
            
            # 添加K线原始数据列
            for col in ['current_price', 'ma5', 'ma10', 'vol_current', 'vol_prev', 
                        'avg_3d_turnover', 'avg_5_20d_turnover', 'avg_10d_turnover', 
                        'avg_11_30d_turnover', 'ma5_15d', 'ma10_15d']:
                if col in row.index and pd.notna(row.get(col)):
                    stock_data[col] = row.get(col)
            
            top10_factors_detail.append(stock_data)

        logger.info(f"🔍 保存因子分析数据: 前10只股票factor1Rank={top10_factors_detail[0].get('factor1Rank') if top10_factors_detail else 0}")
        
        top10_result.detail_data = json.dumps({
            'type': 'top10_stocks',
            'stocks': top10_factors_detail
        }, ensure_ascii=False)
        results.append(top10_result)

        # 4. 板块得分结果
        if not sector_scores.empty:
            from models.reviewresult import ReviewResult
            sector_result = ReviewResult()
            sector_result.task_id = task.id
            sector_result.dimension = '板块得分'
            sector_result.metric_name = '前10板块'
            sector_result.status = 'normal'

            # 获取前30只股票的因子数据
            top30_stocks = factors_df.head(30)
            top30_codes = top30_stocks['stock_code'].tolist()
            
            # 查询前30只股票的板块关联
            sector_relations_top30 = {}
            try:
                relations = db.session.query(
                    StockSectorRelation.stock_code,
                    StockSector.sector_code,
                    StockSector.sector_name
                ).join(
                    StockSector, StockSector.id == StockSectorRelation.sector_id
                ).filter(
                    StockSectorRelation.stock_code.in_(top30_codes)
                ).all()
                for rel in relations:
                    if rel.sector_code not in sector_relations_top30:
                        sector_relations_top30[rel.sector_code] = []
                    sector_relations_top30[rel.sector_code].append(rel.stock_code)
            except Exception as e:
                logger.warning(f"获取前30股票板块关联失败: {e}")

            # 转换数据格式以匹配前端
            top10_sectors = []
            for _, row in sector_scores.head(10).iterrows():
                sector_name = row.get('sector_name', '')
                # 获取板块代码
                sector_code = row.get('sector_code', '')
                
                top10_sectors.append({
                    'sector': sector_name,  # 前端期望 'sector'
                    'sectorCode': sector_code,  # 板块代码，用于获取成分股
                    'name': sector_name,
                    'count': int(row.get('stock_count', 0)),  # 前端期望 'count'
                    'stockCount': int(row.get('stock_count', 0)),
                    'score': float(row.get('score', 0)),
                    'topStocks': json.loads(row.get('top_stocks', '[]')) if isinstance(row.get('top_stocks'), str) else (row.get('top_stocks', []) if isinstance(row.get('top_stocks'), list) else [])  # 前30股票中该板块的股票列表
                })

            sector_result.detail_data = json.dumps({
                'type': 'sector_scores',
                'sectors': top10_sectors  # 前端期望 'sectors'
            }, ensure_ascii=False)
            results.append(sector_result)

        # 5. 因子树形结构 - 保存表达式中使用的因子的依赖关系
        try:
            from models.factor import FactorDefine
            from models.expression import ScoreExpression
            
            # 获取表达式中使用的因子列表
            score_expr = ScoreExpression.query.filter_by(
                scope='stock',
                is_default=True,
                is_active=True
            ).first()
            
            if score_expr and score_expr.factors:
                factor_codes_in_expr = score_expr.factors
            else:
                factor_codes_in_expr = []
            
            # 只获取表达式中使用的因子定义
            all_stock_factors = FactorDefine.query.filter(
                FactorDefine.factor_scope == 'stock',
                FactorDefine.is_active == True,
                FactorDefine.factor_code.in_(factor_codes_in_expr)
            ).all()
            
            logger.info(f"🔍 因子树只显示表达式中的因子: {factor_codes_in_expr}")
            
            # 构建因子依赖树
            factor_tree = _build_factor_tree(all_stock_factors)
            
            # 保存因子树
            from models.reviewresult import ReviewResult
            factor_tree_result = ReviewResult()
            factor_tree_result.task_id = task.id
            factor_tree_result.dimension = '因子体系'
            factor_tree_result.metric_name = '因子依赖树'
            factor_tree_result.metric_value = str(len(all_stock_factors))
            factor_tree_result.status = 'normal'
            factor_tree_result.detail_data = json.dumps({
                'type': 'factor_tree',
                'factors': factor_tree
            }, ensure_ascii=False)
            results.append(factor_tree_result)
            logger.info(f"✅ 保存因子树: {len(factor_tree)} 个因子")
        except Exception as e:
            logger.warning(f"保存因子树失败: {e}")

        # ========== 大盘指数计算 ==========
        try:
            from models.kline import StockDailyKLine
            from services.factor_service import FactorCalculator
            factor_calc = FactorCalculator()
            
            # 计算大盘因子（使用交易日作为日期）
            market_factors = factor_calc.calculate_market_factors(trade_date, db.session)
            logger.info(f"📊 大盘因子计算结果: {market_factors}")
            
            # 保存大盘指数结果 - 整合为树状结构
            from models.reviewresult import ReviewResult
            
            # 获取主要指数行情
            INDEX_CODES = {
                'sh.000001': '上证指数',
                'sz.399001': '深证成指',
                'sz.399006': '创业板指',
                'sh.000300': '沪深300',
                'sh.000905': '中证500',
                'sh.000852': '中证1000',
            }
            
            index_prices = {}
            for code, name in INDEX_CODES.items():
                kline = db.session.query(StockDailyKLine).filter(
                    StockDailyKLine.stock_code == code,
                    StockDailyKLine.trade_date == trade_date
                ).first()
                if kline:
                    index_prices[code] = {
                        'name': name,
                        'close': float(kline.close_price) if kline.close_price else 0,
                        'changePercent': float(kline.change_percent) if kline.change_percent else 0,
                        'turnover': float(kline.turnover) if kline.turnover else 0
                    }
            
            # 构建大盘因子树 - 动态从数据库读取
            from models.factor import FactorDefine
            from models.expression import ScoreExpression
            import re

            builtins = {'IF', 'ABS', 'MAX', 'MIN', 'SUM', 'AVG', 'SQRT', 'LOG', 'ROUND', 'POW'}

            # 获取大盘综合得分的 ScoreExpression（优先于 factor_define.expression）
            market_score_expr = db.session.query(ScoreExpression).filter_by(
                scope='market', is_default=True, is_active=True
            ).first()

            # 获取所有大盘因子定义
            market_factor_defs = db.session.query(FactorDefine).filter(
                FactorDefine.factor_scope == 'market',
                FactorDefine.is_active == True
            ).order_by(FactorDefine.id).all()
            market_factor_code_set = {f.factor_code for f in market_factor_defs}

            # 构建动态因子树
            factors_tree = {}
            for f in market_factor_defs:
                # 解析依赖：如果是表达式计算，提取表达式中的变量名
                dependencies = []
                if f.source == 'calculated' and f.expression:
                    var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', f.expression)
                    dependencies = [v for v in var_names if v not in builtins and v in market_factor_code_set]

                factors_tree[f.factor_code] = {
                    'factor_name': f.factor_name,
                    'value': float(market_factors.get(f.factor_code, 0)) if market_factors.get(f.factor_code, 0) is not None else 0,
                    'expression': f.expression or '',
                    'dependencies': dependencies,
                    'source': f.source,
                    'calculation_method': f.calculation_method
                }

            # 用 ScoreExpression 覆盖 market_score 的 expression 和 dependencies
            # 确保前端展示的树与实际计算逻辑一致
            if market_score_expr and market_score_expr.expression:
                var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', market_score_expr.expression)
                score_deps = [v for v in var_names if v not in builtins and v in market_factor_code_set]
                if 'market_score' in factors_tree:
                    factors_tree['market_score']['expression'] = market_score_expr.expression
                    factors_tree['market_score']['dependencies'] = score_deps
                    factors_tree['market_score']['value'] = float(market_factors.get('market_score', 0)) if market_factors.get('market_score') is not None else 0
                else:
                    # factor_define 中没有 market_score 时兜底创建
                    factors_tree['market_score'] = {
                        'factor_name': '大盘综合得分',
                        'value': float(market_factors.get('market_score', 0)) if market_factors.get('market_score') is not None else 0,
                        'expression': market_score_expr.expression,
                        'dependencies': score_deps,
                        'source': 'calculated',
                        'calculation_method': 'expression'
                    }
            
            market_tree = {
                'type': 'market_overview',
                'indexPrices': index_prices,
                'factors': factors_tree
            }
            
            # 保存为一条记录
            market_result = ReviewResult()
            market_result.task_id = task.id
            market_result.dimension = '市场'
            market_result.metric_name = '大盘综合得分'
            market_result.metric_value = str(float(market_factors.get('market_score', 0)) if market_factors.get('market_score', 0) is not None else 0)
            market_result.status = 'normal'
            market_result.detail_data = json.dumps(market_tree, ensure_ascii=False)
            results.append(market_result)
            
            logger.info(f"✅ 保存大盘指数: {len(index_prices)} 个指数 + {len(market_tree['factors'])} 个因子")
        except Exception as e:
            import traceback
            logger.warning(f"计算大盘指数失败: {e}\n{traceback.format_exc()}")

        # 批量保存所有结果
        if results:
            from models.reviewresult import ReviewResult
            mappings = []
            for r in results:
                mappings.append({
                    'task_id': r.task_id,
                    'dimension': r.dimension,
                    'metric_name': r.metric_name,
                    'metric_value': r.metric_value,
                    'compare_value': r.compare_value,
                    'change_rate': r.change_rate,
                    'status': r.status,
                    'suggestion': r.suggestion,
                    'detail_data': r.detail_data
                })
            db.session.bulk_insert_mappings(ReviewResult, mappings)

        db.session.commit()
        logger.info(f"✅ 保存了 {len(results)} 条分析结果")

        return results

def get_review_task_service():
    """获取复盘任务服务实例"""
    return ReviewTaskService()

