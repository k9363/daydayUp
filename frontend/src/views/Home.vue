<template>
  <div class="home" :class="themeClass">
    <!-- 当前周期信息 -->
    <div class="cycle-section" v-if="latestCycle">
      <el-card>
        <div class="cycle-info">
          <div class="cycle-title">{{ latestCycle.cycle?.title }}</div>
          <div class="cycle-period">
            <el-tag :type="getPeriodTypeTag(latestCycle.sub_period?.period_type)">
              {{ getPeriodTypeName(latestCycle.sub_period?.period_type) }}
            </el-tag>
            <span class="cycle-date">{{ latestCycle.trade_date }}</span>
          </div>
          <div class="cycle-features" v-if="latestCycle.cycle?.features">
            {{ latestCycle.cycle?.features }}
          </div>
        </div>
      </el-card>
    </div>

    <!-- 近期复盘趋势 -->
    <div class="dashboard-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>近期复盘趋势（近10个交易日）</span>
            <el-tag v-if="latestMarketScore !== null" :type="latestMarketScore > 0 ? 'danger' : 'success'" size="large">
              {{ latestMarketScore > 0 ? '上涨' : '下跌' }}
            </el-tag>
          </div>
        </template>
        
        <!-- 趋势图表 -->
        <el-row :gutter="20" v-if="dashboardData.length > 0" style="margin-bottom: 20px">
          <!-- 大盘指数折线图 -->
          <el-col :span="8">
            <div class="chart-title">大盘指数得分趋势</div>
            <div ref="marketChartRef" class="trend-chart"></div>
          </el-col>
          <!-- 板块得分折线图 -->
          <el-col :span="8">
            <div class="chart-title">板块得分趋势 Top10</div>
            <div ref="sectorChartRef" class="trend-chart"></div>
          </el-col>
          <!-- 股票因子折线图 -->
          <el-col :span="8">
            <div class="chart-title">因子Top10股票得分趋势</div>
            <div ref="stockChartRef" class="trend-chart"></div>
          </el-col>
        </el-row>
        
        <!-- 详细数据表格 -->
        <el-empty v-else description="暂无复盘数据，请先创建复盘任务" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getDashboardData, getLatestCycle } from '@/api'
import * as echarts from 'echarts'

const loading = ref(false)
const dashboardData = ref([])
const latestCycle = ref(null)
const latestMarketScore = computed(() => {
  // 获取最近一次复盘的大盘指数（数据已按日期倒序，第一个就是最近的）
  if (dashboardData.value.length > 0) {
    return dashboardData.value[0].marketScore
  }
  return null
})

const themeClass = computed(() => {
  if (latestMarketScore.value === null) return ''
  return latestMarketScore.value > 0 ? 'theme-red' : 'theme-green'
})

const periodTypeMap = {
  chaos: { name: '混沌', type: 'warning' },
  rise: { name: '主升', type: 'success' },
  oscillation: { name: '震荡', type: 'primary' },
  decline: { name: '退潮', type: 'danger' }
}

const getPeriodTypeName = (type) => periodTypeMap[type]?.name || type || ''
const getPeriodTypeTag = (type) => periodTypeMap[type]?.type || 'info'

// 大盘得分折线图配置
const marketChartRef = ref(null)
const stockChartRef = ref(null)
const sectorChartRef = ref(null)
let marketChart = null
let stockChart = null
let sectorChart = null

// 准备图表数据
const marketChartData = computed(() => {
  const data = dashboardData.value.slice().reverse()  // 反转顺序，按时间正序
  return {
    dates: data.map(d => d.tradeDate),
    scores: data.map(d => d.marketScore)
  }
})

const stockChartData = computed(() => {
  const data = dashboardData.value.slice().reverse()
  
  // 按名次构建数据：Top1, Top2, ..., Top10
  const series = []
  for (let rank = 0; rank < 10; rank++) {
    series.push({
      name: `Top${rank + 1}`,
      data: data.map(d => {
        const scores = d.topStockScores || []
        return scores.length > rank ? scores[rank] : null
      })
    })
  }
  
  return {
    dates: data.map(d => d.tradeDate),
    series: series,
    stocks: data.map(d => d.stockRanks || [])
  }
})

