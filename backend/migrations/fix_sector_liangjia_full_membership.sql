-- 修复「板块量价得分」异常：量价/广度类板块因子改为覆盖板块全部成分股
--
-- 背景：板块得分原本只在「成交额前N」的股票池里聚合（calculate_sector_factors），
--       导致大量板块在池内只有1只股，「上涨家数占比」退化成0/1二值，
--       且池子本身按成交额选出，「量比」被系统性抬高 —— 板块量价得分因此异常
--       （多个板块并列、分数虚高/乱飞）。
--
-- 方案：新增4个全成分股口径的板块因子（source='sector_market'，由后端
--       _compute_full_membership_sector_factors 计算），并把「板块量价得分」
--       表达式改为引用这些 *_all 因子。「综合得分」保持原前N池口径不变。
--
-- 配套代码：backend/services/factor_service.py、backend/services/review_service.py

-- 1. 新增全成分股板块因子定义（source='sector_market' 由代码直接聚合，
--    field_name/aggregation 仅用于 UI 展示，计算不依赖它们）
INSERT INTO factor_define
    (factor_code, factor_name, factor_scope, source, field_name, aggregation, is_active, description, created_at, updated_at)
VALUES
    ('sector_avg_change_all',   '板块平均涨跌幅(全成分股)', 'sector', 'sector_market', 'change_percent', 'AVG', 1, '板块全部成分股当日涨跌幅均值（仅统计有成交的成分股）', NOW(), NOW()),
    ('sector_up_ratio_all',     '板块上涨家数占比(全成分股)', 'sector', 'sector_market', 'change_percent', 'AVG', 1, '板块全部成分股中上涨家数占比（仅统计有成交的成分股）', NOW(), NOW()),
    ('sector_total_amount_all', '板块总成交额(全成分股)',   'sector', 'sector_market', 'turnover', 'SUM', 1, '板块全部成分股当日成交额之和', NOW(), NOW()),
    ('sector_amount_ma5_all',   '板块5日均成交额(全成分股)', 'sector', 'sector_market', 'turnover', 'SUM', 1, '板块全部成分股近5日均成交额之和（量比分母）', NOW(), NOW())
ON DUPLICATE KEY UPDATE
    factor_name = VALUES(factor_name),
    factor_scope = VALUES(factor_scope),
    source = VALUES(source),
    field_name = VALUES(field_name),
    aggregation = VALUES(aggregation),
    is_active = 1,
    description = VALUES(description),
    updated_at = NOW();

-- 2. 「板块量价得分」表达式改用全成分股因子（*_all）
UPDATE score_expression
SET expression = 'sector_avg_change_all * 1.0 + (sector_total_amount_all / MAX(sector_amount_ma5_all, sector_total_amount_all * 0.2, 1) - 1) * 4 + (sector_up_ratio_all - 0.5) * 8 + IF(sector_total_amount_all / MAX(sector_amount_ma5_all, sector_total_amount_all * 0.2, 1) > 1.3 AND sector_avg_change_all > 1, 4, 0) - IF(sector_total_amount_all / MAX(sector_amount_ma5_all, sector_total_amount_all * 0.2, 1) > 1.5 AND sector_avg_change_all < -1, 4, 0)',
    factors = JSON_ARRAY('sector_avg_change_all', 'sector_total_amount_all', 'sector_amount_ma5_all', 'sector_up_ratio_all'),
    description = '量价配合排序(全成分股口径):涨幅+量比(放量)+上涨广度+量价共振奖/出货罚',
    updated_at = NOW()
WHERE scope = 'sector' AND expression_name = '板块量价得分';

-- 3. 将「板块量价得分」设为默认板块表达式（复盘板块得分将采用它）
UPDATE score_expression SET is_default = 0, updated_at = NOW()
WHERE scope = 'sector' AND expression_name <> '板块量价得分';
UPDATE score_expression SET is_default = 1, is_active = 1, updated_at = NOW()
WHERE scope = 'sector' AND expression_name = '板块量价得分';
