-- =====================================================
-- 批量添加昨日因子配置
-- 包含: 昨日收盘价、成交量、成交额、涨跌幅、各周期均线
-- =====================================================

-- 昨日基础K线字段
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_offset`, `description`, `is_active`) VALUES
('close_price_y1', '昨日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 1, '昨日收盘价', 1),
('volume_y1', '昨日成交量', 'stock', 'kline', 'volume', 'kline_field', 1, '昨日成交量', 1),
('turnover_y1', '昨日成交额', 'stock', 'kline', 'turnover', 'kline_field', 1, '昨日成交额', 1),
('pct_change_y1', '昨日涨跌幅', 'stock', 'kline', 'pct_change', 'kline_field', 1, '昨日涨跌幅', 1),

-- 前日基础K线字段
('close_price_y2', '前日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 2, '前日收盘价', 1),
('volume_y2', '前日成交量', 'stock', 'kline', 'volume', 'kline_field', 2, '前日成交量', 1),

-- 前3日基础K线字段
('close_price_y3', '前3日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 3, '前3日收盘价', 1),
('volume_y3', '前3日成交量', 'stock', 'kline', 'volume', 'kline_field', 3, '前3日成交量', 1);

-- 昨日均线因子 (Python计算)
INSERT IGNORE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `description`, `is_active`) VALUES
('ma5_y1', '昨日5日均线', 'stock', 'python', 'python', '昨日的5日简单移动平均价', 1),
('ma10_y1', '昨日10日均线', 'stock', 'python', 'python', '昨日的10日简单移动平均价', 1),
('ma20_y1', '昨日20日均线', 'stock', 'python', 'python', '昨日的20日简单移动平均价', 1),
('ma30_y1', '昨日30日均线', 'stock', 'python', 'python', '昨日的30日简单移动平均价', 1);

SELECT '昨日因子配置完成!' AS result;
