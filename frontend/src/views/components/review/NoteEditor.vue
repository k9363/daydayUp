<template>
  <el-card shadow="hover" class="note-card">
    <template #header>
      <div class="card-header">
        <span>每日笔记</span>
        <el-button type="primary" link @click="handleSave" :loading="saving">
          <el-icon><DocumentChecked /></el-icon>
          保存笔记
        </el-button>
      </div>
    </template>
    <el-row :gutter="16">
      <el-col :span="12">
        <div class="note-section">
          <div class="note-label">大盘分析</div>
          <div ref="marketAnalysisRef" class="rich-editor"></div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="note-section">
          <div class="note-label">明日操作</div>
          <div ref="nextActionRef" class="rich-editor"></div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'
import { getDailyNote } from '@/api'

const props = defineProps({
  initialMarketAnalysis: {
    type: String,
    default: ''
  },
  initialNextAction: {
    type: String,
    default: ''
  },
  tradeDate: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['save'])

const marketAnalysisRef = ref(null)
const nextActionRef = ref(null)
const saving = ref(false)
const loadedMarketAnalysis = ref('')
const loadedNextAction = ref('')
let marketAnalysisQuill = null
let nextActionQuill = null

const initializeEditors = () => {
  if (marketAnalysisRef.value && !marketAnalysisQuill) {
    marketAnalysisQuill = new Quill(marketAnalysisRef.value, {
      theme: 'snow',
      placeholder: '记录今日大盘分析...',
      modules: {
        toolbar: [
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'image'],
          ['clean']
        ]
      }
    })
    if (loadedMarketAnalysis.value) {
      marketAnalysisQuill.root.innerHTML = loadedMarketAnalysis.value
    }
  }

  if (nextActionRef.value && !nextActionQuill) {
    nextActionQuill = new Quill(nextActionRef.value, {
      theme: 'snow',
      placeholder: '规划明日操作...',
      modules: {
        toolbar: [
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'image'],
          ['clean']
        ]
      }
    })
    if (loadedNextAction.value) {
      nextActionQuill.root.innerHTML = loadedNextAction.value
    }
  }
}

const loadNote = async () => {
  if (!props.tradeDate) return
  try {
    const res = await getDailyNote(props.tradeDate)
    if (res.code === 200 && res.data) {
      const note = res.data
      if (note.market_analysis !== undefined && note.market_analysis !== null) {
        loadedMarketAnalysis.value = note.market_analysis
        if (marketAnalysisQuill) {
          marketAnalysisQuill.root.innerHTML = note.market_analysis || ''
        }
      }
      if (note.next_action !== undefined && note.next_action !== null) {
        loadedNextAction.value = note.next_action
        if (nextActionQuill) {
          nextActionQuill.root.innerHTML = note.next_action || ''
        }
      }
    }
  } catch (error) {
    console.error('加载每日笔记失败:', error)
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    const marketAnalysis = marketAnalysisQuill?.root.innerHTML || ''
    const nextAction = nextActionQuill?.root.innerHTML || ''
    emit('save', { marketAnalysis, nextAction, tradeDate: props.tradeDate })
  } finally {
    saving.value = false
  }
}

const destroyEditors = () => {
  if (marketAnalysisQuill) {
    marketAnalysisQuill = null
  }
  if (nextActionQuill) {
    nextActionQuill = null
  }
}

onMounted(async () => {
    initializeEditors()
    // 等待编辑器 DOM 渲染后再加载笔记
    await nextTick()
    await loadNote()
})

onBeforeUnmount(() => {
  destroyEditors()
})

watch([() => props.initialMarketAnalysis, () => props.initialNextAction], ([newMarketAnalysis, newNextAction]) => {
  if (marketAnalysisQuill && newMarketAnalysis !== marketAnalysisQuill.root.innerHTML) {
    marketAnalysisQuill.root.innerHTML = newMarketAnalysis
  }
  if (nextActionQuill && newNextAction !== nextActionQuill.root.innerHTML) {
    nextActionQuill.root.innerHTML = newNextAction
  }
})

defineExpose({
  handleSave
})
</script>

<style scoped>
.note-card {
  margin-bottom: 16px;
}

.note-section {
  margin-bottom: 16px;
}

.note-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.rich-editor {
  height: 200px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
</style>
