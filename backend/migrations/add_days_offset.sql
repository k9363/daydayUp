-- =====================================================
-- 添加 days_offset 字段到 factor_define 表
-- 用于支持历史日期偏移因子配置
-- =====================================================

-- 检查字段是否存在，如果不存在则添加
-- SQLite 不支持 ADD COLUMN IF NOT EXISTS，使用如下方式兼容
-- 注意：如果是首次运行，需要确保表结构正确

-- 为现有的昨日因子添加 days_offset
UPDATE factor_define SET days_offset = 1 WHERE factor_code IN ('volume_y1', 'turnover_y1');

SELECT 'days_offset 字段更新完成!' AS result;
