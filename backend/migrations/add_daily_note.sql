-- 每日笔记表 - 存储大盘分析和明日操作
CREATE TABLE IF NOT EXISTS `daily_note` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `trade_date` VARCHAR(10) NOT NULL UNIQUE COMMENT '交易日期(YYYY-MM-DD)，唯一key',
  `market_analysis` TEXT COMMENT '大盘分析（富文本）',
  `next_action` TEXT COMMENT '明日操作（富文本）',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日笔记表';
