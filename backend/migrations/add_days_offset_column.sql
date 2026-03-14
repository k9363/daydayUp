-- =====================================================
-- 添加 days_offset 字段到 factor_define 表
-- 用于支持历史日期偏移因子配置
-- =====================================================

ALTER TABLE factor_define ADD COLUMN days_offset INT DEFAULT 0 COMMENT '日期偏移，0=当日, 1=昨日, 2=前日';

SELECT 'days_offset 字段添加完成!' AS result;
