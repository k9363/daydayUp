-- 新增偏离值因子
-- 偏离值计算：
-- 收盘价涨跌幅偏离值 = (股票收盘价/期初前收盘价 - 1) * 100% - (指数收盘价/期初前收盘价 - 1) * 100%
-- 连续10个交易日偏离值累计达到+100%（-50%）触发正向（负向）异常
-- 连续30个交易日偏离值累计达到+200%（-70%）触发正向（负向）异常
-- 剩余偏离值 = 阈值 - 累计偏离值（正数为未达标，负数为已超标）

-- 先删除已存在的因子定义
DELETE FROM `factor_define` WHERE `factor_code` IN ('deviation_10d', 'deviation_30d', 'remaining_deviation');

INSERT INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `field_name`, `calculation_method`, `expression`, `description`, `is_active`) VALUES
('deviation_10d', '10日偏离值累计', 'stock', 'python', NULL, 'code', NULL, '最近10个交易日收盘价涨跌幅偏离上证指数累计值', 1),
('deviation_30d', '30日偏离值累计', 'stock', 'python', NULL, 'code', NULL, '最近30个交易日收盘价涨跌幅偏离上证指数累计值', 1),
('remaining_deviation', '剩余偏离值', 'stock', 'python', NULL, 'code', NULL, '距离触发阈值(10天±100%/±50%, 30天±200%/±70%)的最小剩余偏离值', 1);
