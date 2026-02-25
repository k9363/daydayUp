-- ================================================
-- 数据库初始化脚本（精简版 + K线数据表）
-- 创建日期: 2026-02-10
-- ================================================

-- 创建 stock_basic 表（股票基本信息）
DROP TABLE IF EXISTS `stock_basic`;
CREATE TABLE `stock_basic` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL UNIQUE COMMENT '股票代码，如 sh.600000',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `exchange` VARCHAR(10) COMMENT '交易所: sh-上海, sz-深圳',
    `market` VARCHAR(20) COMMENT '市场类型: stock_sh/指数_sz/ETF等 (格式: type_market)',
    `stock_type` VARCHAR(20) COMMENT '证券类型: stock-股票, index-指数, other-其它, bond-可转债, etf-ETF',
    `company_name` VARCHAR(200) COMMENT '公司全称',
    `industry` VARCHAR(50) COMMENT '所属行业',
    `area` VARCHAR(50) COMMENT '所在地区',
    `list_date` VARCHAR(10) COMMENT '上市日期 YYYY-MM-DD',
    `delist_date` VARCHAR(10) COMMENT '退市日期 YYYY-MM-DD',
    `is_hs` INT DEFAULT 0 COMMENT '是否沪深港通: 0-否, 1-是',
    `total_shares` DECIMAL(20,2) COMMENT '总股本(万股)',
    `circulate_shares` DECIMAL(20,2) COMMENT '流通股本(万股)',
    `remarks` VARCHAR(500) COMMENT '备注',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uq_stock_code` (`stock_code`),
    KEY `idx_market` (`market`),
    KEY `idx_stock_type` (`stock_type`),
    KEY `idx_exchange` (`exchange`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基本信息表';

-- ================================================

-- 创建 stock_sector 表（板块元数据）
DROP TABLE IF EXISTS `stock_sector`;
CREATE TABLE `stock_sector` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `sector_code` VARCHAR(20) NOT NULL UNIQUE COMMENT '板块代码',
    `sector_name` VARCHAR(100) NOT NULL COMMENT '板块名称',
    `sector_type` VARCHAR(20) NOT NULL COMMENT '板块类型: industry-行业, concept-概念, area-地区',
    `description` VARCHAR(500) COMMENT '板块描述',
    `stock_count` INT DEFAULT 0 COMMENT '包含股票数量',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY `idx_sector_type` (`sector_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='板块元数据表';

-- ================================================