// 板块得分折线图数据
const sectorChartData = computed(() => {
  const data = dashboardData.value.slice().reverse()
  
  // 按名次构建数据：Top1, Top2, ..., Top10
  const series = []
  for (let rank = 0; rank < 10; rank++) {
    series.push({
      name: `Top${rank + 1}`,
      data: data.map(d => {
        const scores = d.sectorScores || []
        return scores.length > rank ? scores[rank] : null
      })
    })
  }
  
  return {
    dates: data.map(d => d.tradeDate),
    series: series,
    sectors: data.map(d => {
      const sectors = d.sectors || []
      return sectors.slice(0, 10).map(s => s.name)
    })
  }
})

const initMarketChart = () => {
  if (!marketChartRef.value) return
  marketChart = echarts.init(marketChartRef.value)
  const data = marketChartData.value
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const param = params[0]
        return `${param.name}<br/>大盘得分: ${param.value !== null ? param.value.toFixed(3) : '无数据'}`
      }
    },
    xAxis: {
      type: 'category',
      data: data.dates,
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '得分',
      axisLabel: {
        formatter: (value) => value.toFixed(1)
      }
    },
    series: [{
      data: data.scores,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: {
        color: '#409EFF',
        width: 3
      },
      itemStyle: {
        color: '#409EFF'
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      }
    }]
  }
  marketChart.setOption(option)
}

const initStockChart = () => {
  if (!stockChartRef.value) return
  stockChart = echarts.init(stockChartRef.value)
  const data = stockChartData.value
  
  // 颜色数组
  const colors = ['#67C23A', '#409EFF', '#E6A23C', '#F56C6C', '#909399', '#19BE6B', '#FFB800', '#46ADFD', '#FF6B6B', '#9B59B6']
  
  // 构建 series
  const series = data.series.map((s, idx) => ({
    name: s.name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    data: s.data,
    lineStyle: {
      width: 2
    },
    itemStyle: {
      color: colors[idx % colors.length]
    }
  }))
  
  const option = {
    tooltip: {
      trigger: 'axis',
      confine: true,
      extraCssText: 'max-width: 300px; white-space: normal; word-wrap: break-word;',
      formatter: (params) => {
        let html = `${params[0].name}<br/>`
        params.forEach(p => {
          if (p.value !== null) {
            // 查找该名次对应的股票名称
            const dateIdx = data.dates.indexOf(p.name)
            const stocks = dateIdx >= 0 ? data.stocks[dateIdx] : []
            const rank = parseInt(p.seriesName.replace('Top', '')) - 1
            const stockName = stocks[rank] ? stocks[rank].name : ''
            html += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)} ${stockName ? `(${stockName})` : ''}<br/>`
          }
        })
        return html
      }
    },
    legend: {
      type: 'scroll',
      orient: 'horizontal',
      bottom: 0,
      width: '80%'
    },
    xAxis: {
      type: 'category',
      data: data.dates,
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '得分',
      axisLabel: {
        formatter: (value) => value.toFixed(1)
      }
    },
    series: series
  }
  stockChart.setOption(option)
}

const initSectorChart = () => {
  if (!sectorChartRef.value) return
  sectorChart = echarts.init(sectorChartRef.value)
  const data = sectorChartData.value
  
  // 颜色数组 - 使用与股票不同的颜色
  const colors = ['#E6A23C', '#F56C6C', '#909399', '#19BE6B', '#FFB800', '#46ADFD', '#FF6B6B', '#9B59B6', '#67C23A', '#409EFF']
  
  // 构建 series
  const series = data.series.map((s, idx) => ({
    name: s.name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    data: s.data,
    lineStyle: {
      width: 2
    },
    itemStyle: {
      color: colors[idx % colors.length]
    }
  }))
  
  const option = {
    tooltip: {
      trigger: 'axis',
      confine: true,
      extraCssText: 'max-width: 300px; white-space: normal; word-wrap: break-word;',
      formatter: (params) => {
        let html = `${params[0].name}<br/>`
        params.forEach(p => {
          if (p.value !== null) {
            // 查找该名次对应的板块名称
            const dateIdx = data.dates.indexOf(p.name)
            const sectors = dateIdx >= 0 ? data.sectors[dateIdx] : []
            const rank = parseInt(p.seriesName.replace('Top', '')) - 1
            const sectorName = sectors[rank] ? sectors[rank] : ''
            html += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)} ${sectorName ? `(${sectorName})` : ''}<br/>`
          }
        })
        return html
      }
    },
    legend: {
      type: 'scroll',
      orient: 'horizontal',
      bottom: 0,
      width: '80%'
    },
    xAxis: {
      type: 'category',
      data: data.dates,
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '得分',
      axisLabel: {
        formatter: (value) => value.toFixed(1)
      }
    },
    series: series
  }
  sectorChart.setOption(option)
}

