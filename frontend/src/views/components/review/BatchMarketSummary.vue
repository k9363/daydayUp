<template>
  <el-card class="batch-market-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="card-title">🌐 当日全市场综合分析（TA-CN 自动推送）</span>
        <div class="card-actions">
          <el-tag v-if="data" size="small" type="success">{{ data.trade_date || '—' }}</el-tag>
          <el-tag v-if="data && data.summary" size="small" type="info">
            {{ data.summary.length }} 字摘要
          </el-tag>
          <el-button
            v-if="data"
            link
            :icon="expanded ? ArrowUp : ArrowDown"
            type="primary"
            :loading="loadingReport"
            @click="toggleReport"
          >
            {{ expanded ? '收起完整报告' : '查看完整报告' }}
          </el-button>
          <el-button :icon="Refresh" link size="small" @click="load">刷新</el-button>
        </div>
      </div>
    </template>

    <el-skeleton v-if="loading" :rows="4" animated />

    <div v-else-if="data" class="summary-content">
      <div class="meta-row">
        <span class="meta-item">
          <el-icon><Calendar /></el-icon>
          交易日：{{ data.trade_date || '—' }}
        </span>
        <span class="meta-item">
          <el-icon><Clock /></el-icon>
          推送时间：{{ formatTime(data.create_time) }}
        </span>
      </div>
      <div class="summary-text">{{ data.summary }}</div>

      <!-- 就地展开完整报告 -->
      <div v-if="expanded" class="full-report-wrapper">
        <div v-if="!fullReport && !loadingReport" class="report-empty">完整报告内容缺失</div>
        <el-skeleton v-else-if="loadingReport" :rows="8" animated />
        <div v-else class="markdown-body" v-html="renderedReport" />
      </div>
    </div>

    <el-empty v-else description="当日尚未生成全市场分析" :image-size="60" />
  </el-card>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import axios from 'axios'
import { Refresh, Calendar, Clock, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { marked } from 'marked'

const props = defineProps({
  tradeDate: { type: String, default: '' },
})

const data = ref(null)
const loading = ref(false)
const expanded = ref(false)
const loadingReport = ref(false)
const fullReport = ref('')

const normalizeDate = (s) => {
  if (!s) return ''
  const t = String(s).replace(/-/g, '')
  if (t.length === 8 && /^\d+$/.test(t)) {
    return `${t.slice(0, 4)}-${t.slice(4, 6)}-${t.slice(6, 8)}`
  }
  return s
}

const load = async () => {
  if (!props.tradeDate) return
  loading.value = true
  data.value = null
  expanded.value = false
  fullReport.value = ''
  try {
    const td = normalizeDate(props.tradeDate)
    const resp = await axios.get('/api/external/analysis', {
      params: { source: 'ta-cn-batch', trade_date: td, limit: 1 },
    })
    if (resp.data?.code === 200 && resp.data.data && resp.data.data.length > 0) {
      data.value = resp.data.data[0]
    }
  } catch (e) {
    console.warn('[BatchMarketSummary] load failed:', e)
  } finally {
    loading.value = false
  }
}

const fetchFullReport = async () => {
  if (!data.value?.id) return
  loadingReport.value = true
  try {
    const resp = await axios.get(`/api/external/analysis/${data.value.id}`)
    if (resp.data?.code === 200) {
      const raw = resp.data.data || {}
      const rr = raw.raw_report || {}
      // raw_report 可能是: {result: {report, data_markdown, ...}} 或直接平铺
      const result = rr.result || rr
      fullReport.value = result.report || result.markdown || raw.summary || ''
    }
  } catch (e) {
    console.warn('[BatchMarketSummary] fetchFullReport failed:', e)
  } finally {
    loadingReport.value = false
  }
}

const toggleReport = async () => {
  expanded.value = !expanded.value
  if (expanded.value && !fullReport.value) {
    await fetchFullReport()
  }
}

const renderedReport = computed(() => {
  if (!fullReport.value) return ''
  try {
    return marked.parse(fullReport.value, { breaks: true, gfm: true })
  } catch (e) {
    return `<pre>${fullReport.value}</pre>`
  }
})

const formatTime = (ts) => {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return ts
  }
}

watch(() => props.tradeDate, () => load(), { immediate: false })
onMounted(() => load())
</script>

<style scoped>
.batch-market-card { margin-bottom: 16px; border-left: 3px solid var(--el-color-primary); }
.card-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.card-title { font-weight: 600; }
.card-actions { display: flex; align-items: center; gap: 8px; }
.meta-row { display: flex; gap: 16px; color: #909399; font-size: 13px; margin-bottom: 8px; flex-wrap: wrap; }
.meta-item { display: inline-flex; align-items: center; gap: 4px; }
.summary-text { line-height: 1.7; white-space: pre-wrap; color: #303133; font-size: 14px; max-height: 200px; overflow-y: auto; padding: 8px; background: #f5f7fa; border-radius: 4px; }
.full-report-wrapper { margin-top: 12px; padding: 12px 16px; background: #fff; border: 1px solid #ebeef5; border-radius: 4px; max-height: 600px; overflow-y: auto; }
.report-empty { color: #909399; text-align: center; padding: 20px; }
</style>

<style>
/* markdown 内容样式 — 不 scoped 以便 v-html 内的子元素能命中 */
.markdown-body { color: #303133; font-size: 14px; line-height: 1.7; }
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 { margin: 16px 0 8px; font-weight: 600; color: #303133; }
.markdown-body h1 { font-size: 22px; }
.markdown-body h2 { font-size: 18px; border-bottom: 1px solid #ebeef5; padding-bottom: 4px; }
.markdown-body h3 { font-size: 16px; }
.markdown-body h4 { font-size: 14px; }
.markdown-body p { margin: 8px 0; }
.markdown-body ul, .markdown-body ol { margin: 8px 0; padding-left: 24px; }
.markdown-body li { margin: 2px 0; }
.markdown-body table { border-collapse: collapse; margin: 12px 0; width: 100%; font-size: 13px; }
.markdown-body th, .markdown-body td { border: 1px solid #dcdfe6; padding: 6px 10px; text-align: left; }
.markdown-body th { background: #f5f7fa; font-weight: 600; }
.markdown-body code { background: #f4f4f5; padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; }
.markdown-body strong { color: #303133; font-weight: 600; }
.markdown-body blockquote { border-left: 4px solid #409eff; padding: 4px 12px; margin: 8px 0; background: #f5f7fa; color: #606266; }
</style>
