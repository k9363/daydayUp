-- ============================================================================
-- DayDayUp 数据库初始化脚本（简化版）
-- ============================================================================
-- 创建时间: 2026-02-05
-- 描述: 简化的数据库结构，删除 DataSource 和 DataRecord 表
-- ============================================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS daydayup
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE daydayup;

-- ============================================================================
-- 1. 复盘任务表 (review_task) - 包含原 DataSource 的字段
-- ============================================================================
DROP TABLE IF EXISTS `review_task`;
CREATE TABLE IF NOT EXISTS `review_task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '任务ID',
    `task_name` VARCHAR(100) NOT NULL COMMENT '任务名称',
    `data_source_type` VARCHAR(20) DEFAULT 'baostock' COMMENT '数据源类型: excel, csv, database, api, stock, baostock',
    `data_source_name` VARCHAR(100) COMMENT '数据源名称',
    `data_source_desc` VARCHAR(500) COMMENT '数据源描述',
    `file_path` VARCHAR(500) COMMENT '文件路径',
    `stock_code` VARCHAR(20) COMMENT '股票代码',
    `trade_date` VARCHAR(10) COMMENT '交易日期(YYYY-MM-DD)',
    `row_count` INT DEFAULT 0 COMMENT '数据行数',
    `column_count` INT DEFAULT 0 COMMENT '列数',
    `data_summary` TEXT COMMENT '数据摘要',
    `review_type` VARCHAR(20) NOT NULL COMMENT '复盘类型: daily-日复盘, weekly-周复盘, monthly-月复盘, custom-自定义',
    `dimensions` TEXT COMMENT '分析维度(JSON数组)',
    `rules` TEXT COMMENT '复盘规则(JSON格式)',
    `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending-待执行, running-执行中, completed-已完成, failed-失败',
    `result_summary` TEXT COMMENT '执行结果摘要',
    `start_time` DATETIME COMMENT '开始时间',
    `end_time` DATETIME COMMENT '结束时间',
    `error_message` TEXT COMMENT '错误信息',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_trade_date` (`trade_date`),
    INDEX `idx_review_type` (`review_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='复盘任务表';

-- ============================================================================
-- 2. 复盘结果表 (review_result)
-- ============================================================================
DROP TABLE IF EXISTS `review_result`;
CREATE TABLE IF NOT EXISTS `review_result` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '结果ID',
    `task_id` BIGINT NOT NULL COMMENT '关联的复盘任务ID',
    `dimension` VARCHAR(100) COMMENT '分析维度',
    `metric_name` VARCHAR(100) NOT NULL COMMENT '指标名称',
    `metric_value` VARCHAR(100) COMMENT '指标值',
    `compare_value` VARCHAR(100) COMMENT '对比值',
    `change_rate` DOUBLE COMMENT '变化率',
    `status` VARCHAR(20) DEFAULT 'normal' COMMENT '状态: normal-正常, warning-警告, critical-严重',
    `suggestion` TEXT COMMENT '分析建议',
    `detail_data` TEXT COMMENT '详细数据(JSON格式)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_task_id` (`task_id`),
    INDEX `idx_status` (`status`),
    CONSTRAINT `fk_review_result_task` FOREIGN KEY (`task_id`) REFERENCES `review_task` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='复盘结果表';

-- ============================================================================
-- 3. 股票基本信息表 (stock_basic)
-- ============================================================================
DROP TABLE IF EXISTS `stock_basic`;
CREATE TABLE IF NOT EXISTS `stock_basic` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码，如 sh.600000',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `exchange` VARCHAR(10) COMMENT '交易所: sh-上海, sz-深圳',
    `market` VARCHAR(20) COMMENT '市场类型: 主板/中小板/创业板/科创板',
    `company_name` VARCHAR(200) COMMENT '公司全称',
    `industry` VARCHAR(50) COMMENT '所属行业',
    `area` VARCHAR(50) COMMENT '所在地区',
    `list_date` VARCHAR(10) COMMENT '上市日期 YYYY-MM-DD',
    `delist_date` VARCHAR(10) COMMENT '退市日期 YYYY-MM-DD',
    `is_hs` INT DEFAULT 0 COMMENT '是否沪深港通: 0-否, 1-是',
    `total_shares` NUMERIC(20, 2) COMMENT '总股本(万股)',
    `circulate_shares` NUMERIC(20, 2) COMMENT '流通股本(万股)',
    `remarks` VARCHAR(500) COMMENT '备注',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_exchange` (`exchange`),
    INDEX `idx_industry` (`industry`),
    INDEX `idx_list_date` (`list_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基本信息表';