const updateCharts = () => {
  setTimeout(() => {
    initMarketChart()
    initSectorChart()
    initStockChart()
  }, 100)
}

const loadData = async () => {
  loading.value = true
  try {
    // 获取周期信息
    try {
      const cycleRes = await getLatestCycle()
      if (cycleRes.code === 200 && cycleRes.data) {
        latestCycle.value = cycleRes.data
      }
    } catch (e) {
      console.log('暂无周期数据')
    }

    // 获取仪表盘数据
    try {
      const dashboardRes = await getDashboardData()
      console.log('仪表盘数据:', dashboardRes)
      dashboardData.value = dashboardRes.data || []
      // 更新图表
      updateCharts()
    } catch (e) {
      console.error('获取仪表盘数据失败:', e)
      dashboardData.value = []
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.home {
  min-height: 100vh;
}

.home.theme-red {
  background:
    radial-gradient(900px 380px at 30% 0%, rgba(245, 108, 108, 0.30) 0%, rgba(245, 108, 108, 0.00) 70%),
    linear-gradient(180deg, rgba(245, 108, 108, 0.16) 0%, rgba(245, 247, 250, 0) 420px);
}

.home.theme-green {
  background:
    radial-gradient(900px 380px at 30% 0%, rgba(103, 194, 58, 0.30) 0%, rgba(103, 194, 58, 0.00) 70%),
    linear-gradient(180deg, rgba(103, 194, 58, 0.16) 0%, rgba(245, 247, 250, 0) 420px);
}

/* Element Plus 深层组件样式（scoped 下需要 deep） */
.home.theme-red :deep(.el-card) {
  border-color: rgba(245, 108, 108, 0.55);
  box-shadow: 0 10px 24px rgba(245, 108, 108, 0.10);
}

.home.theme-green :deep(.el-card) {
  border-color: rgba(103, 194, 58, 0.55);
  box-shadow: 0 10px 24px rgba(103, 194, 58, 0.10);
}

.home.theme-red :deep(.el-card__header) {
  border-bottom-color: rgba(245, 108, 108, 0.25);
}

.home.theme-green :deep(.el-card__header) {
  border-bottom-color: rgba(103, 194, 58, 0.25);
}

.home.theme-red :deep(.el-card__header) {
  position: relative;
}

.home.theme-green :deep(.el-card__header) {
  position: relative;
}

.home.theme-red :deep(.el-card__header)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, rgba(245, 108, 108, 0.95), rgba(245, 108, 108, 0.55));
}

.home.theme-green :deep(.el-card__header)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, rgba(103, 194, 58, 0.95), rgba(103, 194, 58, 0.55));
}

.home.theme-red .cycle-title {
  color: #b25252;
}

.home.theme-green .cycle-title {
  color: #3b7d1a;
}

.home.theme-red .dashboard-section .chart-title {
  color: #b25252;
}

.home.theme-green .dashboard-section .chart-title {
  color: #3b7d1a;
}

.cycle-section {
  margin-bottom: 20px;
}

.cycle-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cycle-title {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}

.cycle-period {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cycle-date {
  color: #909399;
  font-size: 14px;
}

.cycle-features {
  color: #606266;
  font-size: 14px;
  margin-top: 5px;
}

.dashboard-section {
  margin-bottom: 20px;
}

.dashboard-section .chart-title {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #606266;
}

.dashboard-section .more-text {
  color: #909399;
  font-size: 12px;
}

.dashboard-section .dashboard-chart {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.dashboard-section .trend-chart {
  height: 300px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
