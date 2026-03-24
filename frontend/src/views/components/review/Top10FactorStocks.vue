<template>
  <el-card shadow="hover" class="stock-table-card">
    <template #header>
      <div class="card-header">
        <span>因子得分 Top 10 股票</span>
        <el-button v-if="factorTree && factorTree.factors" text @click="$emit('showFactorTree')">
          <el-icon><Grid /></el-icon>
          因子体系
        </el-button>
      </div>
    </template>
    <el-table :data="localStocks" stripe>
      <el-table-column type="index" label="排名" width="60" align="center" />
      <el-table-column prop="code" label="代码" width="90" />
      <el-table-column prop="name" label="名称" width="80" />
      <el-table-column label="成交额(亿)" width="90" align="right">
        <template #default="{ row }">
          {{ formatAmount(row.amount || row.turnover || 0) }}
        </template>
      </el-table-column>
      <el-table-column prop="sector" label="所属板块" min-width="100" />
      <el-table-column label="标签" min-width="150">
        <template #default="{ row }">
          <div v-if="stockTags[row.code]?.length > 0" class="stock-tag-list">
            <el-tag
              v-for="tag in stockTags[row.code]"
              :key="tag.id"
              :color="tag.color"
              :style="{ color: getTagTextColor(tag.color) }"
              size="small"
              closable
              @close.stop="$emit('removeTag', row.code, tag)"
            >
              {{ tag.name }}
            </el-tag>
          </div>
          <span v-else class="no-tag">无</span>
        </template>
      </el-table-column>
      <el-table-column label="综合得分" width="90" align="center">
        <template #default="{ row }">
          <el-tag type="success">{{ (row.totalScore || 0).toFixed(2) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="$emit('showStockDetail', row)">
            因子详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
const props = defineProps({
  stocks: {
    type: Array,
    default: () => []
  },
  factorTree: {
    type: Object,
    default: null
  },
  stockTags: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['showFactorTree', 'showStockDetail', 'removeTag'])

const localStocks = computed(() => props.stocks)

const formatAmount = (value) => {
  if (!value) return '0.00'
  const num = Number(value)
  if (num >= 100000000) {
    return (num / 100000000).toFixed(2)
  } else if (num >= 10000) {
    return (num / 10000).toFixed(2)
  }
  return num.toFixed(2)
}

const getTagTextColor = (bgColor) => {
  if (!bgColor) return '#fff'
  const hex = bgColor.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.5 ? '#333' : '#fff'
}
</script>

<style scoped>
.stock-table-card {
  margin-bottom: 16px;
}

.stock-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.no-tag {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
</style>
