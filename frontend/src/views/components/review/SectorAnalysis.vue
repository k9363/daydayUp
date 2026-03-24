<template>
  <el-card shadow="hover" class="sector-table-card">
    <template #header>
      <div class="card-header">
        <span>板块得分 Top 10</span>
      </div>
    </template>
    <el-row :gutter="12">
      <el-col
        v-for="sector in localSectors"
        :key="sector.sector || sector.name"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <div class="sector-item" @click="$emit('selectSector', sector)">
          <div class="sector-header">
            <span class="sector-name">{{ sector.sector || sector.name }}</span>
            <span class="sector-count">({{ sector.stockCount || sector.count || 0 }})</span>
          </div>
          <div class="sector-score">
            <el-tag :type="getScoreTagType(sector.score)" size="small">
              {{ Number(sector.score || 0).toFixed(2) }}
            </el-tag>
          </div>
          <div class="sector-stocks" v-if="sector.topStocks?.length > 0">
            <el-tag
              v-for="stock in sector.topStocks.slice(0, 3)"
              :key="stock.code || stock"
              size="small"
              type="info"
              class="stock-tag"
            >
              {{ stock.name || stock }}
            </el-tag>
            <span v-if="sector.topStocks.length > 3" class="more-stocks">
              +{{ sector.topStocks.length - 3 }}
            </span>
          </div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
const props = defineProps({
  sectors: {
    type: Array,
    default: () => []
  }
})

defineEmits(['selectSector'])

const localSectors = computed(() => props.sectors)

const getScoreTagType = (score) => {
  const num = Number(score) || 0
  if (num > 0) return 'danger'
  if (num < 0) return 'success'
  return 'info'
}
</script>

<style scoped>
.sector-table-card {
  margin-bottom: 16px;
}

.sector-item {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.sector-item:hover {
  background: var(--el-fill-color);
  transform: translateY(-2px);
}

.sector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sector-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.sector-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.sector-score {
  margin-bottom: 8px;
}

.sector-stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.stock-tag {
  margin-right: 2px;
}

.more-stocks {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
