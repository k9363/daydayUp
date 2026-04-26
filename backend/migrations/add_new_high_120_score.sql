-- 新增高分120日衍生因子
-- 逻辑：如果 new_high_120 为 1 则为20分，否则为0

INSERT INTO factor_define (factor_code, factor_name, factor_scope, source, calculation_method, field_name, expression, description, is_active, created_at, updated_at)
VALUES 
('new_high_120_score', '高分120日', 'stock', 'calculated', 'expression', NULL, 'IF(new_high_120 = 1, 20, 0)', '如果近120日创新高则得20分，否则得0分', TRUE, NOW(), NOW())
ON DUPLICATE KEY UPDATE 
    factor_name = VALUES(factor_name),
    calculation_method = VALUES(calculation_method),
    expression = VALUES(expression),
    description = VALUES(description),
    updated_at = NOW();
