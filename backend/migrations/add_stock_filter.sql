-- 添加 stock_filter 字段到 review_task 表
ALTER TABLE review_task ADD COLUMN stock_filter VARCHAR(500) COMMENT '股票筛选条件(JSON格式)' AFTER rules;
