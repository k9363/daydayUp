<template>
  <el-card v-if="filteredAnalyses.length > 0" shadow="hover" class="ext-analysis-card">
    <template #header>
      <div class="card-header">
        <span>
          <el-icon><Cpu /></el-icon>
          相关历史 AI 报告（近 7 天 × 今日 Top10）
          <el-tag type="info" size="small" style="margin-left: 8px">
            {{ filteredAnalyses.length }} 份
          </el-tag>
          <el-tooltip
            content="非今日复盘新跑的报告。此处展示「近 7 天内已有的 AI 多代理报告」与「今日因子排名 Top10 个股」的交集——目的是提示这几只 Top10 你过去一周已经跑过 AI 分析了,可直接查阅,不必重复跑。每条「生成时间」即报告产生日。"
            placement="top"
            effect="light"
          >
            <el-icon style="margin-left: 6px; color: #909399; cursor: help; vertical-align: middle">
              <QuestionFilled />
            </el-icon>
          </el-tooltip>
        </span>
        <el-button text @click="reload" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </template>

    <el-table :data="filteredAnalyses" stripe>
      <el-table-column label="代码" width="110">
        <template #default="{ row }">
          <StockCodeLink :code="row.stock_code" />
        </template>
      </el-table-column>
      <el-table-column prop="stock_name" label="名称" width="100">
        <template #default="{ row }">
          {{ row.stock_name || nameLookup[normalize(row.stock_code)] || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="决策" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="decisionTagType(row.decision)" size="small" effect="dark">
            {{ decisionText(row.decision) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="置信度" width="90" align="center">
        <template #default="{ row }">
          <span v-if="row.confidence != null">
            {{ (row.confidence * 100).toFixed(0) }}%
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="目标价" width="90" align="right">
        <template #default="{ row }">
          {{ row.target_price != null ? row.target_price.toFixed(2) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="summary-text">{{ row.summary || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="生成时间" width="160" align="center">
        <template #default="{ row }">
          {{ formatTime(row.create_time) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openDetail(row)">
            完整报告
          </el-button>
          <el-button v-if="row.report_url" type="info" link size="small" @click="openExternal(row.report_url)">
            原平台 ↗
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="50%" destroy-on-close>
      <div v-if="currentRow" class="detail-block">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="股票">{{ currentRow.stock_code }} {{ currentRow.stock_name || '' }}</el-descriptions-item>
          <el-descriptions-item label="决策">
            <el-tag :type="decisionTagType(currentRow.decision)">{{ decisionText(currentRow.decision) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">{{ currentRow.confidence != null ? (currentRow.confidence * 100).toFixed(0) + '%' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标价">{{ currentRow.target_price != null ? currentRow.target_price.toFixed(2) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ currentRow.source }}</el-descriptions-item>
          <el-descriptions-item label="生成时间">{{ formatTime(currentRow.create_time) }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 16px">摘要</h4>
        <div class="summary-block">{{ currentRow.summary || '—' }}</div>

        <h4 style="margin-top: 16px">原始多代理报告（raw_report）</h4>
        <el-input
          type="textarea"
          :model-value="prettyJson(currentRow.raw_report)"
          :rows="20"
          readonly
        />
      </div>
    </el-drawer>
  </el-card>

  <el-empty v-else-if="!loading && stockCodes.length > 0" description="本次复盘相关股票尚无 AI 报告（由 TradingAgents-CN 分析后自动推送）" :image-size="80" />
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Cpu, Refresh, QuestionFilled } from '@element-plus/icons-vue'
import StockCodeLink from '@/components/StockCodeLink.vue'

const props = defineProps({
  /** 本次复盘相关的股票代码列表（如 ['sh.002371', 'sz.300323', '600000']），用于过滤 */
  stockCodes: { type: Array, default: () => [] },
  /** 代码 → 名称的查表，列表里 stock_name 为空时兜底用 */
  nameLookup: { type: Object, default: () => ({}) },
})

const loading = ref(false)
const allAnalyses = ref([])
const drawerVisible = ref(false)
const currentRow = ref(null)

const normalize = (code) => {
  if (!code) return ''
  const s = String(code).trim().toLowerCase()
  if (s.startsWith('sh.') || s.startsWith('sz.') || s.startsWith('bj.')) {
    return s.split('.')[1]
  }
  return s
}

const codeSet = computed(() => new Set(props.stockCodes.map(normalize).filter(Boolean)))

const filteredAnalyses = computed(() => {
  if (codeSet.value.size === 0) return allAnalyses.value
  return allAnalyses.value.filter(a => codeSet.value.has(normalize(a.stock_code)))
})

const drawerTitle = computed(() =>
  currentRow.value
    ? `${currentRow.value.stock_code} ${currentRow.value.stock_name || ''} - AI 报告`
    : 'AI 报告'
)

async function reload() {
  loading.value = true
  try {
    const resp = await fetch('/api/external/analysis?days=7&limit=200')
    const data = await resp.json()
    if (data.code === 200) {
      allAnalyses.value = data.data || []
    } else {
      allAnalyses.value = []
    }
  } catch (e) {
    allAnalyses.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(row) {
  currentRow.value = row
  drawerVisible.value = true
}

function openExternal(url) {
  if (url) window.open(url, '_blank')
}

function decisionTagType(d) {
  if (!d) return 'info'
  if (d.includes('buy')) return 'danger'   // 中国习惯：红涨
  if (d.includes('sell')) return 'success' // 绿跌
  if (d.includes('hold') || d.includes('neutral')) return 'warning'
  return 'info'
}

function decisionText(d) {
  if (!d) return '-'
  const map = {
    buy: '买入', sell: '卖出', hold: '持有', neutral: '中性',
  }
  return map[d] || d
}

function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function prettyJson(obj) {
  if (!obj) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

onMounted(reload)
watch(() => props.stockCodes, () => { /* 仅 client filter */ })
</script>

<style scoped>
.ext-analysis-card {
  margin-top: 16px;
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.summary-text {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}
.detail-block {
  padding: 8px 16px;
}
.summary-block {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  white-space: pre-wrap;
  color: #303133;
  font-size: 14px;
  line-height: 1.6;
}
</style>
