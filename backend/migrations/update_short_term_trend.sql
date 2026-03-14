-- 更新短线趋势因子表达式
-- 新逻辑：
-- 1. MA5 > MA10 > MA20 (短期均线在中期均线上方) → +2，否则 -0.5
-- 2. Pt > MA5 (价格在短期均线上方) → +2，否则 -0.5
-- 3. MA20(t) > MA20(t-1) (中长期均线向上) → +2，否则 -0.5

UPDATE factor_define 
SET expression = 'IF(ma5 > ma10 and ma10 > ma20, 2, -0.5) + IF(close_price > ma5, 2, -0.5) + IF(ma20 > ma20_y1, 2, -0.5)',
    description = 'MA5>MA10>MA20:+2, Pt>MA5:+2, MA20向上:+2, 否则各-0.5'
WHERE factor_code = 'factor2_ma';
