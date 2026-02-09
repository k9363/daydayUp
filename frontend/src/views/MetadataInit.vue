<template>
  <div class="metadata-init">
    <!-- 统计概览 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="股票总数" :value="summary.stock_basic_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="行业板块" :value="summary.sector_industry_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="概念板块" :value="summary.sector_concept_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="关联总数" :value="summary.stock_sector_relation_count" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 初始化操作 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>元数据初始化</span>
          <el-tag type="info">基于东方财富数据源</el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <!-- 股票初始化 -->
        <el-col :span="12">
          <el-card shadow="never" class="init-card">
            <template #header>
              <div class="init-card-header">
                <el-icon><Document /></el-icon>
                <span>股票基础信息</span>
              </div>
            </template>
            <p class="description">初始化全部A股股票的基本信息（代码、名称、市场类型等）</p>
            <el-button
              type="primary"
              @click="initStock"
              :loading="stockLoading"
            >
              {{ stockResult ? '已初始化' : '开始初始化' }}
            </el-button>
            <div v-if="stockResult" class="result-info">
              <el-tag type="success">新增 {{ stockResult.added }} 只</el-tag>
              <el-tag type="warning">更新 {{ stockResult.updated }} 只</el-tag>
            </div>
          </el-card>
        </el-col>

        <!-- 行业+概念板块初始化 -->
        <el-col :span="12">
          <el-card shadow="never" class="init-card">
            <template #header>
              <div class="init-card-header">
                <el-icon><Grid /></el-icon>
                <span>行业+概念板块</span>
              </div>
            </template>
            <p class="description">初始化行业板块、概念板块及其成分股关联（一次性获取）</p>
            <el-button
              type="success"
              @click="initAllSectors"
              :loading="sectorLoading"
            >
              {{ sectorResult ? '已初始化' : '开始初始化' }}
            </el-button>
            <div v-if="sectorResult" class="result-info">
              <el-tag>行业 {{ sectorResult.industry.sectors.added }} 个</el-tag>
              <el-tag>概念 {{ sectorResult.concept.sectors.added }} 个</el-tag>
              <el-tag type="info">关联 {{ sectorResult.industry.relations.added + sectorResult.concept.relations.added }} 条</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 板块列表 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>板块列表</span>
          <el-radio-group v-model="sectorType" size="small" @change="loadSectors">
            <el-radio-button label="industry">行业</el-radio-button>
            <el-radio-button label="concept">概念</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-table :data="sectorList" v-loading="sectorLoading" stripe style="width: 100%">
        <el-table-column prop="sector_code" label="板块代码" width="180" />
        <el-table-column prop="sector_name" label="板块名称" min-width="200" />
        <el-table-column prop="stock_count" label="成分股数量" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.stock_count }} 只</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="update_time" label="更新时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.update_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="showSectorStocks(row)"
            >
              查看成分股
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 成分股弹窗 -->
    <el-dialog
      v-model="showStockDialog"
      :title="`${currentSector?.sector_name} - 成分股列表`"
      width="800px"
    >
      <el-table :data="sectorStocks" v-loading="stocksLoading" max-height="400" style="width: 100%">
        <el-table-column prop="stock.stock_code" label="股票代码" width="120" />
        <el-table-column prop="stock.stock_name" label="股票名称" min-width="150" />
        <el-table-column prop="is_main" label="是否主营" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_main ? 'success' : 'info'" size="small">
              {{ row.is_main ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="weight" label="权重" width="100">
          <template #default="{ row }">
            {{ row.weight }}%
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Grid } from '@element-plus/icons-vue'
import {
  getMetadataSummary,
  initStockFromAKShare,
  initIndustryFromAKShare,
  initConceptFromAKShare,
  getSectors,
  getSectorStocks
} from '@/api'

// 统计数据
const summary = ref({
  stock_basic_count: 0,
  sector_industry_count: 0,
  sector_concept_count: 0,
  sector_area_count: 0,
  stock_sector_relation_count: 0
})

// 初始化状态
const stockLoading = ref(false)
const stockResult = ref(null)
const sectorLoading = ref(false)
const sectorResult = ref(null)

// 板块列表
const sectorType = ref('industry')
const sectorList = ref([])

// 成分股弹窗
const showStockDialog = ref(false)
const currentSector = ref(null)
const sectorStocks = ref([])
const stocksLoading = ref(false)

// 加载统计
const loadSummary = async () => {
  try {
    const res = await getMetadataSummary()
    if (res.data.code === 200) {
      summary.value = res.data.data
    }
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

// 初始化股票
const initStock = async () => {
  stockLoading.value = true
  try {
    const res = await initStockFromAKShare({ update_existing: true })
    if (res.data.code === 200) {
      stockResult.value = res.data.data
      ElMessage.success('股票信息初始化完成')
      await loadSummary()
    } else {
      ElMessage.error(res.data.message || '初始化失败')
    }
  } catch (error) {
    console.error('初始化股票失败:', error)
    ElMessage.error('初始化失败')
  } finally {
    stockLoading.value = false
  }
}

// 初始化全部板块（行业+概念）
const initAllSectors = async () => {
  sectorLoading.value = true
  sectorResult.value = null
  try {
    // 1. 先初始化行业板块
    const industryRes = await initIndustryFromAKShare()
    if (industryRes.data.code !== 200) {
      ElMessage.error(industryRes.data.message || '行业板块初始化失败')
      sectorLoading.value = false
      return
    }

    // 2. 再初始化概念板块
    const conceptRes = await initConceptFromAKShare()
    if (conceptRes.data.code !== 200) {
      ElMessage.error(conceptRes.data.message || '概念板块初始化失败')
      sectorLoading.value = false
      return
    }

    sectorResult.value = {
      industry: industryRes.data.data,
      concept: conceptRes.data.data
    }
    ElMessage.success('全部板块初始化完成')
    await loadSummary()
    await loadSectors()
  } catch (error) {
    console.error('初始化板块失败:', error)
    ElMessage.error('初始化失败')
  } finally {
    sectorLoading.value = false
  }
}

// 加载板块列表
const loadSectors = async () => {
  sectorLoading.value = true
  try {
    const res = await getSectors({ type: sectorType.value })
    if (res.data.code === 200) {
      sectorList.value = res.data.data
    }
  } catch (error) {
    console.error('获取板块列表失败:', error)
  } finally {
    sectorLoading.value = false
  }
}

// 查看成分股
const showSectorStocks = async (sector) => {
  currentSector.value = sector
  showStockDialog.value = true
  stocksLoading.value = true
  try {
    const res = await getSectorStocks(sector.sector_code)
    if (res.data.code === 200) {
      sectorStocks.value = res.data.data.stocks || []
    }
  } catch (error) {
    console.error('获取成分股失败:', error)
  } finally {
    stocksLoading.value = false
  }
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 生命周期
onMounted(async () => {
  await loadSummary()
  await loadSectors()
})
</script>

<style scoped>
.metadata-init {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
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

.init-card {
  height: 100%;
}

.init-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
}

.init-card .description {
  color: #909399;
  font-size: 13px;
  margin: 12px 0;
  min-height: 40px;
}

.init-card .el-button {
  width: 100%;
}

.result-info {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-info .el-tag {
  font-size: 12px;
}

:deep(.el-table) {
  margin-top: 20px;
}
</style>
