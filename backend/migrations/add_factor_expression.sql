-- =====================================================
-- 因子表达式系统数据库表结构
-- =====================================================

-- -----------------------------------------------------
-- Table: factor_define
-- 因子定义表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `factor_define` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `factor_code` VARCHAR(50) NOT NULL COMMENT '因子代码',
  `factor_name` VARCHAR(100) NOT NULL COMMENT '因子名称',
  `factor_scope` VARCHAR(20) NOT NULL DEFAULT 'stock' COMMENT '因子作用域: stock-股票因子, sector-板块因子, market-大盘因子',
  `source` VARCHAR(50) NULL COMMENT '数据来源: kline-原始K线数据, stock_factor-股票因子得分, sector_factor-板块因子得分, calculated-表达式计算',
  `field_name` VARCHAR(50) NULL COMMENT '字段名',
  `aggregation` VARCHAR(20) NULL COMMENT '聚合方式: SUM/AVG/MAX/MIN/COUNT',
  `index_code` VARCHAR(20) NULL COMMENT '指数代码(大盘因子使用): 如 sh.000001, sz.399001',
  `expression` TEXT NULL COMMENT '表达式(calculated类型使用)',
  `description` VARCHAR(500) NULL COMMENT '描述',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_factor_code` (`factor_code` ASC),
  INDEX `idx_factor_scope` (`factor_scope` ASC),
  INDEX `idx_is_active` (`is_active` ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子定义表';


-- -----------------------------------------------------
-- Table: score_expression
-- 表达式配置表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `score_expression` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `expression_name` VARCHAR(100) NOT NULL COMMENT '表达式名称',
  `scope` VARCHAR(20) NOT NULL DEFAULT 'stock' COMMENT '作用域: stock-股票, sector-板块, market-大盘',
  `factors` JSON NULL COMMENT '使用因子列表(JSON数组)',
  `expression` TEXT NOT NULL COMMENT '计算表达式',
  `top_n` INT NULL COMMENT '取前N(板块/大盘专用)',
  `description` VARCHAR(500) NULL COMMENT '描述',
  `is_default` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为默认表达式',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_scope` (`scope` ASC),
  INDEX `idx_is_default` (`is_default` ASC),
  INDEX `idx_is_active` (`is_active` ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='表达式配置表';


-- =====================================================
-- 初始化默认因子数据 (可选)
-- =====================================================

-- 股票因子示例
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `description`) VALUES
('close_price', '收盘价', 'stock', 'kline', 'close_price', '当日收盘价'),
('volume', '成交量', 'stock', 'kline', 'volume', '当日成交量'),
('turnover', '成交额', 'stock', 'kline', 'turnover', '当日成交额'),
('pct_change', '涨跌幅', 'stock', 'kline', 'pct_change', '当日涨跌幅'),
('factor2_ma', '均线得分', 'stock', 'calculated', NULL, '均线多头得分'),
('factor3_vol', '成交量得分', 'stock', 'calculated', NULL, '成交量对比得分'),
('factor4_burst', '爆量得分', 'stock', 'calculated', NULL, '近3日爆量得分'),
('factor5_extreme', '极限量得分', 'stock', 'calculated', NULL, '近10日极限量得分'),
('factor6_trend', '多头趋势得分', 'stock', 'calculated', NULL, '多头趋势得分'),
('total_score', '股票总得分', 'stock', 'calculated', NULL, '股票综合得分');

-- 板块因子示例
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `aggregation`, `description`) VALUES
('sum_stock_score', '股票得分总和', 'sector', 'stock_factor', 'total_score', 'SUM', '板块内股票得分之和'),
('avg_stock_score', '股票平均得分', 'sector', 'stock_factor', 'total_score', 'AVG', '板块内股票得分平均值'),
('stock_count', '股票数量', 'sector', 'stock_factor', 'stock_code', 'COUNT', '板块内股票数量'),
('total_volume', '总成交量', 'sector', 'kline', 'volume', 'SUM', '板块内股票成交量之和'),
('avg_change_pct', '平均涨跌幅', 'sector', 'kline', 'pct_change', 'AVG', '板块内股票涨跌幅平均值');

-- 大盘因子示例
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `index_code`, `description`) VALUES
('sh_index_close', '上证指数收盘价', 'market', 'kline', 'close_price', 'sh.000001', '上证指数当日收盘价'),
('sh_index_change', '上证指数涨跌幅', 'market', 'kline', 'pct_change', 'sh.000001', '上证指数当日涨跌幅'),
('sz_index_close', '深证成指收盘价', 'market', 'kline', 'close_price', 'sz.399001', '深证成指当日收盘价'),
('sz_index_change', '深证成指涨跌幅', 'market', 'kline', 'pct_change', 'sz.399001', '深证成指当日涨跌幅'),
('cy_index_close', '创业板指收盘价', 'market', 'kline', 'close_price', 'sz.399006', '创业板指当日收盘价'),
('cy_index_change', '创业板指涨跌幅', 'market', 'kline', 'pct_change', 'sz.399006', '创业板指当日涨跌幅');

-- 表达式配置示例
INSERT INTO `score_expression` (`expression_name`, `scope`, `factors`, `expression`, `top_n`, `is_default`, `description`) VALUES
('股票综合得分', 'stock', '["factor2_ma", "factor3_vol", "factor4_burst", "factor5_extreme", "factor6_trend"]', 'factor2_ma + factor3_vol + factor4_burst + factor5_extreme + factor6_trend', NULL, 1, '股票综合得分表达式'),
('板块综合得分', 'sector', '["sum_stock_score", "stock_count", "avg_change_pct"]', 'sum_stock_score + stock_count * 5 + avg_change_pct * 10', 30, 1, '板块综合得分表达式，取前30'),
('市场强度得分', 'market', '["sh_index_change", "sz_index_change", "cy_index_change"]', '(sh_index_change + sz_index_change + cy_index_change) / 3', NULL, 1, '市场强度得分（三大指数平均涨跌幅）');


-- =====================================================
-- 如果使用 Flask-Migrate，执行以下命令创建表:
-- =====================================================
-- flask db init
-- flask db migrate -m "add factor and expression tables"
-- flask db upgrade
