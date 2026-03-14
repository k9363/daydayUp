-- =====================================================
-- 更新 factor2_ma 短线趋势因子为最新逻辑
-- 逻辑：
-- 1. MA5 > MA10 > MA20 (短期均线在中期均线上方，成本上移) → +2
-- 2. Pt > MA5 (价格在短期均线上方，多头主导) → +2
-- 3. MA20(t) > MA20(t-1) (中长期均线向上，趋势延续) → +2
-- 每满足一项+2，否则各-0.5
-- =====================================================

-- 首先确保 ma20_y1 因子存在（昨日MA20）
-- 如果不存在则创建
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('ma20_y1', '昨日20日均线', 'stock', 'kline', 'close_price', 'ma20_y1', NULL, '昨日的20日简单移动平均价', 1);

-- 更新 factor2_ma 的表达式
UPDATE `factor_define` 
SET expression = 'IF(ma5 > ma10 and ma10 > ma20, 2, -0.5) + IF(close_price > ma5, 2, -0.5) + IF(ma20 > ma20_y1, 2, -0.5)',
    description = 'MA5>MA10>MA20:+2, Pt>MA5:+2, MA20向上:+2, 否则各-0.5',
    calculation_method = 'python'
WHERE factor_code = 'factor2_ma';

SELECT 'factor2_ma 更新完成!' AS result;
