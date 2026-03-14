-- =====================================================
-- 精简版因子定义 - 通过 kline_field + 参数形式生成
-- 格式说明:
--   kline_field: 直接取当日K线字段
--   kline_field_y1: 昨日数据 (y1=昨日, y2=前日, y3=前3日...)
--   avg_{field}_{n}d: 最近N天平均
--   avg_{field}_{n1}_{n2}d: 第N1到N2天平均
-- =====================================================

-- 清空旧因子配置
DELETE FROM factor_define WHERE factor_scope = 'stock';

-- =====================================================
-- 1. 基础K线字段因子 (当日)
-- =====================================================
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
-- 价格类
('close_price', '收盘价', 'stock', 'kline', 'close_price', 'kline_field', NULL, '当日收盘价', 1),
('open_price', '开盘价', 'stock', 'kline', 'open_price', 'kline_field', NULL, '当日开盘价', 1),
('high_price', '最高价', 'stock', 'kline', 'high_price', 'kline_field', NULL, '当日最高价', 1),
('low_price', '最低价', 'stock', 'kline', 'low_price', 'kline_field', NULL, '当日最低价', 1),
('pct_change', '涨跌幅', 'stock', 'kline', 'pct_change', 'kline_field', NULL, '当日涨跌幅(%)', 1),
('change', '涨跌额', 'stock', 'kline', 'change', 'kline_field', NULL, '当日涨跌额', 1),

-- 量价类
('volume', '成交量', 'stock', 'kline', 'volume', 'kline_field', NULL, '当日成交量(手)', 1),
('turnover', '成交额', 'stock', 'kline', 'turnover', 'kline_field', NULL, '当日成交额(元)', 1),

-- 预计算均线
('ma5', '5日均线', 'stock', 'kline', 'ma5', 'kline_field', NULL, '5日简单移动平均价', 1),
('ma10', '10日均线', 'stock', 'kline', 'ma10', 'kline_field', NULL, '10日简单移动平均价', 1),
('ma20', '20日均线', 'stock', 'kline', 'ma20', 'kline_field', NULL, '20日简单移动平均价', 1),
('ma30', '30日均线', 'stock', 'kline', 'ma30', 'kline_field', NULL, '30日简单移动平均价', 1),
('ma60', '60日均线', 'stock', 'kline', 'ma60', 'kline_field', NULL, '60日简单移动平均价', 1),

