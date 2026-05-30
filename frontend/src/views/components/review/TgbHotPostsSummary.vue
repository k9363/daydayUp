<template>
  <el-card class="tgb-hot-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="card-title">📰 淘股吧手机端热帖摘要</span>
        <div class="card-actions">
          <el-tag v-if="data" size="small" type="success">{{ data.trade_date || '—' }}</el-tag>
          <el-tag v-if="data && data.raw_report && data.raw_report.all_count" size="small" type="info">
            采集 {{ data.raw_report.all_count }} 条
          </el-tag>
          <el-button
            v-if="data && data.report_url"
            link
            :icon="Link"
            type="primary"
            @click="openReport"
          >
            打开榜首帖
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

      <div v-if="topPosts.length" class="top-posts">
        <div class="top-posts-title">Top 帖直达：</div>
        <div class="top-posts-list">
          <a
            v-for="p in topPosts.slice(0, 5)"
            :key="p.topic_id"
            :href="p.url"
            target="_blank"
            class="post-link"
          >
            [{{ p.user_name }}] {{ p.subject }}
            <span class="post-meta">回{{ p.reply_num }} / 看{{ p.view_num }}</span>
          </a>
        </div>
      </div>
    </div>

    <el-empty v-else description="当日尚未生成淘股吧热帖摘要" :image-size="60" />
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

const topPosts = computed(() => {
  return data.value?.raw_report?.top_posts || []
})

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
    // 列表接口不返回 raw_report，需要先取 id 再拿详情
    const listResp = await axios.get('/api/external/analysis', {
      params: { source: 'tgb-mobile-hot', trade_date: td, limit: 1 },
    })
    if (listResp.data?.code === 200 && listResp.data.data?.length > 0) {
      const id = listResp.data.data[0].id
      const detailResp = await axios.get(`/api/external/analysis/${id}`)
      if (detailResp.data?.code === 200) {
        data.value = detailResp.data.data
      }
    }
  } catch (e) {
    console.warn('[TgbHotPostsSummary] load failed:', e)
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
.tgb-hot-card { margin-bottom: 16px; border-left: 3px solid #e6a23c; }
.card-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.card-title { font-weight: 600; }
.card-actions { display: flex; align-items: center; gap: 8px; }
.meta-row { display: flex; gap: 16px; color: #909399; font-size: 13px; margin-bottom: 8px; flex-wrap: wrap; }
.meta-item { display: inline-flex; align-items: center; gap: 4px; }
.summary-text { line-height: 1.7; white-space: pre-wrap; color: #303133; font-size: 13px; max-height: 240px; overflow-y: auto; padding: 8px; background: #fdf6ec; border-radius: 4px; }
.top-posts { margin-top: 12px; }
.top-posts-title { font-size: 13px; color: #909399; margin-bottom: 6px; }
.top-posts-list { display: flex; flex-direction: column; gap: 4px; }
.post-link { font-size: 13px; color: #409eff; text-decoration: none; line-height: 1.5; }
.post-link:hover { text-decoration: underline; }
.post-meta { color: #909399; font-size: 12px; margin-left: 6px; }
</style>
