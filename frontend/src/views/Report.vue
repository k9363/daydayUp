<template>
  <div class="report">
    <el-container>
      <el-header class="header">
        <div class="header-content">
          <div class="logo" @click="$router.push('/')">
            <el-icon :size="28" color="#409EFF"><DataAnalysis /></el-icon>
            <span class="title">DaydayUp</span>
          </div>
          <el-menu
            :default-active="activeMenu"
            mode="horizontal"
            :router="true"
            class="nav-menu"
          >
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/metadata">
              <el-icon><Grid /></el-icon>
              <span>元数据</span>
            </el-menu-item>
            <el-menu-item index="/datasource">
              <el-icon><Document /></el-icon>
              <span>数据管理</span>
            </el-menu-item>
            <el-menu-item index="/review">
              <el-icon><TrendCharts /></el-icon>
              <span>复盘分析</span>
            </el-menu-item>
          </el-menu>
        </div>
      </el-header>
      
      <el-main>
        <div class="page-header">
          <el-page-header @back="$router.back()">
            <template #content>
              <span class="page-title">分析报告</span>
            </template>
            <template #extra>
              <el-button @click="exportReport">
                <el-icon><Download /></el-icon>
                导出报告
              </el-button>
            </template>
          </el-page-header>
        </div>
        
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-container">
          <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
          <p>正在加载分析报告...</p>
        </div>
        
        <!-- Baostock 日线数据报告 -->
        <div v-else-if="isBaostockTask && chartData">
          <!-- 任务信息 -->
          <el-card class="info-card">
            <el-descriptions :column="4" border>
              <el-descriptions-item label="任务名称">{{ task.taskName }}</el-descriptions-item>
              <el-descriptions-item label="交易日期">{{ chartData.tradeDate || chartData.trade_date }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getStatusType(task.status)">{{ getStatusName(task.status) }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="股票总数">{{ chartData.summary?.totalStocks || chartData.summary?.total_stocks || '-' }}</el-descriptions-item>
              <el-descriptions-item label="结果摘要" :span="4">
                {{ task.resultSummary }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
          
          <!-- 统计概览 -->
          <el-row :gutter="20" class="summary-row">
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card total">
                <div class="summary-content">
                  <el-icon :size="36" color="#409EFF"><DataAnalysis /></el-icon>
                  <div class="summary-value">{{ chartData.summary?.totalStocks || chartData.summary?.total_stocks || 0 }}</div>
                  <div class="summary-label">A股总数</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card normal">
                <div class="summary-content">
                  <el-icon :size="36" color="#67C23A"><Money /></el-icon>
                  <div class="summary-value">{{ formatAmount(chartData.summary?.totalAmount || chartData.summary?.total_amount) }}</div>
                  <div class="summary-label">TOP100成交额</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card warning">
                <div class="summary-content">
                  <el-icon :size="36" color="#E6A23C"><PieChart /></el-icon>
                  <div class="summary-value">{{ (chartData.sectors || chartData.sectorDistribution || []).length || 0 }}</div>
                  <div class="summary-label">板块数量</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card critical">
                <div class="summary-content">
                  <el-icon :size="36" color="#909399"><TrendCharts /></el-icon>
                  <div class="summary-value">{{ formatPct(chartData.summary?.avgPctChg || chartData.summary?.avg_pct_chg || 0) }}%</div>
                  <div class="summary-label">TOP100平均涨幅</div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- 板块分布图表 -->
          <el-row :gutter="20" class="chart-row">
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>板块成交额分布</span>
                </template>
                <div ref="pieChartRef" class="chart-container"></div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>板块股票数量分布</span>
                </template>
                <div ref="barChartRef" class="chart-container"></div>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- 板块详细数据 -->
          <el-row :gutter="20" class="chart-row">
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>板块成交额排行榜</span>
                </template>
                <el-table :data="sectorTableData" style="width: 100%" stripe max-height="400">
                  <el-table-column prop="sector" label="板块" width="120" />
                  <el-table-column prop="count" label="股票数" width="80" align="center" />
                  <el-table-column prop="totalAmount" label="成交额(亿)" width="120" align="right">
                    <template #default="{ row }">
                      {{ formatAmount(row.totalAmount) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="avgPctChg" label="平均涨幅" width="100" align="center">
                    <template #default="{ row }">
                      <span :class="getPctClass(row.avgPctChg)">
                        {{ formatPct(row.avgPctChg) }}%
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>TOP10 成交额股票</span>
                </template>
                <el-table :data="top10Stocks" style="width: 100%" stripe max-height="400">
                  <el-table-column type="index" label="#" width="50" align="center" />
                  <el-table-column prop="code" label="代码" width="90" />
                  <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
                  <el-table-column prop="amount" label="成交额(亿)" width="110" align="right">
                    <template #default="{ row }">
                      {{ formatAmount(row.amount) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="pctChg" label="涨幅" width="80" align="center">
                    <template #default="{ row }">
                      <span :class="getPctClass(row.pctChg)">
                        {{ formatPct(row.pctChg) }}%
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- TOP100 完整数据 -->
          <el-card class="result-card">
            <template #header>
              <span>成交额 TOP100 完整名单</span>
            </template>
            <el-table :data="top100Detail" style="width: 100%" stripe max-height="500">
              <el-table-column type="index" label="排名" width="70" align="center" />
              <el-table-column prop="code" label="股票代码" width="100" />
              <el-table-column prop="name" label="股票名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="sector" label="板块" width="100" />
              <el-table-column prop="amount" label="成交额(亿)" width="120" align="right">
                <template #default="{ row }">
                  {{ formatAmount(row.amount) }}
                </template>
              </el-table-column>
              <el-table-column prop="pctChg" label="涨跌幅" width="100" align="center">
                <template #default="{ row }">
                  <span :class="getPctClass(row.pctChg)">
                    {{ formatPct(row.pctChg) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="close" label="收盘价" width="100" align="right">
                <template #default="{ row }">
                  {{ row.close ? row.close.toFixed(2) : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
        
        <!-- 传统报告（现有逻辑） -->
        <div v-else-if="reportData">
          <!-- 任务信息 -->
          <el-card class="info-card">
            <el-descriptions :column="4" border>
              <el-descriptions-item label="任务名称">{{ task.taskName }}</el-descriptions-item>
              <el-descriptions-item label="复盘类型">{{ getTypeName(task.reviewType) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getStatusType(task.status)">{{ getStatusName(task.status) }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="执行时间">
                {{ formatTime(task.startTime) }} - {{ formatTime(task.endTime) }}
              </el-descriptions-item>
              <el-descriptions-item label="结果摘要" :span="4">
                {{ task.resultSummary }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
          
          <!-- 统计概览 -->
          <el-row :gutter="20" class="summary-row">
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card normal">
                <div class="summary-content">
                  <el-icon :size="36" color="#67C23A"><CircleCheck /></el-icon>
                  <div class="summary-value">{{ summary.normal }}</div>
                  <div class="summary-label">正常指标</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card warning">
                <div class="summary-content">
                  <el-icon :size="36" color="#E6A23C"><Warning /></el-icon>
                  <div class="summary-value">{{ summary.warning }}</div>
                  <div class="summary-label">警告指标</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card critical">
                <div class="summary-content">
                  <el-icon :size="36" color="#F56C6C"><CircleClose /></el-icon>
                  <div class="summary-value">{{ summary.critical }}</div>
                  <div class="summary-label">严重指标</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card total">
                <div class="summary-content">
                  <el-icon :size="36" color="#409EFF"><DataAnalysis /></el-icon>
                  <div class="summary-value">{{ summary.total }}</div>
                  <div class="summary-label">分析指标</div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- 图表区域 -->
          <el-row :gutter="20" class="chart-row">
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>指标状态分布</span>
                </template>
                <div ref="pieChartRef" class="chart-container"></div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card class="chart-card">
                <template #header>
                  <span>指标变化趋势</span>
                </template>
                <div ref="barChartRef" class="chart-container"></div>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- 详细结果 -->
          <el-card class="result-card">
            <template #header>
              <span>详细分析结果</span>
            </template>
            
            <el-table :data="results" style="width: 100%" stripe>
              <el-table-column prop="dimension" label="分析维度" min-width="150" />
              <el-table-column prop="metricName" label="指标名称" min-width="150" />
              <el-table-column prop="metricValue" label="指标值" width="120" />
              <el-table-column prop="compareValue" label="对比值" width="100" />
              <el-table-column prop="changeRate" label="变化率" width="100">
                <template #default="{ row }">
                  <span :class="getChangeRateClass(row.changeRate)">
                    {{ row.changeRate ? row.changeRate.toFixed(2) + '%' : '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getResultStatusType(row.status)" size="small">
                    {{ getStatusName(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="suggestion" label="建议" min-width="200" show-overflow-tooltip />
            </el-table>
          </el-card>
        </div>
        
        <!-- 错误状态 -->
        <el-empty v-else-if="!loading && !reportData" description="报告数据不存在">
          <el-button type="primary" @click="$router.push('/review')">返回列表</el-button>
        </el-empty>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Download, DataAnalysis, Money, PieChart, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getReviewReport, getReviewTaskChart } from '@/api'

const route = useRoute()
const loading = ref(true)
const reportData = ref(null)
const chartData = ref(null)
const pieChartRef = ref(null)
const barChartRef = ref(null)
let pieChart = null
let barChart = null

const isBaostockTask = computed(() => {
  return task.value?.dataSourceId && chartData.value !== null
})

const task = computed(() => reportData.value?.task || {})
const results = computed(() => reportData.value?.results || [])
const summary = computed(() => reportData.value?.summary || { normal: 0, warning: 0, critical: 0, total: 0 })

// 板块表格数据
const sectorTableData = computed(() => {
  if (!chartData.value?.sectors) return []
  return [...chartData.value.sectors].sort((a, b) => b.totalAmount - a.totalAmount)
})

// TOP10 股票
const top10Stocks = computed(() => {
  if (!chartData.value?.top100Detail) return []
  return chartData.value.top100Detail.slice(0, 10)
})

// TOP100 完整数据
const top100Detail = computed(() => {
  if (!chartData.value?.top100Detail) return []
  return chartData.value.top100Detail
})

const activeMenu = computed(() => '/review')

const getTypeName = (type) => {
  const types = { daily: '日复盘', weekly: '周复盘', monthly: '月复盘', custom: '自定义' }
  return types[type] || type
}

const getStatusName = (status) => {
  const statuses = { pending: '待执行', running: '执行中', completed: '已完成', failed: '失败', normal: '正常', warning: '警告', critical: '严重' }
  return statuses[status] || status
}

const getStatusType = (status) => {
  const types = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
  return types[status] || 'info'
}

const getResultStatusType = (status) => {
  const types = { normal: 'success', warning: 'warning', critical: 'danger' }
  return types[status] || 'info'
}

const getChangeRateClass = (rate) => {
  if (!rate) return ''
  if (rate > 20) return 'text-danger'
  if (rate > 0) return 'text-warning'
  return 'text-success'
}

const getPctClass = (pct) => {
  if (pct > 0) return 'text-danger'
  if (pct < 0) return 'text-success'
  return ''
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const formatAmount = (val) => {
  if (!val) return '0'
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '万亿'
  } else if (val >= 1000) {
    return (val / 1000).toFixed(2) + '千亿'
  }
  return val.toFixed(2)
}

const formatPct = (val) => {
  if (!val) return '0.00'
  return val.toFixed(2)
}

const loadReport = async () => {
  const id = route.params.id
  if (!id) return
  
  loading.value = true
  try {
    // 获取基础报告数据
    const res = await getReviewReport(id)
    reportData.value = res.data
    
    // 获取图表数据
    try {
      const chartRes = await getReviewTaskChart(id)
      if (chartRes.data && chartRes.data.sectors) {
        chartData.value = chartRes.data
      }
    } catch (chartErr) {
      console.log('非Baostock任务或无图表数据')
      chartData.value = null
    }
    
    // 等待DOM更新后渲染图表
    await nextTick()
    setTimeout(() => {
      if (chartData.value) {
        initBaostockCharts()
      } else {
        initCharts()
      }
    }, 100)
  } catch (error) {
    console.error('加载报告失败:', error)
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

const initBaostockCharts = () => {
  if (!pieChartRef.value || !barChartRef.value || !chartData.value) return
  
  // 销毁已有图表
  if (pieChart) pieChart.dispose()
  if (barChart) barChart.dispose()
  
  const sectors = chartData.value.sectors || []
  
  // 饼图 - 成交额分布
  pieChart = echarts.init(pieChartRef.value)
  const pieOption = {
    tooltip: { 
      trigger: 'item', 
      formatter: (params) => {
        return `${params.name}<br/>成交额: ${formatAmount(params.value)}<br/>占比: ${params.percent}%`
      }
    },
    legend: { bottom: 0, type: 'scroll' },
    color: ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#B37FEB', '#36CFC9', '#FF85C0', '#FFC53D', '#73D13D'],
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' }
      },
      data: sectors.map(s => ({
        name: s.sector,
        value: s.totalAmount
      }))
    }]
  }
  pieChart.setOption(pieOption)
  
  // 柱状图 - 板块数量分布
  barChart = echarts.init(barChartRef.value)
  const barOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: sectors.map(s => s.sector),
      axisLabel: { interval: 0, rotate: 30 }
    },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: sectors.map(s => ({
        value: s.count,
        itemStyle: { color: '#409EFF' }
      })),
      label: { show: true, position: 'top' },
      name: '股票数量'
    }]
  }
  barChart.setOption(barOption)
}

const initCharts = () => {
  if (!pieChartRef.value || !barChartRef.value) return
  
  // 销毁已有图表
  if (pieChart) pieChart.dispose()
  if (barChart) barChart.dispose()
  
  // 饼图
  pieChart = echarts.init(pieChartRef.value)
  const pieOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    color: ['#67C23A', '#E6A23C', '#F56C6C'],
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      label: { show: true, formatter: '{b}: {c}' },
      data: [
        { value: summary.value.normal, name: '正常' },
        { value: summary.value.warning, name: '警告' },
        { value: summary.value.critical, name: '严重' }
      ]
    }]
  }
  pieChart.setOption(pieOption)
  
  // 柱状图
  barChart = echarts.init(barChartRef.value)
  const dimensions = results.value.map(r => r.metricName.substring(0, 8))
  const values = results.value.map(r => parseFloat(r.metricValue) || 0)
  const colors = results.value.map(r => {
    if (r.status === 'critical') return '#F56C6C'
    if (r.status === 'warning') return '#E6A23C'
    return '#67C23A'
  })
  
  const barOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dimensions, axisLabel: { rotate: 30, interval: 0 } },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: values.map((val, idx) => ({ value: val, itemStyle: { color: colors[idx] } })),
      label: { show: true, position: 'top', formatter: '{c}' }
    }]
  }
  barChart.setOption(barOption)
}

const handleResize = () => {
  if (pieChart) pieChart.resize()
  if (barChart) barChart.resize()
}

const exportReport = () => {
  ElMessage.info('报告导出功能开发中...')
}

watch(() => route.params.id, () => {
  loadReport()
})

onMounted(() => {
  loadReport()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pieChart) pieChart.dispose()
  if (barChart) barChart.dispose()
})
</script>

<style scoped>
.report {
  min-height: 100vh;
}

.header {
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.logo .title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.nav-menu {
  border-bottom: none !important;
}

.el-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 500;
}

.loading-container {
  text-align: center;
  padding: 100px 0;
}

.loading-icon {
  animation: rotate 1.5s linear infinite;
  color: #409EFF;
  margin-bottom: 20px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.info-card {
  margin-bottom: 20px;
  border-radius: 12px;
}

.summary-row {
  margin-bottom: 20px;
}

.summary-card {
  border-radius: 12px;
  text-align: center;
}

.summary-content {
  padding: 20px 0;
}

.summary-value {
  font-size: 28px;
  font-weight: 600;
  margin: 10px 0;
}

.summary-label {
  font-size: 14px;
  color: #909399;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  border-radius: 12px;
}

.chart-container {
  height: 350px;
}

.result-card {
  border-radius: 12px;
}

.text-success { color: #67C23A; }
.text-warning { color: #E6A23C; }
.text-danger { color: #F56C6C; }
</style>
