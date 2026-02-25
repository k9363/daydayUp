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
        <el-row :gutter="20" v-if="dashboardData.length > 0">
          <!-- 板块前10趋势 -->
          <el-col :span="12">
            <div class="chart-title">板块前10得分</div>
            <div class="dashboard-chart">
              <el-table :data="dashboardData" stripe size="small" :max-height="400">
                <el-table-column prop="tradeDate" label="交易日" width="120" fixed />
                <el-table-column label="板块Top10" min-width="300">
                  <template #default="{ row }">
                    <el-tag v-for="sector in row.sectors.slice(0, 3)" :key="sector.name" 
                            type="warning" size="small" style="margin-right: 4px">
                      {{ sector.name }}
                    </el-tag>
                    <span v-if="row.sectors.length > 3" class="more-text">
                      +{{ row.sectors.length - 3 }}个
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
          <!-- 因子得分Top10趋势 -->
          <el-col :span="12">
            <div class="chart-title">因子得分 Top 10 股票</div>
            <div class="dashboard-chart">
              <el-table :data="dashboardData" stripe size="small" :max-height="400">
                <el-table-column prop="tradeDate" label="交易日" width="120" fixed />
                <el-table-column label="股票Top10" min-width="300">
                  <template #default="{ row }">
                    <el-tag v-for="stock in row.factorStocks.slice(0, 3)" :key="stock.code" 
                            type="success" size="small" style="margin-right: 4px">
                      {{ stock.name }}
                    </el-tag>
                    <span v-if="row.factorStocks.length > 3" class="more-text">
                      +{{ row.factorStocks.length - 3 }}只
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
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
import { ref, onMounted } from 'vue'
import { getReviewTaskList, getDashboardData } from '@/api'

const loading = ref(false)
const taskCount = ref(0)
const completedCount = ref(0)
const warningCount = ref(0)
const pendingCount = ref(0)
const recentTasks = ref([])
const dashboardData = ref([])  // 仪表盘数据

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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
