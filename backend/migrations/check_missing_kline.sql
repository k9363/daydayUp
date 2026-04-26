-- ============================================================
-- 完整统计最近20个交易日K线数据情况
-- ============================================================

-- 查询1: 先确认最近20个交易日有哪些日期
SELECT DISTINCT trade_date 
FROM stock_daily_kline 
ORDER BY trade_date DESC 
LIMIT 20;

-- ============================================================
-- 查询2: 按状态汇总（先运行这个看整体情况）
-- ============================================================
SELECT 
    CASE 
        WHEN data_days = 0 THEN '完全无数据'
        WHEN data_days < 20 THEN '部分缺失'
        ELSE '完整'
    end as data_status,
    COUNT(*) as stock_count
FROM (
    SELECT 
        b.stock_code,
        COALESCE((
            SELECT COUNT(DISTINCT k.trade_date) 
            FROM stock_daily_kline k 
            WHERE k.stock_code = b.stock_code 
            AND k.trade_date >= (
                SELECT MIN(trade_date) 
                FROM (
                    SELECT DISTINCT trade_date 
                    FROM stock_daily_kline 
                    ORDER BY trade_date DESC 
                    LIMIT 20
                ) t20
            )
        ), 0) as data_days
    FROM stock_basic b
    WHERE b.stock_type IN ('stock', 'etf', 'index')) t
GROUP BY 
    CASE 
        WHEN data_days = 0 THEN '完全无数据'
        WHEN data_days < 20 THEN '部分缺失'
        ELSE '完整'
    end
ORDER BY 
    CASE 
        WHEN data_days = 0 THEN 1
        WHEN data_days < 20 THEN 2
        ELSE 3
    end;

-- ============================================================
-- 查询3: 完全无数据的股票（最重要）
-- ============================================================
SELECT 
    b.stock_code,
    b.stock_name,
    b.exchange,
    b.market,
    b.stock_type
FROM stock_basic b
WHERE b.stock_type IN ('stock', 'etf', 'index')
AND NOT EXISTS (
    SELECT 1 
    FROM stock_daily_kline k
    WHERE k.stock_code = b.stock_code
    AND k.trade_date >= (
        SELECT MIN(trade_date) 
        FROM (
            SELECT DISTINCT trade_date 
            FROM stock_daily_kline 
            ORDER BY trade_date DESC 
            LIMIT 20
        ) t20
    )
)
ORDER BY b.exchange, b.stock_code;

-- ============================================================
-- 查询4: 部分缺失的股票（1-19天有数据）
-- ============================================================
SELECT 
    b.stock_code,
    b.stock_name,
    b.exchange,
    b.market,
    t.data_days as data_days,
    20 as total_days,
    ROUND(t.data_days / 20 * 100, 1) as data_percent
FROM stock_basic b
INNER JOIN (
    SELECT 
        stock_code,
        COUNT(DISTINCT trade_date) as data_days
    FROM stock_daily_kline
    WHERE trade_date >= (
        SELECT MIN(trade_date) 
        FROM (
            SELECT DISTINCT trade_date 
            FROM stock_daily_kline 
            ORDER BY trade_date DESC 
            LIMIT 20
        ) t20
    )
    GROUP BY stock_code
    HAVING COUNT(DISTINCT trade_date) BETWEEN 1 AND 19
) t ON b.stock_code = t.stock_code
WHERE b.stock_type IN ('stock', 'etf', 'index')ORDER BY t.data_days ASC, b.stock_code;

-- ============================================================
-- 查询5: 完整有数据的股票（20天全有）
-- ============================================================
SELECT 
    b.stock_code,
    b.stock_name,
    b.exchange,
    b.market
FROM stock_basic b
WHERE b.stock_type IN ('stock', 'etf', 'index')
EXISTS (
    SELECT 1 
    FROM stock_daily_kline k
    WHERE k.stock_code = b.stock_code
    AND k.trade_date >= (
        SELECT MIN(trade_date) 
        FROM (
            SELECT DISTINCT trade_date 
            FROM stock_daily_kline 
            ORDER BY trade_date DESC 
            LIMIT 20
        ) t20
    )
    GROUP BY k.stock_code
    HAVING COUNT(DISTINCT k.trade_date) = 20
)
ORDER BY b.exchange, b.stock_code
LIMIT 100;

-- ============================================================
-- 查询6: 完整统计（包含所有状态，按天数排序）
-- ============================================================
SELECT 
    b.stock_code,
    b.stock_name,
    b.exchange,
    b.market,
    b.stock_type,
    COALESCE(t.data_days, 0) as data_days,
    20 as total_days,
    CASE 
        WHEN COALESCE(t.data_days, 0) = 0 THEN '完全无数据'
        WHEN COALESCE(t.data_days, 0) < 20 THEN CONCAT('部分缺失(', COALESCE(t.data_days, 0), '/20)')
        ELSE '完整'
    end as data_status
FROM stock_basic b
LEFT JOIN (
    SELECT 
        stock_code,
        COUNT(DISTINCT trade_date) as data_days
    FROM stock_daily_kline
    WHERE trade_date >= (
        SELECT MIN(trade_date) 
        FROM (
            SELECT DISTINCT trade_date 
            FROM stock_daily_kline 
            ORDER BY trade_date DESC 
            LIMIT 20
        ) t20
    )
    GROUP BY stock_code
) t ON b.stock_code = t.stock_code
WHERE b.stock_type IN ('stock', 'etf', 'index')ORDER BY 
    CASE 
        WHEN COALESCE(t.data_days, 0) = 0 THEN 1
        WHEN COALESCE(t.data_days, 0) < 20 THEN 2
        ELSE 3
    end,
    COALESCE(t.data_days, 0) ASC,
    b.stock_code
LIMIT 200;
