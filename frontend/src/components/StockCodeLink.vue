<template>
  <a
    :href="taCnUrl"
    target="_blank"
    rel="noopener"
    class="stock-code-link"
    :title="`在 TradingAgents-CN 查看 ${sixDigit} 详情`"
    @click.stop
  >
    {{ code }}
    <el-icon class="ext-icon"><TopRight /></el-icon>
  </a>
</template>

<script setup>
import { computed } from 'vue'
import { TopRight } from '@element-plus/icons-vue'

/**
 * 股票代码链接：点击新窗口跳转到 TradingAgents-CN 股票详情页
 * 代码格式自动归一化：sh.002261 / sz.002261 / 002261.SH → 002261
 */
const props = defineProps({
  /** 原始 code，支持 sh.xxx / sz.xxx / xxx / xxx.SH 等形式 */
  code: { type: String, required: true },
})

const TA_CN_BASE = (import.meta.env.VITE_TA_CN_BASE_URL || 'http://192.168.31.123:3000').replace(/\/+$/, '')

const sixDigit = computed(() => {
  if (!props.code) return ''
  let s = String(props.code).trim().toLowerCase()
  if (s.startsWith('sh.') || s.startsWith('sz.') || s.startsWith('bj.')) {
    return s.split('.')[1]
  }
  if (s.endsWith('.sh') || s.endsWith('.sz') || s.endsWith('.bj')) {
    return s.split('.')[0]
  }
  // 纯数字补足到 6 位
  if (/^\d+$/.test(s)) return s.padStart(6, '0')
  return s
})

const taCnUrl = computed(() => `${TA_CN_BASE}/stocks/${sixDigit.value}`)
</script>

<style scoped>
.stock-code-link {
  color: var(--el-color-primary);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.stock-code-link:hover {
  text-decoration: underline;
}
.ext-icon {
  font-size: 11px;
  opacity: 0.55;
  vertical-align: middle;
}
</style>
