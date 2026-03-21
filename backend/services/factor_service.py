"""
因子计算服务
支持股票因子、板块因子、大盘因子的计算和表达式评估
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

import simpleeval
from extensions import db
from models.factor import FactorDefine, FactorSource
from models.expression import ScoreExpression
from models.kline import StockDailyKLine, StockSectorRelation
from models.stockbasic import StockBasic

logger = logging.getLogger(__name__)


class ExpressionParser:
    """表达式解析器 - 从数据库配置动态解析和计算因子"""
    
    def __init__(self, history_data: Dict[str, List[Dict]]):
        self.history_data = history_data
    
    def parse_and_calculate(self, expression: str, stock_code: str, df_columns: List[str]) -> Any:
        """
        解析表达式并计算结果
        
        支持的表达式格式：
        - AVG(turnover, 10) - 过去N天平均
        - AVG(turnover, 4, 20) - 第M天到第N天平均
        - AVG(volume, 5) - 成交量平均
        - IF(condition, true_val, false_val) - 条件表达式
        - 基本数学运算: +, -, *, /, >, <, >=, <=, ==, !=
        """
        if not expression:
            return 0
        
        expression = expression.strip()
        
        # 处理 AVG 函数
        avg_match = re.match(r'^AVG\s*\(\s*(\w+)\s*,\s*(\d+)(?:\s*,\s*(\d+))?\s*\)$', expression, re.IGNORECASE)
        if avg_match:
            field = avg_match.group(1)
            start = int(avg_match.group(2))
            end = int(avg_match.group(3)) if avg_match.group(3) else start
            return self._calculate_avg(stock_code, field, start, end)
        
        # 返回原始表达式（供 simpleeval 使用）
        return expression
    
    def _calculate_avg(self, stock_code: str, field: str, start: int, end: int) -> float:
        """计算历史平均"""
        hist = self.history_data.get(stock_code, [])
        
        if not hist:
            return 0
        
        # start 和 end 是天数，从最近一天开始计算
        # start=1 表示最近1天，start=10 表示最近10天
        # end 用于范围，如 AVG(turnover, 4, 20) 表示第4天到第20天
        
        if end > start:
            # 范围平均：从 start 天到 end 天
            if len(hist) >= end:
                values = [h.get(field, 0) for h in hist[start-1:end]]
                return sum(values) / len(values) if values else 0
        else:
            # 单点平均：最近 start 天
            if len(hist) >= start:
                values = [h.get(field, 0) for h in hist[:start]]
                return sum(values) / len(values) if values else 0
        
        return 0


class FactorCalculator:
    """因子计算器"""
    
    def __init__(self):
        self.simpleeval_functions = self._setup_simpleeval_functions()
    
    def _setup_simpleeval_functions(self):
        """设置simpleeval自定义函数"""
        return {
            'ABS': abs,
            'MAX': max,
            'MIN': min,
            'SUM': sum,
            'AVG': lambda *args: sum(args) / len(args) if args else 0,
            'SQRT': lambda x: x ** 0.5 if x >= 0 else 0,
            'LOG': lambda x: np.log(x) if x > 0 else 0,
            'IF': lambda cond, true_val, false_val: true_val if cond else false_val,
            'ROUND': round,
            'POW': pow,
        }
    
    def _preprocess_expression(self, expression: str) -> str:
        """预处理表达式，将不支持的语法转换为 simpleeval 支持的格式"""
        if not expression:
            return expression
        
        # 将 AND/or/NOT 转换为小写（simpleeval 需要小写）
        # 注意：需要确保不转换变量名中的这些词
        import re
        
        # 匹配 IF(...) 中的关键字（IF 内部的关键字）
        # 先处理 NOT 关键字：NOT(cond) -> (not cond)
        # 使用负向前瞻，确保 NOT 后面是括号
        expression = re.sub(r'\bNOT\s*\(', '(not ', expression, flags=re.IGNORECASE)
        
        # 处理 AND 关键字：cond1 AND cond2 -> (cond1 and cond2)
        # 使用词边界确保不替换变量名中的 AND
        expression = re.sub(r'\bAND\b', ' and ', expression, flags=re.IGNORECASE)
        
        # 处理 OR 关键字
        expression = re.sub(r'\bOR\b', ' or ', expression, flags=re.IGNORECASE)
        
        # 处理比较运算符：= 转换为 ==（但需要避免转换已经是 == 的情况）
        # 使用负向后顾，确保前面不是 =
        expression = re.sub(r'(?<![=!<>])=(?!=)', '==', expression)
        
        return expression
    
    def _get_factor_definitions(self, db_session) -> Dict[str, FactorDefine]:
        """从数据库加载因子定义"""
        stock_factors = db_session.query(FactorDefine).filter_by(
            factor_scope='stock',
            is_active=True
        ).all()
        
        all_factor_map = {f.factor_code: f for f in stock_factors}
        logger.info(f"📊 从数据库加载 {len(all_factor_map)} 个因子定义")
        for f in stock_factors:
            logger.debug(f"  - {f.factor_code}: {f.factor_name}, method={f.calculation_method}, expression={f.expression}")
        
        return all_factor_map
    
    def calculate_stock_factors(self, stock_codes: List[str], trade_date: str, db_session) -> pd.DataFrame:
        """
        计算股票因子得分
        
        原子因子架构：
        1. 从K线获取原始字段：close_price, volume, turnover, pct_change, ma5, ma10, ma20
        2. 从历史K线计算平均值：avg_amount_3d, avg_amount_5d, avg_amount_10d, avg_amount_20d, avg_amount_4_20d, avg_amount_11_30d
        3. 计算排名：amount_rank
        4. 计算派生因子：price_ma5_diff, price_ma10_diff (使用表达式)
        5. 使用表达式计算6个最终得分因子
        
        Args:
            stock_codes: 股票代码列表
            trade_date: 交易日期 (YYYY-MM-DD)
            db_session: 数据库会话
        
        Returns:
            包含因子得分的DataFrame
        """
        import datetime as dt
        
        # 1. 获取股票代码到名称的映射
        stock_name_map = {}
        stock_basics = db_session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
            StockBasic.stock_code.in_(stock_codes)
        ).all()
        stock_name_map = {s.stock_code: s.stock_name for s in stock_basics}
        
        # 2. 批量获取当日K线数据（一次 IN 查询，避免 N+1 问题）
        klines_today = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date == trade_date
        ).all()

        kline_data = []
        for kline in klines_today:
            code = kline.stock_code
            kline_data.append({
                'stock_code': code,
                'stock_name': stock_name_map.get(code, ''),
                'close_price': float(kline.close_price) if kline.close_price else 0,
                'volume': float(kline.volume) if kline.volume else 0,
                'turnover': float(kline.turnover) if kline.turnover else 0,
                'pct_change': float(kline.change_percent) if kline.change_percent else 0,
            })
        
        if not kline_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(kline_data)
        
        # 初始化ma5, ma10列（后续会从历史数据计算）
        df['ma5'] = 0.0
        df['ma10'] = 0.0
        
        # 3. 获取历史K线数据（用于计算历史平均成交额）
        end_date = dt.datetime.strptime(trade_date, '%Y-%m-%d')
        # 获取200天数据确保有足够交易日（考虑周末和节假日，avg_amount_4_120d需要120天）
        start_date = end_date - dt.timedelta(days=200)
        start_str = start_date.strftime('%Y-%m-%d')
        
        # 查询历史K线（包含当天和之前的数据，用于计算包含今天的MA）
        history_klines = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code.in_(stock_codes),
            StockDailyKLine.trade_date >= start_str,
            StockDailyKLine.trade_date <= trade_date,  # 包含当天，用于计算ma20
            StockDailyKLine.turnover.isnot(None),  # 排除停牌日（turnover为NULL）
            StockDailyKLine.turnover > 0  # 确保成交额大于0
        ).order_by(StockDailyKLine.stock_code, StockDailyKLine.trade_date.desc()).all()
        
        # 按股票代码分组历史数据
        history_data = {}
        for kline in history_klines:
            code = kline.stock_code
            if code not in history_data:
                history_data[code] = []
            history_data[code].append({
                'trade_date': kline.trade_date,
                'turnover': float(kline.turnover) if kline.turnover else 0,
                'volume': float(kline.volume) if kline.volume else 0,
                'close_price': float(kline.close_price) if kline.close_price else 0,
                'high_price': float(kline.high_price) if kline.high_price else 0,
            })
        
        logger.info(f"📊 股票数量: {len(df)}, 有历史数据的股票: {len(history_data)}")

        # 获取上证指数历史数据（用于计算偏离值）
        INDEX_CODE = 'sh.000001'
        index_klines = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code == INDEX_CODE,
            StockDailyKLine.trade_date >= start_str,
            StockDailyKLine.trade_date <= trade_date,
            StockDailyKLine.close_price.isnot(None),
            StockDailyKLine.close_price > 0
        ).order_by(StockDailyKLine.trade_date.desc()).all()

        index_history = []
        for kline in index_klines:
            index_history.append({
                'trade_date': kline.trade_date,
                'close_price': float(kline.close_price) if kline.close_price else 0,
            })
        logger.info(f"📊 上证指数历史数据: {len(index_history)}条")

        # 计算 ma5, ma10, ma20（基于历史数据，一次循环批量收集三列）
        ma5_values, ma10_values, ma20_values = [], [], []
        for stock_code in df['stock_code']:
            hist = history_data.get(stock_code, [])
            ma5_values.append(sum(h['close_price'] for h in hist[:5]) / 5 if len(hist) >= 5 else 0.0)
            ma10_values.append(sum(h['close_price'] for h in hist[:10]) / 10 if len(hist) >= 10 else 0.0)
            ma20_values.append(sum(h['close_price'] for h in hist[:20]) / 20 if len(hist) >= 20 else 0.0)
        df['ma5'] = ma5_values
        df['ma10'] = ma10_values
        df['ma20'] = ma20_values

        # 4. 从数据库加载因子定义，动态计算因子
        all_factor_map = self._get_factor_definitions(db_session)

        # 获取股票得分表达式，只计算表达式中使用的因子
        score_expr = ScoreExpression.query.filter_by(
            scope='stock',
            is_default=True,
            is_active=True
        ).first()

        # 提取表达式中使用的因子列表
        needed_factors = set()
        if score_expr and score_expr.factors:
            needed_factors = set(score_expr.factors)
            logger.debug(f"📊 表达式需要的因子: {needed_factors}")

        # 递归查找所有依赖的因子（包括表达式因子的依赖）
        import re
        def find_dependencies(factor_codes, all_factor_map, visited=None):
            if visited is None:
                visited = set()
            
            new_deps = set()
            for fc in factor_codes:
                if fc in visited:
                    continue
                visited.add(fc)
                
                if fc in all_factor_map:
                    factor_def = all_factor_map[fc]
                    if factor_def.expression:
                        # 从表达式中提取因子代码
                        vars_in_expr = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', factor_def.expression)
                        # 排除函数名
                        func_names = {'ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG', 
                                    'abs', 'sqrt', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log', 'NOT', 'AND', 'OR'}
                        deps = {v for v in vars_in_expr if v not in func_names and v not in visited}
                        new_deps.update(deps)
            
            if new_deps:
                new_deps.update(find_dependencies(new_deps, all_factor_map, visited))
            return visited

        # 扩展依赖因子
        all_needed = find_dependencies(needed_factors, all_factor_map)
        logger.debug(f"📊 扩展后需要的因子（包括依赖）: {all_needed}")

        # 过滤 all_factor_map，保留表达式需要的因子及其依赖
        filtered_factor_map = {k: v for k, v in all_factor_map.items() if k in all_needed}
        logger.debug(f"📊 过滤后需要计算的因子: {list(filtered_factor_map.keys())}")

        # 创建表达式解析器
        expr_parser = ExpressionParser(history_data)
        
        # 获取需要计算的因子列表（基于数据库配置）
        # kline_field: 直接从K线获取
        # expression: 使用表达式计算
        
        # 4.1 首先处理需要历史数据计算的因子（如 AVG 函数）
        calculated_columns = set()  # 已计算的列
        
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'expression' and factor_def.expression:
                # 检查是否是 AVG 函数表达式
                avg_match = re.match(r'^AVG\s*\(\s*(\w+)\s*,\s*(\d+)(?:\s*,\s*(\d+))?\s*\)$', 
                                    factor_def.expression.strip(), re.IGNORECASE)
                if avg_match:
                    # 使用表达式解析器计算，批量收集后赋值
                    col_values = []
                    for stock_code in df['stock_code']:
                        col_values.append(expr_parser.parse_and_calculate(
                            factor_def.expression,
                            stock_code,
                            list(df.columns)
                        ))
                    df[factor_code] = col_values
                    calculated_columns.add(factor_code)
                    logger.debug(f"✅ 计算因子 {factor_code} = {factor_def.expression}")
        
        # 4.1.1 处理 avg_* 计算方法（如 avg_3d, avg_10d 等）
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method and factor_def.calculation_method.startswith('avg_'):
                # 解析 avg_3d, avg_5d, avg_10d, avg_20d, avg_4_20d, avg_11_30d 等
                method = factor_def.calculation_method
                
                col_values = []
                for stock_code in df['stock_code']:
                    hist = history_data.get(stock_code, [])

                    value = 0
                    if method == 'avg_3d' and len(hist) >= 3:
                        value = sum(h['turnover'] for h in hist[:3]) / 3
                    elif method == 'avg_5d' and len(hist) >= 5:
                        value = sum(h['turnover'] for h in hist[:5]) / 5
                    elif method == 'avg_10d' and len(hist) >= 10:
                        value = sum(h['turnover'] for h in hist[:10]) / 10
                    elif method == 'avg_20d' and len(hist) >= 20:
                        value = sum(h['turnover'] for h in hist[:20]) / 20
                    elif method == 'avg_4_20d' and len(hist) >= 20:
                        # 4-20日平均: 第4天到第20天
                        value = sum(h['turnover'] for h in hist[3:20]) / 17 if len(hist) >= 20 else 0
                    elif method == 'avg_11_30d' and len(hist) >= 30:
                        # 11-30日平均: 第11天到第30天
                        value = sum(h['turnover'] for h in hist[10:30]) / 20 if len(hist) >= 30 else 0
                    col_values.append(value)

                df[factor_code] = col_values
                
                calculated_columns.add(factor_code)
                logger.debug(f"✅ 计算因子 {factor_code} = {method}")
        
        # 4.1.2 处理 turnover_ma 计算方法（动态天数区间）
        # 支持 days_range 字段，如 "1_3"(最近3天), "4_20"(第4-20天)
        for factor_code, factor_def in all_factor_map.items():
            method = getattr(factor_def, 'calculation_method', None)
            days_range = getattr(factor_def, 'days_range', None)
            if method == 'turnover_ma' and days_range:
                logger.debug(f"🔍 处理 turnover_ma 因子: {factor_code}, days_range={days_range}")
                # 解析 days_range: "1_3" 表示第1-3天, "4_20" 表示第4-20天
                try:
                    if '_' in days_range:
                        parts = days_range.split('_')
                        start_day = int(parts[0])
                        end_day = int(parts[1])
                    else:
                        # 只有结束天，如 "30" 表示最近30天
                        start_day = 1
                        end_day = int(days_range)
                except (ValueError, IndexError):
                    logger.warning(f"⚠️ 无效的 days_range: {days_range}，使用默认值 1_3")
                    start_day = 1
                    end_day = 3
                
                col_values = []
                for stock_code in df['stock_code']:
                    hist = history_data.get(stock_code, [])

                    value = 0
                    if start_day == 1:
                        # 最近N天: 从最近一天开始取
                        if len(hist) >= end_day:
                            values = [h['turnover'] for h in hist[:end_day]]
                            value = sum(values) / len(values) if values else 0
                    else:
                        # 区间: start_day 到 end_day
                        if len(hist) >= end_day:
                            values = [h['turnover'] for h in hist[start_day-1:end_day]]
                            value = sum(values) / len(values) if values else 0
                    col_values.append(value)

                df[factor_code] = col_values
                
                calculated_columns.add(factor_code)
                logger.debug(f"✅ 计算因子 {factor_code} = turnover_ma 完成")
        
        # 4.2 处理简单的 kline_field（直接取值）
        # 这些已经在步骤2中处理了
        
        # 4.3 处理 price_ma*_diff 派生因子（基于已计算的 ma5, ma10）
        if 'price_ma5_diff' in all_factor_map:
            df['price_ma5_diff'] = df['close_price'] - df['ma5']
            calculated_columns.add('price_ma5_diff')
        
        if 'price_ma10_diff' in all_factor_map:
            df['price_ma10_diff'] = df['close_price'] - df['ma10']
            calculated_columns.add('price_ma10_diff')
        
        logger.info(f"📊 原子因子计算完成，列: {list(df.columns)}")
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'kline_field':
                field_name = factor_def.field_name or factor_code
                
                # 获取日期偏移配置
                days_offset = getattr(factor_def, 'days_offset', 0) or 0
                
                # 映射字段名
                field_map = {
                    'volume_y1': 'volume',
                    'turnover_y1': 'turnover',
                    'close_price_y1': 'close_price',
                    'close_price_y2': 'close_price',
                    'close_price_y3': 'close_price',
                    'volume_y2': 'volume',
                    'volume_y3': 'volume',
                }
                source_field = field_map.get(field_name, field_name)

                col_values = []
                for stock_code in df['stock_code']:
                    hist = history_data.get(stock_code, [])
                    # 获取历史数据（根据 days_offset）
                    # days_offset=0 当日, =1 昨日, =2 前日...
                    col_values.append(hist[days_offset].get(source_field, 0) if len(hist) > days_offset else 0.0)
                df[factor_code] = col_values

                calculated_columns.add(factor_code)
                logger.debug(f"✅ 处理 kline_field 因子 {factor_code}, days_offset={days_offset}")
        
        # 4.4.1 处理均线类因子（包含当日和历史）
        # ma5, ma10, ma20 等：通过 days_offset 配置获取当日或历史的均线
        # 如果 days_offset > 0，则从历史K线重新计算
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'kline_field' and factor_def.field_name in ['ma5', 'ma10', 'ma20', 'ma30', 'ma60']:
                days_offset = getattr(factor_def, 'days_offset', 0) or 0
                ma_field = factor_def.field_name  # ma5, ma10, ma20...
                ma_days = int(ma_field[2:])  # 提取天数：5, 10, 20...
                
                col_values = []
                for stock_code in df['stock_code']:
                    hist = history_data.get(stock_code, [])

                    value = 0
                    if days_offset == 0:
                        # 当日均线：从预计算字段获取（已在步骤2处理）
                        if len(hist) >= ma_days:
                            ma_sum = sum(h['close_price'] for h in hist[:ma_days] if h.get('close_price'))
                            value = ma_sum / ma_days
                    else:
                        # 历史均线：从指定偏移日期开始计算
                        if len(hist) >= days_offset + ma_days:
                            ma_sum = sum(h['close_price'] for h in hist[days_offset:days_offset+ma_days] if h.get('close_price'))
                            value = ma_sum / ma_days
                    col_values.append(value)

                df[factor_code] = col_values
                
                calculated_columns.add(factor_code)
                logger.debug(f"✅ 计算均线因子 {factor_code}, days_offset={days_offset}")

        # 4.4.2 处理新高因子（近N日最高价）
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'new_high':
                # days_range 表示统计天数，如 120 表示近120日新高
                days_range = int(factor_def.days_range) if factor_def.days_range else 120
                
                logger.debug(f"🔍 计算 new_high 因子 {factor_code}, days_range={days_range}")
                
                col_values = []
                for idx in df.index:
                    stock_code = df.loc[idx, 'stock_code']
                    hist = history_data.get(stock_code, [])

                    # 需要至少 days_range 天的数据（昨日到days_range天前，共days_range天）
                    if len(hist) >= days_range:
                        past_high_prices = [h['high_price'] for h in hist[1:days_range+1] if h.get('high_price')]
                        max_high_price = max(past_high_prices) if past_high_prices else 0
                        today_close = df.loc[idx, 'close_price']
                        logger.debug(f"股票 {stock_code}: 今日收盘={today_close}, 过去{days_range}天最高价={max_high_price}")
                        col_values.append(today_close > max_high_price)
                    else:
                        logger.warning(f"股票 {stock_code} 历史数据不足 {days_range} 天，仅有 {len(hist)} 天")
                        col_values.append(False)

                df[factor_code] = col_values
                
                calculated_columns.add(factor_code)
                logger.debug(f"✅ 计算新高因子 {factor_code}, days_range={days_range}")

        # 4.5 计算成交额排名得分（factor1_rank）- 直接用 turnover 计算
        # 排名第一为10分，每下降一名减0.2，最低为0
        if 'turnover' in df.columns:
            # 计算排名：turnover_rank = 1 是成交额最高
            df['turnover_rank'] = df['turnover'].rank(ascending=False, method='min')
            # 计算得分：10 - (rank - 1) * 0.2，最小为0
            df['factor1_rank'] = (10 - (df['turnover_rank'] - 1) * 0.2).clip(lower=0)
            calculated_columns.add('factor1_rank')
            logger.info(f"📊 计算 factor1_rank 排名得分完成")
        
        # 4.6 计算表达式依赖的原子因子（昨日收盘价等）
        # 从历史数据中获取昨日值 - 作为备用逻辑，如果因子表未配置则使用
        if 'close_price_y1' not in df.columns:
            df['close_price_y1'] = [
                history_data[row['stock_code']][1].get('close_price', 0)
                if row['stock_code'] in history_data and len(history_data[row['stock_code']]) >= 2
                else 0
                for _, row in df.iterrows()
            ]
        else:
            # 仅填充值为0的行
            mask = df['close_price_y1'] == 0
            if mask.any():
                df.loc[mask, 'close_price_y1'] = [
                    history_data[row['stock_code']][1].get('close_price', 0)
                    if row['stock_code'] in history_data and len(history_data[row['stock_code']]) >= 2
                    else 0
                    for _, row in df[mask].iterrows()
                ]
        
        # 确保历史均线因子存在于 df 中
        if 'ma5' not in df.columns:
            df['ma5'] = 0.0
        if 'ma10' not in df.columns:
            df['ma10'] = 0.0
        if 'ma20' not in df.columns:
            df['ma20'] = 0.0
        
        # 填充缺失值为0
        for col in all_factor_map.keys():
            if col not in df.columns:
                df[col] = 0.0
            df[col] = df[col].fillna(0)


        # 在步骤7前统一做一次 df.to_dict('records')，后续各步骤增量更新，避免重复全量序列化
        records = df.to_dict('records')

        # 7. 使用表达式计算最终得分因子（非AVG类型的表达式）
        # 从数据库表达式定义中获取每个因子的表达式并计算
        calculated_factors = set()

        # 遍历所有因子定义，找到需要使用表达式计算的因子
        for factor_code, factor_def in all_factor_map.items():
            # 跳过已经计算过的AVG表达式因子
            if factor_code in calculated_columns:
                continue

            if factor_def.calculation_method == 'expression' and factor_def.expression:
                try:
                    # 使用表达式计算因子值，复用已有 records
                    values = self._evaluate_expression(factor_def.expression, records)
                    df[factor_code] = values
                    # 增量更新 records，供后续因子表达式依赖
                    for rec, val in zip(records, values):
                        rec[factor_code] = val
                    calculated_factors.add(factor_code)
                    logger.debug(f"✅ 因子 {factor_code} 使用表达式计算成功")
                except Exception as e:
                    logger.warning(f"⚠️ 因子 {factor_code} 表达式计算失败: {e}，设为0")
                    df[factor_code] = 0.0
                    for rec in records:
                        rec[factor_code] = 0.0

        logger.info(f"📊 表达式因子计算完成: {calculated_factors}")

        # 7.5 计算偏离值因子（在表达式因子计算之前）
        # deviation_10d, deviation_30d 是 python 类型，remaining_deviation 依赖它们
        self._calculate_deviation_factors(df, history_data, all_factor_map, db_session, trade_date)
        logger.info(f"📊 偏离值: 10天累计={df['deviation_10d'].mean():.2f}, 30天累计={df['deviation_30d'].mean():.2f}, 剩余={df['remaining_deviation'].mean():.2f}")

        # 将偏离值新列增量同步到 records（只更新三列，避免全量重建）
        for rec, dev10, dev30, rem in zip(
            records, df['deviation_10d'], df['deviation_30d'], df['remaining_deviation']
        ):
            rec['deviation_10d'] = dev10
            rec['deviation_30d'] = dev30
            rec['remaining_deviation'] = rem

        # 7.6 重新计算依赖偏离值因子的表达式因子（如 remaining_deviation）
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'expression' and factor_def.expression:
                # 检查表达式是否依赖偏离值因子
                if 'deviation_10d' in factor_def.expression or 'deviation_30d' in factor_def.expression or 'remaining_deviation' in factor_def.expression:
                    try:
                        values = self._evaluate_expression(factor_def.expression, records)
                        df[factor_code] = values
                        for rec, val in zip(records, values):
                            rec[factor_code] = val
                        logger.debug(f"✅ 重新计算依赖偏离值的因子 {factor_code}")
                    except Exception as e:
                        logger.warning(f"⚠️ 因子 {factor_code} 重新计算失败: {e}")

        # 8. 计算 Python 因子（通过 calculation_method 调用）
        # 在 all_factor_map 中查找需要用 Python 代码计算的因子
        # 注意：偏离值因子已在上面计算，这里只处理其他 Python 因子
        calculated_columns = set()
        for factor_code, factor_def in all_factor_map.items():
            if factor_def.calculation_method == 'python':
                # 偏离值因子已在上一步计算，跳过
                if factor_code in ['deviation_10d', 'deviation_30d']:
                    calculated_columns.add(factor_code)
                    continue
                logger.debug(f"🔍 计算 Python 因子: {factor_code}, method={factor_def.calculation_method}")

        logger.info(f"📊 Python 因子计算完成: {list(calculated_columns)}")

        # 9. 计算总分（score_expr 在步骤4已查询，此处直接复用；records 已与 df 同步，无需重建）
        # 计算总分（使用表达式因子计算后的结果）
        if score_expr and score_expr.expression:
            # 计算总分
            df['total_score'] = self._evaluate_expression(
                score_expr.expression,
                records  # 复用已同步的 records，无需再次 df.to_dict('records')
            )
        else:
            # 使用默认总分计算：所有因子得分之和
            df['total_score'] = (
                df['factor1_rank'] + df['factor2_ma'] + df['factor3_vol'] + 
                df['factor4_burst'] + df['factor5_extreme'] + df['factor6_trend']
            )
        
        logger.info(f"📊 总分统计: min={df['total_score'].min():.2f}, max={df['total_score'].max():.2f}, mean={df['total_score'].mean():.2f}")

        # 按总分排序
        df = df.sort_values('total_score', ascending=False).reset_index(drop=True)
        
        return df
    
    def _calculate_deviation_factors(self, df, history_data, all_factor_map, db_session, trade_date):
        """
        计算偏离值因子（从配置动态读取）
        配置字段：
        - days_range: 区间天数（如10, 30）
        - index_code: 对比指数代码（如sh.000001）
        - days_offset: 剩余偏离值的参考天数偏移
        
        公式：偏离值 = 个股区间涨跌幅 - 指数区间涨跌幅
        个股区间涨跌幅 = (期末收盘价 / 期初前收盘价 - 1) * 100%
        """
        import datetime as dt
        
        # 查找所有 deviation_ 开头的因子定义
        deviation_factors = {k: v for k, v in all_factor_map.items() if k.startswith('deviation_') and k != 'remaining_deviation'}
        
        if not deviation_factors:
            logger.info("📊 未配置偏离值因子，跳过计算")
            df['deviation_10d'] = 0.0
            df['deviation_30d'] = 0.0
            df['remaining_deviation'] = 0.0
            return
        
        # 获取所有需要的指数代码
        index_codes = set()
        for fc, fd in deviation_factors.items():
            if fd.index_code:
                index_codes.add(fd.index_code)
        
        # 批量获取指数历史数据
        # 注意：需要往前查询足够多的天数（60天），因为假期可能导致交易日不足
        index_history_map = {}
        for index_code in index_codes:
            end_date = dt.datetime.strptime(trade_date, '%Y-%m-%d')
            start_date = end_date - dt.timedelta(days=60)  # 往前60天，确保有足够交易日
            start_str = start_date.strftime('%Y-%m-%d')
            
            from models.kline import StockDailyKLine
            index_klines = db_session.query(StockDailyKLine).filter(
                StockDailyKLine.stock_code == index_code,
                StockDailyKLine.trade_date >= start_str,
                StockDailyKLine.trade_date <= trade_date,
                StockDailyKLine.close_price.isnot(None),
                StockDailyKLine.close_price > 0
            ).order_by(StockDailyKLine.trade_date.desc()).all()
            
            index_history = []
            for kline in index_klines:
                index_history.append({
                    'trade_date': kline.trade_date,
                    'close_price': float(kline.close_price),
                })
            index_history_map[index_code] = index_history
            logger.info(f"📊 指数 {index_code} 获取到 {len(index_history)} 天历史数据")
        
        # 计算每个偏离值因子
        for factor_code, factor_def in deviation_factors.items():
            days_range = int(factor_def.days_range) if factor_def.days_range else 10  # 默认10天
            index_code = factor_def.index_code or 'sh.000001'  # 默认上证指数
            
            index_history = index_history_map.get(index_code, [])
            # 需要 days_range + 1 天的历史数据（期初前1天 + days_range天）
            required_days = days_range + 1
            
            if len(index_history) < required_days:
                logger.warning(f"📊 指数 {index_code} 历史数据不足 {required_days} 天，仅有 {len(index_history)} 天")
                df[factor_code] = 0.0
                continue
            
            # 获取期末和期初前收盘价
            # index_history[0] = 最近（今天或最近交易日），index_history[days_range] = 期初前
            index_end_close = index_history[0]['close_price']
            index_pre_close = index_history[days_range]['close_price']
            
            if index_pre_close <= 0 or index_end_close <= 0:
                df[factor_code] = 0.0
                continue
            
            # 计算指数区间涨跌幅
            index_pct = (index_end_close / index_pre_close - 1) * 100
            
            # 为每只股票计算偏离值
            col_values = []
            for idx in df.index:
                stock_code = df.loc[idx, 'stock_code']
                stock_hist = history_data.get(stock_code, [])

                if len(stock_hist) < required_days:
                    col_values.append(0.0)
                    continue

                stock_end_close = stock_hist[0]['close_price']
                stock_pre_close = stock_hist[days_range]['close_price']

                if stock_pre_close <= 0 or stock_end_close <= 0:
                    col_values.append(0.0)
                    continue

                # 个股区间涨跌幅
                stock_pct = (stock_end_close / stock_pre_close - 1) * 100
                # 偏离值 = 个股涨跌幅 - 指数涨跌幅
                col_values.append(round(stock_pct - index_pct, 2))

            df[factor_code] = col_values
        
        # 计算 remaining_deviation（基于配置的 days_offset）
        remaining_def = all_factor_map.get('remaining_deviation')
        if remaining_def:
            # 阈值配置（可从 description 或扩展字段解析，这里硬编码常用阈值）
            threshold_10d_pos = 100  # 正向阈值
            threshold_10d_neg = -50   # 负向阈值
            threshold_30d_pos = 200
            threshold_30d_neg = -70
            
            remaining_values = []
            for idx in df.index:
                dev_10d = df.loc[idx, 'deviation_10d']
                dev_30d = df.loc[idx, 'deviation_30d']

                # 计算剩余偏离值
                remaining_10d = threshold_10d_pos - dev_10d if dev_10d > 0 else threshold_10d_neg - dev_10d
                remaining_30d = threshold_30d_pos - dev_30d if dev_30d > 0 else threshold_30d_neg - dev_30d

                # 取最小的剩余偏离值（最接近阈值）
                remaining_values.append(round(min(remaining_10d, remaining_30d), 2))
            df['remaining_deviation'] = remaining_values
        else:
            df['remaining_deviation'] = 0.0
    
    def calculate_sector_factors(self, stock_factors_df: pd.DataFrame, db_session) -> pd.DataFrame:
        """
        计算板块因子得分
        
        Args:
            stock_factors_df: 包含股票因子的DataFrame
            db_session: 数据库会话
        
        Returns:
            板块得分DataFrame
        """
        if stock_factors_df.empty:
            return pd.DataFrame()
        
        # 获取股票-板块关系（需要关联StockSector获取板块代码和名称）
        from models.kline import StockSector
        stock_codes = stock_factors_df['stock_code'].tolist()
        relations = db_session.query(StockSectorRelation, StockSector).join(
            StockSector, StockSector.id == StockSectorRelation.sector_id
        ).filter(
            StockSectorRelation.stock_code.in_(stock_codes)
        ).all()
        
        # 构建股票->板块映射
        stock_to_sector = {}
        sector_names = {}
        for rel, sector in relations:
            sector_code = sector.sector_code
            if sector_code not in stock_to_sector:
                stock_to_sector[sector_code] = []
                sector_names[sector_code] = sector.sector_name
            stock_to_sector[sector_code].append(rel.stock_code)
        
        # 获取板块因子定义
        sector_factors = FactorDefine.query.filter_by(
            factor_scope='sector',
            is_active=True
        ).all()
        
        if not sector_factors:
            logger.warning("⚠️ 未配置板块因子，请先在因子管理中配置")
            return pd.DataFrame()
        
        # 计算板块因子
        sector_data = {}
        for sector_code, sector_stocks in stock_to_sector.items():
            sector_df = stock_factors_df[stock_factors_df['stock_code'].isin(sector_stocks)]
            
            if sector_df.empty:
                continue
            
            sector_data[sector_code] = {
                'sector_name': sector_names.get(sector_code, sector_code)
            }
            for factor in sector_factors:
                if factor.source == 'stock_factor':
                    # 从股票因子聚合
                    field = factor.field_name or factor.factor_code
                    if field in sector_df.columns:
                        if factor.aggregation == 'SUM':
                            sector_data[sector_code][factor.factor_code] = sector_df[field].sum()
                        elif factor.aggregation == 'AVG':
                            sector_data[sector_code][factor.factor_code] = sector_df[field].mean()
                        elif factor.aggregation == 'MAX':
                            sector_data[sector_code][factor.factor_code] = sector_df[field].max()
                        elif factor.aggregation == 'MIN':
                            sector_data[sector_code][factor.factor_code] = sector_df[field].min()
                        elif factor.aggregation == 'COUNT':
                            sector_data[sector_code][factor.factor_code] = len(sector_df)
                elif factor.source == 'kline':
                    # 从K线数据聚合（需要先获取板块K线）
                    pass
        
        # 获取板块得分表达式
        score_expr = ScoreExpression.query.filter_by(
            scope='sector',
            is_default=True,
            is_active=True
        ).first()
        
        # 构建板块DataFrame，同时添加 stock_count 和 top_stocks
        top30_codes = stock_factors_df.head(30)['stock_code'].tolist()
        
        sector_records = []
        for sector_code, data in sector_data.items():
            sector_stocks = stock_to_sector.get(sector_code, [])
            
            # 筛选出前30股票中属于该板块的股票
            top_stocks_in_sector = stock_factors_df[
                (stock_factors_df['stock_code'].isin(sector_stocks)) & 
                (stock_factors_df['stock_code'].isin(top30_codes))
            ]
            top_stocks_list = []
            for _, srow in top_stocks_in_sector.iterrows():
                top_stocks_list.append({
                    'code': srow.get('stock_code', ''),
                    'name': srow.get('stock_name', srow.get('stock_code', '')),
                    'totalScore': round(srow.get('total_score', 0), 2)
                })
            
            record = {
                'sector_code': sector_code,
                'sector_name': data.get('sector_name', sector_code),
                'stock_count': len(sector_stocks),
                'top_stocks': top_stocks_list
            }
            # 添加因子数据
            for k, v in data.items():
                if k != 'sector_name':
                    record[k] = v
            sector_records.append(record)
        
        sector_df = pd.DataFrame(sector_records)
        
        if sector_df.empty:
            return sector_df
        
        # 计算板块得分
        if score_expr and score_expr.expression:
            sector_df['score'] = self._evaluate_expression(
                score_expr.expression,
                sector_df.to_dict('records')
            )
        else:
            # 使用默认计算
            sector_df['score'] = self._calculate_default_sector_scores(stock_factors_df, stock_to_sector)['score']
        
        # 取前N
        if score_expr and score_expr.top_n:
            sector_df = sector_df.nlargest(score_expr.top_n, 'score')
        
        sector_df = sector_df.sort_values('score', ascending=False).reset_index(drop=True)
        
        # 将 top_stocks 转换为 JSON 字符串，避免 Pandas 序列化问题
        import json
        sector_df['top_stocks'] = sector_df['top_stocks'].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else '[]')
        
        return sector_df
    
    def calculate_market_factors(self, trade_date: str, db_session) -> Dict:
        """
        计算大盘因子
        
        Args:
            trade_date: 交易日期
            db_session: 数据库会话
        
        Returns:
            大盘因子字典
        """
        # 直接使用字符串比较，避免导入问题
        # 获取大盘因子定义
        market_factors = FactorDefine.query.filter_by(
            factor_scope='market',
            is_active=True
        ).all()
        
        logger.info(f"📊 查询到 {len(market_factors)} 个大盘因子定义")
        for f in market_factors:
            logger.debug(f"  - {f.factor_code}: {f.factor_name}, source={f.source}, method={f.calculation_method}, expression={f.expression}")
        
        if not market_factors:
            # 返回默认大盘因子
            return self._get_default_market_factors(trade_date, db_session)
        
        market_data = {}
        
        # 第一遍：处理 kline 类型的因子（从指数K线获取数据）
        for factor in market_factors:
            if factor.source == 'kline' and factor.index_code and factor.field_name:
                # 从指数K线获取
                index_kline = self._get_index_kline(factor.index_code, trade_date, db_session)
                if index_kline:
                    market_data[factor.factor_code] = getattr(index_kline, factor.field_name, 0)
                    logger.debug(f"✅ K线因子 {factor.factor_code} = {market_data[factor.factor_code]}, 指数={factor.index_code}, 字段={factor.field_name}")
        
        # 第二遍：处理 python 类型的因子（通过Python方法计算）
        for factor in market_factors:
            if factor.source == 'python':
                value = self._calculate_python_factor(factor, trade_date, db_session)
                # 如果返回的是字典（多个原子因子），展开为多个因子
                if isinstance(value, dict):
                    for k, v in value.items():
                        market_data[k] = v
                    logger.debug(f"✅ Python因子 {factor.factor_code} 返回字典: {value}")
                else:
                    market_data[factor.factor_code] = value
                    logger.debug(f"✅ Python因子 {factor.factor_code} = {value}")
        
        # 第三遍：处理 calculated 类型的因子（通过表达式计算）
        # 注意：为了确保依赖关系正确，先计算除 market_score 以外的所有因子，
        # 然后再单独计算一次 market_score（它依赖于其它多个因子）
        deferred_calculated_factors = []
        for factor in market_factors:
            if factor.source == 'calculated' and factor.expression:
                # 将 market_score 延后计算，确保其依赖的因子已经就绪
                if factor.factor_code == 'market_score':
                    deferred_calculated_factors.append(factor)
                    continue
                
                result = self._evaluate_market_expression(
                    factor.expression, market_data
                )
                market_data[factor.factor_code] = result
                logger.debug(f"✅ 计算派生因子 {factor.factor_code} = {result}, 表达式: {factor.expression}")
        
        # 最后再计算一次 market_score（如果存在）
        for factor in deferred_calculated_factors:
            result = self._evaluate_market_expression(
                factor.expression, market_data
            )
            market_data[factor.factor_code] = result
            logger.info(f"✅ 计算派生因子 {factor.factor_code} = {result}, 表达式: {factor.expression}（延后计算）")
        
        logger.info(f"📊 最终大盘因子结果: {market_data}")
        return market_data
    
    def _calculate_python_factor(self, factor, trade_date: str, db_session) -> float:
        """
        根据 calculation_method 调用相应的Python计算方法
        """
        calc_method = factor.calculation_method
        logger.debug(f"🔍 处理因子 {factor.factor_code}, calculation_method={calc_method}")
        
        if calc_method == 'up_down_ratio':
            return self._calculate_up_down_ratio(trade_date, db_session)
        
        elif calc_method == 'up_down_ratio_top50':
            return self._calculate_up_down_ratio_top50(trade_date, db_session)
        
        elif calc_method == 'ma5_trend_score':
            ma5_score, ma10_score = self._get_trend_scores_cached(trade_date, db_session)
            return ma5_score

        elif calc_method == 'ma10_trend_score':
            ma5_score, ma10_score = self._get_trend_scores_cached(trade_date, db_session)
            return ma10_score
        
        elif calc_method == 'prev_trade_turnover':
            # 获取上一个交易日的成交额
            if factor.index_code:
                prev_kline = self._get_prev_trade_kline(factor.index_code, trade_date, db_session)
                if prev_kline:
                    field = factor.field_name or 'turnover'
                    return getattr(prev_kline, field, 0)
            return 0
        
        elif calc_method == 'up_down_count':
            # 原子因子：上涨家数、下跌家数、总家数
            return self._calculate_up_down_count(trade_date, db_session)
        
        elif calc_method == 'up_down_count_top50':
            # 原子因子：成交额前50的上涨家数、下跌家数
            return self._calculate_up_down_count_top50(trade_date, db_session)
        
        elif calc_method == 'top20_avg_price':
            # 大盘因子：昨日成交额前20的股票在今天的平均价格
            return self._calculate_top20_avg_price(trade_date, db_session)
        
        else:
            logger.warning(f"未知的 Python 计算方法: {calc_method}")
            return 0
    
    def _calculate_up_down_ratio(self, trade_date: str, db_session) -> float:
        """
        计算涨跌比：上涨股票数 / 下跌股票数
        """
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy.orm import aliased
        
        # 使用 left outer join 避免过滤掉 stock_basic 中不存在的股票
        sb = aliased(StockBasic)
        
        # 统计上涨和下跌的股票数量（排除平盘和停牌）
        up_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            # stock_type == 'stock' 或者 stock_basic 中没有记录（允许旧数据兼容）
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.change_percent > 0,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).count()
        
        down_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.change_percent < 0,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).count()
        
        if down_count == 0:
            return float(up_count) if up_count > 0 else 0
        
        return float(up_count) / down_count
    
    def _calculate_up_down_ratio_top50(self, trade_date: str, db_session) -> float:
        """
        计算成交额前50股票的涨跌比
        """
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy.orm import aliased
        
        # 使用 left outer join 避免过滤掉 stock_basic 中不存在的股票
        sb = aliased(StockBasic)
        
        # 先获取成交额前50的股票（仅 stock 类型，排除 etf/index）
        top50_stocks = db_session.query(StockDailyKLine.stock_code).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).order_by(StockDailyKLine.turnover.desc()).limit(50).all()
        
        top50_codes = [s.stock_code for s in top50_stocks]
        
        if not top50_codes:
            return 0
        
        # 统计前50中上涨和下跌的股票数量
        up_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.stock_code.in_(top50_codes),
            StockDailyKLine.change_percent > 0
        ).count()
        
        down_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.stock_code.in_(top50_codes),
            StockDailyKLine.change_percent < 0
        ).count()
        
        if down_count == 0:
            return float(up_count) if up_count > 0 else 0
        
        return float(up_count) / down_count
    
    def _calculate_up_down_count(self, trade_date: str, db_session) -> Dict:
        """
        计算涨跌家数原子因子：上涨家数、下跌家数、总家数
        
        Returns:
            包含 up_count, down_count, total_count 的字典
        """
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy.orm import aliased
        
        # 使用 left outer join 避免过滤掉 stock_basic 中不存在的股票
        sb = aliased(StockBasic)
        
        # 统计上涨和下跌的股票数量（排除平盘和停牌）
        up_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.change_percent > 0,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).count()
        
        down_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.change_percent < 0,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).count()
        
        result = {
            'up_count': up_count,
            'down_count': down_count,
            'total_count': up_count + down_count
        }
        logger.debug(f"📊 _calculate_up_down_count: {result}")
        return result
    
    def _calculate_up_down_count_top50(self, trade_date: str, db_session) -> Dict:
        """
        计算成交额前50的涨跌家数原子因子
        
        Returns:
            包含 up_count_top50, down_count_top50 的字典
        """
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy.orm import aliased
        
        # 使用 left outer join 避免过滤掉 stock_basic 中不存在的股票
        sb = aliased(StockBasic)
        
        # 先获取成交额前50的股票（仅 stock 类型，排除 etf/index）
        top50_stocks = db_session.query(StockDailyKLine.stock_code).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).order_by(StockDailyKLine.turnover.desc()).limit(50).all()
        
        top50_codes = [s.stock_code for s in top50_stocks]
        
        if not top50_codes:
            return {
                'up_count_top50': 0,
                'down_count_top50': 0
            }
        
        # 统计前50中上涨和下跌的股票数量
        up_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.stock_code.in_(top50_codes),
            StockDailyKLine.change_percent > 0
        ).count()
        
        down_count = db_session.query(StockDailyKLine).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.stock_code.in_(top50_codes),
            StockDailyKLine.change_percent < 0
        ).count()
        
        return {
            'up_count_top50': up_count,
            'down_count_top50': down_count
        }
    
    def _calculate_top20_avg_price(self, trade_date: str, db_session) -> float:
        """
        计算昨日成交额前20的股票在今天的平均涨幅
        
        逻辑：
        1. 获取昨日（trade_date前一天）成交额排名前20的股票
        2. 获取这些股票今天的涨跌幅 (pct_change)
        3. 计算平均涨幅
        
        Returns:
            昨日成交额前20股票的平均涨幅
        """
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic
        from sqlalchemy.orm import aliased
        import datetime
        
        # 计算昨日日期
        trade_date_dt = datetime.datetime.strptime(trade_date, '%Y-%m-%d')
        prev_date_dt = trade_date_dt - datetime.timedelta(days=1)
        prev_date = prev_date_dt.strftime('%Y-%m-%d')
        
        # 找到上一个交易日（跳过周末和节假日）
        # 查询昨日有成交额的股票
        sb = aliased(StockBasic)
        
        # 获取昨日成交额前20的股票代码（排除 ETF 和指数）
        top20_stocks = db_session.query(StockDailyKLine.stock_code).outerjoin(
            sb, sb.stock_code == StockDailyKLine.stock_code
        ).filter(
            (sb.stock_type == 'stock') | (sb.stock_code.is_(None)),
            StockDailyKLine.trade_date == prev_date,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).order_by(StockDailyKLine.turnover.desc()).limit(20).all()
        
        top20_codes = [s.stock_code for s in top20_stocks]
        
        if not top20_codes:
            logger.warning(f"⚠️ 昨日没有找到成交额数据")
            return 0
        
        # 获取这些股票今天的涨跌幅
        today_pct_changes = db_session.query(StockDailyKLine.change_percent).filter(
            StockDailyKLine.stock_code.in_(top20_codes),
            StockDailyKLine.trade_date == trade_date,
            StockDailyKLine.change_percent.isnot(None)
        ).all()
        
        if not today_pct_changes:
            logger.warning(f"⚠️ 昨日成交额前20的股票今天没有涨跌幅数据")
            return 0
        
        # 计算平均涨幅
        total_pct = sum(p.change_percent for p in today_pct_changes)
        avg_pct = total_pct / len(today_pct_changes)
        
        logger.info(f"📊 昨日成交额前20股票今日平均涨幅: {avg_pct:.2f}% (共{len(today_pct_changes)}只)")
        
        return round(avg_pct, 2)
    
    def _get_trend_scores_cached(self, trade_date: str, db_session) -> tuple:
        """缓存趋势得分，同一 trade_date 只计算一次（避免 ma5/ma10 两个因子重复触发 DB 查询）"""
        if not hasattr(self, '_trend_score_cache'):
            self._trend_score_cache = {}
        if trade_date not in self._trend_score_cache:
            self._trend_score_cache[trade_date] = self._calculate_trend_scores(trade_date, db_session)
        return self._trend_score_cache[trade_date]

    def _calculate_trend_scores(self, trade_date: str, db_session) -> tuple:
        """
        计算上证指数的多头趋势得分
        - 近15个交易日不含今日，上证指数收盘价在5日线上+0.2分，在10日线上+0.1分
        
        Returns:
            (ma5_trend_score, ma10_trend_score)
        """
        import datetime
        from models.kline import StockDailyKLine
        
        # 固定使用上证指数 sh.000001
        INDEX_CODE = 'sh.000001'
        
        # 计算历史日期范围（过去30个交易日，不含今日）
        end_date = datetime.datetime.strptime(trade_date, '%Y-%m-%d')
        start_date = end_date - datetime.timedelta(days=30)
        start_str = start_date.strftime('%Y-%m-%d')
        
        # 获取上证指数的历史K线数据（过去30天，升序排列）
        klines = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code == INDEX_CODE,
            StockDailyKLine.trade_date >= start_str,
            StockDailyKLine.trade_date < trade_date,  # 不含今日
            StockDailyKLine.close_price.isnot(None),
            StockDailyKLine.close_price > 0
        ).order_by(StockDailyKLine.trade_date.asc()).all()
        
        if not klines or len(klines) < 6:
            logger.warning(f"⚠️ 上证指数历史数据不足，无法计算趋势得分")
            return 0, 0
        
        # klines 是升序排列：klines[0] = 最早, klines[-1] = 最近（昨天）
        # 计算过去15个交易日（从昨天往前数15天）的得分
        ma5_score = 0
        ma10_score = 0
        
        # 根据实际可用数据确定计算范围（最多15天）
        max_days = min(15, len(klines) - 1)  # 不含今日
        
        # 从昨天开始往前数
        # klines[-1] = 昨天, klines[-2] = 前天, ...
        for day_offset in range(1, max_days + 1):
            day_idx = len(klines) - day_offset
            
            if day_idx < 0:
                break
            
            # 获取当天的收盘价
            day_kline = klines[day_idx]
            close_price = day_kline.close_price
            
            # 计算 MA5：需要当天之前5天的收盘价
            ma5_start = day_idx - 5
            ma5_end = day_idx
            if ma5_start >= 0:
                ma5_prices = [h.close_price for h in klines[ma5_start:ma5_end] if h.close_price and h.close_price > 0]
                ma5 = sum(ma5_prices) / len(ma5_prices) if len(ma5_prices) >= 4 else 0
            else:
                ma5 = 0
            
            # 计算 MA10：需要当天之前10天的收盘价
            ma10_start = day_idx - 10
            ma10_end = day_idx
            if ma10_start >= 0:
                ma10_prices = [h.close_price for h in klines[ma10_start:ma10_end] if h.close_price and h.close_price > 0]
                ma10 = sum(ma10_prices) / len(ma10_prices) if len(ma10_prices) >= 8 else 0
            else:
                ma10 = 0
            
            if ma5 and close_price and ma5 > 0:
                if close_price > ma5:
                    ma5_score += 0.2
            
            if ma10 and close_price and ma10 > 0:
                if close_price > ma10:
                    ma10_score += 0.1
        
        logger.info(f"📊 上证指数趋势得分: ma5={ma5_score}, ma10={ma10_score} (计算天数={max_days})")
        
        # 返回得分（不需要平均，因为只有一只"股票"）
        return round(ma5_score, 2), round(ma10_score, 2)
    
    def _get_index_kline(self, index_code, trade_date, db_session):
        """获取指数K线数据 - 从 stock_daily_kline 表获取"""
        from models.kline import StockDailyKLine
        
        kline = db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code == index_code,
            StockDailyKLine.trade_date == trade_date
        ).first()
        
        if kline:
            return kline
        
        # 如果没有，返回None
        return None

    def _get_prev_trade_kline(self, index_code: str, trade_date: str, db_session):
        """
        获取某指数的上一个交易日K线
        从 stock_daily_kline 表中查找 trade_date < 当前日期 的最近一条数据
        """
        from models.kline import StockDailyKLine
        from sqlalchemy import func
        
        # 查找当前日期之前的最近一个交易日
        prev_date = db_session.query(
            func.max(StockDailyKLine.trade_date)
        ).filter(
            StockDailyKLine.stock_code == index_code,
            StockDailyKLine.trade_date < trade_date,
            StockDailyKLine.turnover.isnot(None),
            StockDailyKLine.turnover > 0
        ).scalar()
        
        if not prev_date:
            return None
        
        return db_session.query(StockDailyKLine).filter(
            StockDailyKLine.stock_code == index_code,
            StockDailyKLine.trade_date == prev_date
        ).first()
    
    def _calculate_rank_score(self, df: pd.DataFrame, field_name: str = 'turnover') -> pd.Series:
        """
        排名得分计算：排名第一为10，每少一名减0.2，最低为0
        """
        # 按指定字段排名
        df[f'temp_rank_{field_name}'] = df[field_name].rank(ascending=False, method='min')
        # 计算得分：10 - (rank - 1) * 0.2，最小为0
        scores = 10 - (df[f'temp_rank_{field_name}'] - 1) * 0.2
        scores = scores.clip(lower=0)
        return scores
    
    def _calculate_ma_trend(self, df: pd.DataFrame, history_data: Dict) -> pd.Series:
        """
        因子2 短线趋势：新逻辑
        - MA5 > MA10 > MA20 (短期均线在中期均线上方) → +2
        - Pt > MA5 (价格在短期均线上方) → +2
        - MA20(t) > MA20(t-1) (中长期均线向上) → +2
        每满足一项 +2，否则 -0.5
        """
        scores = pd.Series(0, index=df.index)
        
        for idx, row in df.iterrows():
            code = row['stock_code']
            close = row['close_price']
            
            if code not in history_data or len(history_data[code]) < 20:
                continue
            
            hist = history_data[code]
            
            # 计算当日的 MA5, MA10, MA20
            ma5 = sum([h['close_price'] for h in hist[:5]]) / 5 if len(hist) >= 5 else 0
            ma10 = sum([h['close_price'] for h in hist[:10]]) / 10 if len(hist) >= 10 else 0
            ma20 = sum([h['close_price'] for h in hist[:20]]) / 20 if len(hist) >= 20 else 0
            
            # 计算昨日的 MA20 (包含当天，index 0 是今天，index 1 是昨天)
            # ma20_y1: 昨天~第20天前 = hist[1:21] = 20条数据
            ma20_y1 = 0
            if len(hist) >= 21:  # 需要21天数据才能计算昨日的20日均线
                ma20_y1 = sum([h['close_price'] for h in hist[1:21]]) / 20
            
            score = 0
            count = 0
            
            # 条件1: MA5 > MA10 > MA20 (短期均线在中期均线上方，成本上移)
            if ma5 > ma10 > ma20:
                score += 2
                count += 1
            
            # 条件2: Pt > MA5 (价格在短期均线上方，多头主导)
            if close > ma5:
                score += 2
                count += 1
            
            # 条件3: MA20(t) > MA20(t-1) (中长期均线向上，趋势延续)
            if ma20 > ma20_y1 and ma20_y1 > 0:
                score += 2
                count += 1
            
            # 如果没有满足任何条件，扣分
            if count == 0:
                score = -0.5
            
            scores.at[idx] = score
        
        return scores
    
    def _calculate_factor3_vol(self, df: pd.DataFrame, history_data: Dict) -> pd.Series:
        """
        成交量对比：成交量>=上一交易日+3，否则-1
        """
        scores = pd.Series(0, index=df.index)
        
        for idx, row in df.iterrows():
            code = row['stock_code']
            current_vol = row['volume']
            
            if code not in history_data or len(history_data[code]) < 1:
                continue
            
            # 上一交易日成交量
            prev_vol = history_data[code][0]['volume']
            
            if current_vol >= prev_vol:
                scores.at[idx] = 3
            else:
                scores.at[idx] = -1
        
        return scores
    
    def _calculate_burst(self, df: pd.DataFrame, history_data: Dict) -> pd.Series:
        """
        爆量：3日均值/(4-20日均值)*2
        """
        scores = pd.Series(0, index=df.index)
        
        for idx, row in df.iterrows():
            code = row['stock_code']
            
            if code not in history_data or len(history_data[code]) < 20:
                continue
            
            hist = history_data[code]
            
            # 最近3个交易日平均成交额
            avg_3d = sum([h['turnover'] for h in hist[:3]]) / 3 if len(hist) >= 3 else 0
            
            # 前20到前4交易日（共17天）的平均成交额
            avg_4_20 = sum([h['turnover'] for h in hist[3:20]]) / 17 if len(hist) >= 20 else 0
            
            if avg_4_20 > 0:
                scores.at[idx] = (avg_3d / avg_4_20) * 2
        
        return scores
    
    def _calculate_extreme(self, df: pd.DataFrame, history_data: Dict) -> pd.Series:
        """
        极限量：10日均值/(11-30日均值)*3
        """
        scores = pd.Series(0, index=df.index)
        
        has_history_count = sum(1 for idx, row in df.iterrows() if row['stock_code'] in history_data and len(history_data[row['stock_code']]) >= 30)
        
        for idx, row in df.iterrows():
            code = row['stock_code']
            
            if code not in history_data or len(history_data[code]) < 30:
                continue
            
            hist = history_data[code]
            
            # 最近10个交易日平均成交额
            avg_10d = sum([h['turnover'] for h in hist[:10]]) / 10 if len(hist) >= 10 else 0
            
            # 前30到前11交易日（共20天）的平均成交额
            avg_11_30 = sum([h['turnover'] for h in hist[10:30]]) / 20 if len(hist) >= 30 else 0
            
            if avg_11_30 > 0:
                scores.at[idx] = (avg_10d / avg_11_30) * 3
        
        return scores
    
    def _calculate_trend(self, df: pd.DataFrame, history_data: Dict) -> pd.Series:
        """
        多头趋势：15日每日MA5+0.2，MA10+0.1
        """
        scores = pd.Series(0, index=df.index)
        
        for idx, row in df.iterrows():
            code = row['stock_code']
            
            if code not in history_data or len(history_data[code]) < 15:
                continue
            
            hist = history_data[code]
            
            score = 0
            # 遍历最近15个交易日（不含今日）
            for i in range(min(15, len(hist))):
                # 需要计算从i日往前的MA5和MA10
                start_idx = i
                end_idx = i + 5
                
                if end_idx > len(hist):
                    break
                
                # 计算该日的MA5和MA10
                ma5 = sum([h['close_price'] for h in hist[start_idx:end_idx]]) / 5
                ma10 = sum([h['close_price'] for h in hist[start_idx:start_idx+10]]) / 10 if start_idx + 10 <= len(hist) else ma5
                
                close = hist[start_idx]['close_price']
                
                # 股价在MA5上+0.2分
                if close >= ma5:
                    score += 0.2
                # 股价在MA10上+0.1分
                if close >= ma10:
                    score += 0.1
            
            scores.at[idx] = score
        
        return scores
    
    def _get_default_market_factors(self, trade_date, db_session):
        """获取默认大盘因子"""
        # 主要指数
        main_indices = ['sh.000001', 'sz.399001', 'sz.399006']
        
        result = {}
        for idx_code in main_indices:
            kline = self._get_index_kline(idx_code, trade_date, db_session)
            if kline:
                result[f'{idx_code}_close'] = float(kline.close_price) if kline.close_price else 0
                result[f'{idx_code}_change'] = float(kline.change_percent) if kline.change_percent else 0
                result[f'{idx_code}_volume'] = float(kline.volume) if kline.volume else 0
        
        return result
    
    def _evaluate_market_expression(self, expression: str, context: Dict) -> float:
        """评估大盘表达式"""
        try:
            # 展平上下文 - 支持 int, float, Decimal
            names = {}
            for key, value in context.items():
                if value is None:
                    continue
                # 处理 Decimal 类型
                if hasattr(value, '__float__'):
                    try:
                        names[key] = float(value)
                    except (TypeError, ValueError):
                        pass
            
            result = simpleeval.simple_eval(self._preprocess_expression(expression), names=names, functions=self.simpleeval_functions)
            return float(result) if result else 0
        except ZeroDivisionError:
            return 0
        except Exception as e:
            logger.warning(f"评估大盘表达式失败: {expression}, 错误: {e}")
            return 0
    
    def _evaluate_factor_expression(self, expression: str, df: pd.DataFrame, 
                                     trade_date: str, db_session) -> pd.Series:
        """评估因子表达式（针对每行数据）"""
        results = []
        
        for _, row in df.iterrows():
            # 构建上下文
            context = row.to_dict()
            
            # 添加大盘因子
            market_factors = self.calculate_market_factors(trade_date, db_session)
            context.update(market_factors)
            
            try:
                result = simpleeval.simple_eval(self._preprocess_expression(expression), names=context, functions=self.simpleeval_functions)
                results.append(result if result else 0)
            except Exception as e:
                logger.warning(f"评估因子表达式失败: {expression}, 错误: {e}")
                results.append(0)
        
        return pd.Series(results)
    
    def _evaluate_expression(self, expression: str, records: List[Dict]) -> List[float]:
        """评估表达式（针对多条记录）"""
        results = []
        
        # 提取表达式中使用的所有变量名
        import re
        # 匹配变量名（简单匹配，假设变量名只包含字母数字下划线）
        var_names = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expression))
        # 排除内置函数名
        builtins = {'abs', 'min', 'max', 'sum', 'round', 'len', 'pow', 'float', 'int', 'str', 'bool', 'list', 'dict', 'tuple', 'set', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return', 'import', 'from', 'as', 'try', 'except', 'finally', 'raise', 'with', 'lambda', 'yield', 'global', 'nonlocal', 'pass', 'break', 'continue', 'assert'}
        var_names = var_names - builtins
        
        for record in records:
            try:
                # 为缺失的因子添加默认值0
                record_with_defaults = dict(record)
                for var in var_names:
                    if var not in record_with_defaults:
                        record_with_defaults[var] = 0
                # 防止除零：将除数设为1如果为0
                for var in ['ma5', 'ma10', 'ma20', 'ma30', 'avg_price', 'prev_close']:
                    if var in record_with_defaults and record_with_defaults[var] == 0:
                        record_with_defaults[var] = 1
                result = simpleeval.simple_eval(self._preprocess_expression(expression), names=record_with_defaults, functions=self.simpleeval_functions)
                results.append(result if result else 0)
            except ZeroDivisionError:
                results.append(0)
            except Exception as e:
                logger.warning(f"评估表达式失败: {expression}, 错误: {e}")
                results.append(0)
        
        return results
    
    @staticmethod
    def test_expression(expression: str, factors: Dict) -> Dict:
        """测试表达式（静态方法）"""
        # 创建临时实例获取functions
        temp_instance = FactorCalculator()
        try:
            result = simpleeval.simple_eval(temp_instance._preprocess_expression(expression), names=factors, functions=temp_instance.simpleeval_functions)
            return {
                'success': True,
                'result': result,
                'message': '表达式计算成功'
            }
        except Exception as e:
            return {
                'success': False,
                'result': None,
                'message': f'表达式计算失败: {str(e)}'
            }


# 全局因子计算器实例
factor_calculator = FactorCalculator()
