-- =====================================================
-- 修复大盘因子计算顺序和表达式问题
-- 问题：market_score 在 up_down_balance 之前计算，导致依赖因子未定义
-- =====================================================

-- 1. 修复 market_score 的表达式（使用正确的因子）
UPDATE factor_define 
SET expression = 'up_down_ratio * 2 + up_down_ratio_top50 * 3 + turnover_growth + ma5_trend_score + ma10_trend_score'
WHERE factor_code = 'market_score';

-- 2. 检查并显示修复后的结果
SELECT factor_code, factor_name, source, expression, 
       CASE 
           WHEN source = 'kline' THEN CONCAT(index_code, '.', field_name)
           WHEN source = 'python' THEN calculation_method
           ELSE expression
       END AS calculation_info
FROM factor_define 
WHERE factor_scope = 'market' AND is_active = 1
ORDER BY id;

SELECT '修复完成!' AS result;
