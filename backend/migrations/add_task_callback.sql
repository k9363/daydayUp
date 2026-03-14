-- 添加任务依赖相关字段
-- 为 ReviewTask 添加等待数据同步和关联同步任务ID字段
-- 为 DataSyncTask 添加回调类型和回调参数字段

-- 1. 为 ReviewTask 添加字段
ALTER TABLE review_task ADD COLUMN waiting_for_sync BOOLEAN DEFAULT 0 COMMENT '是否等待数据同步任务完成';
ALTER TABLE review_task ADD COLUMN sync_task_id BIGINT COMMENT '关联的数据同步任务ID';

-- 2. 为 DataSyncTask 添加回调字段
ALTER TABLE data_sync_task ADD COLUMN callback_type VARCHAR(50) COMMENT '回调类型: review_task';
ALTER TABLE data_sync_task ADD COLUMN callback_params TEXT COMMENT '回调参数(JSON格式)';

-- 3. 更新 status 字段的注释（如果需要支持新状态）
-- 状态: pending-待执行, running-执行中, completed-已完成, failed-失败, waiting_for_sync-等待数据同步
