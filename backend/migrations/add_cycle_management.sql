-- ================================================
-- 周期管理表
-- 创建日期: 2026-03-04
-- ================================================

-- 创建 cycle 表（周期主表）
DROP TABLE IF EXISTS `cycle`;
CREATE TABLE `cycle` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `title` VARCHAR(100) NOT NULL COMMENT '周期标题',
    `features` TEXT COMMENT '周期特点',
    `start_date` VARCHAR(20) NOT NULL COMMENT '开始日期 YYYY-MM-DD',
    `end_date` VARCHAR(20) COMMENT '结束日期 YYYY-MM-DD',
    `status` VARCHAR(20) DEFAULT 'active' COMMENT '状态: active-进行中, completed-已结束',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY `idx_status` (`status`),
    KEY `idx_dates` (`start_date`, `end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='周期主表';

-- ================================================

-- 创建 cycle_sub_period 表（周期内的小周期）
DROP TABLE IF EXISTS `cycle_sub_period`;
CREATE TABLE `cycle_sub_period` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `cycle_id` BIGINT NOT NULL COMMENT '周期ID',
    `period_type` VARCHAR(20) NOT NULL COMMENT '小周期类型: chaos-混沌, rise-主升,震荡-oscillation, decline-退潮',
    `name` VARCHAR(50) NOT NULL COMMENT '小周期名称',
    `start_date` VARCHAR(20) NOT NULL COMMENT '开始日期 YYYY-MM-DD',
    `end_date` VARCHAR(20) COMMENT '结束日期 YYYY-MM-DD',
    `order_num` INT DEFAULT 0 COMMENT '排序号',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY `idx_cycle_id` (`cycle_id`),
    KEY `idx_dates` (`start_date`, `end_date`),
    CONSTRAINT `fk_cycle_sub_period` FOREIGN KEY (`cycle_id`) REFERENCES `cycle` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='周期内的小周期表';

-- ================================================

-- 创建 cycle_trade_day 表（交易日与小周期关联）
DROP TABLE IF EXISTS `cycle_trade_day`;
CREATE TABLE `cycle_trade_day` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `sub_period_id` BIGINT NOT NULL COMMENT '小周期ID',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期 YYYY-MM-DD',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY `uq_trade_date` (`trade_date`),
    KEY `idx_sub_period` (`sub_period_id`),
    CONSTRAINT `fk_trade_day_sub_period` FOREIGN KEY (`sub_period_id`) REFERENCES `cycle_sub_period` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日与小周期关联表';

-- ================================================

SELECT '周期管理表创建完成！' AS result;