-- 创建 stock_sector_relation 表（股票-板块关联）
DROP TABLE IF EXISTS `stock_sector_relation`;
CREATE TABLE `stock_sector_relation` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `sector_id` BIGINT NOT NULL COMMENT '板块ID',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_stock_code` (`stock_code`),
    KEY `idx_sector_id` (`sector_id`),
    CONSTRAINT `uq_stock_sector` UNIQUE (`stock_code`, `sector_id`),
    CONSTRAINT `fk_sector_id` FOREIGN KEY (`sector_id`) REFERENCES `stock_sector` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票-板块关联关系表';

-- ================================================

-- 创建 metadata_progress 表（元数据获取进度-断点续传）
DROP TABLE IF EXISTS `metadata_progress`;
CREATE TABLE `metadata_progress` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型: industry_sector-行业板块, concept_sector-概念板块',
    `target_name` VARCHAR(100) COMMENT '目标名称: 行业名称/概念名称',
    `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending-待处理, processing-处理中, completed-已完成, failed-失败',
    `retry_count` INT DEFAULT 0 COMMENT '重试次数',
    `max_retries` INT DEFAULT 3 COMMENT '最大重试次数',
    `error_message` VARCHAR(500) COMMENT '错误信息',
    `started_at` DATETIME COMMENT '开始时间',
    `completed_at` DATETIME COMMENT '完成时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY `idx_task_type_status` (`task_type`, `status`),
    CONSTRAINT `uq_task_target` UNIQUE (`task_type`, `target_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='元数据获取进度表';

-- ================================================

-- 创建 task_execution_log 表（任务执行日志）
DROP TABLE IF EXISTS `task_execution_log`;
CREATE TABLE `task_execution_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `task_name` VARCHAR(100) NOT NULL COMMENT '任务名称',
    `task_type` VARCHAR(50) COMMENT '任务类型',
    `status` VARCHAR(20) COMMENT '执行状态: started-开始, completed-完成, failed-失败',
    `start_time` DATETIME COMMENT '开始时间',
    `end_time` DATETIME COMMENT '结束时间',
    `duration` INT COMMENT '执行时长(秒)',
    `message` TEXT COMMENT '执行消息',
    `error_info` TEXT COMMENT '错误信息',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_task_name` (`task_name`),
    KEY `idx_task_type` (`task_type`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务执行日志表';

-- ================================================

-- 创建 stock_kline_daily 表（股票日K线）
DROP TABLE IF EXISTS `stock_kline_daily`;
CREATE TABLE `stock_kline_daily` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期',
    `ts_code` VARCHAR(20) COMMENT 'TS代码',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `pre_close` DECIMAL(15,4) COMMENT '昨收价',
    `change` DECIMAL(15,4) COMMENT '涨跌额',
    `pct_chg` DECIMAL(10,4) COMMENT '涨跌幅',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `turn` DECIMAL(10,4) COMMENT '换手率',
    `tradestatus` INT COMMENT '交易状态: 1-正常, 0-停牌',
    `pct_amount` DECIMAL(15,4) COMMENT '成交额涨跌幅',
    `isST` INT COMMENT '是否ST: 1-是, 0-否',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_daily_stock` (`stock_code`),
    KEY `idx_daily_date` (`trade_date`),
    CONSTRAINT `uq_daily_kline` UNIQUE (`stock_code`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票日K线数据表';

-- ================================================

-- 创建 stock_kline_5min 表（股票5分钟K线）
DROP TABLE IF EXISTS `stock_kline_5min`;
CREATE TABLE `stock_kline_5min` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `trade_time` VARCHAR(20) NOT NULL COMMENT '交易时间',
    `ts_code` VARCHAR(20) COMMENT 'TS代码',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_5min_stock` (`stock_code`),
    KEY `idx_5min_time` (`trade_time`),
    CONSTRAINT `uq_5min_kline` UNIQUE (`stock_code`, `trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票5分钟K线数据表';

-- ================================================

-- 创建 stock_kline_15min 表（股票15分钟K线）
DROP TABLE IF EXISTS `stock_kline_15min`;
CREATE TABLE `stock_kline_15min` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `trade_time` VARCHAR(20) NOT NULL COMMENT '交易时间',
    `ts_code` VARCHAR(20) COMMENT 'TS代码',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_15min_stock` (`stock_code`),
    KEY `idx_15min_time` (`trade_time`),
    CONSTRAINT `uq_15min_kline` UNIQUE (`stock_code`, `trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票15分钟K线数据表';

-- ================================================

-- 创建 stock_kline_30min 表（股票30分钟K线）
DROP TABLE IF EXISTS `stock_kline_30min`;
CREATE TABLE `stock_kline_30min` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `trade_time` VARCHAR(20) NOT NULL COMMENT '交易时间',
    `ts_code` VARCHAR(20) COMMENT 'TS代码',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_30min_stock` (`stock_code`),
    KEY `idx_30min_time` (`trade_time`),
    CONSTRAINT `uq_30min_kline` UNIQUE (`stock_code`, `trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票30分钟K线数据表';

-- ================================================

-- 创建 stock_kline_60min 表（股票60分钟K线）
DROP TABLE IF EXISTS `stock_kline_60min`;
CREATE TABLE `stock_kline_60min` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `trade_time` VARCHAR(20) NOT NULL COMMENT '交易时间',
    `ts_code` VARCHAR(20) COMMENT 'TS代码',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_60min_stock` (`stock_code`),
    KEY `idx_60min_time` (`trade_time`),
    CONSTRAINT `uq_60min_kline` UNIQUE (`stock_code`, `trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票60分钟K线数据表';

-- ================================================

-- 创建 index_kline_daily 表（指数日K线）
DROP TABLE IF EXISTS `index_kline_daily`;
CREATE TABLE `index_kline_daily` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `index_code` VARCHAR(20) NOT NULL COMMENT '指数代码',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期',
    `open` DECIMAL(15,4) COMMENT '开盘价',
    `high` DECIMAL(15,4) COMMENT '最高价',
    `low` DECIMAL(15,4) COMMENT '最低价',
    `close` DECIMAL(15,4) COMMENT '收盘价',
    `pre_close` DECIMAL(15,4) COMMENT '昨收价',
    `change` DECIMAL(15,4) COMMENT '涨跌额',
    `pct_chg` DECIMAL(10,4) COMMENT '涨跌幅',
    `vol` DECIMAL(20,4) COMMENT '成交量(手)',
    `amount` DECIMAL(20,4) COMMENT '成交额(千元)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY `idx_index_daily_code` (`index_code`),
    KEY `idx_index_daily_date` (`trade_date`),
    CONSTRAINT `uq_index_daily_kline` UNIQUE (`index_code`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数日K线数据表';

-- ================================================

-- 初始化完成提示
SELECT '数据库初始化完成！' AS result;
