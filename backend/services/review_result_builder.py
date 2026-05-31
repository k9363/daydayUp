"""
复盘结果构建器 - 将 _save_review_results 拆分为多个独立方法
"""
import json
import logging
import pandas as pd
from typing import List, Dict, Any
from config import (
    MARKET_INDEX_CODE_LIST, MARKET_INDEX_CODES,
    DEFAULT_TOP_N, TOP_N_FOR_SECTOR, TOP_N_FOR_DISPLAY
)

logger = logging.getLogger(__name__)


class ReviewResultBuilder:
    """复盘结果构建器 - 负责构建各种分析结果"""

    def __init__(self, db_session):
        self.db = db_session

    def _get_sector_score_expression_meta(self):
        """返回默认板块得分表达式信息：(expression_text, expression_name, factor_meta)

        factor_meta = [{'code': 因子代码, 'name': 因子名称}, ...]，按表达式 factors 列表顺序，
        供前端「板块得分 -> 因子详情」树展示使用。
        """
        from models.expression import ScoreExpression
        from models.factor import FactorDefine

        expr = ScoreExpression.query.filter_by(
            scope='sector', is_default=True, is_active=True
        ).first()
        if not expr:
            return '', '', []

        factor_codes = expr.factors if isinstance(expr.factors, list) else []
        name_map = {}
        if factor_codes:
            for fd in FactorDefine.query.filter(FactorDefine.factor_code.in_(factor_codes)).all():
                name_map[fd.factor_code] = fd.factor_name
        factor_meta = [{'code': c, 'name': name_map.get(c, c)} for c in factor_codes]
        return (expr.expression or ''), (expr.expression_name or ''), factor_meta

    def build_index_results(self, task, all_df: pd.DataFrame) -> List[Dict]:
        """
        构建指数行情结果

        Args:
            task: 复盘任务
            all_df: 全部股票数据 DataFrame

        Returns:
            List[Dict]: 指数结果列表
        """
        results = []

        # 从 all_df 中获取指数数据
        if all_df is not None and not all_df.empty:
            index_data = all_df[all_df['stock_code'].isin(MARKET_INDEX_CODE_LIST)]
        else:
            index_data = pd.DataFrame()

        # 批量查询指数元数据
        index_codes = index_data['stock_code'].tolist() if not index_data.empty else []
        index_metadata_map = self._get_stock_metadata_map(index_codes)

        # 转换指数数据格式
        index_list = []
        for _, row in index_data.iterrows():
            stock_code = row.get('stock_code', '')
            stock_name = row.get('stock_name', '')
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

        return results

    def build_top_stocks_result(self, task, top_df: pd.DataFrame) -> List[Dict]:
        """
        构建成交额前N股票结果

        Args:
            task: 复盘任务
            top_df: 成交额前N股票 DataFrame

        Returns:
            List[Dict]: Top 股票结果列表
        """
        from models.reviewresult import ReviewResult

        results = []
        top_result = ReviewResult()
        top_result.task_id = task.id
        top_result.dimension = '成交额排名'
        top_result.metric_name = '前100股票明细'
        top_result.metric_value = str(len(top_df))
        top_result.status = 'normal'

        # 批量获取所有股票的板块信息
        stock_codes = top_df['stock_code'].tolist()
        sector_map = self._get_stock_sector_map(stock_codes)

        # 批量获取股票元数据
        stock_metadata_map = self._get_stock_metadata_map(stock_codes)

        # 构建 Top 100 详细信息
        top100_detail = []
        stock_name_map = dict(zip(top_df['stock_code'], top_df['stock_name']))

        for _, row in top_df.iterrows():
            stock_code = row.get('stock_code', '')
            sector_info = ','.join(sector_map.get(stock_code, []))

            stock_name = stock_name_map.get(stock_code, '')
            if not stock_name or stock_name == '1':
                stock_name = stock_code

            metadata = stock_metadata_map.get(stock_code, {})

            top100_detail.append({
                'code': stock_code,
                'name': metadata.get('stock_name', stock_name),
                'sector': sector_info,
                'industry': metadata.get('industry', ''),
                'amount': float(row['turnover']) / 100000000 if pd.notna(row['turnover']) else 0,
                'turnover': float(row['turnover']) / 100000000 if pd.notna(row['turnover']) else 0,
                'changePercent': float(row.get('change_percent', 0)) if pd.notna(row.get('change_percent', 0)) else 0,
                'totalMarketValue': metadata.get('total_market_value', 0),
                'circulateMarketValue': metadata.get('circulate_market_value', 0)
            })

        top_result.detail_data = json.dumps({
            'count': len(top_df),
            'totalTurnover': float(top_df['turnover'].sum()) / 100000000,
            'avgTurnover': float(top_df['turnover'].mean()) / 100000000,
            'maxTurnover': float(top_df['turnover'].max()) / 100000000,
            'minTurnover': float(top_df['turnover'].min()) / 100000000,
            'stocks': top100_detail,
            'top10': top100_detail[:TOP_N_FOR_DISPLAY]
        }, ensure_ascii=False)
        results.append(top_result)

        return results

    def build_factor_analysis_result(self, task, factors_df: pd.DataFrame, top_df: pd.DataFrame) -> List[Dict]:
        """
        构建因子分析结果

        Args:
            task: 复盘任务
            factors_df: 因子得分 DataFrame
            top_df: 成交额前N股票 DataFrame

        Returns:
            List[Dict]: 因子分析结果列表
        """
        from models.reviewresult import ReviewResult

        results = []
        top10_result = ReviewResult()
        top10_result.task_id = task.id
        top10_result.dimension = '因子分析'
        top10_result.metric_name = '前10股票'
        top10_result.status = 'normal'

        # 获取股票名称映射和板块信息
        stock_name_map = dict(zip(top_df['stock_code'], top_df['stock_name']))
        stock_codes = factors_df.head(TOP_N_FOR_DISPLAY)['stock_code'].tolist()
        sector_map = self._get_stock_sector_map(stock_codes)
        stock_metadata_map = self._get_stock_metadata_map(stock_codes)

        # 获取表达式使用的因子列表
        factor_codes = self._get_expression_factor_codes()

        # 构建因子数据
        top10_factors_detail = []
        for _, row in factors_df.head(TOP_N_FOR_DISPLAY).iterrows():
            stock_code = row.get('stock_code', '')
            sector_info = ','.join(sector_map.get(stock_code, []))

            # 获取股票名称
            stock_name = stock_name_map.get(stock_code, '')
            if not stock_name or stock_name == '1':
                stock_name = row.get('stock_name', '')
            if not stock_name or stock_name == '1':
                stock_name = stock_metadata_map.get(stock_code, {}).get('stock_name', stock_code)

            # 获取市值信息
            metadata = stock_metadata_map.get(stock_code, {})
            total_mv = metadata.get('total_market_value', 0)
            circulate_mv = metadata.get('circulate_market_value', 0)

            # 构建因子数据
            stock_data = {
                'code': stock_code,
                'name': stock_name,
                'sector': sector_info,
                'industry': '',
                'amount': float(row.get('turnover', 0)) / 100000000 if pd.notna(row.get('turnover', 0)) else 0,
                'changePercent': float(row.get('change_percent', 0)),
                'totalScore': float(row.get('total_score', 0)),
                'close': float(row.get('close_price', 0)),
                'close_price': float(row.get('close_price', 0)),
                'volume': float(row.get('volume', 0)) if pd.notna(row.get('volume', 0)) else 0,
                'turnover': float(row.get('turnover', 0)) if pd.notna(row.get('turnover', 0)) else 0,
                'volume_y1': float(row.get('volume_y1', 0)) if pd.notna(row.get('volume_y1', 0)) else 0,
                'turnover_y1': float(row.get('turnover_y1', 0)) if pd.notna(row.get('turnover_y1', 0)) else 0,
                'ma5': float(row.get('ma5', 0)) if pd.notna(row.get('ma5', 0)) else 0,
                'ma10': float(row.get('ma10', 0)) if pd.notna(row.get('ma10', 0)) else 0,
                'ma20': float(row.get('ma20', 0)) if pd.notna(row.get('ma20', 0)) else 0,
                'amount_rank': float(row.get('amount_rank', 999)) if pd.notna(row.get('amount_rank', 999)) else 999,
                'turnover_rank': float(row.get('turnover_rank', 999)) if pd.notna(row.get('turnover_rank', 999)) else 999,
                'avg_amount_3d': float(row.get('avg_3d_turnover', 0)) if pd.notna(row.get('avg_3d_turnover', 0)) else 0,
                'avg_amount_5d': float(row.get('avg_5d_turnover', 0)) if pd.notna(row.get('avg_5d_turnover', 0)) else 0,
                'avg_amount_10d': float(row.get('avg_10d_turnover', 0)) if pd.notna(row.get('avg_10d_turnover', 0)) else 0,
                'avg_amount_20d': float(row.get('avg_20d_turnover', 0)) if pd.notna(row.get('avg_20d_turnover', 0)) else 0,
                'avg_amount_4_20d': float(row.get('avg_5_20d_turnover', 0)) if pd.notna(row.get('avg_5_20d_turnover', 0)) else 0,
                'avg_amount_11_30d': float(row.get('avg_11_30d_turnover', 0)) if pd.notna(row.get('avg_11_30d_turnover', 0)) else 0,
                'totalMarketValue': total_mv,
                'circulateMarketValue': circulate_mv,
            }

            # 添加所有因子列
            kline_fields = {'stock_code', 'stock_name', 'close_price', 'volume', 'turnover', 
                          'pct_change', 'change_percent', 'close', 'total_score'}
            for col in factors_df.columns:
                if col not in kline_fields and col not in stock_data:
                    val = row.get(col, 0)
                    stock_data[col] = float(val) if pd.notna(val) else 0

            top10_factors_detail.append(stock_data)

        top10_result.detail_data = json.dumps({
            'type': 'top10_stocks',
            'stocks': top10_factors_detail
        }, ensure_ascii=False)
        results.append(top10_result)

        return results

    def build_sector_score_result(self, task, factors_df: pd.DataFrame, sector_scores: pd.DataFrame) -> List[Dict]:
        """
        构建板块得分结果

        Args:
            task: 复盘任务
            factors_df: 因子得分 DataFrame
            sector_scores: 板块得分 DataFrame

        Returns:
            List[Dict]: 板块得分结果列表
        """
        from models.reviewresult import ReviewResult

        results = []

        if sector_scores.empty:
            return results

        sector_result = ReviewResult()
        sector_result.task_id = task.id
        sector_result.dimension = '板块得分'
        sector_result.metric_name = '前10板块'
        sector_result.status = 'normal'

        # 获取前30只股票的板块关联
        top30_stocks = factors_df.head(TOP_N_FOR_SECTOR)
        top30_codes = top30_stocks['stock_code'].tolist()
        sector_relations_map = self._get_sector_stocks_relation_map(top30_codes)

        # 板块得分表达式 + 其引用的因子（用于「点击得分看因子详情」，与股票/大盘因子展示一致）
        expression_text, expression_name, score_factor_meta = self._get_sector_score_expression_meta()
        score_factor_codes = [f['code'] for f in score_factor_meta]

        def _build_sector_item(row):
            sector_name = row.get('sector_name', '')
            # 该板块各引用因子的取值（用于因子详情树）
            factor_values = {}
            for code in score_factor_codes:
                val = row.get(code)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    factor_values[code] = float(val)
            return {
                'sector': sector_name,
                'sectorCode': row.get('sector_code', ''),
                'name': sector_name,
                'sectorType': row.get('sector_type', 'industry'),
                'count': int(row.get('stock_count', 0)),
                'stockCount': int(row.get('stock_count', 0)),
                'score': float(row.get('score', 0)),
                'factorValues': factor_values,
                'topStocks': json.loads(row.get('top_stocks', '[]')) if isinstance(row.get('top_stocks'), str) else (row.get('top_stocks', []) if isinstance(row.get('top_stocks'), list) else [])
            }

        # 全部已排序板块 -> item
        all_items = [_build_sector_item(row) for _, row in sector_scores.iterrows()]

        # 行业 / 概念 分别取前 N（页面左右两栏分别展示）
        industry_sectors = [it for it in all_items if it['sectorType'] == 'industry'][:TOP_N_FOR_DISPLAY]
        concept_sectors = [it for it in all_items if it['sectorType'] == 'concept'][:TOP_N_FOR_DISPLAY]
        # 兼容旧前端：保留混合前N
        top10_sectors = all_items[:TOP_N_FOR_DISPLAY]

        sector_result.detail_data = json.dumps({
            'type': 'sector_scores',
            'sectors': top10_sectors,
            'industry': industry_sectors,
            'concept': concept_sectors,
            'scoreExpression': expression_text,
            'scoreExpressionName': expression_name,
            'scoreFactors': score_factor_meta,
        }, ensure_ascii=False)
        results.append(sector_result)

        return results

    def build_factor_tree_result(self, task) -> List[Dict]:
        """
        构建因子树形结构结果

        Args:
            task: 复盘任务

        Returns:
            List[Dict]: 因子树结果列表
        """
        from models.reviewresult import ReviewResult
        from services.review_service import _build_factor_tree

        results = []

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

            # 构建因子依赖树
            factor_tree = _build_factor_tree(all_stock_factors)

            # 保存因子树
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

        except Exception as e:
            logger.warning(f"构建因子树失败: {e}")

        return results

    def build_market_analysis_result(self, task, trade_date: str) -> List[Dict]:
        """
        构建大盘指数计算结果

        Args:
            task: 复盘任务
            trade_date: 交易日期

        Returns:
            List[Dict]: 大盘分析结果列表
        """
        from models.reviewresult import ReviewResult

        results = []

        try:
            from models.kline import StockDailyKLine, StockSectorRelation, StockSector
            from models.factor import FactorDefine
            from models.expression import ScoreExpression
            from services.factor_service import FactorCalculator
            import re

            factor_calc = FactorCalculator()

            # 计算大盘因子
            market_factors = factor_calc.calculate_market_factors(trade_date, self.db)

            # 获取主要指数行情
            index_prices = {}
            for code, name in MARKET_INDEX_CODES.items():
                kline = self.db.query(StockDailyKLine).filter(
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

            # 构建大盘因子树
            builtins = {'IF', 'ABS', 'MAX', 'MIN', 'SUM', 'AVG', 'SQRT', 'LOG', 'ROUND', 'POW'}

            # 获取大盘综合得分的表达式
            market_score_expr = self.db.query(ScoreExpression).filter_by(
                scope='market', is_default=True, is_active=True
            ).first()

            # 获取所有大盘因子定义
            market_factor_defs = self.db.query(FactorDefine).filter(
                FactorDefine.factor_scope == 'market',
                FactorDefine.is_active == True
            ).order_by(FactorDefine.id).all()
            market_factor_code_set = {f.factor_code for f in market_factor_defs}

            # 构建动态因子树
            factors_tree = {}
            for f in market_factor_defs:
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

            # 用 ScoreExpression 覆盖 market_score
            if market_score_expr and market_score_expr.expression:
                var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', market_score_expr.expression)
                score_deps = [v for v in var_names if v not in builtins and v in market_factor_code_set]
                if 'market_score' in factors_tree:
                    factors_tree['market_score']['expression'] = market_score_expr.expression
                    factors_tree['market_score']['dependencies'] = score_deps
                    factors_tree['market_score']['value'] = float(market_factors.get('market_score', 0)) if market_factors.get('market_score') is not None else 0
                else:
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

            # 保存结果
            market_result = ReviewResult()
            market_result.task_id = task.id
            market_result.dimension = '市场'
            market_result.metric_name = '大盘综合得分'
            market_result.metric_value = str(float(market_factors.get('market_score', 0)) if market_factors.get('market_score', 0) is not None else 0)
            market_result.status = 'normal'
            market_result.detail_data = json.dumps(market_tree, ensure_ascii=False)
            results.append(market_result)

        except Exception as e:
            import traceback
            logger.warning(f"计算大盘指数失败: {e}\n{traceback.format_exc()}")

        return results

    # ==================== 私有辅助方法 ====================

    def _get_stock_sector_map(self, stock_codes: List[str]) -> Dict[str, List[str]]:
        """批量获取股票板块映射"""
        if not stock_codes:
            return {}

        try:
            from models.kline import StockSectorRelation, StockSector
            relations = self.db.query(
                StockSectorRelation.stock_code,
                StockSector.sector_name
            ).join(
                StockSector, StockSector.id == StockSectorRelation.sector_id
            ).filter(StockSectorRelation.stock_code.in_(stock_codes)).all()

            sector_map = {}
            for stock_code, sector_name in relations:
                if stock_code not in sector_map:
                    sector_map[stock_code] = []
                sector_map[stock_code].append(sector_name)
            return sector_map
        except Exception as e:
            logger.warning(f"获取股票板块信息失败: {e}")
            return {}

    def _get_stock_metadata_map(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """批量获取股票元数据"""
        if not stock_codes:
            return {}

        try:
            from models.stockbasic import StockBasic
            stock_metadatas = self.db.query(
                StockBasic.stock_code,
                StockBasic.stock_name,
                StockBasic.industry,
                StockBasic.total_market_value,
                StockBasic.circulate_market_value
            ).filter(
                StockBasic.stock_code.in_(stock_codes)
            ).all()

            return {sm.stock_code: {
                'stock_name': sm.stock_name if sm.stock_name and sm.stock_name != '1' else sm.stock_code,
                'industry': sm.industry or '',
                'total_market_value': float(sm.total_market_value) if sm.total_market_value else 0,
                'circulate_market_value': float(sm.circulate_market_value) if sm.circulate_market_value else 0
            } for sm in stock_metadatas}
        except Exception as e:
            logger.warning(f"获取股票元数据失败: {e}")
            return {}

    def _get_sector_stocks_relation_map(self, stock_codes: List[str]) -> Dict[str, List[str]]:
        """获取板块-股票关联映射"""
        if not stock_codes:
            return {}

        try:
            from models.kline import StockSectorRelation, StockSector
            relations = self.db.query(
                StockSectorRelation.stock_code,
                StockSector.sector_code,
                StockSector.sector_name
            ).join(
                StockSector, StockSector.id == StockSectorRelation.sector_id
            ).filter(
                StockSectorRelation.stock_code.in_(stock_codes)
            ).all()

            sector_relations = {}
            for rel in relations:
                if rel.sector_code not in sector_relations:
                    sector_relations[rel.sector_code] = []
                sector_relations[rel.sector_code].append(rel.stock_code)
            return sector_relations
        except Exception as e:
            logger.warning(f"获取板块股票关联失败: {e}")
            return {}

    def _get_expression_factor_codes(self) -> List[str]:
        """获取表达式中使用的因子代码"""
        try:
            from models.expression import ScoreExpression
            score_expr = ScoreExpression.query.filter_by(
                scope='stock',
                is_default=True,
                is_active=True
            ).first()
            if score_expr and score_expr.factors:
                return score_expr.factors
            return []
        except Exception as e:
            logger.warning(f"获取表达式因子失败: {e}")
            return []
