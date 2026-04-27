<template>
  <el-card shadow="hover" class="note-card">
    <template #header>
      <div class="card-header">
        <span>每日笔记</span>
        <div class="header-right">
          <el-button-group size="small" class="toolbar-group">
            <el-button @click="marketEditor?.chain().focus().toggleBold().run()" :type="marketEditor?.isActive('bold') ? 'primary' : 'default'" title="加粗">
              <strong>B</strong>
            </el-button>
            <el-button @click="marketEditor?.chain().focus().toggleItalic().run()" :type="marketEditor?.isActive('italic') ? 'primary' : 'default'" title="斜体">
              <em>I</em>
            </el-button>
            <el-button @click="marketEditor?.chain().focus().toggleUnderline().run()" :type="marketEditor?.isActive('underline') ? 'primary' : 'default'" title="下划线">
              <u>U</u>
            </el-button>
            <el-button @click="marketEditor?.chain().focus().toggleStrike().run()" :type="marketEditor?.isActive('strike') ? 'primary' : 'default'" title="删除线">
              <s>S</s>
            </el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button-group size="small">
            <el-button @click="marketEditor?.chain().focus().toggleHeading({ level: 2 }).run()" :type="marketEditor?.isActive('heading', { level: 2 }) ? 'primary' : 'default'" title="标题2">
              H2
            </el-button>
            <el-button @click="marketEditor?.chain().focus().toggleHeading({ level: 3 }).run()" :type="marketEditor?.isActive('heading', { level: 3 }) ? 'primary' : 'default'" title="标题3">
              H3
            </el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button-group size="small">
            <el-button @click="marketEditor?.chain().focus().toggleBulletList().run()" :type="marketEditor?.isActive('bulletList') ? 'primary' : 'default'" title="无序列表">
              <el-icon><List /></el-icon>
            </el-button>
            <el-button @click="marketEditor?.chain().focus().toggleOrderedList().run()" :type="marketEditor?.isActive('orderedList') ? 'primary' : 'default'" title="有序列表">
              <el-icon><List /></el-icon>#
            </el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button size="small" @click="marketEditor?.chain().focus().setHorizontalRule().run()" title="分隔线">
            ——
          </el-button>
          <el-button size="small" @click="marketEditor?.chain().focus().toggleBlockquote().run()" :type="marketEditor?.isActive('blockquote') ? 'primary' : 'default'" title="引用">
            引用
          </el-button>
          <el-button size="small" @click="marketEditor?.chain().focus().toggleCodeBlock().run()" :type="marketEditor?.isActive('codeBlock') ? 'primary' : 'default'" title="代码块">
            代码
          </el-button>
        </div>
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
          <div class="editor-wrapper">
            <editor-content :editor="marketEditor" class="tiptap-content" />
          </div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="note-section">
          <div class="note-label">明日操作</div>
          <div class="editor-wrapper">
            <editor-content :editor="nextActionEditor" class="tiptap-content" />
          </div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import { getDailyNote } from '@/api'

const props = defineProps({
  initialMarketAnalysis: { type: String, default: '' },
  initialNextAction: { type: String, default: '' },
  tradeDate: { type: String, default: '' }
})

const emit = defineEmits(['save'])
const saving = ref(false)

const makeEditor = (placeholder) => useEditor({
  extensions: [
    StarterKit.configure({ heading: { levels: [2, 3] } }),
    Placeholder.configure({ placeholder }),
    Underline,
  ],
  content: '',
})

const marketEditor = makeEditor('记录今日大盘分析...')
const nextActionEditor = makeEditor('规划明日操作...')

const loadNote = async () => {
  if (!props.tradeDate) return
  try {
    const res = await getDailyNote(props.tradeDate)
    if (res.code === 200 && res.data) {
      const note = res.data
      if (note.market_analysis !== undefined && note.market_analysis !== null) {
        marketEditor.value?.commands.setContent(note.market_analysis || '')
      }
      if (note.next_action !== undefined && note.next_action !== null) {
        nextActionEditor.value?.commands.setContent(note.next_action || '')
      }
    }
  } catch (error) {
    console.error('加载每日笔记失败:', error)
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    const marketAnalysis = marketEditor.value?.getHTML() || ''
    const nextAction = nextActionEditor.value?.getHTML() || ''
    emit('save', { marketAnalysis, nextAction, tradeDate: props.tradeDate })
  } finally {
    saving.value = false
  }
}

watch([() => props.initialMarketAnalysis, () => props.initialNextAction],
  ([newMarketAnalysis, newNextAction]) => {
    if (marketEditor.value && newMarketAnalysis !== marketEditor.value.getHTML()) {
      marketEditor.value.commands.setContent(newMarketAnalysis || '')
    }
    if (nextActionEditor.value && newNextAction !== nextActionEditor.value.getHTML()) {
      nextActionEditor.value.commands.setContent(newNextAction || '')
    }
  }
)

onMounted(async () => {
  await nextTick()
  await loadNote()
})

onBeforeUnmount(() => {
  marketEditor.value?.destroy()
  nextActionEditor.value?.destroy()
})

defineExpose({ handleSave })
</script>

<style scoped>
.note-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  flex: 1;
}

.toolbar-group :deep(.el-button) {
  padding: 4px 8px;
  font-size: 13px;
}

.note-section {
  margin-bottom: 16px;
}

.note-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.editor-wrapper {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  min-height: 200px;
}

:deep(.tiptap-content) .ProseMirror {
  outline: none;
  min-height: 200px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

:deep(.tiptap-content) .ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  color: #c0c4cc;
  pointer-events: none;
  float: left;
  height: 0;
}

:deep(.tiptap-content) .ProseMirror h2 {
  font-size: 18px;
  font-weight: 700;
  margin: 12px 0 6px;
  color: #1d1d1d;
}

:deep(.tiptap-content) .ProseMirror h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 10px 0 4px;
  color: #1d1d1d;
}

:deep(.tiptap-content) .ProseMirror p { margin: 0 0 6px; }

:deep(.tiptap-content) .ProseMirror ul,
:deep(.tiptap-content) .ProseMirror ol { padding-left: 20px; margin: 0 0 6px; }

:deep(.tiptap-content) .ProseMirror blockquote {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  margin: 8px 0;
  color: #606266;
  background: #f5f7fa;
  border-radius: 0 4px 4px 0;
}

:deep(.tiptap-content) .ProseMirror code {
  background: #f0f0f0;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

:deep(.tiptap-content) .ProseMirror pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px 14px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

:deep(.tiptap-content) .ProseMirror pre code {
  background: none;
  padding: 0;
  color: inherit;
}
</style>
