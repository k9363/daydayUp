-- 偏离值因子定义
-- 说明：偏离值因子通过Python代码计算（calculation_method='python'），不依赖表达式

-- 10天累计偏离值：股票10日累计涨跌幅与上证指数10日累计涨跌幅的差值
INSERT INTO factor_define (factor_code, factor_name, factor_scope, source, calculation_method, description, is_active, created_at, updated_at)
VALUES 
('deviation_10d', '10日累计偏离值', 'stock', 'calculated', 'python', '股票10日累计涨跌幅与上证指数10日累计涨跌幅的差值', 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE factor_name=VALUES(factor_name), calculation_method=VALUES(calculation_method), description=VALUES(description);

-- 30天累计偏离值：股票30日累计涨跌幅与上证指数30日累计涨跌幅的差值
INSERT INTO factor_define (factor_code, factor_name, factor_scope, source, calculation_method, description, is_active, created_at, updated_at)
VALUES 
('deviation_30d', '30日累计偏离值', 'stock', 'calculated', 'python', '股票30日累计涨跌幅与上证指数30日累计涨跌幅的差值', 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE factor_name=VALUES(factor_name), calculation_method=VALUES(calculation_method), description=VALUES(description);

-- 剩余偏离值：距离阈值的差距（正=未达标，负=超标）
-- 阈值：10天+100%或-50%，30天+200%或-70%
INSERT INTO factor_define (factor_code, factor_name, factor_scope, source, calculation_method, description, is_active, created_at, updated_at)
VALUES 
('remaining_deviation', '剩余偏离值', 'stock', 'calculated', 'python', '距离目标阈值的差距，正向阈值10天+100%/30天+200%，负向阈值10天-50%/30天-70%', 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE factor_name=VALUES(factor_name), calculation_method=VALUES(calculation_method), description=VALUES(description);

-- 验证插入结果
SELECT factor_code, factor_name, factor_scope, source, calculation_method, description 
FROM factor_define 
WHERE factor_code IN ('deviation_10d', 'deviation_30d', 'remaining_deviation');
