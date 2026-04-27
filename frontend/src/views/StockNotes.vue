<template>
  <div class="notes-page">
    <!-- 左侧：笔记列表 -->
    <div class="notes-sidebar">
      <div class="sidebar-header">
        <div class="search-box">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索笔记..."
            clearable
            size="default"
            @input="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <el-button type="primary" class="new-btn" @click="createNewNote">
          <el-icon><Plus /></el-icon>
          新建笔记
        </el-button>
      </div>

      <!-- 标签筛选 -->
      <div class="tags-filter" v-if="allTags.length">
        <span class="filter-label">标签：</span>
        <el-tag
          v-for="tag in allTags"
          :key="tag"
          size="small"
          :type="activeTag === tag ? 'primary' : 'info'"
          class="tag-item"
          style="cursor:pointer"
          @click="toggleTag(tag)"
        >{{ tag }}</el-tag>
        <el-tag v-if="activeTag" size="small" type="warning" class="tag-item" style="cursor:pointer" @click="activeTag = ''">
          <el-icon><Close /></el-icon> 清除
        </el-tag>
      </div>

      <!-- 笔记列表 -->
      <div class="notes-list" v-loading="loading">
        <div v-if="!loading && notes.length === 0" class="empty-hint">
          <el-empty description="暂无笔记，点击上方按钮创建" :image-size="80" />
        </div>
        <div
          v-for="note in notes"
          :key="note.id"
          class="note-item"
          :class="{ active: selectedNoteId === note.id }"
          @click="selectNote(note)"
        >
          <div class="note-item-header">
            <el-icon v-if="note.isPinned" class="pin-icon" color="#E6A23C"><StarFilled /></el-icon>
            <span class="note-title">{{ note.title || '无标题' }}</span>
          </div>
          <div class="note-item-meta">
            <span
              v-if="note.stockCode"
              class="stock-badge clickable"
              :title="`查看「${note.stockName || note.stockCode}」的复盘详情`"
              @click.stop="jumpToReview(note)"
            >
              {{ note.stockName || note.stockCode }}
            </span>
            <span class="note-date">{{ formatDate(note.updateTime) }}</span>
          </div>
          <div class="note-item-tags" v-if="note.tags">
            <el-tag
              v-for="tag in note.tags.split(',').slice(0, 3)"
              :key="tag"
              size="small"
              type="info"
            >{{ tag.trim() }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="list-footer" v-if="total > pageSize">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="handlePageChange"
          :small="true"
        />
      </div>
    </div>

    <!-- 右侧：编辑器 -->
    <div class="notes-editor">
      <div v-if="!editingNote" class="editor-placeholder">
        <el-empty description="选择或新建笔记开始编辑" :image-size="120">
          <el-button type="primary" @click="createNewNote">
            <el-icon><Plus /></el-icon>
            新建笔记
          </el-button>
        </el-empty>
      </div>

      <div v-else class="editor-container">
        <!-- 编辑器工具栏 -->
        <div class="editor-toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="editingNote.title"
              placeholder="笔记标题（可选）"
              class="title-input"
              maxlength="100"
              show-word-limit
              @input="markDirty"
            />
          </div>
          <div class="toolbar-right">
            <el-button-group size="small">
              <el-button :type="editingNote.isPinned ? 'warning' : 'default'" @click="togglePin">
                <el-icon><Star /></el-icon>
                {{ editingNote.isPinned ? '取消置顶' : '置顶' }}
              </el-button>
            </el-button-group>
            <el-button type="primary" size="small" :loading="saving" @click="saveNote">
              <el-icon><DocumentChecked /></el-icon>
              保存
            </el-button>
            <el-button type="danger" size="small" plain @click="handleDeleteNote">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>

        <!-- 富文本工具栏（与 NoteEditor 保持一致） -->
        <div class="rich-toolbar">
          <el-button-group size="small">
            <el-button @click="editor?.chain().focus().toggleBold().run()" :type="editor?.isActive('bold') ? 'primary' : 'default'" title="加粗"><strong>B</strong></el-button>
            <el-button @click="editor?.chain().focus().toggleItalic().run()" :type="editor?.isActive('italic') ? 'primary' : 'default'" title="斜体"><em>I</em></el-button>
            <el-button @click="editor?.chain().focus().toggleUnderline().run()" :type="editor?.isActive('underline') ? 'primary' : 'default'" title="下划线"><u>U</u></el-button>
            <el-button @click="editor?.chain().focus().toggleStrike().run()" :type="editor?.isActive('strike') ? 'primary' : 'default'" title="删除线"><s>S</s></el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button-group size="small">
            <el-button @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()" :type="editor?.isActive('heading', { level: 2 }) ? 'primary' : 'default'" title="标题2">H2</el-button>
            <el-button @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()" :type="editor?.isActive('heading', { level: 3 }) ? 'primary' : 'default'" title="标题3">H3</el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button-group size="small">
            <el-button @click="editor?.chain().focus().toggleBulletList().run()" :type="editor?.isActive('bulletList') ? 'primary' : 'default'" title="无序列表"><el-icon><List /></el-icon></el-button>
            <el-button @click="editor?.chain().focus().toggleOrderedList().run()" :type="editor?.isActive('orderedList') ? 'primary' : 'default'" title="有序列表"><el-icon><List /></el-icon>#</el-button>
          </el-button-group>
          <el-divider direction="vertical" />
          <el-button size="small" @click="editor?.chain().focus().setHorizontalRule().run()" title="分隔线">——</el-button>
          <el-button size="small" @click="editor?.chain().focus().toggleBlockquote().run()" :type="editor?.isActive('blockquote') ? 'primary' : 'default'" title="引用">引用</el-button>
          <el-button size="small" @click="editor?.chain().focus().toggleCodeBlock().run()" :type="editor?.isActive('codeBlock') ? 'primary' : 'default'" title="代码块">代码</el-button>
        </div>

        <!-- 关联股票（自动补全） -->
        <div class="stock-link">
          <el-row :gutter="12" align="middle">
            <el-col :span="12">
              <el-select
                v-model="editingNote.stockCode"
                placeholder="输入代码或名称搜索股票"
                filterable
                remote
                :remote-method="searchStock"
                :loading="stockLoading"
                clearable
                reserve-keyword
                style="width: 100%"
                @change="onStockCodeChange"
              >
                <el-option
                  v-for="s in stockOptions"
                  :key="s.stock_code"
                  :label="`${s.stock_code} ${s.stock_name}`"
                  :value="s.stock_code"
                >
                  <span>{{ s.stock_code }}</span>
                  <span style="color: #909399; margin-left: 8px">{{ s.stock_name }}</span>
                </el-option>
              </el-select>
            </el-col>
          </el-row>
        </div>

        <!-- 富文本编辑器 -->
        <div class="tiptap-wrapper">
          <editor-content :editor="editor" class="tiptap-content" />
        </div>

        <!-- 标签管理 -->
        <div class="tags-section">
          <span class="tags-label">标签：</span>
          <el-tag
            v-for="tag in editingTags"
            :key="tag"
            closable
            size="default"
            class="note-tag"
            @close="removeTag(tag)"
          >{{ tag }}</el-tag>
          <el-input
            v-model="newTagInput"
            size="small"
            style="width: 100px"
            placeholder="添加标签"
            @keyup.enter="addTag"
            @blur="addTag"
          />
          <span class="tag-hint">回车添加，多个用逗号分隔</span>
        </div>

        <!-- 保存状态提示 -->
        <div class="save-status" v-if="isDirty">
          <el-icon><Edit /></el-icon>
          有未保存的修改
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import {
  getNoteList, getNote, createNote, updateNote, deleteNote,
  toggleNotePin, getNoteTags, searchStocks, getReviewTaskList
} from '@/api'

// ============ 状态 ============
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const notes = ref([])
const selectedNoteId = ref(null)
const editingNote = ref(null)
const allTags = ref([])
const activeTag = ref('')
const searchKeyword = ref('')
const newTagInput = ref('')
const isDirty = ref(false)
const stockOptions = ref([])
const stockLoading = ref(false)

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
let searchTimer = null

// ============ 富文本编辑器 ============
const editor = useEditor({
  extensions: [
    StarterKit.configure({ heading: { levels: [2, 3] } }),
    Placeholder.configure({ placeholder: '开始记录你的投资心得...' }),
    Underline,
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Link.configure({ openOnClick: false }),
    Image,
  ],
  content: '',
  onUpdate: () => {
    markDirty()
    if (editingNote.value) {
      editingNote.value.content = editor.value.getHTML()
    }
  },
})

const editingTags = computed(() => {
  if (!editingNote.value?.tags) return []
  return editingNote.value.tags.split(',').map(t => t.trim()).filter(Boolean)
})

// ============ 数据加载 ============
async function loadNotes() {
  loading.value = true
  try {
    const res = await getNoteList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value,
      tag: activeTag.value,
    })
    if (res.code === 200) {
      notes.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    ElMessage.error('加载笔记失败')
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  try {
    const res = await getNoteTags()
    if (res.code === 200) {
      allTags.value = res.data || []
    }
  } catch (e) { /* ignore */ }
}

// ============ 股票搜索 ============
async function searchStock(query) {
  if (!query || query.length < 1) {
    stockOptions.value = []
    return
  }
  stockLoading.value = true
  try {
    const res = await searchStocks(query)
    if (res.code === 200) {
      stockOptions.value = res.data || []
    }
  } catch (e) {
    stockOptions.value = []
  } finally {
    stockLoading.value = false
  }
}

function onStockCodeChange(code) {
  if (!code) {
    editingNote.value.stockName = ''
    stockOptions.value = []
    return
  }
  const found = stockOptions.value.find(s => s.stock_code === code)
  editingNote.value.stockName = found ? found.stock_name : ''
  markDirty()
}

// ============ 笔记操作 ============
function selectNote(note) {
  if (isDirty.value && !confirm('有未保存的修改，确定要切换吗？')) return
  selectedNoteId.value = note.id
  loadNoteDetail(note.id)
}

async function loadNoteDetail(noteId) {
  try {
    const res = await getNote(noteId)
    if (res.code === 200 && res.data) {
      editingNote.value = { ...res.data }
      editor.value?.commands.setContent(res.data.content || '')
      stockOptions.value = res.data.stockCode
        ? [{ stock_code: res.data.stockCode, stock_name: res.data.stockName }]
        : []
      isDirty.value = false
    }
  } catch (e) {
    ElMessage.error('加载笔记详情失败')
  }
}

function createNewNote() {
  if (isDirty.value && !confirm('有未保存的修改，确定要新建吗？')) return
  selectedNoteId.value = null
  editingNote.value = {
    id: null, title: '', content: '', stockCode: '', stockName: '',
    tags: '', isPinned: false,
  }
  editor.value?.commands.clearContent()
  stockOptions.value = []
  isDirty.value = false
}

async function saveNote() {
  const raw = editor.value?.getHTML()?.replace(/<[^>]+>/g, '').trim() || ''
  if (!raw) {
    ElMessage.warning('请输入笔记内容')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: editingNote.value.title,
      content: editingNote.value.content || editor.value?.getHTML() || '',
      stockCode: editingNote.value.stockCode,
      stockName: editingNote.value.stockName,
      tags: editingNote.value.tags,
      isPinned: editingNote.value.isPinned,
    }
    let res
    if (editingNote.value.id) {
      res = await updateNote(editingNote.value.id, payload)
    } else {
      res = await createNote(payload)
    }
    if (res.code === 200) {
      editingNote.value.id = res.data.id
      editingNote.value.title = res.data.title
      isDirty.value = false
      ElMessage.success('保存成功')
      loadNotes()
      loadTags()
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteNote() {
  if (!editingNote.value?.id) return
  try {
    await ElMessageBox.confirm('确定要删除这条笔记吗？', '删除确认', { type: 'warning' })
  } catch { return }
  try {
    const res = await deleteNote(editingNote.value.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      editingNote.value = null
      editor.value?.commands.clearContent()
      selectedNoteId.value = null
      loadNotes()
      loadTags()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function togglePin() {
  if (!editingNote.value?.id) return
  try {
    const res = await toggleNotePin(editingNote.value.id)
    if (res.code === 200) {
      editingNote.value.isPinned = res.data.isPinned
      loadNotes()
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// ============ 跳转复盘详情 ============
async function jumpToReview(note) {
  if (!note.stockCode) return
  try {
    // 查找包含这只股票的复盘任务，取最新一个
    const res = await getReviewTaskList({ page: 1, page_size: 20 })
    if (res.code === 200) {
      const tasks = res.data.list || []
      // 优先选已完成且包含该股票的
      const task = tasks.find(t =>
        (t.status === 'completed' || t.status === 'success') && t.stockCode === note.stockCode
      ) || tasks.find(t => t.status === 'completed' || t.status === 'success')

      if (task && task.id) {
        router.push(`/review/result/${task.id}?stock_code=${note.stockCode}`)
      } else {
        ElMessage.info(`暂无「${note.stockName || note.stockCode}」的复盘数据`)
      }
    }
  } catch (e) {
    ElMessage.error('查找复盘数据失败')
  }
}

// ============ 标签管理 ============
function toggleTag(tag) {
  activeTag.value = activeTag.value === tag ? '' : tag
  currentPage.value = 1
  loadNotes()
}

function addTag() {
  const input = newTagInput.value.trim()
  if (!input) return
  const tags = input.split(',').map(t => t.trim()).filter(Boolean)
  const current = editingNote.value.tags
    ? editingNote.value.tags.split(',').map(t => t.trim()).filter(Boolean)
    : []
  editingNote.value.tags = [...new Set([...current, ...tags])].join(',')
  newTagInput.value = ''
  markDirty()
}

function removeTag(tag) {
  const current = editingNote.value.tags.split(',').map(t => t.trim()).filter(Boolean)
  editingNote.value.tags = current.filter(t => t !== tag).join(',')
  markDirty()
}

// ============ 搜索 & 分页 ============
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadNotes()
  }, 400)
}

function handlePageChange(page) {
  currentPage.value = page
  loadNotes()
}

function markDirty() {
  isDirty.value = true
}

// ============ 工具 ============
function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ============ 生命周期 ============
onMounted(() => {
  loadNotes()
  loadTags()
})

onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>

<style scoped>
.notes-page {
  display: flex;
  height: calc(100vh - 40px);
  gap: 0;
  background: #f5f7fa;
}

/* ============ 左侧列表 ============ */
.notes-sidebar {
  width: 320px;
  min-width: 280px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.new-btn { width: 100%; }

.notes-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.note-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.note-item:hover { background: #f5f7fa; }
.note-item.active { background: #ecf5ff; border-color: #409eff; }

.note-item-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}

.pin-icon { font-size: 12px; flex-shrink: 0; }

.note-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.note-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.stock-badge {
  font-size: 11px;
  background: #e6f0ff;
  color: #409eff;
  padding: 1px 6px;
  border-radius: 4px;
}

.stock-badge.clickable {
  cursor: pointer;
}

.stock-badge.clickable:hover {
  background: #cce0ff;
  text-decoration: underline;
}

.note-date { font-size: 11px; color: #909399; }
.note-item-tags { display: flex; flex-wrap: wrap; gap: 3px; }
.empty-hint { padding: 20px 0; }

.tags-filter {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.filter-label { font-size: 12px; color: #909399; flex-shrink: 0; }
.list-footer { padding: 8px; border-top: 1px solid #f0f0f0; display: flex; justify-content: center; }

/* ============ 右侧编辑器 ============ */
.notes-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.editor-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
}

.toolbar-left { flex: 1; }
.title-input { max-width: 400px; }
.toolbar-right { display: flex; gap: 8px; align-items: center; }

/* 富文本工具栏 */
.rich-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
  flex-wrap: wrap;
}

.stock-link {
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
}

/* TipTap 编辑器 */
.tiptap-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
}

:deep(.tiptap-content) .ProseMirror {
  outline: none;
  min-height: 300px;
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
  padding: 16px 0;
}

:deep(.tiptap-content) .ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  color: #c0c4cc;
  pointer-events: none;
  float: left;
  height: 0;
}

:deep(.tiptap-content) .ProseMirror h2 { font-size: 20px; font-weight: 700; margin: 16px 0 8px; }
:deep(.tiptap-content) .ProseMirror h3 { font-size: 16px; font-weight: 600; margin: 12px 0 6px; }
:deep(.tiptap-content) .ProseMirror p { margin: 0 0 8px; }
:deep(.tiptap-content) .ProseMirror ul,
:deep(.tiptap-content) .ProseMirror ol { padding-left: 24px; margin: 0 0 8px; }

:deep(.tiptap-content) .ProseMirror blockquote {
  border-left: 3px solid #409eff;
  padding-left: 16px;
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
  padding: 12px 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

:deep(.tiptap-content) .ProseMirror pre code { background: none; padding: 0; color: inherit; }
:deep(.tiptap-content) .ProseMirror hr { border: none; border-top: 1px solid #e4e7ed; margin: 16px 0; }

/* 标签区 */
.tags-section {
  padding: 10px 16px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.tags-label { font-size: 13px; color: #909399; flex-shrink: 0; }
.note-tag { margin: 0; }
.tag-hint { font-size: 11px; color: #c0c4cc; margin-left: 4px; }

/* 保存状态 */
.save-status {
  padding: 6px 16px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
}
</style>
