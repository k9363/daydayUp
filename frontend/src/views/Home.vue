<template>
  <div class="home">
        <!-- 欢迎区域 -->
        <div class="welcome-section">
          <el-card class="welcome-card">
            <template #header>
              <div class="card-header">
                <span>欢迎使用智能复盘系统</span>
              </div>
            </template>
            <div class="welcome-content">
              <el-row :gutter="20">
                <el-col :span="6">
                  <div class="stat-item" @click="$router.push('/review/create')">
                    <el-icon :size="40" color="#409EFF"><Plus /></el-icon>
                    <div class="stat-value">{{ taskCount }}</div>
                    <div class="stat-label">复盘任务</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-item" @click="$router.push('/review')">
                    <el-icon :size="40" color="#67C23A"><Finished /></el-icon>
                    <div class="stat-value">{{ completedCount }}</div>
                    <div class="stat-label">已完成</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-item">
                    <el-icon :size="40" color="#E6A23C"><Warning /></el-icon>
                    <div class="stat-value">{{ warningCount }}</div>
                    <div class="stat-label">进行中</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-item">
                    <el-icon :size="40" color="#909399"><Clock /></el-icon>
                    <div class="stat-value">{{ pendingCount }}</div>
                    <div class="stat-label">待执行</div>
                  </div>
                </el-col>
              </el-row>
            </div>
          </el-card>
        </div>
        
        <!-- 快速开始 -->
        <div class="quick-start">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-card class="action-card" shadow="hover" @click="$router.push('/review/create')">
                <el-icon :size="48" color="#409EFF"><Plus /></el-icon>
                <h3>创建复盘</h3>
                <p>选择日期和复盘类型，自动获取Baostock股票数据进行分析</p>
                <el-button type="primary">立即创建</el-button>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card class="action-card" shadow="hover" @click="$router.push('/review')">
                <el-icon :size="48" color="#67C23A"><List /></el-icon>
                <h3>历史复盘</h3>
                <p>查看历史复盘记录、分析报告和趋势图表</p>
                <el-button type="success">查看历史</el-button>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card class="action-card" shadow="hover" @click="$router.push('/datasource')">
                <el-icon :size="48" color="#909399"><DataLine /></el-icon>
                <h3>数据管理</h3>
                <p>管理系统数据源和同步任务</p>
                <el-button type="info">数据管理</el-button>
              </el-card>
            </el-col>
          </el-row>
        </div>
    
    <!-- 近期复盘趋势 -->
    <div class="dashboard-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>近期复盘趋势（近10个交易日）</span>
          </div>
        </template>
        
        <!-- 趋势图表 -->
        <el-row :gutter="20" v-if="dashboardData.length > 0" style="margin-bottom: 20px">
          <!-- 大盘指数折线图 -->
          <el-col :span="12">
            <div class="chart-title">大盘指数得分趋势</div>
            <div ref="marketChartRef" class="trend-chart"></div>
          </el-col>
          <!-- 股票因子折线图 -->
          <el-col :span="12">
            <div class="chart-title">因子Top10股票得分趋势</div>
            <div ref="stockChartRef" class="trend-chart"></div>
          </el-col>
        </el-row>
        
        <!-- 详细数据表格 -->
        <el-empty v-else description="暂无复盘数据，请先创建复盘任务" />
      </el-card>
    </div>
        
        <!-- 最近复盘 -->
        <div class="recent-reviews">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>最近复盘</span>
                <el-button type="primary" link @click="$router.push('/review')">查看更多</el-button>
              </div>
            </template>
            <el-table :data="recentTasks" style="width: 100%" v-loading="loading">
              <el-table-column prop="taskName" label="任务名称" />
              <el-table-column prop="tradeDate" label="交易日期" width="120">
                <template #default="{ row }">
                  {{ row.tradeDate || '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">
                    {{ getStatusName(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="createTime" label="创建时间" width="160">
                <template #default="{ row }">
                  {{ formatTime(row.createTime) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button 
                    type="primary" 
                    link 
                    size="small"
                    v-if="row.status === 'completed'"
                @click="$router.push(`/review/result/${row.id}`)"
                  >
                查看结果
                  </el-button>
                  <el-button 
                    type="warning" 
                    link 
                    size="small"
                    v-if="row.status === 'pending' || row.status === 'running'"
                    @click="$router.push(`/review/result/${row.id}`)"
                  >
                    查看进度
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!loading && recentTasks.length === 0" description="暂无复盘任务">
              <el-button type="primary" @click="$router.push('/review/create')">
                创建第一个复盘
              </el-button>
            </el-empty>
          </el-card>
        </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getReviewTaskList, getDashboardData } from '@/api'
import * as echarts from 'echarts'

const loading = ref(false)
const taskCount = ref(0)
const completedCount = ref(0)
const warningCount = ref(0)
const pendingCount = ref(0)
const recentTasks = ref([])
const dashboardData = ref([])  // 仪表盘数据

// 大盘得分折线图配置
const marketChartRef = ref(null)
const stockChartRef = ref(null)
let marketChart = null
let stockChart = null

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

const updateCharts = () => {
  setTimeout(() => {
    initMarketChart()
    initStockChart()
  }, 100)
}

const getStatusName = (status) => {
  const statuses = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return statuses[status] || status
}

const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadData = async () => {
  loading.value = true
  try {
    const taskRes = await getReviewTaskList({ includeCompleted: true })
    const tasks = taskRes.data?.data || []
    taskCount.value = tasks.length
    completedCount.value = tasks.filter(t => t.status === 'completed').length
    warningCount.value = tasks.filter(t => t.status === 'running').length
    pendingCount.value = tasks.filter(t => t.status === 'pending').length
    recentTasks.value = tasks.slice(0, 5)
    
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

.welcome-section {
  margin-bottom: 20px;
}

.welcome-card {
  border-radius: 12px;
}

.welcome-content {
  padding: 10px 0;
}

.stat-item {
  text-align: center;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
  border-radius: 8px;
}

.stat-item:hover {
  background: #f5f7fa;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #303133;
  margin: 10px 0;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.quick-start {
  margin-bottom: 20px;
}

.action-card {
  text-align: center;
  padding: 30px 20px;
  cursor: pointer;
  border-radius: 12px;
  transition: all 0.3s;
}

.action-card:hover {
  transform: translateY(-5px);
}

.action-card h3 {
  margin: 15px 0 10px;
  color: #303133;
}

.action-card p {
  color: #909399;
  font-size: 14px;
  margin-bottom: 15px;
}

.recent-reviews {
  margin-bottom: 20px;
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

.dashboard-section .chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
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
