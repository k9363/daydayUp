-- 新增新高因子定义
-- 因子逻辑：如果今日收盘股价是近120交易日最高的则为 true

INSERT INTO factor_define (factor_code, factor_name, factor_scope, source, calculation_method, days_range, description, is_active, created_at, updated_at)
VALUES 
('new_high_120', '新高120日', 'stock', 'kline', 'new_high', '120', '近120个交易日最高价，如果今日收盘价是近120日最高则为true', TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE 
    factor_name = VALUES(factor_name),
    calculation_method = VALUES(calculation_method),
    days_range = VALUES(days_range),
    description = VALUES(description);
