-- =====================================================
-- 股票得分因子定义
-- 基于用户提供的6个因子逻辑
-- =====================================================

-- 删除旧的股票得分因子（如果存在）
DELETE FROM factor_define WHERE factor_scope = 'stock' AND source = 'calculated' AND factor_code LIKE 'factor%';

-- 重新定义6个得分因子
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
-- 因子1: 成交额权重 (当日成交额第一为10，每少一名减0.2，最低为0)
('factor1_rank', '成交额权重', 'stock', 'calculated', NULL, 'expression', 
 'IF(amount_rank <= 50, 10 - (amount_rank - 1) * 0.2, 0)', 
 '当日成交额第一为10，每少一名减0.2，最低为0（仅计算前50名）', 1),

-- 因子2: 短线趋势 (股价在五日线上+3否则-1，在10日线上加2否则-0.5)
('factor2_ma', '短线趋势', 'stock', 'calculated', NULL, 'expression', 
 'IF(close_price > ma5, 3, -1) + IF(close_price > ma10, 2, -0.5)', 
 '股价在五日线上+3否则-1，在10日线上加2否则-0.5', 1),

-- 因子3: 昨日同比 (成交量大于等于上个交易加3，否则减1)
('factor3_vol', '昨日同比', 'stock', 'calculated', NULL, 'expression', 
 'IF(volume >= volume_y1, 3, -1)', 
 '成交量大于等于上个交易加3，否则减1', 1),

-- 因子4: 爆量 (最近3个交易日的平均成交金额与前20到前4交易日的比值*2)
('factor4_burst', '爆量', 'stock', 'calculated', NULL, 'expression', 
 'IF(avg_amount_4_20d > 0, avg_amount_3d / avg_amount_4_20d * 2, 0)', 
 '最近3个交易日的平均成交金额与前20到前4交易日的比值*2', 1),

-- 因子5: 极限量 (最近10个交易日的平均成交金额与前30到前11交易日的比值*3)
('factor5_extreme', '极限量', 'stock', 'calculated', NULL, 'expression', 
 'IF(avg_amount_11_30d > 0, avg_amount_10d / avg_amount_11_30d * 3, 0)', 
 '最近10个交易日的平均成交金额与前30到前11交易日的比值*3', 1),

-- 因子6: 多头趋势 (近15个交易日不含今日，每个交易日股价在5日线上+0.2分，在10日线上+0.1分)
-- 由于需要历史K线数据，这里使用简化表达式：收盘价与MA5差值比例 + 收盘价与MA10差值比例
('factor6_trend', '多头趋势', 'stock', 'calculated', NULL, 'expression', 
 'IF(ma5 > 0, (close_price - ma5) / ma5 * 10, 0) + IF(ma10 > 0, (close_price - ma10) / ma10 * 5, 0)', 
 '近似多头趋势：收盘价与5日线差值*10 + 收盘价与10日线差值*5', 1);

-- =====================================================
-- 股票得分表达式
-- 选出前10个股进行展示
-- =====================================================

-- 删除旧的默认股票表达式
DELETE FROM score_expression WHERE scope = 'stock' AND is_default = 1;

-- 创建新的默认股票表达式
-- factors只包含最终得分因子，用于前端展示
REPLACE INTO `score_expression` (`expression_name`, `scope`, `factors`, `expression`, `top_n`, `is_default`, `is_active`, `description`) VALUES
('股票综合得分', 'stock', 
 '["factor1_rank", "factor2_ma", "factor3_vol", "factor4_burst", "factor5_extreme", "factor6_trend"]',
 'factor1_rank + factor2_ma + factor3_vol + factor4_burst + factor5_extreme + factor6_trend',
 10, 1, 1, 
 '成交额权重+短线趋势+昨日同比+爆量+极限量+多头趋势，取前10名');
