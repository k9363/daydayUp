<template>
  <div class="create-review">
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
              <el-input 
                v-model="formData.taskName" 
                placeholder="请输入复盘任务名称"
                maxlength="100"
                show-word-limit
              />
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
            
            <el-form-item label="复盘类型" prop="reviewType">
              <el-radio-group v-model="formData.reviewType">
                <el-radio-button label="daily">日复盘</el-radio-button>
                <el-radio-button label="weekly">周复盘</el-radio-button>
                <el-radio-button label="monthly">月复盘</el-radio-button>
                <el-radio-button label="custom">自定义</el-radio-button>
              </el-radio-group>
            </el-form-item>
            
            <el-divider content-position="left">分析概览</el-divider>
            
            <el-descriptions :column="2" border>
              <el-descriptions-item label="数据来源">
                <el-tag type="info">Baostock A股日线</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="分析内容">
                <el-tag type="success">成交额TOP100 + 板块分布</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="数据缓存">
                <el-tag type="warning">相同日期只获取一次</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="输出">
                <el-tag type="primary">图表 + 数据表格</el-tag>
              </el-descriptions-item>
            </el-descriptions>
            
            <!-- 提交按钮 -->
            <el-form-item class="submit-section">
              <el-button @click="$router.back()">取消</el-button>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">
                <el-icon><Download /></el-icon>
                获取数据并分析
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
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
  reviewType: 'daily'
})

const rules = {
  taskName: [
    { required: true, message: '请输入任务名称', trigger: 'blur' }
  ],
  tradeDate: [
    { required: true, message: '请选择交易日期', trigger: 'change' }
  ]
}

const activeMenu = computed(() => '/review')

// 禁用未来日期
const disabledFutureDate = (time) => {
  return time.getTime() > Date.now()
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    submitting.value = true
    
    const res = await createBaostockReviewTask({
      taskName: formData.taskName,
      tradeDate: formData.tradeDate,
      reviewType: formData.reviewType
    })
    
    ElMessage.success('数据获取成功，正在分析...')
    router.push(`/report/${res.data.id}`)
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

.page-title {
  font-size: 18px;
  font-weight: 500;
}

.form-card {
  border-radius: 12px;
}

.submit-section {
  margin-top: 30px;
  text-align: center;
}
</style>
