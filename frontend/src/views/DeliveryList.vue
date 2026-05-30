<template>
  <div class="delivery-list">
    <el-row :gutter="20">
      <!-- 左侧股票列表 -->
      <el-col :span="7">
        <el-card class="stock-card">
          <template #header>
            <div class="card-header">
              <span>股票列表</span>
              <el-button type="primary" link @click="loadStocks">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>
          
          <!-- 筛选区域 -->
          <div class="filter-section">
            <!-- 时间筛选 -->
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
              size="small"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              class="date-filter"
              @change="handleDateChange"
            />
            <!-- 重置按钮 -->
            <el-button 
              v-if="dateRange || stockSearch" 
              size="small" 
              text 
              @click="resetFilters"
            >
              重置
            </el-button>
          </div>
          
          <!-- 搜索框 -->
          <el-input
            v-model="stockSearch"
            placeholder="搜索股票代码或名称"
            clearable
            prefix-icon="Search"
            class="stock-search"
            @input="handleSearchInput"
          />
          
          <!-- 股票列表 -->
          <el-table
            :data="filteredStocks"
            height="calc(100vh - 330px)"
            highlight-current-row
            @current-change="handleStockSelect"
            row-key="security_code"
            v-loading="loadingStocks"
            class="stock-table"
            size="small"
          >
            <el-table-column prop="security_code" label="代码" width="80" />
            <el-table-column prop="security_name" label="名称" width="70" />
            <el-table-column prop="trade_count" label="次数" width="65" align="center">
              <template #header>
                <div class="sortable-header" @click="handleSortClick('trade_count')">
                  <span :class="{ 'active-sort': sortColumn === 'trade_count' }">次数</span>
                  <span class="sort-icons">
                    <i :class="['sort-up', { active: sortColumn === 'trade_count' && sortOrder === 'asc' }]">▲</i>
                    <i :class="['sort-down', { active: sortColumn === 'trade_count' && sortOrder === 'desc' }]">▼</i>
                  </span>
                </div>
              </template>
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.trade_count }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="profit" label="获利" min-width="95" align="center">
              <template #header>
                <div class="sortable-header" @click="handleSortClick('profit')">
                  <span :class="{ 'active-sort': sortColumn === 'profit' }">获利</span>
                  <span class="sort-icons">
                    <i :class="['sort-up', { active: sortColumn === 'profit' && sortOrder === 'asc' }]">▲</i>
                    <i :class="['sort-down', { active: sortColumn === 'profit' && sortOrder === 'desc' }]">▼</i>
                  </span>
                </div>
              </template>
              <template #default="{ row }">
                <span :class="row.profit > 0 ? 'profit-positive' : row.profit < 0 ? 'profit-negative' : 'profit-zero'">
                  {{ row.profit > 0 ? '+' : '' }}{{ formatAmount(row.profit) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      
      <!-- 右侧交割单详情 -->
      <el-col :span="17">
        <!-- 股票汇总信息 -->
        <el-card class="summary-card" v-if="selectedStock">
          <template #header>
            <div class="card-header">
              <span>{{ selectedStockInfo.security_name }} ({{ selectedStockInfo.security_code }})</span>
            </div>
          </template>
          
          <el-row :gutter="20">
            <el-col :span="4">
              <div class="summary-item">
                <div class="summary-value">{{ stockSummary.total_trades || 0 }}</div>
                <div class="summary-label">交易次数</div>
              </div>
            </el-col>
            <el-col :span="5">
              <div class="summary-item">
                <div class="summary-value" :class="totalProfit >= 0 ? 'profit-positive' : 'profit-negative'">
                  {{ totalProfit > 0 ? '+' : '' }}¥{{ formatAmount(totalProfit) }}
                </div>
                <div class="summary-label">总获利</div>
              </div>
            </el-col>
            <el-col :span="5">
              <div class="summary-item">
                <div class="summary-value">¥{{ formatAmount(stockSummary.total_amount) }}</div>
                <div class="summary-label">总成交金额</div>
              </div>
            </el-col>
            <el-col :span="5">
              <div class="summary-item">
                <div class="summary-value date-value">{{ stockSummary.date_range?.earliest || '-' }}</div>
                <div class="summary-label">最早交易日</div>
              </div>
            </el-col>
            <el-col :span="5">
              <div class="summary-item">
                <div class="summary-value date-value">{{ stockSummary.date_range?.latest || '-' }}</div>
                <div class="summary-label">最新交易日</div>
              </div>
            </el-col>
          </el-row>
          
          <!-- 操作类型统计 -->
          <div class="operation-summary" v-if="stockSummary.operations">
            <div class="operation-title">操作类型分布</div>
            <div class="operation-tags">
              <el-tag 
                v-for="(info, op) in stockSummary.operations" 
                :key="op"
                :type="getOperationType(op)"
                class="op-tag"
              >
                {{ op }}: {{ info.count }}次 / ¥{{ formatAmount(info.total_amount) }}
              </el-tag>
            </div>
          </div>
        </el-card>
        
        <!-- 交割单列表 -->
        <el-card class="delivery-card" v-if="selectedStock">
          <template #header>
            <div class="card-header">
              <span>交割单明细</span>
              <div class="header-filters">
                <el-select 
                  v-model="operationFilter" 
                  placeholder="筛选操作类型" 
                  clearable 
                  size="small"
                  style="width: 130px"
                >
                  <el-option label="全部" value="" />
                  <el-option label="证券买入" value="证券买入" />
                  <el-option label="证券卖出" value="证券卖出" />
                </el-select>
              </div>
            </div>
          </template>
          
          <el-table
            :data="deliveryList"
            height="calc(100vh - 480px)"
            v-loading="loadingDeliveries"
            stripe
            size="small"
          >
            <el-table-column prop="trade_date" label="日期" width="90" />
            <el-table-column prop="trade_time" label="时间" width="70" />
            <el-table-column prop="security_code" label="代码" width="80" />
            <el-table-column prop="security_name" label="名称" width="70" />
            <el-table-column prop="operation" label="操作" width="75">
              <template #default="{ row }">
                <el-tag :type="getOperationType(row.operation)" size="small">
                  {{ row.operation }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" width="65" align="right" />
            <el-table-column prop="price" label="价格" width="70" align="right">
              <template #default="{ row }">
                {{ row.price?.toFixed(3) || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="95" align="right">
              <template #default="{ row }">
                ¥{{ formatAmount(row.amount) }}
              </template>
            </el-table-column>
            <el-table-column prop="commission" label="佣金" width="60" align="right">
              <template #default="{ row }">
                {{ row.commission?.toFixed(2) || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="复盘记录" min-width="320">
              <template #default="{ row }">
                <div class="review-cell">
                  <span
                    class="review-preview"
                    :title="row.review_note || '点击添加复盘记录'"
                  >{{ row.review_note || '点击添加' }}</span>
                  <el-button
                    size="small"
                    link
                    type="primary"
                    @click="openNoteDialog(row)"
                    class="review-btn"
                  >{{ row.review_note ? '编辑' : '添加' }}</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          
          <!-- 分页 -->
          <div class="pagination-wrapper" v-if="deliveryTotal > pageSize">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="deliveryTotal"
              layout="prev, pager, next"
              @current-change="handlePageChange"
            />
          </div>
        </el-card>

        <!-- 复盘记录编辑弹窗 -->
        <el-dialog
          v-model="noteDialogVisible"
          :title="`复盘记录 - ${currentNoteRow?.trade_date || ''} ${currentNoteRow?.security_name || ''}`"
          width="580px"
          destroy-on-close
        >
          <div class="note-dialog-tip">
            <span>操作：</span>
            <el-tag :type="getOperationType(currentNoteRow?.operation)" size="small">
              {{ currentNoteRow?.operation }}
            </el-tag>
            <span style="margin-left: 12px">数量：{{ currentNoteRow?.quantity }} 股</span>
            <span style="margin-left: 12px">价格：¥{{ currentNoteRow?.price?.toFixed(3) }}</span>
          </div>
          <el-input
            v-model="noteDialogContent"
            type="textarea"
            :rows="7"
            placeholder="记录这笔操作的复盘心得..."
            resize="vertical"
            class="note-textarea"
            @input="noteDialogDirty = true"
          />
          <template #footer>
            <span class="dialog-tip" v-if="noteDialogDirty">有未保存的修改</span>
            <div style="flex: 1" />
            <el-button @click="noteDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="noteSaving" @click="saveNoteDialog">保存</el-button>
          </template>
        </el-dialog>
        
        <!-- 未选择股票时的提示 -->
        <el-empty 
          v-if="!selectedStock" 
          description="请先选择左侧股票查看交割单"
          class="empty-tip"
        />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getDeliveryStocks, getDeliveryByStock, getDeliverySummary, updateDeliveryReviewNote } from '@/api'

// 股票列表相关
const loadingStocks = ref(false)
const stocks = ref([])
const stockSearch = ref('')
const selectedStock = ref(null)
const selectedStockInfo = ref({})
const dateRange = ref(null)
const sortColumn = ref('latest_date')  // 排序字段
const sortOrder = ref('desc')  // 排序方向

// 交割单列表相关
const loadingDeliveries = ref(false)
const deliveryList = ref([])
const deliveryTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const operationFilter = ref('')

// 复盘记录弹窗相关
const noteDialogVisible = ref(false)
const currentNoteRow = ref(null)
const noteDialogContent = ref('')
const noteDialogDirty = ref(false)
const noteSaving = ref(false)

// 汇总信息
const stockSummary = ref({})

// 计算总获利
const totalProfit = computed(() => {
  if (!stockSummary.value.operations) return 0
  const ops = stockSummary.value.operations
  const sellAmount = ops['证券卖出']?.total_amount || 0
  const buyAmount = ops['证券买入']?.total_amount || 0
  return sellAmount - buyAmount
})

// 过滤和排序后的股票列表
const filteredStocks = computed(() => {
  let result = stocks.value
  
  // 搜索过滤
  if (stockSearch.value) {
    const search = stockSearch.value.toLowerCase()
    result = result.filter(s => 
      s.security_code?.toLowerCase().includes(search) ||
      s.security_name?.toLowerCase().includes(search)
    )
  }
  
  // 排序
  result = [...result].sort((a, b) => {
    let valA, valB
    if (sortColumn.value === 'profit') {
      valA = a.profit || 0
      valB = b.profit || 0
    } else if (sortColumn.value === 'trade_count') {
      valA = a.trade_count || 0
      valB = b.trade_count || 0
    } else {
      valA = a.latest_date || ''
      valB = b.latest_date || ''
    }
    
    if (sortOrder.value === 'asc') {
      return valA > valB ? 1 : -1
    } else {
      return valA < valB ? 1 : -1
    }
  })
  
  return result
})

// 点击排序
const handleSortClick = (column) => {
  if (sortColumn.value === column) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortOrder.value = 'desc'
  }
}

// 加载股票列表
const loadStocks = async () => {
  loadingStocks.value = true
  try {
    const params = {
      start_date: dateRange.value ? dateRange.value[0] : undefined,
      end_date: dateRange.value ? dateRange.value[1] : undefined
    }
    const res = await getDeliveryStocks(params)
    if (res.code === 200) {
      stocks.value = res.data.map(s => ({
        ...s,
        profit: s.profit || 0
      }))
    }
  } catch (error) {
    console.error('加载股票列表失败:', error)
    ElMessage.error('加载股票列表失败')
  } finally {
    loadingStocks.value = false
  }
}

// 重置筛选
const resetFilters = () => {
  dateRange.value = null
  stockSearch.value = ''
  sortColumn.value = 'latest_date'
  sortOrder.value = 'desc'
  currentPage.value = 1
  loadStocks()
  loadDeliveryList()
}

// 搜索输入
const handleSearchInput = () => {
  // 搜索是前端过滤的，不需要重新请求
}

// 时间筛选变化
const handleDateChange = () => {
  currentPage.value = 1
  loadStocks()
  loadDeliveryList()
}

// 选择股票
const handleStockSelect = async (row) => {
  if (!row) return
  selectedStock.value = row.security_code
  selectedStockInfo.value = row
  currentPage.value = 1
  await Promise.all([
    loadDeliveryList(),
    loadSummary()
  ])
}

// 加载交割单列表
const loadDeliveryList = async () => {
  if (!selectedStock.value) return
  
  loadingDeliveries.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      operation: operationFilter.value || undefined,
      start_date: dateRange.value ? dateRange.value[0] : undefined,
      end_date: dateRange.value ? dateRange.value[1] : undefined
    }
    const res = await getDeliveryByStock(selectedStock.value, params)
    if (res.code === 200) {
      deliveryList.value = res.data.items
      deliveryTotal.value = res.data.total
    }
  } catch (error) {
    console.error('加载交割单列表失败:', error)
    ElMessage.error('加载交割单列表失败')
  } finally {
    loadingDeliveries.value = false
  }
}

// 加载汇总信息
const loadSummary = async () => {
  if (!selectedStock.value) return
  
  try {
    const res = await getDeliverySummary(selectedStock.value)
    if (res.code === 200) {
      stockSummary.value = res.data
    }
  } catch (error) {
    console.error('加载汇总信息失败:', error)
  }
}

// 保存复盘记录
const saveReviewNote = async (row) => {
  try {
    await updateDeliveryReviewNote(row.id, row.review_note || '')
  } catch (error) {
    console.error('保存复盘记录失败:', error)
  }
}

// 打开复盘记录弹窗
const openNoteDialog = (row) => {
  currentNoteRow.value = row
  noteDialogContent.value = row.review_note || ''
  noteDialogDirty.value = false
  noteDialogVisible.value = true
}

// 保存复盘记录（弹窗）
const saveNoteDialog = async () => {
  if (!currentNoteRow.value) return
  noteSaving.value = true
  try {
    const res = await updateDeliveryReviewNote(currentNoteRow.value.id, noteDialogContent.value)
    if (res.code === 200) {
      currentNoteRow.value.review_note = noteDialogContent.value
      noteDialogDirty.value = false
      noteDialogVisible.value = false
      ElMessage.success('复盘记录已保存')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    noteSaving.value = false
  }
}

// 分页变化
const handlePageChange = (page) => {
  currentPage.value = page
  loadDeliveryList()
}

// 格式化金额
const formatAmount = (amount) => {
  if (amount === null || amount === undefined) return '0.00'
  return Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 获取操作类型对应的标签类型
const getOperationType = (operation) => {
  const typeMap = {
    '证券买入': 'success',
    '证券卖出': 'danger',
    '配股': 'warning',
    '送股': 'warning',
    '转股': 'warning',
    '申购': 'primary',
    '赎回': 'info'
  }
  return typeMap[operation] || 'info'
}

// 监听操作类型过滤变化
watch(operationFilter, () => {
  currentPage.value = 1
  loadDeliveryList()
})

onMounted(() => {
  loadStocks()
})
</script>

<style scoped>
.delivery-list {
  height: calc(100vh - 80px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 16px;
  font-weight: 600;
}

.stock-card {
  height: calc(100vh - 120px);
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.date-filter {
  flex: 1;
}

.stock-search {
  margin-bottom: 10px;
}

.stock-table {
  margin-top: 5px;
}

/* 表头样式 - 简洁专业风格 */
.sortable-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
}

.sortable-header > span {
  color: #909399;
  font-weight: 500;
  transition: color 0.2s;
}

.sortable-header > span.active-sort {
  color: #409EFF;
}

.sortable-header:hover > span {
  color: #409EFF;
}

.sort-icons {
  display: inline-flex;
  flex-direction: column;
  line-height: 10px;
  height: 16px;
}

.sort-icons i {
  font-size: 8px;
  font-style: normal;
  color: #C0C4CC;
  transition: color 0.2s;
}

.sort-icons i.active {
  color: #409EFF;
}

.sort-icons i.sort-up {
  transform: translateY(2px);
}

.sort-icons i.sort-down {
  transform: translateY(-2px);
}

/* 盈利为红，亏损为绿 */
.profit-positive {
  color: #F56C6C;
  font-weight: 600;
}

.profit-negative {
  color: #67C23A;
  font-weight: 600;
}

.profit-zero {
  color: #909399;
}

.summary-card {
  margin-bottom: 20px;
}

.summary-item {
  text-align: center;
}

.summary-value {
  font-size: 18px;
  font-weight: 600;
  color: #409EFF;
}

.date-value {
  font-size: 14px;
}

.summary-label {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.operation-summary {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.operation-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.operation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.op-tag {
  margin: 2px;
}

.delivery-card {
  height: calc(100vh - 320px);
}

.header-filters {
  display: flex;
  gap: 10px;
}

.review-input :deep(.el-textarea__inner) {
  font-size: 12px;
}

/* 表格内复盘单元格 */
.review-cell {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-height: 28px;
}

.review-preview {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  font-size: 12px;
  color: #606266;
  cursor: pointer;
  max-width: 200px;
}

.review-preview:hover {
  color: #409eff;
}

.review-btn {
  flex-shrink: 0;
  font-size: 12px;
}

/* 弹窗样式 */
.note-dialog-tip {
  margin-bottom: 12px;
  font-size: 13px;
  color: #606266;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.note-textarea :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.8;
}

.dialog-tip {
  font-size: 12px;
  color: #909399;
  align-self: center;
}

.pagination-wrapper {
  margin-top: 15px;
  display: flex;
  justify-content: center;
}

.empty-tip {
  margin-top: 100px;
}
</style>