-- ============================================================================
-- 4. 股票板块表 (stock_sector)
-- ============================================================================
DROP TABLE IF EXISTS `stock_sector`;
CREATE TABLE IF NOT EXISTS `stock_sector` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `sector_code` VARCHAR(50) NOT NULL COMMENT '板块代码',
    `sector_name` VARCHAR(100) NOT NULL COMMENT '板块名称',
    `sector_type` VARCHAR(20) NOT NULL COMMENT '板块类型: industry-行业, concept-概念, area-地区',
    `description` VARCHAR(500) COMMENT '板块描述',
    `stock_count` INT DEFAULT 0 COMMENT '包含股票数量',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_sector_code` (`sector_code`),
    INDEX `idx_sector_type` (`sector_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票板块表';

-- ============================================================================
-- 5. 股票-板块关联表 (stock_sector_relation)
-- ============================================================================
DROP TABLE IF EXISTS `stock_sector_relation`;
CREATE TABLE IF NOT EXISTS `stock_sector_relation` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `sector_id` BIGINT NOT NULL COMMENT '板块ID',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE INDEX `uq_stock_sector` (`stock_code`, `sector_id`),
    INDEX `idx_stock_code` (`stock_code`),
    CONSTRAINT `fk_relation_sector` FOREIGN KEY (`sector_id`) REFERENCES `stock_sector` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票-板块关联表';

