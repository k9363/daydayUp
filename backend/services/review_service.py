"""
复盘任务服务 - 核心分析引擎
"""
import json
import logging
from datetime import datetime
from collections import defaultdict
from extensions import db
from models.reviewtask import ReviewTask
from models.reviewresult import ReviewResult
from services.baostock_service import get_baostock_service
from utils.excel_utils import read_excel

logger = logging.getLogger(__name__)


class ReviewTaskService:
    """复盘任务服务类"""
    
    def create_task(self, task_name, review_type, dimensions=None, rules=None,
                    trade_date=None, data_source_type='baostock',
                    data_source_name=None, data_source_desc=None):
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

        Returns:
            ReviewTask: 创建的任务
        """
        task = ReviewTask()
        task.task_name = task_name
        task.review_type = review_type
        task.dimensions = json.dumps(dimensions, ensure_ascii=False) if dimensions else None
        task.rules = json.dumps(rules, ensure_ascii=False) if rules else None
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
        执行复盘任务（Excel文件方式）

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
            # 从任务中读取数据源信息
            file_path = task.file_path
            data_source_type = task.data_source_type

            # 读取数据
            if data_source_type == 'excel' and file_path:
                data = read_excel(file_path)
            else:
                raise Exception(f"不支持的数据源类型({data_source_type})或文件不存在")
            
            if not data:
                raise Exception("数据为空")
            
            # 3. 执行分析
            results = self._analyze_data(task, data)
            
            # 4. 保存结果
            for result in results:
                db.session.add(result)
            
            # 5. 更新任务状态
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
            raise Exception(f"复盘执行失败: {str(e)}")
    
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
    
    def get_task_list(self, include_completed=False):
        """
        获取任务列表
        
        Args:
            include_completed: 是否包含已完成的任务
        
        Returns:
            list: 任务列表
        """
        query = ReviewTask.query
        
        if not include_completed:
            query = query.filter(ReviewTask.status != 'completed')
        
        return query.order_by(ReviewTask.create_time.desc()).all()
    
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
        执行Baostock复盘任务 - 新版
        1. 获取指定时间A股全部股票日线数据
        2. 获取前先查库（StockDaily），没有则通过API进行查询
        3. 获取后落库，对原始数据进行积累
        4. 筛选出每日成交额前100，按照板块进行划分

        Args:
            task_id: 任务ID

        Returns:
            ReviewTask: 执行后的任务
        """
        import pandas as pd
        from models.stockdaily import StockDaily

        task = ReviewTask.query.get(task_id)

        if not task:
            raise Exception("任务不存在")

        task.status = 'running'
        task.start_time = datetime.now()
        db.session.commit()

        try:
            # 从任务中获取交易日期
            trade_date = task.trade_date

            # 2. 先查库：使用新的fetch_and_save_daily_data方法
            # 这个方法会自动检查数据库，如果没有则从API获取并落库
            baostock_service = get_baostock_service()
            saved_count = baostock_service.fetch_and_save_daily_data(trade_date, db.session)

            if saved_count == 0:
                raise Exception(f"未能获取到{trade_date}日的A股日线数据")

            # 3. 从数据库查询已保存的数据进行分析
            from models.stockdaily import StockDaily
            stock_records = db.session.query(StockDaily).filter(
                StockDaily.trade_date == trade_date
            ).all()

            if not stock_records:
                raise Exception(f"数据库中未找到{trade_date}日的A股日线数据")

            stock_data = [record.to_dict() for record in stock_records]

            # 获取所有股票代码
            stock_codes = list(set(record.stock_code for record in stock_records))

            # 补充元数据：股票基本信息和板块关联
            logger.info(f"开始为 {len(stock_codes)} 只股票补充元数据...")
            
            # 检查配置
            is_enabled = is_auto_supplement_enabled('review')
            logger.info(f"复盘元数据补充配置: is_auto_supplement_enabled('review')={is_enabled}")
            
            try:
                from services.metadata_service import get_metadata_service

                # 检查是否启用自动补充
                if is_enabled:
                    logger.info("开始执行元数据补充...")
                    metadata_service = get_metadata_service()

                    # 使用统一的综合补充方法
                    result = metadata_service.supplement_metadata(
                        stock_codes=stock_codes,
                        db_session=db.session,
                        context='review'
                    )
                    logger.info(f"元数据补充完成: {result}")
                else:
                    logger.info("复盘时自动补充元数据已禁用")

            except Exception as e:
                logger.error(f"补充元数据失败: {e}")

            # 转换为DataFrame
            df = pd.DataFrame(stock_data)

            # 4.1 获取板块信息并添加到数据中
            from models.kline import StockSectorRelation, StockSector
            sector_relations = db.session.query(
                StockSectorRelation.stock_code,
                StockSector.sector_name
            ).join(
                StockSector, StockSector.id == StockSectorRelation.sector_id
            ).filter(
                StockSectorRelation.stock_code.in_([r.stock_code for r in stock_records]),
                StockSectorRelation.is_main == 1  # 只获取主板块
            ).all()
            
            # 创建股票代码到板块名称的映射
            stock_sector_map = {rel.stock_code: rel.sector_name for rel in sector_relations}
            
            # 添加板块列到DataFrame
            df['sector'] = df['stock_code'].map(stock_sector_map).fillna('未分类')

            # 4. 更新任务的数据源信息（替代原来的DataRecord）
            task.row_count = len(df)
            task.column_count = len(df.columns)
            task.data_summary = f"{trade_date}日A股数据: {len(df)}只股票"
            db.session.commit()

            # 5. 筛选成交额前100
            if 'turnover' not in df.columns and 'amount' not in df.columns:
                raise Exception("数据中缺少成交额(turnover/amount)字段")

            # 使用 turnover 字段（单位：元）
            df['turnover'] = pd.to_numeric(df.get('turnover', 0), errors='coerce')
            df['amount'] = df['turnover']  # 统一使用 amount 作为成交额

            top100 = df.nlargest(100, 'amount').copy()

            # 6. 按板块划分统计
            sector_stats = top100.groupby('sector').agg({
                'stock_code': 'count',
                'amount': 'sum',
                'change_percent': 'mean' if 'change_percent' in top100.columns else None
            }).reset_index()
            
            # 处理可能为None的平均涨幅
            sector_stats.columns = ['sector', 'count', 'total_amount', 'avg_pctChg']
            sector_stats['avg_pctChg'] = sector_stats['avg_pctChg'].fillna(0)
            
            # 6. 生成分析结果
            results = []
            
            # 6.1 总体统计
            total_result = ReviewResult()
            total_result.task_id = task.id
            total_result.dimension = '总体统计'
            total_result.metric_name = '获取股票数'
            total_result.metric_value = str(len(df))
            total_result.status = 'normal'
            total_result.detail_data = json.dumps({
                'totalStocks': len(df),
                'top100Count': len(top100),
                'tradeDate': trade_date
            }, ensure_ascii=False)
            results.append(total_result)
            
            # 6.2 成交额前100统计
            top_result = ReviewResult()
            top_result.task_id = task.id
            top_result.dimension = '成交额排名'
            top_result.metric_name = '前100成交额总和'
            top_result.metric_value = f"{top100['amount'].sum():.2f}"
            top_result.status = 'normal'
            
            # Top 10 详细信息
            top10_detail = []
            for _, row in top100.head(10).iterrows():
                top10_detail.append({
                    'code': row.get('stock_code', row.get('code', '')),
                    'name': row.get('stock_name', row.get('name', '')),
                    'amount': float(row['amount']) if pd.notna(row['amount']) else 0,
                    'changePercent': float(row.get('change_percent', row.get('pctChg', 0))) if pd.notna(row.get('change_percent', row.get('pctChg', 0))) else 0
                })
            
            top_result.detail_data = json.dumps({
                'count': len(top100),
                'totalAmount': float(top100['amount'].sum()),
                'avgAmount': float(top100['amount'].mean()),
                'maxAmount': float(top100['amount'].max()),
                'minAmount': float(top100['amount'].min()),
                'top10': top10_detail
            }, ensure_ascii=False)
            results.append(top_result)
            
            # 6.3 按板块划分统计
            sector_list = []
            for _, row in sector_stats.iterrows():
                sector_name = str(row['sector']) if pd.notna(row['sector']) else '未知'
                sector_top = top100[top100['sector'] == sector_name].head(10)
                
                sector_result = ReviewResult()
                sector_result.task_id = task.id
                sector_result.dimension = f"板块: {sector_name}"
                sector_result.metric_name = '板块统计'
                sector_result.metric_value = f"{int(row['count'])}只 | 成交额: {row['total_amount']:.2f}亿 | 平均涨幅: {row['avg_pctChg']:.2f}%"
                sector_result.status = 'normal'
                
                # 获取该板块前10
                sector_detail = []
                for _, srow in sector_top.iterrows():
                    sector_detail.append({
                        'code': srow.get('stock_code', srow.get('code', '')),
                        'name': srow.get('stock_name', srow.get('name', '')),
                        'amount': float(srow['amount']) if pd.notna(srow['amount']) else 0,
                        'changePercent': float(srow.get('change_percent', srow.get('pctChg', 0))) if pd.notna(srow.get('change_percent', srow.get('pctChg', 0))) else 0
                    })
                
                sector_result.detail_data = json.dumps({
                    'count': int(row['count']),
                    'totalAmount': float(row['total_amount']),
                    'avgPctChg': float(row['avg_pctChg']),
                    'top10': sector_detail
                }, ensure_ascii=False)
                results.append(sector_result)
                
                sector_list.append({
                    'sector': sector_name,
                    'count': int(row['count']),
                    'totalAmount': float(row['total_amount']),
                    'avgPctChg': float(row['avg_pctChg'])
                })
            
            # 6.4 保存板块图表数据
            chart_result = ReviewResult()
            chart_result.task_id = task.id
            chart_result.dimension = '图表数据'
            chart_result.metric_name = '板块分布'
            chart_result.metric_value = f"{len(sector_stats)}个板块"
            chart_result.status = 'normal'

            # 构建ECharts图表数据
            chart_data = {
                'tradeDate': trade_date,
                'summary': {
                    'totalStocks': int(len(df)),
                    'top100Count': int(len(top100)),
                    'totalAmount': float(top100['amount'].sum()),
                    'avgAmount': float(top100['amount'].mean())
                },
                'sectors': sector_list,
                'top100Detail': [{
                    'code': row.get('stock_code', row.get('code', '')),
                    'name': row.get('stock_name', row.get('name', '')),
                    'amount': float(row['amount']) if pd.notna(row['amount']) else 0,
                    'changePercent': float(row.get('change_percent', row.get('pctChg', 0))) if pd.notna(row.get('change_percent', row.get('pctChg', 0))) else 0,
                    'sector': str(row.get('sector', '未知')),
                    'industry': str(row.get('industry', '未知'))
                } for _, row in top100.iterrows()],
                'charts': {
                    'sectorPie': {
                        'labels': [s['sector'] for s in sector_list],
                        'data': [s['totalAmount'] for s in sector_list]
                    },
                    'sectorBar': {
                        'labels': [s['sector'] for s in sector_list],
                        'data': [s['count'] for s in sector_list]
                    },
                    'amountTop10': {
                        'labels': [row.get('stock_name', row.get('name', '')) for _, row in top100.head(10).iterrows()],
                        'data': [float(row['amount']) if pd.notna(row['amount']) else 0 for _, row in top100.head(10).iterrows()]
                    }
                }
            }
            
            chart_result.detail_data = json.dumps(chart_data, ensure_ascii=False)
            results.append(chart_result)
            
            # 7. 保存所有结果
            for result in results:
                db.session.add(result)
            
            # 8. 更新任务状态
            task.status = 'completed'
            task.end_time = datetime.now()
            task.result_summary = f"{trade_date}日: 获取{len(df)}只A股，前100成交额{top100['amount'].sum():.2f}，覆盖{len(sector_stats)}个板块"
            
            db.session.commit()
            
            return task
            
        except Exception as e:
            task.status = 'failed'
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.session.commit()
            raise Exception(f"复盘执行失败: {str(e)}")


def get_review_task_service():
    """获取复盘任务服务实例"""
    return ReviewTaskService()

