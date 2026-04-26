/**
 * 复盘数据处理 composable
 * 处理图表数据、因子数据等复杂计算逻辑
 */
import { computed } from 'vue'

export function useReviewData(chartData) {

  // 判断是否为对象格式
  const isObjectFormat = computed(() => {
    return chartData.value && typeof chartData.value === 'object' && !Array.isArray(chartData.value)
  })

  // 指数数据
  const indexData = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.indexData || []
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return []
    const indexResult = chartData.value.find(r => r.dimension === '指数行情')
    if (!indexResult?.detail_data?.indexes) return []
    return indexResult.detail_data.indexes || []
  })

  // Top 100 股票数据
  const top100Stocks = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.top100Detail || []
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return []
    const topResult = chartData.value.find(r => r.dimension === '成交额排名')
    if (!topResult?.detail_data?.stocks) return []
    return topResult.detail_data.stocks || []
  })

  // Top 10 因子得分股票
  const top10FactorStocks = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.top10FactorStocks || []
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return []
    const factorResult = chartData.value.find(r => r.dimension === '因子分析')
    if (!factorResult?.detail_data?.stocks) return []
    return factorResult.detail_data.stocks || []
  })

  // 板块得分数据
  const sectorScores = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.sectors || []
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return []
    const sectorResult = chartData.value.find(r => r.dimension === '板块得分')
    if (!sectorResult?.detail_data?.sectors) return []
    return sectorResult.detail_data.sectors || []
  })

  // 因子树数据
  const factorTree = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.factorTree || null
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return null
    const factorTreeResult = chartData.value.find(r => r.dimension === '因子体系')
    if (!factorTreeResult?.detail_data) return null
    return factorTreeResult.detail_data
  })

  // 大盘指数计算结果 - 直接使用 marketDetail
  const marketAnalysis = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.marketDetail || null
    }
    // 兼容数组格式
    if (!chartData.value || !Array.isArray(chartData.value)) return null
    const marketResult = chartData.value.find(r => r.dimension === '市场')
    if (!marketResult?.detail_data) return null
    return marketResult.detail_data
  })

  // 大盘指数数据（用于展示）—— factors 的 value 为 { factor_name, value, ... } 对象
  const marketData = computed(() => {
    const market = marketAnalysis.value
    if (!market || !market.factors) return {}

    const result = { ...market.factors }
    delete result.type
    return result
  })

  /** 大盘综合得分：后端用 factor code market_score，不是中文键名 */
  const marketCompositeScore = computed(() => {
    const market = marketAnalysis.value
    if (!market?.factors) return 0
    const raw =
      market.factors.market_score ??
      market.factors['大盘综合得分']
    if (raw == null) return 0
    if (typeof raw === 'object' && raw !== null && 'value' in raw) {
      const v = raw.value
      return v == null || v === '' ? 0 : Number(v) || 0
    }
    return Number(raw) || 0
  })

  const ONE_YI = 100000000

  /** 大盘成交额类因子：后端 value 为元，展示需除一亿（code 可能为英文或中文）
   *  注意：top20_avg_price 是百分比（%），turnover_growth 是增速（倍数），都包含 turnover 但不是金额，需排除 */
  const isMarketTurnoverLike = (code, factorName) => {
    const c = String(code)
    // 排除已知非金额因子：top20_avg_price(百分比)、turnover_growth(增速)
    if (c === 'top20_avg_price' || c === 'turnover_growth') return false
    if (/turnover|amount/i.test(c)) return true
    if (/成交额/.test(c)) return true
    if (factorName && /成交额/.test(String(factorName))) return true
    return false
  }

  // 关键因子列表（用于展示）：显示 factor_name，排除综合得分根节点
  const marketKeyFactors = computed(() => {
    const market = marketAnalysis.value
    if (!market || !market.factors) return []

    const excludeKeys = ['market_score', '大盘综合得分', 'type', 'indexPrices', 'factors']
    return Object.entries(market.factors)
      .filter(([key]) => !excludeKeys.includes(key))
      .map(([code, raw]) => {
        let value =
          typeof raw === 'object' && raw !== null && 'value' in raw
            ? Number(raw.value) || 0
            : Number(raw) || 0
        const name =
          typeof raw === 'object' && raw?.factor_name
            ? raw.factor_name
            : code
        const isTurnover = isMarketTurnoverLike(code, name)
        if (isTurnover) {
          value = value / ONE_YI
        }
        return {
          code,
          name,
          value,
          /** 成交额类展示单位 */
          unit: isTurnover ? '亿元' : ''
        }
      })
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 6)
  })

  // 指数行情详情
  const marketIndexPrices = computed(() => {
    const market = marketAnalysis.value
    if (!market || !market.indexPrices) return {}

    return market.indexPrices
  })

  // 交易日期
  const tradeDate = computed(() => {
    if (isObjectFormat.value) {
      return chartData.value.summary?.tradeDate || ''
    }
    // 兼容数组格式
    if (!chartData.value?.length) return ''
    const firstTask = chartData.value[0]
    if (!firstTask?.task?.trade_date) return ''
    return firstTask.task.trade_date
  })

  // 统计汇总
  const summary = computed(() => {
    const top100 = top100Stocks.value
    const top10 = top10FactorStocks.value
    const sectors = sectorScores.value

    const totalTurnover = top100.reduce((sum, s) => sum + (s.amount || s.turnover || 0), 0)
    const avgTurnover = top100.length > 0 ? totalTurnover / top100.length : 0
    const positiveCount = top10.filter(s => (s.changePercent || 0) > 0).length
    const marketTrend = positiveCount > top10.length / 2 ? '偏强' : '偏弱'

    return {
      totalStocks: top100.length,
      totalTurnover: totalTurnover / 100000000, // 转换为亿
      avgTurnover: avgTurnover / 100000000,
      topStocksCount: top10.length,
      sectorCount: sectors.length,
      positiveCount,
      negativeCount: top10.length - positiveCount,
      marketTrend
    }
  })

  return {
    indexData,
    top100Stocks,
    top10FactorStocks,
    sectorScores,
    factorTree,
    marketAnalysis,
    marketData,
    marketCompositeScore,
    marketKeyFactors,
    marketIndexPrices,
    tradeDate,
    summary
  }
}
