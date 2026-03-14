-- =====================================================
-- 新增成交额均线因子 (支持4-120日区间)
-- 创建日期: 2026-03-07
-- =====================================================

-- 1. 添加 days_range 字段到 factor_define 表
ALTER TABLE `factor_define` ADD COLUMN `days_range` VARCHAR(20) NULL COMMENT '天数区间，如 1_3 表示最近3天，4_20 表示第4-20天' AFTER `field_name`;

-- 2. 更新现有因子的 days_range 配置
UPDATE `factor_define` SET `days_range` = '1_3' WHERE `factor_code` = 'avg_amount_3d';
UPDATE `factor_define` SET `days_range` = '1_5' WHERE `factor_code` = 'avg_amount_5d';
UPDATE `factor_define` SET `days_range` = '1_10' WHERE `factor_code` = 'avg_amount_10d';
UPDATE `factor_define` SET `days_range` = '1_20' WHERE `factor_code` = 'avg_amount_20d';
UPDATE `factor_define` SET `days_range` = '4_20' WHERE `factor_code` = 'avg_amount_4_20d';
UPDATE `factor_define` SET `days_range` = '11_30' WHERE `factor_code` = 'avg_amount_11_30d';

-- 3. 新增 4-120 日平均成交额因子
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `field_name`, `days_range`, `description`, `is_active`) VALUES
('avg_amount_4_120d', '4-120日平均成交额', 'stock', 'kline', 'turnover_ma', 'turnover', '4_120', '第4到120个交易日的平均成交额(用于爆量计算)', 1);

-- 4. 更新 calculation_method 字段（可选，用于标识计算方法类型）
UPDATE `factor_define` SET `calculation_method` = 'turnover_ma' WHERE `factor_code` LIKE 'avg_amount_%';
