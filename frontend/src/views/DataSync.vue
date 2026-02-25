<template>
  <div class="data-sync">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>数据补充</span>
          <el-button type="primary" @click="handleCreateTask" :loading="creating">
            创建同步任务
          </el-button>
        </div>
      </template>

      <!-- 创建任务对话框 -->
      <el-dialog v-model="showForm" title="创建同步任务" width="600px" :close-on-click-modal="false">
        <el-form :model="formData" label-width="100px">
          <el-form-item label="任务名称">
            <el-input v-model="formData.taskName" placeholder="请输入任务名称（可选）" />
          </el-form-item>
          <el-form-item label="开始日期" required>
            <el-date-picker
              v-model="formData.startDate"
              type="date"
              placeholder="选择开始日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledStartDate"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="结束日期" required>
            <el-date-picker
              v-model="formData.endDate"
              type="date"
              placeholder="选择结束日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledEndDate"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="K线频率" required>
            <el-select v-model="formData.frequency" placeholder="选择K线频率" style="width: 100%">
              <el-option
                v-for="item in frequencyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              >
                <span>{{ item.label }}</span>
                <span style="color: #8492a6; font-size: 12px; margin-left: 10px">{{ item.description }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="股票范围">
            <el-select v-model="formData.stockType" placeholder="选择股票范围" style="width: 100%">
              <el-option
                v-for="item in stockTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              >
                <span>{{ item.label }}</span>
                <span style="color: #8492a6; font-size: 12px; margin-left: 10px">{{ item.description }}</span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showForm = false">取消</el-button>
          <el-button type="primary" @click="submitTask" :loading="creating">创建并启动</el-button>
        </template>
      </el-dialog

      <!-- 任务列表 -->
      <el-table :data="taskList" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="task_name" label="任务名称" min-width="180" />
        <el-table-column label="日期范围" min-width="200">
          <template #default="{ row }">
            {{ row.start_date }} ~ {{ row.end_date }}
          </template>
        </el-table-column>
        <el-table-column label="频率" width="100">
          <template #default="{ row }">
            <el-tag>{{ getFrequencyLabel(row.frequency) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="范围" width="100">
          <template #default="{ row }">
            <el-tag type="info">{{ getStockTypeLabel(row.stock_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress || 0"
              :status="getStatusType(row.status)"
              v-if="row.status === 'running' || row.status === 'completed'"
            />
            <el-tag :type="getStatusType(row.status)" v-else>
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="统计" width="150">
          <template #default="{ row }">
            <span v-if="row.processed_stocks > 0 || row.saved_records > 0">
              已处理: {{ row.processed_stocks }} 只 / 已保存: {{ row.saved_records }} 条
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="refreshTask(row)"
              :loading="row.id === refreshingId"
            >
              刷新
            </el-button>
            <el-button
              type="success"
              link
              size="small"
              @click="startTask(row)"
              v-if="row.status === 'pending' || row.status === 'stopped'"
              :loading="row.id === startingId"
            >
              启动
            </el-button>
            <el-button
              type="warning"
              link
              size="small"
              @click="stopTask(row)"
              v-if="row.status === 'running'"
              :loading="row.id === stoppingId"
            >
              停止
            </el-button>
            <el-button
              type="danger"
              link
              size="small"
              @click="deleteTask(row)"
              v-if="row.status !== 'running'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSyncTask,
  getSyncTaskList,
  getSyncTaskDetail,
  startSyncTask,
  stopSyncTask,
  deleteSyncTask,
  getFrequencyOptions,
  getStockTypeOptions
} from '@/api'

// 响应式数据
const loading = ref(false)
const creating = ref(false)
const startingId = ref(null)
const stoppingId = ref(null)
const refreshingId = ref(null)
const showForm = ref(false)
const taskList = ref([])
const frequencyOptions = ref([])
const stockTypeOptions = ref([])
const pollTimer = ref(null)

const formData = ref({
  taskName: '',
  startDate: '',
  endDate: '',
  frequency: 'daily',
  stockType: 'all'
})

// 获取频率选项
const loadFrequencyOptions = async () => {
  try {
    const res = await getFrequencyOptions()
    if (res.code === 200) {
      frequencyOptions.value = res.data
    }
  } catch (error) {
    console.error('获取频率选项失败:', error)
  }
}

// 获取股票类型选项
const loadStockTypeOptions = async () => {
  try {
    const res = await getStockTypeOptions()
    if (res.code === 200) {
      stockTypeOptions.value = res.data
    }
  } catch (error) {
    console.error('获取股票类型选项失败:', error)
  }
}

// 获取任务列表
const loadTaskList = async () => {
  try {
    const res = await getSyncTaskList({ limit: 50 })
    if (res.code === 200) {
      taskList.value = res.data
    }
  } catch (error) {
    console.error('获取任务列表失败:', error)
  }
}

// 刷新单个任务
const refreshTask = async (task) => {
  refreshingId.value = task.id
  try {
    const res = await getSyncTaskDetail(task.id)
    if (res.code === 200) {
      const index = taskList.value.findIndex(t => t.id === task.id)
      if (index !== -1) {
        taskList.value[index] = res.data
      }
    }
  } catch (error) {
    console.error('刷新任务失败:', error)
  } finally {
    refreshingId.value = null
  }
}

// 启动任务
const startTask = async (task) => {
  startingId.value = task.id
  try {
    const res = await startSyncTask(task.id)
    if (res.code === 200) {
      ElMessage.success('任务已启动')
      await refreshTask(task)
    } else {
      ElMessage.error(res.data.message || '启动任务失败')
    }
  } catch (error) {
    console.error('启动任务失败:', error)
    ElMessage.error('启动任务失败')
  } finally {
    startingId.value = null
  }
}

// 停止任务
const stopTask = async (task) => {
  stoppingId.value = task.id
  try {
    const res = await stopSyncTask(task.id)
    if (res.code === 200) {
      ElMessage.success('任务已停止，可继续从断点开始')
      await refreshTask(task)
    } else {
      ElMessage.error(res.data.message || '停止任务失败')
    }
  } catch (error) {
    console.error('停止任务失败:', error)
    ElMessage.error('停止任务失败')
  } finally {
    stoppingId.value = null
  }
}

// 删除任务
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务 "${task.task_name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )

    const res = await deleteSyncTask(task.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      taskList.value = taskList.value.filter(t => t.id !== task.id)
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除任务失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 创建任务
const handleCreateTask = () => {
  formData.value = {
    taskName: '',
    startDate: '',
    endDate: '',
    frequency: 'daily',
    stockType: 'all'
  }
  showForm.value = true
}

// 提交任务
const submitTask = async () => {
  if (!formData.value.startDate) {
    ElMessage.warning('请选择开始日期')
    return
  }
  if (!formData.value.endDate) {
    ElMessage.warning('请选择结束日期')
    return
  }

  creating.value = true
  try {
    const res = await createSyncTask(formData.value)
    if (res.code === 200) {
      ElMessage.success('任务创建成功')
      showForm.value = false
      await loadTaskList()
      // 自动启动任务
      await startTask(res.data)
    } else {
      ElMessage.error(res.message || '创建任务失败')
    }
  } catch (error) {
    console.error('创建任务失败:', error)
    ElMessage.error('创建任务失败')
  } finally {
    creating.value = false
  }
}

// 轮询更新任务状态
const pollTasks = () => {
  pollTimer.value = setInterval(async () => {
    const runningTasks = taskList.value.filter(t => t.status === 'running')
    for (const task of runningTasks) {
      await refreshTask(task)
    }
  }, 5000)
}

// 日期禁用
const disabledStartDate = (time) => {
  if (formData.value.endDate) {
    return time.getTime() > new Date(formData.value.endDate).getTime()
  }
  return time.getTime() > Date.now()
}

const disabledEndDate = (time) => {
  if (formData.value.startDate) {
    return time.getTime() < new Date(formData.value.startDate).getTime() - 86400000
  }
  return time.getTime() > Date.now()
}

// 辅助函数
const getFrequencyLabel = (value) => {
  const option = frequencyOptions.value.find(o => o.value === value)
  return option ? option.label : value
}

const getStockTypeLabel = (value) => {
  const option = stockTypeOptions.value.find(o => o.value === value)
  return option ? option.label : value
}

const getStatusType = (status) => {
  const map = {
    pending: 'info',
    running: '',
    completed: 'success',
    failed: 'exception'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 生命周期
onMounted(async () => {
  await loadFrequencyOptions()
  await loadStockTypeOptions()
  await loadTaskList()
  pollTasks()
})

onUnmounted(() => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
  }
})
</script>

<style scoped>
.data-sync {
  padding: 20px;
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

:deep(.el-table) {
  margin-top: 20px;
}
</style>

