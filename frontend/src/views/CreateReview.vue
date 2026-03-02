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
              description="此功能将从 Baostock 获取指定日期全A股市场的日线数据，筛选成交额前100名，按板块划分并生成图表分析报告。"
              show-icon
              style="margin-bottom: 20px;"
            />
            
            <el-form-item label="任务名称" prop="taskName">
          <el-input v-model="formData.taskName" placeholder="选择日期和复盘类型后自动生成" />
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
            
            <el-form-item class="submit-section">
              <el-button @click="$router.back()">取消</el-button>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">
                <el-icon><Download /></el-icon>
                获取数据并分析
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { createBaostockReviewTask } from '@/api'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)

// 表单数据
const formData = reactive({
  taskName: '',
  tradeDate: '',
  stockFilterType: 'top_by_amount',
  stockFilterValue: 100
})

// 自动生成任务名称
const generateTaskName = () => {
  if (formData.tradeDate) {
    formData.taskName = `${formData.tradeDate} 日复盘`
  }
}

// 监听交易日期和复盘类型变化，自动生成任务名称
watch(() => formData.tradeDate, generateTaskName)
watch(() => formData.reviewType, generateTaskName)

const rules = {
  tradeDate: [
    { required: true, message: '请选择交易日期', trigger: 'change' }
  ]
}

const disabledFutureDate = (time) => {
  return time.getTime() > Date.now()
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    submitting.value = true
    
    try {
      const stockFilter = formData.stockFilterType === 'all' 
        ? { type: 'all' }
        : { type: 'top_by_amount', value: formData.stockFilterValue }
      
      const res = await createBaostockReviewTask({
        taskName: formData.taskName,
        tradeDate: formData.tradeDate,
        reviewType: 'daily',
        stockFilter: stockFilter
      })
      
      ElMessage.success('任务已创建')
      router.push('/review')
    } catch (apiError) {
      // 检查是否是任务已存在的冲突
      if (apiError.code === 409) {
        // 弹窗确认是否覆盖
        const { ElMessageBox } = await import('element-plus')
        try {
          await ElMessageBox.confirm(
            `该交易日 ${formData.tradeDate} 已存在复盘任务「${apiError.data?.existingTaskName}」，是否覆盖？`,
            '任务冲突',
            {
              confirmButtonText: '覆盖并重新创建',
              cancelButtonText: '取消',
              type: 'warning'
            }
          )
          // 用户选择覆盖，重新创建
          const stockFilter = formData.stockFilterType === 'all' 
            ? { type: 'all' }
            : { type: 'top_by_amount', value: formData.stockFilterValue }
          
          await createBaostockReviewTask({
            taskName: formData.taskName,
            tradeDate: formData.tradeDate,
            reviewType: 'daily',
            overwrite: true,
            stockFilter: stockFilter
          })
          ElMessage.success('任务已覆盖重建')
          router.push('/review')
        } catch (confirmError) {
          // 用户取消
        }
      } else {
        throw apiError
      }
    }
  } catch (error) {
    console.error('创建任务失败:', error)
    ElMessage.error(error.message || '创建任务失败')
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
