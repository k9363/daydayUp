-- =====================================================
-- 原子因子定义和表达式配置
-- 因子是最简化的原子逻辑，表达式组合因子计算得分
-- =====================================================

-- =====================================================
-- 股票原子因子定义
-- =====================================================
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
-- K线原始字段因子 (source=kline)
('close_price', '收盘价', 'stock', 'kline', 'close_price', 'kline_field', NULL, '当日收盘价', 1),
('volume', '成交量', 'stock', 'kline', 'volume', 'kline_field', NULL, '当日成交量', 1),
('turnover', '成交额', 'stock', 'kline', 'turnover', 'kline_field', NULL, '当日成交额(元)', 1),
('pct_change', '涨跌幅', 'stock', 'kline', 'pct_change', 'kline_field', NULL, '当日涨跌幅(%)', 1),

-- 均线因子 (从K线获取预计算的均线)
('ma5', '5日均线', 'stock', 'kline', 'ma5', 'kline_field', NULL, '5日简单移动平均价', 1),
('ma10', '10日均线', 'stock', 'kline', 'ma10', 'kline_field', NULL, '10日简单移动平均价', 1),
('ma20', '20日均线', 'stock', 'kline', 'ma20', 'kline_field', NULL, '20日简单移动平均价', 1),

-- 均线差值因子 (使用表达式计算)
('price_ma5_diff', '股价与5日线差值', 'stock', 'calculated', NULL, 'expression', 'close_price - ma5', '收盘价与5日均线的差值', 1),
('price_ma10_diff', '股价与10日线差值', 'stock', 'calculated', NULL, 'expression', 'close_price - ma10', '收盘价与10日均线的差值', 1),

-- 成交量/额相关因子 (从K线获取昨日数据)
('volume_y1', '昨日成交量', 'stock', 'kline', 'volume_y1', 'kline_field', NULL, '昨日成交量', 1),
('turnover_y1', '昨日成交额', 'stock', 'kline', 'turnover_y1', 'kline_field', NULL, '昨日成交额', 1),

-- 历史平均成交额因子 (使用聚合计算方法)
('avg_amount_3d', '近3日平均成交额', 'stock', 'kline', 'turnover', 'avg_3d', NULL, '最近3个交易日平均成交额', 1),
('avg_amount_5d', '近5日平均成交额', 'stock', 'kline', 'turnover', 'avg_5d', NULL, '最近5个交易日平均成交额', 1),
('avg_amount_10d', '近10日平均成交额', 'stock', 'kline', 'turnover', 'avg_10d', NULL, '最近10个交易日平均成交额', 1),
('avg_amount_20d', '近20日平均成交额', 'stock', 'kline', 'turnover', 'avg_20d', NULL, '最近20个交易日平均成交额', 1),
('avg_amount_4_20d', '4-20日平均成交额', 'stock', 'kline', 'turnover', 'avg_4_20d', NULL, '第4到20个交易日的平均成交额(用于爆量计算)', 1),
('avg_amount_11_30d', '11-30日平均成交额', 'stock', 'kline', 'turnover', 'avg_11_30d', NULL, '第11到30个交易日的平均成交额(用于极限量计算)', 1),

-- 成交额排名因子 (使用排名计算方法)
('amount_rank', '成交额排名', 'stock', 'kline', 'turnover', 'rank', NULL, '当日成交额在股票池中的排名(从1开始)', 1);

-- =====================================================
-- 板块因子定义
-- =====================================================
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `aggregation`, `expression`, `description`, `is_active`) VALUES
('sector_total_score', '板块股票得分总和', 'sector', 'stock_factor', 'total_score', 'SUM', NULL, '板块内所有股票的得分之和', 1),
('sector_avg_score', '板块股票平均得分', 'sector', 'stock_factor', 'total_score', 'AVG', NULL, '板块内股票得分的平均值', 1),
('sector_stock_count', '板块股票数量', 'sector', 'stock_factor', 'stock_code', 'COUNT', NULL, '板块内的股票数量', 1),
('sector_total_amount', '板块总成交额', 'sector', 'kline', 'turnover', 'SUM', NULL, '板块内股票成交额之和', 1),
('sector_avg_change', '板块平均涨跌幅', 'sector', 'kline', 'pct_change', 'AVG', NULL, '板块内股票涨跌幅平均值', 1);

-- =====================================================
-- 大盘因子定义
-- =====================================================
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `index_code`, `expression`, `description`, `is_active`) VALUES
('sh_index_close', '上证指数收盘价', 'market', 'kline', 'close_price', 'sh.000001', NULL, '上证指数当日收盘价', 1),
('sh_index_pct', '上证指数涨跌幅', 'market', 'kline', 'pct_change', 'sh.000001', NULL, '上证指数当日涨跌幅', 1),
('sz_index_close', '深证成指收盘价', 'market', 'kline', 'close_price', 'sz.399001', NULL, '深证成指当日收盘价', 1),
('sz_index_pct', '深证成指涨跌幅', 'market', 'kline', 'pct_change', 'sz.399001', NULL, '深证成指当日涨跌幅', 1);

-- =====================================================
-- 表达式配置
-- 使用原子因子组合计算最终得分
-- =====================================================
REPLACE INTO `score_expression` (`expression_name`, `scope`, `factors`, `expression`, `top_n`, `is_default`, `is_active`, `description`) VALUES
-- 股票得分表达式: 使用6个因子
('股票综合得分', 'stock', 
 '["factor1_rank", "factor2_ma", "factor3_vol", "factor4_burst", "factor5_extreme", "factor6_trend", "close_price", "amount_rank"]',
 'factor1_rank + factor2_ma + factor3_vol + factor4_burst + factor5_extreme + factor6_trend',
 NULL, 1, 1, 
 '成交额权重+短线趋势+昨日同比+爆量+极限量+多头趋势'),

-- 板块得分表达式
('板块综合得分', 'sector', 
 '["sector_total_score", "sector_avg_score", "sector_stock_count", "sector_avg_change"]',
 'sector_total_score + sector_stock_count * 5 + sector_avg_change * 10',
 30, 1, 1, 
 '股票得分总和+股票数量*5+平均涨跌幅*10'),

-- 市场得分表达式
('市场强度得分', 'market', 
 '["sh_index_pct", "sz_index_pct"]',
 '(sh_index_pct + sz_index_pct) / 2',
 NULL, 1, 1, 
 '上证和深证涨跌幅平均值');

SELECT '配置完成!' AS result;
