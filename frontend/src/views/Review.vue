<template>
  <div class="review">
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
          <h2>复盘分析</h2>
          <el-button type="primary" @click="$router.push('/review/create')">
            <el-icon><Plus /></el-icon>
            创建复盘
          </el-button>
        </div>
        
        <!-- 统计卡片 -->
        <el-row :gutter="20" class="stat-row">
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-content">
                <el-icon :size="32" color="#409EFF"><Document /></el-icon>
                <div class="stat-info">
                  <div class="stat-num">{{ totalCount }}</div>
                  <div class="stat-text">总任务数</div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-content">
                <el-icon :size="32" color="#67C23A"><CircleCheck /></el-icon>
                <div class="stat-info">
                  <div class="stat-num">{{ completedCount }}</div>
                  <div class="stat-text">已完成</div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-content">
                <el-icon :size="32" color="#E6A23C"><Warning /></el-icon>
                <div class="stat-info">
                  <div class="stat-num">{{ pendingCount }}</div>
                  <div class="stat-text">待执行</div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-content">
                <el-icon :size="32" color="#F56C6C"><CircleClose /></el-icon>
                <div class="stat-info">
                  <div class="stat-num">{{ failedCount }}</div>
                  <div class="stat-text">失败</div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 任务列表 -->
        <el-card>
          <el-table :data="taskList" style="width: 100%" v-loading="loading">
            <el-table-column type="index" label="#" width="60" />
            <el-table-column prop="taskName" label="任务名称" min-width="150" />
            <el-table-column prop="reviewType" label="复盘类型" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ getTypeName(row.reviewType) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dataSourceId" label="数据源ID" width="100" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="resultSummary" label="结果摘要" min-width="200" show-overflow-tooltip />
            <el-table-column prop="createTime" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.createTime) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button 
                  type="primary" 
                  link 
                  size="small"
                  v-if="row.status === 'pending'"
                  @click="executeTask(row)"
                >
                  <el-icon><VideoPlay /></el-icon>
                  执行
                </el-button>
                <el-button 
                  type="success" 
                  link 
                  size="small"
                  v-if="row.status === 'completed'"
                  @click="viewReport(row)"
                >
                  <el-icon><DataAnalysis /></el-icon>
                  报告
                </el-button>
                <el-button 
                  type="warning" 
                  link 
                  size="small"
                  v-if="row.status === 'running'"
                  loading
                >
                  执行中
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty v-if="!loading && taskList.length === 0" description="暂无复盘任务">
            <el-button type="primary" @click="$router.push('/review/create')">创建复盘</el-button>
          </el-empty>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReviewTaskList, executeReviewTask } from '@/api'

const router = useRouter()

const loading = ref(false)
const taskList = ref([])

const activeMenu = computed(() => '/review')

const totalCount = computed(() => taskList.value.length)
const completedCount = computed(() => taskList.value.filter(t => t.status === 'completed').length)
const pendingCount = computed(() => taskList.value.filter(t => t.status === 'pending').length)
const failedCount = computed(() => taskList.value.filter(t => t.status === 'failed').length)

const getTypeName = (type) => {
  const types = {
    daily: '日复盘',
    weekly: '周复盘',
    monthly: '月复盘',
    custom: '自定义'
  }
  return types[type] || type
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

const loadTasks = async () => {
  loading.value = true
  try {
    const res = await getReviewTaskList()
    taskList.value = res.data || []
  } catch (error) {
    console.error('加载任务列表失败:', error)
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const executeTask = async (task) => {
  try {
    await executeReviewTask(task.id)
    ElMessage.success('任务已开始执行')
    loadTasks()
  } catch (error) {
    ElMessage.error('执行失败: ' + error.message)
  }
}

const viewReport = (task) => {
  router.push(`/review/result/${task.id}`)
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.review {
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
  max-width: 1200px;
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 24px;
  color: #303133;
  margin: 0;
}

.stat-row {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 12px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-info {
  flex: 1;
}

.stat-num {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
}

.stat-text {
  font-size: 14px;
  color: #909399;
}
</style>