-- ============================================================================
-- 6. 股票日线数据表 (stock_daily)
-- ============================================================================
DROP TABLE IF EXISTS `stock_daily`;
CREATE TABLE IF NOT EXISTS `stock_daily` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码，如 sh.600000',
    `stock_name` VARCHAR(50) COMMENT '股票名称',
    `trade_date` VARCHAR(10) NOT NULL COMMENT '交易日期 YYYY-MM-DD',
    `open_price` NUMERIC(15, 4) COMMENT '开盘价',
    `high_price` NUMERIC(15, 4) COMMENT '最高价',
    `low_price` NUMERIC(15, 4) COMMENT '最低价',
    `close_price` NUMERIC(15, 4) COMMENT '收盘价',
    `pre_close_price` NUMERIC(15, 4) COMMENT '昨收价',
    `volume` NUMERIC(20, 0) COMMENT '成交量(股)',
    `turnover` NUMERIC(20, 4) COMMENT '成交额(元)',
    `turnover_rate` NUMERIC(10, 4) COMMENT '换手率',
    `change` NUMERIC(10, 4) COMMENT '涨跌幅',
    `change_percent` NUMERIC(10, 4) COMMENT '涨跌额',
    `industry` VARCHAR(50) COMMENT '所属行业',
    `market` VARCHAR(20) COMMENT '市场类型:主板/中小板/创业板/科创板',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_trade_date` (`trade_date`),
    INDEX `idx_turnover` (`trade_date`, `turnover`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日线数据表';

-- ============================================================================
-- 7. 股票日K线数据表 (stock_daily_kline)
-- ============================================================================
DROP TABLE IF EXISTS `stock_daily_kline`;
CREATE TABLE IF NOT EXISTS `stock_daily_kline` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) COMMENT '股票名称',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期时间',
    `open_price` NUMERIC(15, 4) COMMENT '开盘价',
    `high_price` NUMERIC(15, 4) COMMENT '最高价',
    `low_price` NUMERIC(15, 4) COMMENT '最低价',
    `close_price` NUMERIC(15, 4) COMMENT '收盘价',
    `pre_close_price` NUMERIC(15, 4) COMMENT '昨收价',
    `volume` NUMERIC(20, 0) COMMENT '成交量',
    `turnover` NUMERIC(20, 4) COMMENT '成交额',
    `change` NUMERIC(10, 4) COMMENT '涨跌额',
    `change_percent` NUMERIC(10, 4) COMMENT '涨跌幅',
    `turnover_rate` NUMERIC(10, 4) COMMENT '换手率',
    `peTTM` NUMERIC(15, 4) COMMENT '市盈率TTM',
    `psTTM` NUMERIC(15, 4) COMMENT '市销率TTM',
    `industry` VARCHAR(50) COMMENT '所属行业',
    `market` VARCHAR(20) COMMENT '市场类型',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_daily_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_daily_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='日K线数据表';

-- ============================================================================
-- 8. 股票周K线数据表 (stock_weekly_kline)
-- ============================================================================
DROP TABLE IF EXISTS `stock_weekly_kline`;
CREATE TABLE IF NOT EXISTS `stock_weekly_kline` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) COMMENT '股票名称',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期时间',
    `open_price` NUMERIC(15, 4) COMMENT '开盘价',
    `high_price` NUMERIC(15, 4) COMMENT '最高价',
    `low_price` NUMERIC(15, 4) COMMENT '最低价',
    `close_price` NUMERIC(15, 4) COMMENT '收盘价',
    `pre_close_price` NUMERIC(15, 4) COMMENT '昨收价',
    `volume` NUMERIC(20, 0) COMMENT '成交量',
    `turnover` NUMERIC(20, 4) COMMENT '成交额',
    `change` NUMERIC(10, 4) COMMENT '涨跌额',
    `change_percent` NUMERIC(10, 4) COMMENT '涨跌幅',
    `week_open` NUMERIC(15, 4) COMMENT '周开盘价',
    `week_close` NUMERIC(15, 4) COMMENT '周收盘价',
    `week_high` NUMERIC(15, 4) COMMENT '周最高价',
    `week_low` NUMERIC(15, 4) COMMENT '周最低价',
    `avg_price` NUMERIC(15, 4) COMMENT '周均价',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_weekly_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_weekly_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='周K线数据表';

-- ============================================================================
-- 9. 股票月K线数据表 (stock_monthly_kline)
-- ============================================================================
DROP TABLE IF EXISTS `stock_monthly_kline`;
CREATE TABLE IF NOT EXISTS `stock_monthly_kline` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) COMMENT '股票名称',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期时间',
    `open_price` NUMERIC(15, 4) COMMENT '开盘价',
    `high_price` NUMERIC(15, 4) COMMENT '最高价',
    `low_price` NUMERIC(15, 4) COMMENT '最低价',
    `close_price` NUMERIC(15, 4) COMMENT '收盘价',
    `pre_close_price` NUMERIC(15, 4) COMMENT '昨收价',
    `volume` NUMERIC(20, 0) COMMENT '成交量',
    `turnover` NUMERIC(20, 4) COMMENT '成交额',
    `change` NUMERIC(10, 4) COMMENT '涨跌额',
    `change_percent` NUMERIC(10, 4) COMMENT '涨跌幅',
    `month_open` NUMERIC(15, 4) COMMENT '月开盘价',
    `month_close` NUMERIC(15, 4) COMMENT '月收盘价',
    `month_high` NUMERIC(15, 4) COMMENT '月最高价',
    `month_low` NUMERIC(15, 4) COMMENT '月最低价',
    `avg_price` NUMERIC(15, 4) COMMENT '月均价',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_monthly_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_monthly_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='月K线数据表';

-- ============================================================================
-- 10. 股票分钟K线数据表 (stock_minute_kline)
-- ============================================================================
DROP TABLE IF EXISTS `stock_minute_kline`;
CREATE TABLE IF NOT EXISTS `stock_minute_kline` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) COMMENT '股票名称',
    `trade_date` VARCHAR(20) NOT NULL COMMENT '交易日期时间',
    `open_price` NUMERIC(15, 4) COMMENT '开盘价',
    `high_price` NUMERIC(15, 4) COMMENT '最高价',
    `low_price` NUMERIC(15, 4) COMMENT '最低价',
    `close_price` NUMERIC(15, 4) COMMENT '收盘价',
    `pre_close_price` NUMERIC(15, 4) COMMENT '昨收价',
    `volume` NUMERIC(20, 0) COMMENT '成交量',
    `turnover` NUMERIC(20, 4) COMMENT '成交额',
    `change` NUMERIC(10, 4) COMMENT '涨跌额',
    `change_percent` NUMERIC(10, 4) COMMENT '涨跌幅',
    `frequency` VARCHAR(10) NOT NULL COMMENT '频率: 5, 15, 30, 60 (分钟)',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_minute_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_minute_freq_date` (`frequency`, `trade_date`),
    INDEX `idx_minute_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分钟K线数据表';

-- ============================================================================
-- 11. 数据同步任务表 (data_sync_task)
-- ============================================================================
DROP TABLE IF EXISTS `data_sync_task`;
CREATE TABLE IF NOT EXISTS `data_sync_task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '任务ID',
    `task_name` VARCHAR(100) NOT NULL COMMENT '任务名称',
    `start_date` VARCHAR(10) NOT NULL COMMENT '开始日期',
    `end_date` VARCHAR(10) NOT NULL COMMENT '结束日期',
    `frequency` VARCHAR(20) NOT NULL COMMENT 'K线频率: daily, weekly, monthly, 5, 15, 30, 60',
    `stock_type` VARCHAR(20) DEFAULT 'all' COMMENT '股票类型: all-全部, sh-上海, sz-深圳',
    `status` VARCHAR(20) DEFAULT 'pending' COMMENT '任务状态: pending, running, completed, failed',
    `total_stocks` INT DEFAULT 0 COMMENT '总股票数',
    `processed_stocks` INT DEFAULT 0 COMMENT '已处理股票数',
    `total_records` INT DEFAULT 0 COMMENT '总记录数',
    `saved_records` INT DEFAULT 0 COMMENT '已保存记录数',
    `error_message` TEXT COMMENT '错误信息',
    `start_time` DATETIME COMMENT '开始时间',
    `end_time` DATETIME COMMENT '结束时间',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_sync_status` (`status`),
    INDEX `idx_sync_dates` (`start_date`, `end_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据同步任务表';

