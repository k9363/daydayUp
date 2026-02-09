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
      <!-- 统计摘要 -->
      <el-row :gutter="20" class="summary-cards">
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <template #header>股票总数</template>
            <div class="card-value">{{ summary.totalStocks }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <template #header>前100成交额</template>
            <div class="card-value">{{ formatAmount(summary.totalAmount) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <template #header>前100平均成交</template>
            <div class="card-value">{{ formatAmount(summary.avgAmount) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <template #header>板块数量</template>
            <div class="card-value">{{ sectors.length }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="20" class="chart-row">
        <!-- 板块成交额饼图 -->
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>
              <span>板块成交额分布</span>
            </template>
            <div ref="pieChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
        <!-- 板块股票数量柱状图 -->
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>
              <span>板块股票数量</span>
            </template>
            <div ref="barChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 成交额Top10图表 -->
      <el-card shadow="hover" class="top10-chart-card">
        <template #header>
          <span>成交额 Top 10</span>
        </template>
        <div ref="top10ChartRef" class="chart-container-large"></div>
      </el-card>

      <!-- 板块详情表格 -->
      <el-card shadow="hover" class="sector-table-card">
        <template #header>
          <span>板块统计详情</span>
        </template>
        <el-table :data="sectors" stripe style="width: 100%">
          <el-table-column prop="sector" label="板块" width="180" />
          <el-table-column prop="count" label="股票数量" width="120" align="center">
            <template #default="{ row }">
              <el-tag type="info">{{ row.count }}只</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿)" width="150" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.totalAmount) }}
            </template>
          </el-table-column>
          <el-table-column label="平均涨幅" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.avgPctChg >= 0 ? 'positive' : 'negative'">
                {{ row.avgPctChg >= 0 ? '+' : '' }}{{ row.avgPctChg.toFixed(2) }}%
              </span>
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
          <el-table-column prop="name" label="名称" width="150" />
          <el-table-column prop="sector" label="板块" width="120" />
          <el-table-column prop="industry" label="行业" width="150" />
          <el-table-column label="成交额(亿)" width="150" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount) }}
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

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

// 计算属性
const summary = computed(() => chartData.value?.summary || {})
const sectors = computed(() => chartData.value?.sectors || [])
const top100Detail = computed(() => chartData.value?.top100Detail || [])

// 返回上一页
const goBack = () => {
  router.back()
}

// 刷新数据
const refreshData = () => {
  fetchChartData()
}

// 格式化金额
const formatAmount = (value) => {
  if (!value && value !== 0) return '-'
  if (value >= 10000) {
    return `${(value / 10000).toFixed(2)}万亿`
  } else if (value >= 100) {
    return `${value.toFixed(2)}亿`
  }
  return `${value.toFixed(2)}`
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
</style>
