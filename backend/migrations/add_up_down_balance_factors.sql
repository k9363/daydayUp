-- =====================================================
-- 涨跌家数原子因子定义
-- 原子因子：上涨家数、下跌家数、总家数、前50上涨家数、前50下跌家数
-- 派生因子：通过表达式计算涨跌平衡
-- =====================================================

-- 1. 删除旧的因子（如果存在）- 只删除涨跌平衡相关的因子
DELETE FROM factor_define WHERE factor_code IN (
    'up_down_balance', 'up_down_balance_top50'
);

-- 2. 新增涨跌家数原子因子（Python硬编码计算）
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `field_name`, `index_code`, `expression`, `description`, `is_active`) VALUES
-- 原子因子1：全市场涨跌家数
('up_count', '上涨家数', 'market', 'python', 'up_down_count', NULL, NULL, NULL, '当日上涨的股票家数（排除平盘和停牌）', 1),
('down_count', '下跌家数', 'market', 'python', 'up_down_count', NULL, NULL, NULL, '当日下跌的股票家数（排除平盘和停牌）', 1),
('total_count', '总家数', 'market', 'python', 'up_down_count', NULL, NULL, NULL, '当日有成交的股票总家数', 1),

-- 原子因子2：成交额前50涨跌家数
('up_count_top50', '前50上涨家数', 'market', 'python', 'up_down_count_top50', NULL, NULL, NULL, '成交额前50股票中上涨的家数', 1),
('down_count_top50', '前50下跌家数', 'market', 'python', 'up_down_count_top50', NULL, NULL, NULL, '成交额前50股票中下跌的家数', 1);

-- 3. 新增派生因子（通过表达式计算）
REPLACE INTO `factor_define` (`factor_code`, `factor_name`, `factor_scope`, `source`, `calculation_method`, `field_name`, `index_code`, `expression`, `description`, `is_active`) VALUES
-- 派生因子1：涨跌平衡 = (上涨-下跌)/总家数
-- 全部上涨=1，全部下跌=-1，一半一半=0
('up_down_balance', '涨跌平衡', 'market', 'calculated', NULL, NULL, NULL, 
 '(up_count - down_count) / total_count', 
 '(上涨家数-下跌家数)/总家数，范围-1到1，值越大市场越强势', 1),

-- 派生因子2：前50涨跌平衡
('up_down_balance_top50', '前50涨跌平衡', 'market', 'calculated', NULL, NULL, NULL, 
 '(up_count_top50 - down_count_top50) / 50', 
 '(前50上涨-前50下跌)/50，范围-1到1，值越大越强势', 1);

SELECT '涨跌家数原子因子配置完成!' AS result;
