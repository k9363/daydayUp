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
            all_stocks_df = self._fetch_daily_data(trade_date, db.session)
            kline_type = '日K'

            if all_stocks_df.empty:
                raise Exception(f"未能获取到 {trade_date} 的{kline_type}数据")

            logger.info(f"✅ 步骤1完成: 获取到 {len(all_stocks_df)} 只股票的{kline_type}数据")

            # ========== 步骤2: 筛选成交金额前100的股票 ==========
            logger.info(f"📊 步骤2: 筛选成交金额前100的股票")
            top100_df = self._filter_top_stocks(all_stocks_df, top_n=100)

            if top100_df.empty:
                raise Exception("未能筛选出成交额前100的股票")

            logger.info(f"✅ 步骤2完成: 筛选出 {len(top100_df)} 只股票")

            # ========== 步骤3: 计算因子并排名 ==========
            logger.info(f"📊 步骤3: 计算因子得分")
            # 获取前100只股票的历史数据（用于计算因子）
            stock_pool = top100_df['stock_code'].tolist()
            factors_df = self._calculate_factors(stock_pool, trade_date, db.session)

            if factors_df.empty:
                raise Exception("未能计算因子得分")

            logger.info(f"✅ 步骤3完成: 计算了 {len(factors_df)} 只股票的因子得分")

            # ========== 步骤4: 选出前10只股票 ==========
            top10_stocks = factors_df.nlargest(10, 'total_score')
            logger.info(f"✅ 步骤4完成: 选出前10只股票: {top10_stocks[['stock_code', 'stock_name', 'total_score']].to_dict('records')}")

            # ========== 步骤5: 计算板块得分 ==========
            sector_scores = self._calculate_sector_scores(factors_df, db.session, trade_date)
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
            return task

        except Exception as e:
            task.status = 'failed'
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.session.commit()
            logger.error(f"❌ 复盘任务失败: {e}")
            raise Exception(f"复盘执行失败: {str(e)}")

    def _fetch_daily_data(self, trade_date, db_session):
        """
        获取指定日期的全部日K数据

        Args:
            trade_date: 交易日期
            db_session: 数据库会话

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
        
        # 查询数据库中已有的股票代码
        existing_in_db = db_session.query(StockDailyKLine.stock_code).distinct().all()
        existing_in_db_codes = [e.stock_code for e in existing_in_db]
        logger.info(f"=== DEBUG: K线表中存在的股票代码数量: {len(existing_in_db_codes)}")
        logger.info(f"=== DEBUG: K线表中的股票代码前10: {existing_in_db_codes[:10]}")

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
        logger.info(f"缺失 {len(missing_codes)} 只股票的 {trade_date} 日K数据")
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
        data_sync_service = DataSyncService()
        
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
        计算因子得分

        因子1（成交额权重）：当日成交额第一为10，每少一名减0.2，最低为0
        因子2（短线趋势）：股价在5日线上+3否则-1，在10日线上+2否则-0.5
        因子3（昨日同比）：成交量大于等于上个交易日+3，否则-1
        因子4（爆量）：近3日平均成交额 / 前5-20日平均成交额 * 3
        因子5（极限量）：近10日平均成交额 / 前11-30日平均成交额 * 5

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

        # 获取历史交易日 - 需要从数据库查询实际存在的交易日
        # 首先查询该日期之前实际存在的所有交易日
        trading_dates = db_session.query(StockDailyKLine.trade_date).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date <= trade_date
        ).distinct().order_by(StockDailyKLine.trade_date.desc()).limit(50).all()
        
        # 提取日期列表
        all_dates = [t[0] for t in trading_dates]
        
        if len(all_dates) < 30:
            logger.warning(f"⚠️ 历史交易日不足30天，仅有{len(all_dates)}天，无法计算因子5")
            return pd.DataFrame()
        
        # 取前35个交易日（包括当天）
        dates_needed = all_dates[:35]
        logger.info(f"🔍 实际交易日范围: {dates_needed[-1]} ~ {dates_needed[0]} (共{len(dates_needed)}天)")

        # 查询历史数据
        historical_data = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date.in_(dates_needed)
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
        results = []
        for stock_code in stock_codes:
            stock_hist = hist_df[hist_df['stock_code'] == stock_code].sort_values('trade_date', ascending=False)

            if stock_hist.empty:
                continue

            # 获取股票名称
            stock_name = stock_hist.iloc[0]['stock_name'] if 'stock_name' in stock_hist.columns else ''

            # 因子1：成交额排名得分（基于当日成交额排名）
            # 这里我们直接用top100的排名
            factor1 = 0
            current_price = stock_hist.iloc[0]['close'] if len(stock_hist) >= 1 else 0

            # 因子2：股价与均线关系 - 记录详细数据
            factor2 = 0
            ma5_detail = None
            ma10_detail = None
            if len(stock_hist) >= 5:
                prices_5d = stock_hist.head(5)['close'].values
                ma5 = sum(prices_5d) / len(prices_5d) if len(prices_5d) > 0 else 0
                ma5_detail = round(ma5, 2)

                if current_price >= ma5:
                    factor2 += 3
                else:
                    factor2 -= 1

            if len(stock_hist) >= 10:
                prices_10d = stock_hist.head(10)['close'].values
                ma10 = sum(prices_10d) / len(prices_10d) if len(prices_10d) > 0 else 0
                ma10_detail = round(ma10, 2)

                if current_price >= ma10:
                    factor2 += 2
                else:
                    factor2 -= 0.5

            # 因子3：成交量对比 - 记录详细数据
            factor3 = 0
            vol_detail = None
            prev_vol_detail = None
            if len(stock_hist) >= 2:
                current_vol = stock_hist.iloc[0]['volume']
                prev_vol = stock_hist.iloc[1]['volume']
                vol_detail = round(current_vol, 0)
                prev_vol_detail = round(prev_vol, 0)
                if current_vol >= prev_vol:
                    factor3 += 3
                else:
                    factor3 -= 1

            # 因子4：爆量 - 最近3个交易日的平均成交金额与前20到前4交易日的比值*2
            factor4 = 0
            avg_3d_detail = None
            avg_5_20d_detail = None
            if len(stock_hist) >= 20:
                # 近3日平均成交额
                avg_3d = stock_hist.head(3)['turnover'].mean() if len(stock_hist) >= 3 else 0
                # 前20到前4交易日（即第5-20日）的平均成交额
                avg_5_20d = stock_hist.iloc[4:20]['turnover'].mean() if len(stock_hist) >= 20 else 0
                
                avg_3d_detail = round(avg_3d, 2) if avg_3d else None
                avg_5_20d_detail = round(avg_5_20d, 2) if avg_5_20d else None

                if avg_5_20d > 0:
                    factor4 = (avg_3d / avg_5_20d) * 2

            # 因子5：极限量 - 最近10个交易日的平均成交金额与前30到前11交易日的比值*3
            factor5 = 0
            avg_10d_detail = None
            avg_11_30d_detail = None
            if len(stock_hist) >= 30:
                # 近10日平均成交额
                avg_10d = stock_hist.head(10)['turnover'].mean() if len(stock_hist) >= 10 else 0
                # 前30到前11交易日（即第11-30日）的平均成交额
                avg_11_30d = stock_hist.iloc[10:30]['turnover'].mean() if len(stock_hist) >= 30 else 0
                
                avg_10d_detail = round(avg_10d, 2) if avg_10d else None
                avg_11_30d_detail = round(avg_11_30d, 2) if avg_11_30d else None

                if avg_11_30d > 0:
                    factor5 = (avg_10d / avg_11_30d) * 3

            # 因子6：多头趋势 - 近15个交易日不含今日，每个交易日股价在5日线上+0.2分，在10日线上+0.1分
            factor6 = 0
            ma5_15d_detail = None
            ma10_15d_detail = None
            # stock_hist是按日期降序的，第0条是今天，第1-15条是近15个交易日（不含今日）
            if len(stock_hist) >= 16:
                # 取近15个交易日（不含今日）的历史数据
                hist_15d = stock_hist.iloc[1:16]  # 跳过今天，取前15个交易日
                if len(hist_15d) >= 10:
                    # 遍历每一天计算
                    for i in range(len(hist_15d)):
                        # 计算该日的5日均线和10日均线
                        if i + 5 <= len(hist_15d):
                            ma5_i = hist_15d.iloc[i:i+5]['close'].mean()
                            close_i = hist_15d.iloc[i]['close']
                            # 收盘价在5日线上 +0.2分
                            if close_i >= ma5_i:
                                factor6 += 0.2
                        
                        if i + 10 <= len(hist_15d):
                            ma10_i = hist_15d.iloc[i:i+10]['close'].mean()
                            close_i = hist_15d.iloc[i]['close']
                            # 收盘价在10日线上 +0.1分
                            if close_i >= ma10_i:
                                factor6 += 0.1
                    
                    # 记录最近一天的MA5和MA10作为参考
                    ma5_15d = hist_15d.head(5)['close'].mean()
                    ma10_15d = hist_15d.head(10)['close'].mean()
                    ma5_15d_detail = round(ma5_15d, 2) if ma5_15d else None
                    ma10_15d_detail = round(ma10_15d, 2) if ma10_15d else None

            results.append({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'factor1_rank': factor1,  # 成交额排名得分（后续填充）
                'factor2_ma': factor2,    # 均线得分
                'factor3_vol': factor3,   # 成交量得分
                'factor4_burst': factor4,  # 爆量得分
                'factor5_extreme': factor5,  # 极限量得分
                'factor6_trend': factor6,  # 多头趋势得分
                'total_score': factor2 + factor3 + factor4 + factor5 + factor6,  # 暂不包含factor1，后续填充
                'close': today_close_map.get(stock_code, current_price if len(stock_hist) >= 1 else 0),
                'volume': today_volume_map.get(stock_code, stock_hist.iloc[0]['volume'] if len(stock_hist) >= 1 else 0),
                'turnover': today_turnover_map.get(stock_code, stock_hist.iloc[0]['turnover'] if len(stock_hist) >= 1 else 0),
                # 详细计算数据
                'current_price': round(current_price, 2) if current_price else None,
                'ma5': ma5_detail,
                'ma10': ma10_detail,
                'vol_current': vol_detail,
                'vol_prev': prev_vol_detail,
                'avg_3d_turnover': avg_3d_detail,
                'avg_5_20d_turnover': avg_5_20d_detail,
                'avg_10d_turnover': avg_10d_detail,
                'avg_11_30d_turnover': avg_11_30d_detail,
                'ma5_15d': ma5_15d_detail,
                'ma10_15d': ma10_15d_detail
            })

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
            for rel in sector_relations:
                if rel.stock_code == stock_code:
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
        保存复盘分析结果

        Args:
            task: 复盘任务
            all_df: 全部股票数据
            top_df: 成交额前N股票数据
            factors_df: 因子得分数据（包含100只股票）
            sector_scores: 板块得分
            trade_date: 交易日期
        """
        import pandas as pd

        results = []

        # 1. 指数数据 - 获取主要指数的行情数据
        INDEX_CODES = [
            'sh.000001',  # 上证指数
            'sz.399006',  # 创业板指
            'sz.399001',  # 深证成指
            'sh.000300',  # 沪深300
            'sh.000905',  # 中证500
            'sh.000852',  # 中证1000
        ]
        
        # 从 all_df 中获取指数数据
        index_data = all_df[all_df['stock_code'].isin(INDEX_CODES)] if not all_df.empty else pd.DataFrame()
        
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
                'close': float(row.get('close', 0)) if pd.notna(row.get('close', 0)) else 0,
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
            relations = db.session.query(StockSectorRelation.stock_code, StockSector.sector_name).join(
                StockSector, StockSector.id == StockSectorRelation.sector_id
            ).filter(StockSectorRelation.stock_code.in_(stock_codes)).all()
            for stock_code, sector_name in relations:
                if stock_code not in sector_map:
                    sector_map[stock_code] = []
                sector_map[stock_code].append(sector_name)
        except Exception as e:
            logger.warning(f"获取板块信息失败: {e}")

        # Top 100 详细信息 - 转换格式以匹配前端
        top100_detail = []
        
        # 直接使用 K 线数据中的股票名称
        stock_name_map_from_kline = dict(zip(top_df['stock_code'], top_df['stock_name']))
        
        for _, row in top_df.iterrows():  # 遍历全部100只
            stock_code = row.get('stock_code', '')
            sector_info = ','.join(sector_map.get(stock_code, []))

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
            sector_info = ','.join(sector_map.get(stock_code, []))
            
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

            # 获取因子详细计算数据
            current_price = row.get('current_price')
            ma5 = row.get('ma5')
            ma10 = row.get('ma10')
            vol_current = row.get('vol_current')
            vol_prev = row.get('vol_prev')
            avg_3d_turnover = row.get('avg_3d_turnover')
            avg_5_20d_turnover = row.get('avg_5_20d_turnover')
            avg_10d_turnover = row.get('avg_10d_turnover')
            avg_11_30d_turnover = row.get('avg_11_30d_turnover')

            top10_factors_detail.append({
                'code': stock_code,
                'name': stock_name,
                'sector': sector_info,
                'industry': '',
                'amount': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'changePercent': float(row.get('change_percent', 0)),
                'totalScore': float(row.get('total_score', 0)),
                'factor1Rank': float(row.get('factor1_rank', 0)),
                'factor2MA': float(row.get('factor2_ma', 0)),
                'factor3Vol': float(row.get('factor3_vol', 0)),
                'factor4Burst': float(row.get('factor4_burst', 0)),
                'factor5Extreme': float(row.get('factor5_extreme', 0)),
                'factor6Trend': float(row.get('factor6_trend', 0)),
                'close': float(row.get('close', 0)),
                'turnover': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'totalMarketValue': total_mv,
                'circulateMarketValue': circulate_mv,
                # 因子详细计算数据
                'currentPrice': current_price,
                'ma5': ma5,
                'ma10': ma10,
                'volCurrent': vol_current,
                'volPrev': vol_prev,
                'avg3dTurnover': avg_3d_turnover,
                'avg520dTurnover': avg_5_20d_turnover,
                'avg10dTurnover': avg_10d_turnover,
                'avg1130dTurnover': avg_11_30d_turnover,
                'ma5_15d': row.get('ma5_15d'),
                'ma10_15d': row.get('ma10_15d')
            })

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
                    'topStocks': row.get('top_stocks', [])  # 前30股票中该板块的股票列表
                })

            sector_result.detail_data = json.dumps({
                'type': 'sector_scores',
                'sectors': top10_sectors  # 前端期望 'sectors'
            }, ensure_ascii=False)
            results.append(sector_result)

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

