<template>
  <el-card shadow="hover" class="cycle-info-card">
    <div class="cycle-info">
      <div class="cycle-title">{{ cycle?.title }}</div>
      <div class="cycle-period">
        <el-tag :type="getPeriodTypeTag(subPeriod?.period_type)">
          {{ getPeriodTypeName(subPeriod?.period_type) }}
        </el-tag>
        <span class="cycle-date">{{ tradeDate }}</span>
      </div>
      <div class="cycle-features" v-if="cycle?.features">
        {{ cycle?.features }}
      </div>
    </div>
  </el-card>
</template>

<script setup>
const props = defineProps({
  cycleInfo: {
    type: Object,
    default: null
  }
})

const cycle = computed(() => props.cycleInfo?.cycle)
const subPeriod = computed(() => props.cycleInfo?.sub_period)
const tradeDate = computed(() => props.cycleInfo?.trade_date || '')

const getPeriodTypeTag = (type) => {
  const map = {
    'daily': 'success',
    'weekly': 'warning',
    'monthly': 'info'
  }
  return map[type] || ''
}

const getPeriodTypeName = (type) => {
  const map = {
    'daily': '日线',
    'weekly': '周线',
    'monthly': '月线'
  }
  return map[type] || type || ''
}
</script>

<style scoped>
.cycle-info-card {
  margin-bottom: 16px;
}

.cycle-info {
  padding: 8px 0;
}

.cycle-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.cycle-period {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.cycle-date {
  color: var(--el-text-color-secondary);
}

.cycle-features {
  color: var(--el-text-color-regular);
  font-size: 14px;
}
</style>
