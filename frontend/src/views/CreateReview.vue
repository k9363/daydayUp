<template>
  <div class="create-review">
    <div class="page-header">
      <el-page-header @back="$router.back()">
        <template #content>
          <span class="page-title">创建复盘任务</span>
        </template>
      </el-page-header>
    </div>

    <el-card class="form-card">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px">
        <el-divider content-position="left">Baostock A股日线数据</el-divider>

        <el-alert
          title="功能说明"
          type="info"
          description="从 Baostock 获取指定日期（或日期范围内每个交易日）全A股市场的日线数据，筛选后按板块划分并生成图表分析报告。"
          show-icon
          style="margin-bottom: 20px;"
        />

        <!-- 模式切换 -->
        <el-form-item label="复盘模式">
          <el-radio-group v-model="mode" @change="onModeChange">
            <el-radio-button value="single">单日复盘</el-radio-button>
            <el-radio-button value="range">日期范围</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 单日模式 -->
        <template v-if="mode === 'single'">
          <el-form-item label="任务名称" prop="taskName">
            <el-input v-model="formData.taskName" placeholder="选择日期后自动生成" />
          </el-form-item>

          <el-form-item label="交易日期" prop="tradeDate">
            <el-date-picker
              v-model="formData.tradeDate"
              type="date"
              placeholder="选择交易日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledFutureDate"
              style="width: 100%"
            />
          </el-form-item>
        </template>

        <!-- 日期范围模式 -->
        <template v-else>
          <el-form-item label="日期范围" prop="dateRange">
            <el-date-picker
              v-model="formData.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledFutureDate"
              style="width: 100%"
            />
          </el-form-item>
          <el-alert
            v-if="estimatedDays > 0"
            :title="`预计创建 ${estimatedDays} 个工作日的复盘任务（已排除周末），将依次顺序执行`"
            type="warning"
            show-icon
            style="margin-bottom: 16px;"
          />
        </template>

        <el-form-item label="股票筛选">
          <el-select v-model="formData.stockFilterType" style="width: 40%; margin-right: 10px;">
            <el-option label="成交额前N名" value="top_by_amount" />
            <el-option label="全部A股" value="all" />
          </el-select>
          <el-input-number
            v-if="formData.stockFilterType === 'top_by_amount'"
            v-model="formData.stockFilterValue"
            :min="10"
            :max="500"
            :step="10"
            style="width: 40%"
          />
          <span v-if="formData.stockFilterType === 'top_by_amount'" style="margin-left: 10px;">只</span>
        </el-form-item>

        <!-- 日期范围模式：覆盖选项 -->
        <el-form-item v-if="mode === 'range'" label="已存在任务">
          <el-checkbox v-model="formData.overwrite">覆盖重建（跳过不覆盖则仅创建缺失日期）</el-checkbox>
        </el-form-item>

        <el-form-item class="submit-section">
          <el-button @click="$router.back()">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            <el-icon><Download /></el-icon>
            {{ mode === 'single' ? '获取数据并分析' : '批量创建并执行' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { createBaostockReviewTask, createBaostockBatchReviewTask } from '@/api'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)
const mode = ref('single')  // 'single' | 'range'

const formData = reactive({
  taskName: '',
  tradeDate: '',
  dateRange: [],
  stockFilterType: 'top_by_amount',
  stockFilterValue: 100,
  overwrite: false
})

// 估算工作日数量
const estimatedDays = computed(() => {
  if (!formData.dateRange || formData.dateRange.length !== 2) return 0
  const [s, e] = formData.dateRange
  if (!s || !e) return 0
  let count = 0
  const cur = new Date(s)
  const end = new Date(e)
  while (cur <= end) {
    if (cur.getDay() !== 0 && cur.getDay() !== 6) count++
    cur.setDate(cur.getDate() + 1)
  }
  return count
})

const onModeChange = () => {
  formData.tradeDate = ''
  formData.dateRange = []
  formData.taskName = ''
}

watch(() => formData.tradeDate, (val) => {
  if (val) formData.taskName = `${val} 日复盘`
})

const rules = computed(() => ({
  tradeDate: mode.value === 'single'
    ? [{ required: true, message: '请选择交易日期', trigger: 'change' }]
    : [],
  dateRange: mode.value === 'range'
    ? [{ required: true, type: 'array', len: 2, message: '请选择日期范围', trigger: 'change' }]
    : []
}))

const disabledFutureDate = (time) => time.getTime() > Date.now()

// ---- 单日提交 ----
const handleSingleSubmit = async () => {
  const stockFilter = formData.stockFilterType === 'all'
    ? { type: 'all' }
    : { type: 'top_by_amount', value: formData.stockFilterValue }

  try {
    await createBaostockReviewTask({
      taskName: formData.taskName,
      tradeDate: formData.tradeDate,
      reviewType: 'daily',
      stockFilter
    })
    ElMessage.success('任务已创建')
    router.push('/review')
  } catch (apiError) {
    if (apiError.code === 409) {
      try {
        await ElMessageBox.confirm(
          `该交易日 ${formData.tradeDate} 已存在复盘任务「${apiError.data?.existingTaskName}」，是否覆盖？`,
          '任务冲突',
          { confirmButtonText: '覆盖并重新创建', cancelButtonText: '取消', type: 'warning' }
        )
        await createBaostockReviewTask({
          taskName: formData.taskName,
          tradeDate: formData.tradeDate,
          reviewType: 'daily',
          overwrite: true,
          stockFilter
        })
        ElMessage.success('任务已覆盖重建')
        router.push('/review')
      } catch (_) { /* 用户取消 */ }
    } else {
      throw apiError
    }
  }
}

// ---- 批量提交 ----
const handleBatchSubmit = async () => {
  if (!formData.dateRange || formData.dateRange.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }
  const [startDate, endDate] = formData.dateRange
  const stockFilter = formData.stockFilterType === 'all'
    ? { type: 'all' }
    : { type: 'top_by_amount', value: formData.stockFilterValue }

  const res = await createBaostockBatchReviewTask({
    startDate,
    endDate,
    stockFilter,
    overwrite: formData.overwrite
  })

  if (res.code === 200) {
    const { created, skipped } = res.data
    ElMessage.success(
      `已创建 ${created} 个任务并开始后台执行` +
      (skipped.length ? `，跳过 ${skipped.length} 个已存在日期` : '')
    )
    router.push('/review')
  } else {
    ElMessage.error(res.message || '批量创建失败')
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    if (mode.value === 'single') {
      await handleSingleSubmit()
    } else {
      await handleBatchSubmit()
    }
  } catch (error) {
    if (error !== false) {
      console.error('创建任务失败:', error)
      ElMessage.error(error.message || '创建任务失败')
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.create-review {
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.form-card {
  border-radius: 12px;
}

.submit-section {
  margin-top: 40px;
  text-align: center;
}
</style>
