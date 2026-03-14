<template>
  <div class="review">
        <div class="page-header">
      <h2>每日复盘</h2>
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
                  <div class="stat-num">{{ stats.total }}</div>
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
                  <div class="stat-num">{{ stats.completed }}</div>
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
                  <div class="stat-num">{{ stats.pending }}</div>
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
                  <div class="stat-num">{{ stats.failed }}</div>
                  <div class="stat-text">失败</div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 筛选和分页 -->
        <el-card class="filter-card">
          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="复盘日期">
              <el-date-picker
                v-model="filterForm.tradeDate"
                type="date"
                placeholder="选择日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                clearable
                style="width: 160px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">
                <el-icon><Search /></el-icon>
                查询
              </el-button>
              <el-button @click="handleReset">
                <el-icon><RefreshRight /></el-icon>
                重置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 任务列表 -->
        <el-card>
          <el-table :data="taskList" style="width: 100%" v-loading="loading">
            <el-table-column type="index" label="#" width="60" />
            <el-table-column prop="taskName" label="任务名称" min-width="150" />
            <el-table-column prop="tradeDate" label="复盘日期" width="120">
              <template #default="{ row }">
                {{ row.tradeDate || '-' }}
              </template>
            </el-table-column>
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
        <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              v-if="row.status === 'completed'"
              @click="viewResult(row)"
            >
              <el-icon><DataAnalysis /></el-icon>
              查看结果
            </el-button>
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
                  type="warning"
                  link
                  size="small"
                  v-if="row.status === 'running'"
                  loading
                >
                  执行中
                </el-button>
            <el-button
              type="danger"
              link
              size="small"
              @click="deleteTask(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="pagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handlePageChange"
            />
          </div>

          <el-empty v-if="!loading && taskList.length === 0" description="暂无复盘任务">
            <el-button type="primary" @click="$router.push('/review/create')">创建复盘</el-button>
          </el-empty>
        </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, DataAnalysis, Delete, Search, RefreshRight } from '@element-plus/icons-vue'
import { getReviewTaskList, executeReviewTask, deleteReviewTask } from '@/api'

const router = useRouter()

const loading = ref(false)
const taskList = ref([])

// 筛选表单
const filterForm = reactive({
  tradeDate: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 统计数据
const stats = computed(() => {
  // 由于分页后数据不完整，暂时显示当前页统计，后续可调接口获取完整统计
  const list = taskList.value
  return {
    total: pagination.total,
    completed: list.filter(t => t.status === 'completed').length,
    pending: list.filter(t => t.status === 'pending').length,
    failed: list.filter(t => t.status === 'failed').length
  }
})

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
    const params = {
      includeCompleted: true,
      page: pagination.page,
      pageSize: pagination.pageSize
    }
    if (filterForm.tradeDate) {
      params.tradeDate = filterForm.tradeDate
    }
    const res = await getReviewTaskList(params)
    taskList.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('加载任务列表失败:', error)
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadTasks()
}

const handleReset = () => {
  filterForm.tradeDate = ''
  pagination.page = 1
  loadTasks()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadTasks()
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadTasks()
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

const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务「${task.taskName}」吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await deleteReviewTask(task.id)
    ElMessage.success('任务已删除')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

const viewResult = (task) => {
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

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
