<template>
  <div class="review-result">
    <!-- 头部信息 -->
    <div class="header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">复盘分析结果</span>
        </template>
        <template #extra>
          <el-button type="primary" @click="refreshData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </template>
      </el-page-header>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 错误提示 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon class="error-alert" />

    <!-- 数据内容 -->
    <div v-else-if="chartData" class="content">
      <!-- 指数行情 -->
      <el-card shadow="hover" class="index-card" v-if="indexData.length > 0">
        <template #header>
          <span>主要指数行情</span>
        </template>
        <el-table :data="indexData" stripe style="width: 100%">
          <el-table-column prop="name" label="指数名称" width="150" />
          <el-table-column prop="code" label="指数代码" width="150" />
          <el-table-column label="收盘价" width="120" align="right">
            <template #default="{ row }">
              {{ row.close.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿)" width="140" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="成交量(亿)" width="140" align="right">
            <template #default="{ row }">
              {{ ((row.volume || 0) / 100000000).toFixed(2) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 因子得分排名 Top 10 -->
      <el-card shadow="hover" class="stock-table-card" v-if="top10FactorStocks.length > 0">
        <template #header>
          <span>因子得分 Top 10 股票</span>
        </template>
        <el-table :data="top10FactorStocks" stripe style="width: 100%">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column label="成交额(亿)" width="140" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column prop="sector" label="所属板块" width="180" />
          <el-table-column label="综合得分" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="success">{{ row.totalScore.toFixed(2) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="因子1(排名)" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`成交额排名: 第${Math.round((10 - row.factor1Rank) / 0.2 + 1)}名`" placement="top">
                {{ row.factor1Rank.toFixed(1) }}
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子2(均线)" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`收盘: ${row.currentPrice || '-'} | MA5: ${row.ma5 || '-'} | MA10: ${row.ma10 || '-'}`" placement="top">
                <span :class="row.factor2MA >= 0 ? 'positive' : 'negative'">
                  {{ row.factor2MA >= 0 ? '+' : '' }}{{ row.factor2MA.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子3(量能)" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`今量: ${row.volCurrent ? (row.volCurrent / 10000).toFixed(0) + '万' : '-'} | 昨量: ${row.volPrev ? (row.volPrev / 10000).toFixed(0) + '万' : '-'}`" placement="top">
                <span :class="row.factor3Vol >= 0 ? 'positive' : 'negative'">
                  {{ row.factor3Vol >= 0 ? '+' : '' }}{{ row.factor3Vol.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子4(量比)" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`近5日均: ${row.avg5dTurnover ? (row.avg5dTurnover / 100000000).toFixed(2) + '亿' : '-'} | 前5日均: ${row.avg5dBeforeTurnover ? (row.avg5dBeforeTurnover / 100000000).toFixed(2) + '亿' : '-'}`" placement="top">
                <span :class="row.factor4Amt >= 0 ? 'positive' : 'negative'">
                  {{ row.factor4Amt >= 0 ? '+' : '' }}{{ row.factor4Amt.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 板块详情表格 -->
      <el-card shadow="hover" class="sector-table-card">
        <template #header>
          <span>板块统计详情</span>
        </template>
        <el-table :data="sectors" stripe style="width: 100%">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="sector" label="板块" width="180" />
          <el-table-column label="得分" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="warning">{{ Math.round(row.score) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="股票数量" width="120" align="center">
            <template #default="{ row }">
              <el-tag type="info" class="clickable-tag" @click="handleShowSectorStocks(row)">
                {{ row.count }}只
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="实际涨幅" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.avgPctChg >= 0 ? 'positive' : 'negative'">
                {{ row.avgPctChg >= 0 ? '+' : '' }}{{ row.avgPctChg.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="因子1" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip content="板块内前30股票因子1得分合计" placement="top">
                <span class="factor-label">{{ row.factor1?.toFixed(1) || 0 }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子2" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip content="板块内前30股票因子2得分合计" placement="top">
                <span :class="(row.factor2 || 0) >= 0 ? 'positive' : 'negative'">
                  {{ (row.factor2 || 0) >= 0 ? '+' : '' }}{{ (row.factor2 || 0).toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子3" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip content="板块内前30股票因子3得分合计" placement="top">
                <span :class="(row.factor3 || 0) >= 0 ? 'positive' : 'negative'">
                  {{ (row.factor3 || 0) >= 0 ? '+' : '' }}{{ (row.factor3 || 0).toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="因子4" width="100" align="center">
            <template #default="{ row }">
              <el-tooltip content="板块内前30股票因子4得分合计" placement="top">
                <span :class="(row.factor4 || 0) >= 0 ? 'positive' : 'negative'">
                  {{ (row.factor4 || 0) >= 0 ? '+' : '' }}{{ (row.factor4 || 0).toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Top100 股票明细 -->
      <el-card shadow="hover" class="stock-table-card">
        <template #header>
          <span>成交额 Top 100 股票明细</span>
        </template>
        <el-table :data="top100Detail" stripe style="width: 100%" max-height="500">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="sector" label="所属板块" width="180" />
          <el-table-column prop="industry" label="所属行业" width="120" />
          <el-table-column label="总市值(亿)" width="120" align="right">
            <template #default="{ row }">
              {{ formatMarketValue(row.totalMarketValue) }}
            </template>
          </el-table-column>
          <el-table-column label="流通市值(亿)" width="130" align="right">
            <template #default="{ row }">
              {{ formatMarketValue(row.circulateMarketValue) }}
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿)" width="150" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 板块成分股对话框 -->
      <el-dialog
        v-model="showSectorStocksDialog"
        :title="currentSectorName + ' - 成分股'"
        width="800px"
      >
        <el-table :data="sectorStocksList" v-loading="sectorStocksLoading" stripe max-height="400">
          <el-table-column prop="stock_code" label="代码" width="100" />
          <el-table-column prop="stock_name" label="名称" width="120" />
          <el-table-column prop="industry" label="所属行业" width="120" />
          <el-table-column label="总市值(亿)" width="120" align="right">
            <template #default="{ row }">
              {{ formatMarketValue(row.total_market_value) }}
            </template>
          </el-table-column>
        </el-table>
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="showSectorStocksDialog = false">关闭</el-button>
          </span>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getSectorStocks } from '@/api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

// 响应式数据
const loading = ref(true)
const error = ref(null)
const chartData = ref(null)
const pieChartRef = ref(null)
const barChartRef = ref(null)
const top10ChartRef = ref(null)
let pieChart = null
let barChart = null
let top10Chart = null

// 板块成分股相关
const showSectorStocksDialog = ref(false)
const sectorStocksLoading = ref(false)
const sectorStocksList = ref([])
const currentSectorName = ref('')
const sectorStocksTotal = ref(0)

// 计算属性
const summary = computed(() => chartData.value?.summary || {})
const sectors = computed(() => chartData.value?.sectors || [])
const top100Detail = computed(() => chartData.value?.top100Detail || [])
const top10FactorStocks = computed(() => chartData.value?.top10FactorStocks || [])
const indexData = computed(() => chartData.value?.indexData || [])

// 返回上一页
const goBack = () => {
  router.back()
}

// 刷新数据
const refreshData = () => {
  fetchChartData()
}

// 点击查看板块成分股
const handleShowSectorStocks = async (row) => {
  // 优先使用后端返回的前30股票列表
  if (row.topStocks && row.topStocks.length > 0) {
    sectorStocksList.value = row.topStocks.map(s => ({
      stock_code: s.code,
      stock_name: s.name,
      total_score: s.totalScore,
      rank: s.rank
    }))
    sectorStocksTotal.value = row.topStocks.length
    currentSectorName.value = row.sector || row.name
    showSectorStocksDialog.value = true
    return
  }
  
  // 兼容处理：sectorCode 可能不存在，尝试从 sector 获取
  let sectorCode = row.sectorCode || row.sector_code || ''
  
  if (!sectorCode && row.sector) {
    // 如果没有 sectorCode，尝试从后端获取
    try {
      const res = await getSectorStocks('', { sector_name: row.sector })
      if (res.code === 200 && res.data.list && res.data.list.length > 0) {
        sectorStocksList.value = res.data.list || []
        sectorStocksTotal.value = res.data.total || 0
        currentSectorName.value = row.sector
        showSectorStocksDialog.value = true
        return
      }
    } catch (e) {
      console.error('按名称查询板块失败:', e)
    }
    ElMessage.warning('板块代码不存在')
    return
  }
  
  currentSectorName.value = row.sector
  showSectorStocksDialog.value = true
  sectorStocksLoading.value = true
  
  try {
    const res = await getSectorStocks(sectorCode, { page: 1, page_size: 100 })
    if (res.code === 200) {
      sectorStocksList.value = res.data.list || []
      sectorStocksTotal.value = res.data.total || 0
    }
  } catch (error) {
    console.error('获取板块成分股失败:', error)
    ElMessage.error('获取板块成分股失败')
  } finally {
    sectorStocksLoading.value = false
  }
}

// 格式化金额（后端已转为亿，直接展示）
const formatAmount = (value) => {
  if (!value && value !== 0) return '-'
  return `${parseFloat(value).toFixed(2)}亿`
}

// 格式化市值（直接是元，转为亿/万亿显示）
const formatMarketValue = (value) => {
  if (!value && value !== 0) return '-'
  if (value >= 100000000) {
    // 转换为万亿
    return `${(value / 100000000).toFixed(2)}万亿`
  } else if (value >= 10000000000) {
    // 转换为亿
    return `${(value / 100000000).toFixed(2)}亿`
  }
  return `${(value / 100000000).toFixed(2)}亿`
}

// 获取图表数据
const fetchChartData = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch(`/api/review/task/${taskId}/chart`)
    const result = await response.json()
    
    if (result.code === 200) {
      chartData.value = result.data
      // 数据加载后初始化图表
      await nextTick()
      initCharts()
    } else {
      error.value = result.message || '获取数据失败'
    }
  } catch (e) {
    error.value = '网络错误，请检查后端服务'
    console.error('获取图表数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 初始化图表
const initCharts = () => {
  initPieChart()
  initBarChart()
  initTop10Chart()
}

// 初始化饼图
const initPieChart = () => {
  if (!pieChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorPie || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}亿 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [{
      name: '成交额',
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}: {d}%'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      data: labels.map((label, index) => ({
        value: data[index],
        name: label
      }))
    }]
  })
}

// 初始化柱状图
const initBarChart = () => {
  if (!barChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorBar || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  barChart = echarts.init(barChartRef.value)
  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        rotate: 30,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      name: '股票数量'
    },
    series: [{
      name: '股票数量',
      type: 'bar',
      data: data,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#83bff6' },
          { offset: 0.5, color: '#188df0' },
          { offset: 1, color: '#188df0' }
        ])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2378f7' },
            { offset: 1, color: '#2378f7' }
          ])
        }
      }
    }]
  })
}

// 初始化Top10图表
const initTop10Chart = () => {
  if (!top10ChartRef.value) return
  
  const chartsData = chartData.value?.charts?.amountTop10 || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  top10Chart = echarts.init(top10ChartRef.value)
  top10Chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '成交额(亿)',
      axisLabel: {
        formatter: (value) => value.toFixed(0)
      }
    },
    yAxis: {
      type: 'category',
      data: labels.reverse(),
      axisLabel: {
        fontSize: 11
      }
    },
    series: [{
      name: '成交额',
      type: 'bar',
      data: data.reverse(),
      itemStyle: {
        color: (params) => {
          const colors = ['#FF6B6B', '#FF8E72', '#FFA940', '#FFC53D', '#FFEC3D', '#A0D911', '#52C41A', '#13C2C2', '#1890FF', '#2F54EB']
          return colors[params.dataIndex] || '#1890FF'
        }
      },
      label: {
        show: true,
        position: 'right',
        formatter: (params) => formatAmount(params.value)
      }
    }]
  })
}

// 监听窗口大小变化
const handleResize = () => {
  pieChart?.resize()
  barChart?.resize()
  top10Chart?.resize()
}

// 生命周期
onMounted(() => {
  fetchChartData()
  window.addEventListener('resize', handleResize)
})

// 清理
watch(() => chartData.value, () => {
  if (chartData.value) {
    nextTick(() => {
      initCharts()
    })
  }
})
</script>

<style scoped>
.review-result {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.loading-container {
  padding: 40px;
}

.error-alert {
  margin: 20px;
}

.content {
  padding: 0 10px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-card :deep(.el-card__header) {
  font-weight: 500;
  color: #666;
}

.card-value {
  font-size: 24px;
  font-weight: bold;
  color: #1890ff;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.chart-container-large {
  height: 400px;
  width: 100%;
}

.top10-chart-card,
.sector-table-card,
.stock-table-card {
  margin-bottom: 20px;
}

.positive {
  color: #f56c6c;
  font-weight: 500;
}

.negative {
  color: #52c41a;
  font-weight: 500;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.clickable-tag:hover {
  color: #409eff;
  transform: scale(1.05);
}
</style>
