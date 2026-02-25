<template>
  <div class="delivery-upload">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>上传交割单</span>
        </div>
      </template>
      
      <!-- 上传区域 -->
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :action="uploadUrl"
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-success="handleSuccess"
        :on-error="handleError"
        :before-upload="beforeUpload"
        accept=".txt,.csv,.xls,.xlsx"
        :limit="1"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .txt, .csv, .xls, .xlsx 格式的交割单文件（Tab分隔）
          </div>
        </template>
      </el-upload>
      
      <div class="upload-actions">
        <el-button type="primary" @click="submitUpload" :loading="uploading">
          开始导入
        </el-button>
        <el-button @click="resetUpload">重置</el-button>
      </div>
      
      <!-- 导入结果 -->
      <el-alert
        v-if="importResult"
        :title="importResult.message"
        :type="importResult.code === 200 ? 'success' : 'error'"
        show-icon
        class="result-alert"
      >
        <template #default>
          <div v-if="importResult.code === 200 && importResult.data">
            <div>成功导入: {{ importResult.data.imported }} 条</div>
            <div v-if="importResult.data.skipped_letters > 0" class="skip-info">
              跳过（含字母）: {{ importResult.data.skipped_letters }} 条
            </div>
            <div v-if="importResult.data.skipped_apply_allotment > 0" class="skip-info">
              跳过（申请配号）: {{ importResult.data.skipped_apply_allotment }} 条
            </div>
            <div v-if="importResult.data.skipped_duplicate > 0" class="skip-info">
              跳过（重复）: {{ importResult.data.skipped_duplicate }} 条
            </div>
            <div v-if="importResult.data.error > 0" class="error-info">
              错误: {{ importResult.data.error }} 条
            </div>
          </div>
        </template>
      </el-alert>
    </el-card>
    
    <!-- 交割单统计 -->
    <el-card class="stats-card" v-if="stats">
      <template #header>
        <div class="card-header">
          <span>交割单统计</span>
          <el-button type="primary" link @click="loadStats">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">总记录数</div>
          </div>
        </el-col>
        <el-col :span="18">
          <div class="stat-item">
            <div class="stat-label">操作类型分布</div>
            <div class="operation-stats">
              <el-tag 
                v-for="op in stats.operations" 
                :key="op.operation"
                type="info"
                class="operation-tag"
              >
                {{ op.operation }}: {{ op.count }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <!-- 文件格式说明 -->
    <el-card class="help-card">
      <template #header>
        <span>文件格式说明</span>
      </template>
      <el-alert
        title="交割单文件格式要求"
        type="info"
        :closable="false"
      >
        <template #default>
          <div class="format-help">
            <p>支持以下格式的文件：</p>
            <ul>
              <li><strong>Excel文件：</strong> .xls, .xlsx 格式</li>
              <li><strong>文本文件：</strong> .txt, .csv 格式（Tab分隔）</li>
            </ul>
            <p>文件应包含以下字段（按顺序）：</p>
            <ol>
              <li>成交日期 (YYYYMMDD)</li>
              <li>成交时间 (HH:MM:SS)</li>
              <li>证券代码</li>
              <li>证券名称</li>
              <li>操作类型（买入/卖出等）</li>
              <li>成交数量</li>
              <li>成交编号</li>
              <li>成交价格</li>
              <li>成交金额</li>
              <li>余额</li>
              <li>股票余额</li>
              <li>发生金额</li>
              <li>佣金</li>
              <li>印花税</li>
              <li>其他杂费</li>
              <li>资金余额</li>
              <li>本次金额</li>
              <li>合同编号</li>
              <li>其他费</li>
              <li>过户费</li>
              <li>交易市场</li>
            </ol>
          </div>
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Refresh } from '@element-plus/icons-vue'
import { importDelivery, getDeliveryStats } from '@/api'

const uploadRef = ref(null)
const uploading = ref(false)
const importResult = ref(null)
const fileList = ref([])
const stats = ref(null)

const uploadUrl = '/api/metadata/delivery/import'

const beforeUpload = (file) => {
  // 支持 txt, csv, xls, xlsx 格式
  const allowedTypes = ['.txt', '.csv', '.xls', '.xlsx']
  const fileName = file.name.toLowerCase()
  const isAllowed = allowedTypes.some(type => fileName.endsWith(type))
  
  if (!isAllowed) {
    ElMessage.error('只能上传 .txt、.csv、.xls 或 .xlsx 格式的文件')
    return false
  }
  return true
}

const handleFileChange = (file, files) => {
  fileList.value = files
}

const submitUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  uploading.value = true
  importResult.value = null
  
  try {
    const file = fileList.value[0].raw
    const res = await importDelivery(file)
    importResult.value = res
    
    if (res.code === 200) {
      ElMessage.success('导入成功')
      loadStats()
    } else {
      ElMessage.error(res.message || '导入失败')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败: ' + (error.message || '未知错误'))
    importResult.value = {
      code: 500,
      message: error.message || '导入失败',
      data: null
    }
  } finally {
    uploading.value = false
  }
}

const resetUpload = () => {
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  fileList.value = []
  importResult.value = null
}

const handleSuccess = (response) => {
  console.log('上传成功:', response)
}

const handleError = (error) => {
  console.error('上传失败:', error)
  ElMessage.error('上传失败: ' + error.message)
}

const loadStats = async () => {
  try {
    const res = await getDeliveryStats()
    if (res.code === 200) {
      stats.value = res.data
    }
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.delivery-upload {
  max-width: 900px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 18px;
  font-weight: 600;
}

.upload-area {
  margin-bottom: 20px;
}

.upload-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.result-alert {
  margin-bottom: 20px;
}

.skip-info {
  color: #909399;
  font-size: 12px;
}

.error-info {
  color: #F56C6C;
  font-size: 12px;
}

.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #409EFF;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.operation-stats {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.operation-tag {
  margin: 2px;
}

.help-card {
  margin-top: 20px;
}

.format-help {
  padding: 10px 0;
}

.format-help ol {
  margin: 10px 0;
  padding-left: 20px;
}

.format-help li {
  margin: 5px 0;
  color: #606266;
}
</style>