-- 成交额均线 (使用 days_range 配置)
('avg_turnover_3d', '近3日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '最近3个交易日平均成交额', 1),
('avg_turnover_5d', '近5日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '最近5个交易日平均成交额', 1),
('avg_turnover_10d', '近10日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '最近10个交易日平均成交额', 1),
('avg_turnover_20d', '近20日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '最近20个交易日平均成交额', 1),
('avg_turnover_4_20d', '4-20日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '第4到20个交易日的平均成交额', 1),
('avg_turnover_11_30d', '11-30日平均成交额', 'stock', 'kline', 'turnover', 'turnover_ma', NULL, '第11到30个交易日的平均成交额', 1);

-- 更新 days_range
UPDATE factor_define SET days_range = '1_3' WHERE factor_code = 'avg_turnover_3d';
UPDATE factor_define SET days_range = '1_5' WHERE factor_code = 'avg_turnover_5d';
UPDATE factor_define SET days_range = '1_10' WHERE factor_code = 'avg_turnover_10d';
UPDATE factor_define SET days_range = '1_20' WHERE factor_code = 'avg_turnover_20d';
UPDATE factor_define SET days_range = '4_20' WHERE factor_code = 'avg_turnover_4_20d';
UPDATE factor_define SET days_range = '11_30' WHERE factor_code = 'avg_turnover_11_30d';

-- =====================================================
-- 2. 历史偏移因子 (通过 days_offset 配置)
-- 格式: field_name_y{n}
-- =====================================================
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `days_offset`, `expression`, `description`, `is_active`) VALUES
-- 昨日数据 (offset=1)
('close_price_y1', '昨日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 1, NULL, '昨日收盘价', 1),
('volume_y1', '昨日成交量', 'stock', 'kline', 'volume', 'kline_field', 1, NULL, '昨日成交量', 1),
('turnover_y1', '昨日成交额', 'stock', 'kline', 'turnover', 'kline_field', 1, NULL, '昨日成交额', 1),
('pct_change_y1', '昨日涨跌幅', 'stock', 'kline', 'pct_change', 'kline_field', 1, NULL, '昨日涨跌幅', 1),

-- 前日数据 (offset=2)
('close_price_y2', '前日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 2, NULL, '前日收盘价', 1),
('volume_y2', '前日成交量', 'stock', 'kline', 'volume', 'kline_field', 2, NULL, '前日成交量', 1),

-- 前3日数据 (offset=3)
('close_price_y3', '前3日收盘价', 'stock', 'kline', 'close_price', 'kline_field', 3, NULL, '前3日收盘价', 1),
('volume_y3', '前3日成交量', 'stock', 'kline', 'volume', 'kline_field', 3, NULL, '前3日成交量', 1);

-- =====================================================
-- 3. 计算类因子 (Python/Expression)
-- =====================================================
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES

-- 均线差值
('price_ma5_diff', '股价与5日线差值', 'stock', 'calculated', NULL, 'expression', 'close_price - ma5', '收盘价与5日均线的差值', 1),
('price_ma10_diff', '股价与10日线差值', 'stock', 'calculated', NULL, 'expression', 'close_price - ma10', '收盘价与10日均线的差值', 1),
('price_ma20_diff', '股价与20日线差值', 'stock', 'calculated', NULL, 'expression', 'close_price - ma20', '收盘价与20日均线的差值', 1),

-- 昨日MA (Python计算)
('ma5_y1', '昨日5日均线', 'stock', 'python', NULL, 'python', NULL, '昨日的5日简单移动平均价', 1),
('ma10_y1', '昨日10日均线', 'stock', 'python', NULL, 'python', NULL, '昨日的10日简单移动平均价', 1),
('ma20_y1', '昨日20日均线', 'stock', 'python', NULL, 'python', NULL, '昨日的20日简单移动平均价', 1),

-- 成交额排名
('amount_rank', '成交额排名', 'stock', 'kline', 'turnover', 'rank', NULL, '当日成交额在股票池中的排名(从1开始)', 1);

-- =====================================================
-- 4. 得分因子 (最终评分用)
-- =====================================================
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES

-- factor1: 成交额排名得分
('factor1_rank', '成交额排名得分', 'stock', 'calculated', NULL, 'expression', 
'IF(amount_rank <= 10, 10, IF(amount_rank <= 20, 8, IF(amount_rank <= 30, 6, IF(amount_rank <= 50, 4, IF(amount_rank <= 100, 2, 0)))))', 
'成交额排名前10得10分，前20得8分，前30得6分，前50得4分，前100得2分', 1),

-- factor2: 短线趋势 (新逻辑)
('factor2_ma', '短线趋势', 'stock', 'python', NULL, 'python', NULL, 
'MA5>MA10>MA20:+2, Pt>MA5:+2, MA20向上:+2, 否则各-0.5', 1),

-- factor3: 昨日同比
('factor3_vol', '昨日同比', 'stock', 'calculated', NULL, 'expression', 
'IF(volume >= volume_y1, 3, -1)', 
'成交量大于等于昨日加3，否则减1', 1),

-- factor4: 爆量
('factor4_burst', '爆量', 'stock', 'calculated', NULL, 'expression', 
'IF(avg_turnover_3d >= avg_turnover_4_20d, 3, -1) + (avg_turnover_3d / avg_turnover_4_20d) * 2', 
'近3日平均成交额大于4-20日平均加3，否则减1', 1),

-- factor5: 极限量
('factor5_extreme', '极限量', 'stock', 'calculated', NULL, 'expression', 
'(avg_turnover_10d / avg_turnover_11_30d) * 3', 
'10日均值/11-30日均值*3', 1),

-- factor6: 多头趋势 (Python计算)
('factor6_trend', '多头趋势', 'stock', 'python', NULL, 'python', NULL, 
'15日每日MA5+0.2，MA10+0.1', 1);

-- =====================================================
-- 5. 偏离值因子
-- =====================================================
INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('deviation_10d', '10日偏离值累计', 'stock', 'python', NULL, 'python', NULL, '最近10个交易日收盘价涨跌幅偏离上证指数累计值', 1),
('deviation_30d', '30日偏离值累计', 'stock', 'python', NULL, 'python', NULL, '最近30个交易日收盘价涨跌幅偏离上证指数累计值', 1),
('remaining_deviation', '剩余偏离值', 'stock', 'python', NULL, 'python', NULL, '距离触发阈值的最小剩余偏离值', 1);

SELECT '股票因子配置完成!' AS result;
