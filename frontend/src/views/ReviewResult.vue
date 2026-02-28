<template>
  <div class="review-result">
    <!-- 头部信息 -->
    <div class="header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">复盘分析结果</span>
        </template>
        <template #extra>
          <el-button type="primary" @click="refreshData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </template>
      </el-page-header>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 错误提示 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon class="error-alert" />

    <!-- 数据内容 -->
    <div v-else-if="chartData" class="content">
      <!-- 指数行情 -->
      <el-card shadow="hover" class="index-card" v-if="indexData.length > 0">
            <template #header>
          <span>主要指数行情</span>
        </template>
        <el-table :data="indexData" stripe style="width: 100%">
          <el-table-column prop="name" label="指数名称" width="150" />
          <el-table-column prop="code" label="指数代码" width="150" />
          <el-table-column label="收盘价" width="120" align="right">
            <template #default="{ row }">
              {{ row.close.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿)" width="140" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="成交量(亿)" width="140" align="right">
            <template #default="{ row }">
              {{ ((row.volume || 0) / 100000000).toFixed(2) }}
            </template>
          </el-table-column>
        </el-table>
          </el-card>

      <!-- 因子得分排名 Top 10 -->
      <el-card shadow="hover" class="stock-table-card" v-if="top10FactorStocks.length > 0">
        <template #header>
          <span>因子得分 Top 10 股票</span>
        </template>
        <el-table :data="top10FactorStocks" stripe>
          <el-table-column type="index" label="排名" width="60" align="center" />
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" width="80" />
          <el-table-column label="成交额(亿)" width="90" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column prop="sector" label="所属板块" min-width="100" />
          <el-table-column label="标签" min-width="120">
            <template #default="{ row }">
              <div v-if="stockTags[row.code] && stockTags[row.code].length > 0">
                <el-tag
                  v-for="tag in stockTags[row.code].slice(0, 2)"
                  :key="tag.id"
                  :color="tag.color"
                  :style="{ color: getTagTextColor(tag.color) }"
                  size="small"
                >
                  {{ tag.name }}
                </el-tag>
                <el-tag v-if="stockTags[row.code].length > 2" type="info" size="small">
                  +{{ stockTags[row.code].length - 2 }}
                </el-tag>
              </div>
              <span v-else class="no-tag">无</span>
            </template>
          </el-table-column>
          <el-table-column label="综合得分" width="80" align="center">
            <template #default="{ row }">
              <el-tag type="success">{{ row.totalScore.toFixed(2) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成交额权重" width="80" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`成交额排名: 第${Math.round((10 - row.factor1Rank) / 0.2 + 1)}名`" placement="top">
                {{ row.factor1Rank.toFixed(1) }}
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="短线趋势" width="80" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`收盘: ${row.currentPrice || '-'} | MA5: ${row.ma5 || '-'} | MA10: ${row.ma10 || '-'}`" placement="top">
                <span :class="row.factor2MA >= 0 ? 'positive' : 'negative'">
                  {{ row.factor2MA >= 0 ? '+' : '' }}{{ row.factor2MA.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="昨日同比" width="80" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`今量: ${row.volCurrent ? (row.volCurrent / 10000).toFixed(0) + '万' : '-'} | 昨量: ${row.volPrev ? (row.volPrev / 10000).toFixed(0) + '万' : '-'}`" placement="top">
                <span :class="row.factor3Vol >= 0 ? 'positive' : 'negative'">
                  {{ row.factor3Vol >= 0 ? '+' : '' }}{{ row.factor3Vol.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="爆量" width="70" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`近3日均: ${row.avg3dTurnover ? (row.avg3dTurnover / 100000000).toFixed(2) + '亿' : '-'} | 前5-20日均: ${row.avg520dTurnover ? (row.avg520dTurnover / 100000000).toFixed(2) + '亿' : '-'}`" placement="top">
                <span :class="row.factor4Burst >= 0 ? 'positive' : 'negative'">
                  {{ row.factor4Burst >= 0 ? '+' : '' }}{{ row.factor4Burst.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="极限量" width="70" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`近10日均: ${row.avg10dTurnover ? (row.avg10dTurnover / 100000000).toFixed(2) + '亿' : '-'} | 前11-30日均: ${row.avg1130dTurnover ? (row.avg1130dTurnover / 100000000).toFixed(2) + '亿' : '-'}`" placement="top">
                <span :class="row.factor5Extreme >= 0 ? 'positive' : 'negative'">
                  {{ row.factor5Extreme >= 0 ? '+' : '' }}{{ row.factor5Extreme.toFixed(1) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="多头趋势" width="80" align="center">
            <template #default="{ row }">
              <el-tooltip :content="`15日MA5: ${row.ma5_15d || '-'} | 15日MA10: ${row.ma10_15d || '-'}`" placement="top">
                <span :class="row.factor6Trend >= 0 ? 'positive' : 'negative'">
                  {{ row.factor6Trend >= 0 ? '+' : '' }}{{ row.factor6Trend.toFixed(2) }}
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button type="warning" link size="small" @click="openTagDialog(row)">
                管理标签
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 板块详情表格 -->
      <el-card shadow="hover" class="sector-table-card">
        <template #header>
          <span>板块统计详情</span>
        </template>
        <el-table :data="sectors" stripe style="width: 100%">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="sector" label="板块" width="200" />
          <el-table-column label="得分" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="warning">{{ Math.round(row.score) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="股票数量" width="120" align="center">
            <template #default="{ row }">
              <el-tag type="info" class="clickable-tag" @click="handleShowSectorStocks(row)">
                {{ row.count }}只
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Top100 股票明细 -->
      <el-card shadow="hover" class="stock-table-card">
        <template #header>
          <span>成交额 Top 100 股票明细</span>
        </template>
        <el-table :data="top100Detail" stripe style="width: 100%" max-height="500">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="sector" label="所属板块" width="180" />
          <el-table-column prop="industry" label="所属行业" width="120" />
          <el-table-column label="总市值(亿)" width="120" align="right">
            <template #default="{ row }">
              {{ formatMarketValue(row.totalMarketValue) }}
            </template>
          </el-table-column>
          <el-table-column label="流通市值(亿)" width="130" align="right">
            <template #default="{ row }">
              {{ formatMarketValue(row.circulateMarketValue) }}
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿)" width="150" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 板块成分股对话框 -->
      <el-dialog
        v-model="showSectorStocksDialog"
        :title="currentSectorName + ' - 成分股'"
        width="600px"
      >
        <el-table :data="sectorStocksList" stripe>
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="stock_code" label="代码" width="120" />
          <el-table-column prop="stock_name" label="名称" width="150" />
          <el-table-column label="得分" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="warning">{{ row.total_score?.toFixed(2) || row.totalScore?.toFixed(2) || 0 }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="showSectorStocksDialog = false">关闭</el-button>
          </span>
        </template>
      </el-dialog>

      <!-- 标签管理弹窗 -->
      <el-dialog
        v-model="showTagDialog"
        :title="'管理标签 - ' + (currentTagStock ? currentTagStock.code + ' ' + currentTagStock.name : '')"
        width="700px"
      >
        <!-- 标签列表 -->
        <div class="tag-management">
          <div class="section-title">选择标签：</div>
          <div class="tag-list">
            <el-tag
              v-for="tag in allTags"
              :key="tag.id"
              :color="tag.color"
              :style="{ color: getTagTextColor(tag.color) }"
              :effect="stockTags[currentTagStock?.code]?.some(t => t.id === tag.id) ? 'dark' : 'plain'"
              class="selectable-tag"
              @click="toggleStockTag(tag)"
            >
              {{ tag.name }}
            </el-tag>
          </div>
          
          <el-divider />
          
          <!-- 创建新标签 -->
          <div class="create-tag">
            <div class="section-title">创建新标签：</div>
            <el-form :inline="true" :model="newTagForm">
              <el-form-item label="标签名称">
                <el-input v-model="newTagForm.name" placeholder="请输入标签名称" style="width: 150px" />
              </el-form-item>
              <el-form-item label="标签颜色">
                <el-color-picker v-model="newTagForm.color" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleCreateTag">创建</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getSectorStocks, getTags, addTag, addStockTag, removeStockTag, getBatchStockTags } from '@/api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

// 响应式数据
const loading = ref(true)
const error = ref(null)
const chartData = ref(null)
const pieChartRef = ref(null)
const barChartRef = ref(null)
const top10ChartRef = ref(null)
let pieChart = null
let barChart = null
let top10Chart = null

// 板块成分股相关
const showSectorStocksDialog = ref(false)
const sectorStocksLoading = ref(false)
const sectorStocksList = ref([])
const currentSectorName = ref('')
const sectorStocksTotal = ref(0)

// 标签管理
const showTagDialog = ref(false)
const allTags = ref([])
const stockTags = ref({})  // { stock_code: [tag1, tag2, ...] }
const currentTagStock = ref(null)
const newTagForm = ref({
  name: '',
  color: '#409EFF'
})

// 计算属性
const summary = computed(() => chartData.value?.summary || {})
const sectors = computed(() => chartData.value?.sectors || [])
const top100Detail = computed(() => chartData.value?.top100Detail || [])
const top10FactorStocks = computed(() => chartData.value?.top10FactorStocks || [])
const indexData = computed(() => chartData.value?.indexData || [])

// 返回上一页
const goBack = () => {
  router.back()
}

// 刷新数据
const refreshData = () => {
  fetchChartData()
}

// 点击查看板块成分股
const handleShowSectorStocks = async (row) => {
  console.log('点击板块股票数量, row:', row)
  // 优先使用后端返回的前30股票列表
  if (row.topStocks && row.topStocks.length > 0) {
    console.log('使用topStocks数据:', row.topStocks)
    sectorStocksList.value = row.topStocks.map(s => ({
      stock_code: s.code,
      stock_name: s.name,
      total_score: s.totalScore,
      rank: s.rank
    }))
    sectorStocksTotal.value = row.topStocks.length
    currentSectorName.value = row.sector || row.name
    showSectorStocksDialog.value = true
    return
  }
  
  // 兼容处理：sectorCode 可能不存在，尝试从 sector 获取
  let sectorCode = row.sectorCode || row.sector_code || ''
  
  if (!sectorCode && row.sector) {
    // 如果没有 sectorCode，尝试从后端获取
    try {
      const res = await getSectorStocks('', { sector_name: row.sector })
      if (res.code === 200 && res.data.list && res.data.list.length > 0) {
        sectorStocksList.value = res.data.list || []
        sectorStocksTotal.value = res.data.total || 0
        currentSectorName.value = row.sector
        showSectorStocksDialog.value = true
        return
      }
    } catch (e) {
      console.error('按名称查询板块失败:', e)
    }
    ElMessage.warning('板块代码不存在')
    return
  }
  
  currentSectorName.value = row.sector
  showSectorStocksDialog.value = true
  sectorStocksLoading.value = true
  
  try {
    const res = await getSectorStocks(sectorCode, { page: 1, page_size: 100 })
    if (res.code === 200) {
      sectorStocksList.value = res.data.list || []
      sectorStocksTotal.value = res.data.total || 0
    }
  } catch (error) {
    console.error('获取板块成分股失败:', error)
    ElMessage.error('获取板块成分股失败')
  } finally {
    sectorStocksLoading.value = false
  }
}

// 格式化金额（后端已转为亿，直接展示）
const formatAmount = (value) => {
  if (!value && value !== 0) return '-'
  return `${parseFloat(value).toFixed(2)}亿`
}

// 格式化市值（直接是元，转为亿/万亿显示）
const formatMarketValue = (value) => {
  if (!value && value !== 0) return '-'
  if (value >= 100000000) {
    // 转换为万亿
    return `${(value / 100000000).toFixed(2)}万亿`
  } else if (value >= 10000000000) {
    // 转换为亿
    return `${(value / 100000000).toFixed(2)}亿`
  }
  return `${(value / 100000000).toFixed(2)}亿`
}

// 加载所有标签
const loadAllTags = async () => {
  try {
    const res = await getTags()
    if (res.code === 200) {
      allTags.value = res.data || []
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

// 批量加载股票标签
const loadBatchStockTags = async (stockCodes) => {
  if (!stockCodes || stockCodes.length === 0) return
  try {
    const res = await getBatchStockTags(stockCodes)
    if (res.code === 200) {
      stockTags.value = res.data || {}
    }
  } catch (error) {
    console.error('获取股票标签失败:', error)
  }
}

// 打开标签管理弹窗
const openTagDialog = async (stock) => {
  currentTagStock.value = stock
  showTagDialog.value = true
  // 加载所有标签
  await loadAllTags()
  // 加载当前股票的标签
  await loadBatchStockTags([stock.code])
}

// 切换股票的标签
const toggleStockTag = async (tag) => {
  if (!currentTagStock.value) return
  const stockCode = currentTagStock.value.code
  const hasTag = stockTags.value[stockCode]?.some(t => t.id === tag.id)
  
  try {
    if (hasTag) {
      await removeStockTag(stockCode, tag.id)
      stockTags.value[stockCode] = stockTags.value[stockCode].filter(t => t.id !== tag.id)
    } else {
      await addStockTag(stockCode, tag.id)
      if (!stockTags.value[stockCode]) {
        stockTags.value[stockCode] = []
      }
      stockTags.value[stockCode].push(tag)
    }
  } catch (error) {
    console.error('更新标签失败:', error)
  }
}

// 创建新标签
const handleCreateTag = async () => {
  if (!newTagForm.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  try {
    const res = await addTag(newTagForm.value)
    if (res.code === 200) {
      ElMessage.success('标签创建成功')
      await loadAllTags()
      newTagForm.value.name = ''
      newTagForm.value.color = '#409EFF'
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (error) {
    console.error('创建标签失败:', error)
  }
}

// 计算标签文字颜色
const getTagTextColor = (color) => {
  if (!color) return '#fff'
  const hex = color.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000' : '#fff'
}

// 获取图表数据
const fetchChartData = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch(`/api/review/task/${taskId}/chart`)
    const result = await response.json()
    
    if (result.code === 200) {
      chartData.value = result.data
      // 数据加载后初始化图表
      await nextTick()
      initCharts()
      
      // 加载股票标签
      const stockCodes = (chartData.value?.top10FactorStocks || []).map(s => s.code)
      if (stockCodes.length > 0) {
        await loadBatchStockTags(stockCodes)
      }
    } else {
      error.value = result.message || '获取数据失败'
    }
  } catch (e) {
    error.value = '网络错误，请检查后端服务'
    console.error('获取图表数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 初始化图表
const initCharts = () => {
  initPieChart()
  initBarChart()
  initTop10Chart()
}

// 初始化饼图
const initPieChart = () => {
  if (!pieChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorPie || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}亿 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [{
      name: '成交额',
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}: {d}%'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      data: labels.map((label, index) => ({
        value: data[index],
        name: label
      }))
    }]
  })
}

// 初始化柱状图
const initBarChart = () => {
  if (!barChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorBar || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  barChart = echarts.init(barChartRef.value)
  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        rotate: 30,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      name: '股票数量'
    },
    series: [{
      name: '股票数量',
      type: 'bar',
      data: data,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#83bff6' },
          { offset: 0.5, color: '#188df0' },
          { offset: 1, color: '#188df0' }
        ])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2378f7' },
            { offset: 1, color: '#2378f7' }
          ])
        }
      }
    }]
  })
}

// 初始化Top10图表
const initTop10Chart = () => {
  if (!top10ChartRef.value) return
  
  const chartsData = chartData.value?.charts?.amountTop10 || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  top10Chart = echarts.init(top10ChartRef.value)
  top10Chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '成交额(亿)',
      axisLabel: {
        formatter: (value) => value.toFixed(0)
      }
    },
    yAxis: {
      type: 'category',
      data: labels.reverse(),
      axisLabel: {
        fontSize: 11
      }
    },
    series: [{
      name: '成交额',
      type: 'bar',
      data: data.reverse(),
      itemStyle: {
        color: (params) => {
          const colors = ['#FF6B6B', '#FF8E72', '#FFA940', '#FFC53D', '#FFEC3D', '#A0D911', '#52C41A', '#13C2C2', '#1890FF', '#2F54EB']
          return colors[params.dataIndex] || '#1890FF'
        }
      },
      label: {
        show: true,
        position: 'right',
        formatter: (params) => formatAmount(params.value)
      }
    }]
  })
}

// 监听窗口大小变化
const handleResize = () => {
  pieChart?.resize()
  barChart?.resize()
  top10Chart?.resize()
}

// 生命周期
onMounted(() => {
  fetchChartData()
  window.addEventListener('resize', handleResize)
})

// 清理
watch(() => chartData.value, () => {
  if (chartData.value) {
    nextTick(() => {
      initCharts()
    })
  }
})
</script>

<style scoped>
.review-result {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.loading-container {
  padding: 40px;
}

.error-alert {
  margin: 20px;
}

.content {
  padding: 0 10px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-card :deep(.el-card__header) {
  font-weight: 500;
  color: #666;
}

.card-value {
  font-size: 24px;
  font-weight: bold;
  color: #1890ff;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.chart-container-large {
  height: 400px;
  width: 100%;
}

.top10-chart-card,
.sector-table-card,
.stock-table-card {
  margin-bottom: 20px;
}

.positive {
  color: #f56c6c;
  font-weight: 500;
}

.negative {
  color: #52c41a;
  font-weight: 500;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.clickable-tag:hover {
  color: #409eff;
  transform: scale(1.05);
}

/* 标签管理样式 */
.tag-management {
  padding: 10px 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.selectable-tag {
  cursor: pointer;
  padding: 8px 15px;
  border-radius: 4px;
  transition: all 0.3s;
}

.selectable-tag:hover {
  transform: scale(1.05);
}

.no-tag {
  color: #909399;
  font-size: 12px;
}

.create-tag {
  margin-top: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #303133;
}
</style>
