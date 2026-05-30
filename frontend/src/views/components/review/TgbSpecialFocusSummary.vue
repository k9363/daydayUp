<template>
  <el-card class="tgb-spefocus-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="card-title">📌 特别关注动态（你跟的人在说什么）</span>
        <div class="card-actions">
          <el-tag v-if="data" size="small" type="success">{{ data.trade_date || '—' }}</el-tag>
          <el-tag v-if="data && data.raw_report && data.raw_report.all_count" size="small" type="info">
            {{ data.raw_report.all_count }} 条动作
          </el-tag>
          <el-button
            v-if="data && data.report_url"
            link
            :icon="Link"
            type="primary"
            @click="openReport"
          >
            打开最新主题
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
          采集时间：{{ formatTime(data.create_time) }}
        </span>
      </div>
      <div class="summary-text">{{ data.summary }}</div>

      <div v-if="topActions.length" class="top-actions">
        <div class="top-actions-title">最新 5 条直达：</div>
        <div class="top-actions-list">
          <a
            v-for="a in topActions.slice(0, 5)"
            :key="a.other_id"
            :href="a.topic_url"
            target="_blank"
            class="action-link"
          >
            <span class="action-time">{{ (a.action_date || '').slice(5, 16) }}</span>
            <span class="action-user">{{ a.user_name }}</span>
            <span class="action-verb">{{ a.action_label }}</span>
            「{{ (a.object_name || '').slice(0, 30) }}」
          </a>
        </div>
      </div>
    </div>

    <el-empty v-else description="当日尚未生成特别关注动态" :image-size="60" />
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { Link, Refresh, Calendar, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  tradeDate: { type: String, default: '' },
})

const data = ref(null)
const loading = ref(false)

const topActions = computed(() => data.value?.raw_report?.top_actions || [])

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
  try {
    const td = normalizeDate(props.tradeDate)
    const listResp = await axios.get('/api/external/analysis', {
      params: { source: 'tgb-special-focus', trade_date: td, limit: 1 },
    })
    if (listResp.data?.code === 200 && listResp.data.data?.length > 0) {
      const id = listResp.data.data[0].id
      const detailResp = await axios.get(`/api/external/analysis/${id}`)
      if (detailResp.data?.code === 200) {
        data.value = detailResp.data.data
      }
    }
  } catch (e) {
    console.warn('[TgbSpecialFocusSummary] load failed:', e)
  } finally {
    loading.value = false
  }
}

const formatTime = (ts) => {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return ts
  }
}

const openReport = () => {
  if (data.value?.report_url) {
    window.open(data.value.report_url, '_blank')
  }
}

watch(() => props.tradeDate, () => load(), { immediate: false })
onMounted(() => load())
</script>

<style scoped>
.tgb-spefocus-card { margin-bottom: 16px; border-left: 3px solid #67c23a; }
.card-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.card-title { font-weight: 600; }
.card-actions { display: flex; align-items: center; gap: 8px; }
.meta-row { display: flex; gap: 16px; color: #909399; font-size: 13px; margin-bottom: 8px; flex-wrap: wrap; }
.meta-item { display: inline-flex; align-items: center; gap: 4px; }
.summary-text { line-height: 1.7; white-space: pre-wrap; color: #303133; font-size: 13px; max-height: 360px; overflow-y: auto; padding: 8px; background: #f0f9eb; border-radius: 4px; }
.top-actions { margin-top: 12px; }
.top-actions-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.top-actions-list { display: flex; flex-direction: column; gap: 4px; }
.action-link { font-size: 13px; color: #409eff; text-decoration: none; line-height: 1.5; }
.action-link:hover { text-decoration: underline; }
.action-time { color: #909399; font-size: 12px; margin-right: 6px; }
.action-user { font-weight: 600; margin-right: 4px; }
.action-verb { color: #67c23a; margin-right: 4px; }
</style>
