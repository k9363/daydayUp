-- =====================================================
-- 大盘指数因子定义
-- 分解为原子因子，通过表达式计算综合得分
-- =====================================================

-- 1. 删除旧的非必要因子（如果存在重复的）
DELETE FROM factor_define WHERE factor_scope = 'market' AND factor_code LIKE 'market_%';
DELETE FROM score_expression WHERE scope = 'market';

-- 2. 新增大盘指数原子因子
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `field_name`, `index_code`, `expression`, `description`, `is_active`) VALUES
-- 涨跌比因子（Python硬编码计算）
('up_down_ratio', '涨跌比', 'market', 'python', 'up_down_ratio', NULL, NULL, NULL, '上涨股票数/下跌股票数', 1),
('up_down_ratio_top50', '成交额前50涨跌比', 'market', 'python', 'up_down_ratio_top50', NULL, NULL, NULL, '成交额前50股票的涨跌比', 1),

-- 指数成交额因子（从K线获取）
('sh_turnover', '上证成交额', 'market', 'kline', NULL, 'turnover', 'sh.000001', NULL, '上证指数当日成交额（元）', 1),
('sz_turnover', '深证成交额', 'market', 'kline', NULL, 'turnover', 'sz.399001', NULL, '深证成指当日成交额（元）', 1),
('total_turnover', '指数总成交额', 'market', 'calculated', NULL, NULL, NULL, 'sh_turnover + sz_turnover', '上证+深证成交额之和', 1),

-- 昨日成交额（通过Python获取上一个交易日）
('sh_turnover_y1', '上证昨日成交额', 'market', 'python', 'prev_trade_turnover', 'turnover', 'sh.000001', NULL, '上证指数上一个交易日成交额', 1),
('sz_turnover_y1', '深证昨日成交额', 'market', 'python', 'prev_trade_turnover', 'turnover', 'sz.399001', NULL, '深证成指上一个交易日成交额', 1),
('total_turnover_y1', '昨日总成交额', 'market', 'calculated', NULL, NULL, NULL, 'sh_turnover_y1 + sz_turnover_y1', '昨日上证+深证成交额之和', 1),

-- 成交额增速
('turnover_growth', '成交额增速', 'market', 'calculated', NULL, NULL, NULL, 'IF(total_turnover_y1 > 0, total_turnover / total_turnover_y1 * 5, 0)', '今日成交额/昨日成交额*5', 1),

-- 多头趋势得分（Python硬编码计算）
('ma5_trend_score', '5日线多头得分', 'market', 'python', 'ma5_trend_score', NULL, NULL, NULL, '过去15日每日股价在5日线上+0.2分', 1),
('ma10_trend_score', '10日线多头得分', 'market', 'python', 'ma10_trend_score', NULL, NULL, NULL, '过去15日每日股价在10日线上+0.1分', 1),

-- 大盘综合得分（最终表达式）
('market_score', '大盘综合得分', 'market', 'calculated', NULL, NULL, NULL, 
'up_down_ratio * 2 + up_down_ratio_top50 * 3 + turnover_growth + ma5_trend_score + ma10_trend_score',
'涨跌比*2 + 前50涨跌比*3 + 成交额增速 + 5日线多头得分 + 10日线多头得分', 1);

-- 3. 新增大盘得分表达式
REPLACE INTO `score_expression` (`expression_name`, `scope`, `factors`, `expression`, `top_n`, `is_default`, `is_active`, `description`) VALUES
('大盘综合得分', 'market', 
 '["up_down_ratio", "up_down_ratio_top50", "turnover_growth", "ma5_trend_score", "ma10_trend_score", "market_score"]',
 'market_score',
 NULL, 1, 1, 
 '涨跌比*2 + 前50涨跌比*3 + 成交额增速 + 多头趋势得分');

SELECT '大盘指数因子配置完成!' AS result;
