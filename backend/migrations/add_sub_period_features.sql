-- 添加小周期特点字段
ALTER TABLE cycle_sub_period ADD COLUMN features TEXT COMMENT '小周期特点' AFTER name;
