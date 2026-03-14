<template>
  <div class="cycle-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>周期管理</span>
          <el-button type="primary" @click="openCreateCycleDialog">新建周期</el-button>
        </div>
      </template>

      <el-table :data="cycleList" v-loading="loading" stripe>
        <el-table-column prop="title" label="周期标题" min-width="120" />
        <el-table-column label="时间范围" min-width="180">
          <template #default="{ row }">
            {{ row.start_date }} ~ {{ row.end_date || '进行中' }}
          </template>
        </el-table-column>
        <el-table-column prop="features" label="特点" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="小周期数" width="100">
          <template #default="{ row }">
            {{ row.sub_periods?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewCycleDetail(row)">详情</el-button>
            <el-button type="primary" link @click="openEditCycleDialog(row)">编辑</el-button>
            <el-button type="danger" link @click="deleteCycle(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 周期详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="`周期详情 - ${currentCycle?.title}`" width="800px">
      <div v-if="currentCycle">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="周期标题">{{ currentCycle.title }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentCycle.status === 'active' ? 'success' : 'info'">
              {{ currentCycle.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ currentCycle.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ currentCycle.end_date || '进行中' }}</el-descriptions-item>
          <el-descriptions-item label="周期特点" :span="2">{{ currentCycle.features }}</el-descriptions-item>
        </el-descriptions>

        <div class="sub-periods-section">
          <div class="section-header">
            <span class="section-title">小周期</span>
            <el-button type="primary" size="small" @click="openCreateSubPeriodDialog">新增小周期</el-button>
          </div>
          <el-table :data="currentCycle.sub_periods || []" stripe size="small">
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="period_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="getPeriodTypeTag(row.period_type)">{{ getPeriodTypeName(row.period_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间范围" min-width="150">
              <template #default="{ row }">
                {{ row.start_date }} ~ {{ row.end_date || '进行中' }}
              </template>
            </el-table-column>
            <el-table-column prop="trade_day_count" label="交易日数" width="80" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openEditSubPeriodDialog(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="deleteSubPeriod(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

    <!-- 新建/编辑周期对话框 -->
    <el-dialog v-model="cycleDialogVisible" :title="isEdit ? '编辑周期' : '新建周期'" width="500px">
      <el-form :model="cycleForm" label-width="80px">
        <el-form-item label="周期标题" required>
          <el-input v-model="cycleForm.title" placeholder="例如：2024年度行情" />
        </el-form-item>
        <el-form-item label="开始日期" required>
          <el-date-picker v-model="cycleForm.start_date" type="date" placeholder="选择开始日期" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="cycleForm.end_date" type="date" placeholder="选择结束日期（可选）" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="周期特点">
          <el-input v-model="cycleForm.features" type="textarea" :rows="3" placeholder="描述这个周期的特点" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="cycleForm.status">
            <el-radio value="active">进行中</el-radio>
            <el-radio value="completed">已结束</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cycleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCycle" :loading="saving">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑小周期对话框 -->
    <el-dialog v-model="subPeriodDialogVisible" :title="isEditSubPeriod ? '编辑小周期' : '新增小周期'" width="500px">
      <el-form :model="subPeriodForm" label-width="80px">
        <el-form-item label="小周期类型" required>
          <el-select v-model="subPeriodForm.period_type" placeholder="选择类型" style="width: 100%">
            <el-option value="chaos" label="混沌" />
            <el-option value="rise" label="主升" />
            <el-option value="oscillation" label="震荡" />
            <el-option value="decline" label="退潮" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="subPeriodForm.name" placeholder="默认为类型名称" />
        </el-form-item>
        <el-form-item label="开始日期" required>
          <el-date-picker v-model="subPeriodForm.start_date" type="date" placeholder="选择开始日期" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="subPeriodForm.end_date" type="date" placeholder="选择结束日期（可选）" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subPeriodDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSubPeriod" :loading="saving">{{ isEditSubPeriod ? '保存' : '确定' }}</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCycleList, getCycleDetail, createCycle, updateCycle, deleteCycle as apiDeleteCycle, createSubPeriod, updateSubPeriod as apiUpdateSubPeriod, deleteSubPeriod as apiDeleteSubPeriod } from '@/api'

const loading = ref(false)
const saving = ref(false)
const cycleList = ref([])
const currentCycle = ref(null)
const detailDialogVisible = ref(false)
const cycleDialogVisible = ref(false)
const isEdit = ref(false)

const cycleForm = ref({
  title: '',
  start_date: '',
  end_date: '',
  features: '',
  status: 'active'
})

const subPeriodDialogVisible = ref(false)
const isEditSubPeriod = ref(false)
const currentSubPeriod = ref(null)
const subPeriodForm = ref({
  period_type: '',
  name: '',
  start_date: '',
  end_date: ''
})

const periodTypeMap = {
  chaos: { name: '混沌', type: 'warning' },
  rise: { name: '主升', type: 'success' },
  oscillation: { name: '震荡', type: 'primary' },
  decline: { name: '退潮', type: 'danger' }
}

const getPeriodTypeName = (type) => periodTypeMap[type]?.name || type
const getPeriodTypeTag = (type) => periodTypeMap[type]?.type || 'info'

const loadCycles = async () => {
  loading.value = true
  try {
    const res = await getCycleList()
    cycleList.value = res.data || []
  } catch (e) {
    console.error('加载周期列表失败:', e)
    ElMessage.error('加载周期列表失败')
  } finally {
    loading.value = false
  }
}

const viewCycleDetail = async (row) => {
  try {
    const res = await getCycleDetail(row.id)
    currentCycle.value = res.data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载周期详情失败')
  }
}

const openCreateCycleDialog = () => {
  isEdit.value = false
  cycleForm.value = {
    title: '',
    start_date: '',
    end_date: '',
    features: '',
    status: 'active'
  }
  cycleDialogVisible.value = true
}

const openEditCycleDialog = (row) => {
  isEdit.value = true
  cycleForm.value = {
    title: row.title,
    start_date: row.start_date,
    end_date: row.end_date,
    features: row.features,
    status: row.status
  }
  currentCycle.value = row
  cycleDialogVisible.value = true
}

const saveCycle = async () => {
  if (!cycleForm.value.title || !cycleForm.value.start_date) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await updateCycle(currentCycle.value.id, cycleForm.value)
      ElMessage.success('更新成功')
    } else {
      await createCycle(cycleForm.value)
      ElMessage.success('创建成功')
    }
    cycleDialogVisible.value = false
    loadCycles()
  } catch (e) {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const deleteCycle = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除周期"${row.title}"吗？`, '提示', { type: 'warning' })
    await apiDeleteCycle(row.id)
    ElMessage.success('删除成功')
    loadCycles()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const openCreateSubPeriodDialog = () => {
  isEditSubPeriod.value = false
  currentSubPeriod.value = null
  subPeriodForm.value = {
    period_type: '',
    name: '',
    start_date: '',
    end_date: ''
  }
  subPeriodDialogVisible.value = true
}

const openEditSubPeriodDialog = (row) => {
  isEditSubPeriod.value = true
  currentSubPeriod.value = row
  subPeriodForm.value = {
    period_type: row.period_type,
    name: row.name,
    start_date: row.start_date,
    end_date: row.end_date || ''
  }
  subPeriodDialogVisible.value = true
}

const saveSubPeriod = async () => {
  if (!subPeriodForm.value.period_type || !subPeriodForm.value.start_date) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    const data = {
      ...subPeriodForm.value,
      name: subPeriodForm.value.name || getPeriodTypeName(subPeriodForm.value.period_type)
    }
    if (isEditSubPeriod.value) {
      await apiUpdateSubPeriod(currentSubPeriod.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createSubPeriod(currentCycle.value.id, data)
      ElMessage.success('创建成功')
    }
    subPeriodDialogVisible.value = false
    viewCycleDetail(currentCycle.value)
  } catch (e) {
    ElMessage.error(isEditSubPeriod.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const deleteSubPeriod = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除小周期"${row.name}"吗？`, '提示', { type: 'warning' })
    await apiDeleteSubPeriod(row.id)
    ElMessage.success('删除成功')
    viewCycleDetail(currentCycle.value)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadCycles()
})
</script>

<style scoped>
.cycle-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sub-periods-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.section-title {
  font-size: 16px;
  font-weight: bold;
}


</style>