-- ============================================================================
-- 12. 股票交割单表 (stock_delivery)
-- ============================================================================
DROP TABLE IF EXISTS `stock_delivery`;
CREATE TABLE `stock_delivery` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `trade_date` VARCHAR(10) NOT NULL COMMENT '成交日期 YYYYMMDD',
    `trade_time` VARCHAR(8) COMMENT '成交时间 HH:MM:SS',
    `security_code` VARCHAR(20) NOT NULL COMMENT '证券代码',
    `security_name` VARCHAR(50) COMMENT '证券名称',
    `operation` VARCHAR(20) COMMENT '操作: 买入/卖出/配股等',
    `quantity` INT COMMENT '成交数量',
    `deal_no` VARCHAR(50) COMMENT '成交编号',
    `price` DECIMAL(16,3) COMMENT '成交价格',
    `amount` DECIMAL(16,2) COMMENT '成交金额',
    `balance` DECIMAL(16,2) COMMENT '余额',
    `stock_balance` INT COMMENT '股票余额',
    `occur_amount` DECIMAL(16,2) COMMENT '发生金额',
    `commission` DECIMAL(16,3) COMMENT '佣金',
    `stamp_duty` DECIMAL(16,3) COMMENT '印花税',
    `other_fee` DECIMAL(16,3) COMMENT '其他杂费',
    `transfer_fee` DECIMAL(16,3) COMMENT '过户费',
    `other_expense` DECIMAL(16,3) COMMENT '其他费',
    `fund_balance` DECIMAL(16,2) COMMENT '资金余额',
    `current_amount` DECIMAL(16,2) COMMENT '本次金额',
    `contract_no` VARCHAR(20) COMMENT '合同编号',
    `market` VARCHAR(20) COMMENT '交易市场',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_deal_no` (`deal_no`),
    INDEX `idx_trade_date` (`trade_date`),
    INDEX `idx_security_code` (`security_code`),
    INDEX `idx_operation` (`operation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票交割单表';

-- ============================================================================
-- 初始化完成
-- ============================================================================
SELECT '========================================' AS '';
SELECT '  DayDayUp 数据库初始化完成!' AS '';
SELECT '========================================' AS '';
SELECT CONCAT('  表数量: ', COUNT(*)) AS '表统计' FROM information_schema.tables WHERE table_schema = 'daydayup';
SELECT '  简化设计: 删除了 data_source 和 data_record 表' AS '';
SELECT '  数据源信息已合并到 review_task 表' AS '';
