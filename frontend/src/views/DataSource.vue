<template>
  <div class="data-manage">
        <div class="page-header">
          <h2>数据管理</h2>
        </div>
        
        <!-- 数据统计 -->
        <el-row :gutter="20" class="stats-row">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <el-icon :size="32" color="#409EFF"><Document /></el-icon>
                <div class="stat-info">
                  <span class="stat-value">{{ taskCount }}</span>
                  <span class="stat-label">复盘任务</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <el-icon :size="32" color="#67C23A"><DataLine /></el-icon>
                <div class="stat-info">
                  <span class="stat-value">{{ stockCount }}</span>
                  <span class="stat-label">股票数据</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <el-icon :size="32" color="#E6A23C"><Download /></el-icon>
                <div class="stat-info">
                  <span class="stat-value">{{ syncCount }}</span>
                  <span class="stat-label">同步任务</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <el-icon :size="32" color="#F56C6C"><Connection /></el-icon>
                <div class="stat-info">
                  <span class="stat-value">Baostock</span>
                  <span class="stat-label">数据源</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 快捷操作 -->
        <el-card class="action-card">
          <template #header>
            <div class="card-header">
              <span>快捷操作</span>
            </div>
          </template>
          
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="action-item" @click="$router.push('/review/create')">
                <el-icon :size="48" color="#409EFF"><Plus /></el-icon>
                <span>创建复盘</span>
                <p>使用Baostock数据创建新的复盘任务</p>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="action-item" @click="$router.push('/review')">
                <el-icon :size="48" color="#67C23A"><List /></el-icon>
                <span>查看复盘</span>
                <p>查看和管理所有复盘任务</p>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="action-item" @click="$router.push('/sync')">
                <el-icon :size="48" color="#E6A23C"><Refresh /></el-icon>
                <span>同步数据</span>
                <p>从Baostock同步股票历史数据</p>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 说明 -->
        <el-card class="info-card">
          <template #header>
            <span>数据源说明</span>
          </template>
          <el-empty description="已简化为Baostock单一数据源">
            <template #description>
              <p>系统目前使用 <strong>Baostock</strong> 作为唯一的数据源。</p>
              <p>无需手动上传数据，直接在创建复盘任务时选择日期即可自动获取股票数据。</p>
            </template>
            <el-button type="primary" @click="$router.push('/review/create')">
              立即创建复盘
            </el-button>
          </el-empty>
        </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getReviewTaskList, getSyncTaskList } from '@/api'
import { Document, DataLine, Download, Connection, Plus, List, Refresh } from '@element-plus/icons-vue'

const router = useRouter()

const loading = ref(false)
const taskCount = ref(0)
const stockCount = ref(0)
const syncCount = ref(0)

// 加载统计数据
const loadStats = async () => {
  loading.value = true
  try {
    // 获取复盘任务数量
    const tasksRes = await getReviewTaskList({ includeCompleted: false })
    if (tasksRes.data.code === 200) {
      taskCount.value = tasksRes.data.data?.length || 0
    }
    
    // 获取同步任务数量
    const syncRes = await getSyncTaskList({ limit: 100 })
    if (syncRes.data.code === 200) {
      syncCount.value = syncRes.data.data?.length || 0
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.data-manage {
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
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 24px;
  color: #303133;
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.action-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 18px;
  font-weight: bold;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.3s;
}

.action-item:hover {
  background: #f5f7fa;
}

.action-item span {
  font-size: 16px;
  font-weight: 500;
  margin-top: 12px;
  color: #303133;
}

.action-item p {
  font-size: 13px;
  color: #909399;
  margin: 8px 0 0 0;
  text-align: center;
}

.info-card {
  margin-top: 20px;
}

.info-card :deep(.el-card__header) {
  font-weight: bold;
}
</style>
