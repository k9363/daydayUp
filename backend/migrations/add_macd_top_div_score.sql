-- 新增大盘因子：MACD 日线顶背离得分
-- 因子逻辑：
--   取近 60 交易日上证指数（sh.000001）收盘价，计算 MACD（DIF = EMA12-EMA26）
--   找最近两个价格波峰，如果峰2价格 > 峰1价格 且 峰2 DIF < 峰1 DIF，则确认顶背离
--   得分 = min(10, 价格涨幅% × DIF回落幅度% / 10)，无顶背离时为 0

INSERT INTO factor_define (
    factor_code, factor_name, factor_scope, source,
    calculation_method, days_range, index_code,
    description, is_active, created_at, updated_at
)
VALUES (
    'macd_top_div_score',
    'MACD顶背离得分',
    'market',
    'python',
    'macd_top_div_score',
    '60',
    'sh.000001',
    'MACD日线顶背离强度得分（0~10）。近60日出现价格新高但DIF未新高时触发，得分越高背离越强，可作为大盘看空信号纳入市场评分表达式（建议负向加权）',
    TRUE,
    NOW(),
    NOW()
)
ON DUPLICATE KEY UPDATE
    factor_name        = VALUES(factor_name),
    calculation_method = VALUES(calculation_method),
    days_range         = VALUES(days_range),
    index_code         = VALUES(index_code),
    description        = VALUES(description),
    updated_at         = NOW();
