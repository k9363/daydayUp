-- =====================================================
-- 新增4个技术面因子（表达式方式）- 简化版
-- 辅助因子逻辑直接合并到主因子表达式中
-- =====================================================

-- 删除旧的因子配置
DELETE FROM factor_define WHERE factor_code IN ('factor1_rank', 'factor2_ma', 'factor3_vol', 'factor4_burst');
DELETE FROM factor_define WHERE factor_code IN ('factor2_ma_alignment', 'factor2_ma_price', 'factor2_ma_trend');
DELETE FROM factor_define WHERE factor_code IN ('close_price_y1', 'ma20_y1', 'avg_turnover_3d', 'avg_amount_4_120d');

-- 依赖的原子因子
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_range`, `description`, `is_active`) VALUES
('close_price_y1', '昨日收盘价', 'stock', 'kline', 'close_price', 'kline_field', NULL, '昨日收盘价', 1);

INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_range`, `description`, `is_active`) VALUES
('ma20_y1', '昨日MA20', 'stock', 'kline', 'ma20', 'kline_field', NULL, '昨日20日均线', 1);

INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_range`, `description`, `is_active`) VALUES
('avg_turnover_3d', '3日成交额均线', 'stock', 'kline', 'turnover', 'turnover_ma', '3', '3日成交额均线', 1);

INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_range`, `description`, `is_active`) VALUES
('avg_amount_4_120d', '120日成交额均值', 'stock', 'kline', 'turnover', 'amount_ma', '120', '120日成交额均值', 1);

-- =====================================================
-- 最终4个技术面因子（表达式）- 逻辑直接展开
-- =====================================================

-- factor1_rank: 排名得分 = 10 - 排名，最低0分
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('factor1_rank', '排名得分', 'stock', 'calculated', 'expression', 'IF(10-amount_rank>0, 10-amount_rank, 0)', '排名每减1分数减1,满分10分,最低0分', 1);

-- factor2_ma: 均线多头得分 - 三个条件得分之和（逻辑直接展开）
-- (MA5>MA10>MA20 ? +2 : -0.5) + (价格>MA5 ? +2 : -0.5) + (MA20>MA20_y1 ? +2 : -0.5)
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('factor2_ma', '均线多头得分', 'stock', 'calculated', 'expression', 
 'IF(ma5>ma10 AND ma10>ma20, 2, -0.5) + IF(close_price>ma5, 2, -0.5) + IF(ma20>ma20_y1 AND ma20_y1>0, 2, -0.5)', 
 'MA5>MA10>MA20:+2分,价格>MA5:+2分,MA20向上:+2分,不满足每项:-0.5分', 1);

-- factor3_vol: 涨幅得分 = (收盘价/昨日收盘价 - 1) * 3
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('factor3_vol', '涨幅得分', 'stock', 'calculated', 'expression', '(close_price/close_price_y1-1)*3', '收盘价相对昨日涨幅*3', 1);

-- factor4_burst: 放量得分 = 3日均量 / 120日均量 * 3
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('factor4_burst', '放量得分', 'stock', 'calculated', 'expression', 'avg_turnover_3d/avg_amount_4_120d*3', '3日均量/120日均量*3', 1);

SELECT '技术面因子配置完成!' AS result;
