<template>
  <!-- 大盘指数 + 主要指数行情 一行展示 -->
  <el-row :gutter="12" class="market-row">
    <!-- 大盘指数 -->
    <el-col :span="8" v-if="Object.keys(localMarketData).length > 0">
      <el-card shadow="hover" class="market-card">
        <template #header>
          <div class="card-header">
            <span>大盘指数</span>
            <el-button v-if="marketDetail" type="primary" link @click="$emit('showMarketDetail')">
              <el-icon><Grid /></el-icon> 因子详情
            </el-button>
          </div>
        </template>

        <div class="market-score">
          <div
            class="score-value"
            :class="compositeScore >= 0 ? 'positive' : 'negative'"
          >
            {{ Number(compositeScore).toFixed(3) }}
          </div>
          <div class="score-label">综合得分</div>
        </div>

        <!-- 🧭 顶底仪表盘（TA-CN 计算，阈值来自 2025-2026 回测） -->
        <div v-if="gauge && gauge.market" class="gauge-box">
          <div class="gauge-verdict">🧭 {{ gauge.market.verdict }}</div>
          <div class="gauge-readings">
            量能比 {{ gauge.market.amt_ratio ?? '—' }} · 上涨 {{ gauge.market.up_ratio }}% ·
            涨停 {{ gauge.market.limit_up }}/跌停 {{ gauge.market.limit_dn }} ·
            top100中位 {{ gauge.market.top100_chg }}%
          </div>
          <div v-if="gauge.market.top_score != null" class="gauge-thermo">
            顶底温度计：顶 <b>{{ gauge.market.top_score }}</b>/100<span v-if="gauge.market.tb_top_label" class="thermo-top">（{{ gauge.market.tb_top_label }}）</span>
            ｜底 <b>{{ gauge.market.bot_score }}</b>/100<span v-if="gauge.market.tb_bot_label" class="thermo-bot">（{{ gauge.market.tb_bot_label }}）</span>
          </div>
          <div v-if="gauge.market.position_ladder" class="gauge-ladder">
            🎚️ 建议仓位档（趋势控仓）：<b>{{ gauge.market.position_ladder.state }}</b> →
            <b class="ladder-expo">{{ ladderLabel(gauge.market.position_ladder.exposure) }}（{{ Math.round(gauge.market.position_ladder.exposure * 100) }}%）</b>
            <span class="ladder-ma">上证{{ gauge.market.position_ladder.close }} vs MA60 {{ gauge.market.position_ladder.ma60 }}/MA120 {{ gauge.market.position_ladder.ma120 }}<span v-if="gauge.market.position_ladder.topdiv">·顶背离</span></span>
          </div>
          <div v-if="(gauge.market.top_signals || []).length || (gauge.market.bottom_signals || []).length" class="gauge-signals">
            <div v-for="s in gauge.market.top_signals || []" :key="'t' + s" class="sig-top">⚠ {{ s }}</div>
            <div v-for="s in gauge.market.bottom_signals || []" :key="'b' + s" class="sig-bot">▼ {{ s }}</div>
          </div>
          <div v-if="(gauge.sectors || []).length" class="gauge-sectors">
            <el-tooltip
              v-for="s in gauge.sectors" :key="s.sector" placement="top"
              :content="`顶底温度计 顶${s.sec_top_score ?? '—'}/底${s.sec_bot_score ?? '—'}${s.sec_tb_bot ? '(' + s.sec_tb_bot + ')' : (s.sec_tb_top ? '(' + s.sec_tb_top + ')' : '')} · 回撤${s.drawdown_pct}%(${s.days_since_top}日) · 派发风险${s.dist_risk ?? '—'}/3 · 新高占比${s.nh_now}%/峰${s.nh_peak60}% · 量能比${s.amt_ratio ?? '—'} · 阴阳量比${s.yy_ratio ?? '—'} · corr${s.corr_now ?? '—'}`"
            >
              <el-tag size="small" effect="plain" class="gauge-sector-tag">{{ s.sector }}：{{ s.state }}</el-tag>
            </el-tooltip>
          </div>
        </div>

        <template v-if="keyFactors.length > 0">
          <el-divider style="margin: 10px 0" />
          <el-row :gutter="8">
            <el-col v-for="factor in keyFactors" :key="factor.code" :span="12" class="key-factor-col">
              <div class="key-factor-item">
                <div class="key-factor-value" :class="factor.value >= 0 ? 'positive' : 'negative'">
                  {{ factor.value >= 0 ? '+' : '' }}{{ Number(factor.value).toFixed(2)
                  }}{{ factor.unit ? factor.unit : '' }}
                </div>
                <div class="key-factor-name">{{ factor.name }}</div>
              </div>
            </el-col>
          </el-row>
        </template>
      </el-card>
    </el-col>

    <!-- 主要指数行情 -->
    <el-col :span="16" v-if="localIndexData.length > 0">
      <el-card shadow="hover" class="index-card">
        <template #header>
          <span>主要指数行情</span>
        </template>
        <el-table :data="localIndexData" stripe size="small" style="width: 100%">
          <el-table-column prop="name" label="指数名称" min-width="90" />
          <el-table-column prop="code" label="代码" min-width="80" />
          <el-table-column label="收盘价" min-width="80" align="right">
            <template #default="{ row }">
              {{ row.close.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" min-width="80" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="成交额(亿元)" min-width="100" align="right">
            <template #default="{ row }">
              {{ formatTurnover(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  marketData: {
    type: Object,
    default: () => ({})
  },
  indexData: {
    type: Array,
    default: () => []
  },
  marketDetail: {
    type: Object,
    default: null
  }
})

defineEmits(['showMarketDetail'])

const localMarketData = computed(() => props.marketData)
const localIndexData = computed(() => props.indexData)

// 顶底仪表盘（market_tree.topbottom_gauge，由复盘时从 TA-CN 拉取并入库）
const gauge = computed(() => props.marketDetail?.topbottom_gauge || null)

// 仓位阶梯档位中文（趋势控仓建议，与温度计分工：阶梯管仓位纪律、温度计管情绪预警）
const ladderLabel = (e) => {
  const m = { 1: '满仓', 0.5: '减仓(~半仓)', 0.3: '轻仓', 0: '空仓' }
  return m[e] != null ? m[e] : `${e}`
}

/** 与 useReviewData.marketCompositeScore 一致：factors 里用 market_score */
const compositeScore = computed(() => {
  const m = props.marketData
  if (!m || typeof m !== 'object') return 0
  const raw = m.market_score ?? m['大盘综合得分']
  if (raw == null) return 0
  if (typeof raw === 'object' && raw !== null && 'value' in raw) {
    const v = raw.value
    return v == null || v === '' ? 0 : Number(v) || 0
  }
  return Number(raw) || 0
})

// 成交额字段除一亿，显示亿元（code 可能为英文 snake_case 或中文）
const isTurnoverFactor = (code, factorName) => {
  const c = String(code)
  if (/turnover|amount/i.test(c)) return true
  if (/成交额/.test(c)) return true
  if (factorName && /成交额/.test(String(factorName))) return true
  return false
}

const formatTurnover = (value) => {
  // 2026-05-26: 后端 review_service.py 在 detail_data.indexes 中已把 turnover 除 1e8 转为亿元
  //   前端再除 1e8 → 14616.85 亿 / 1e8 = 0.00（双重换算 bug）
  //   修复：前端不再换算，直接展示
  if (!value) return '0.00'
  const num = Number(value)
  return num.toFixed(2)
}

// 关键因子：展示 factor_name，排除综合得分；成交额因子除一亿
const keyFactors = computed(() => {
  const excludeKeys = ['market_score', '大盘综合得分', 'type', 'indexPrices', 'factors']
  if (!props.marketData || typeof props.marketData !== 'object') return []

  return Object.entries(props.marketData)
    .filter(([key]) => !excludeKeys.includes(key))
    .map(([code, raw]) => {
      let value =
        typeof raw === 'object' && raw !== null && 'value' in raw
          ? Number(raw.value) || 0
          : Number(raw) || 0
      const name =
        typeof raw === 'object' && raw?.factor_name ? raw.factor_name : code
      const turnover = isTurnoverFactor(code, name)
      if (turnover) {
        value = value / 100000000
      }
      return {
        code,
        name,
        value,
        unit: turnover ? '亿元' : ''
      }
    })
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 6)
})

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
</script>

<style scoped>
.market-row {
  margin-bottom: 16px;
}

.market-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.market-score {
  text-align: center;
  padding: 8px 0;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
}

.score-value.positive {
  color: #f56c6c;
}

.score-value.negative {
  color: #67c23a;
}

.score-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.key-factor-col {
  margin-bottom: 8px;
}

.key-factor-item {
  text-align: center;
}

.key-factor-value {
  font-size: 16px;
  font-weight: 600;
}

.key-factor-value.positive {
  color: #f56c6c;
}

.key-factor-value.negative {
  color: #67c23a;
}

.key-factor-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.gauge-box {
  margin-top: 10px;
  padding: 8px 10px;
  background: #f8f9fb;
  border-radius: 6px;
  font-size: 12px;
}
.gauge-verdict { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.gauge-readings { color: #888; margin-bottom: 4px; }
.gauge-thermo { color: #666; margin-bottom: 4px; }
.gauge-thermo .thermo-top { color: #e67e22; }
.gauge-thermo .thermo-bot { color: #27ae60; }
.gauge-ladder { color: #555; margin-bottom: 4px; }
.gauge-ladder .ladder-expo { color: #c0392b; }
.gauge-ladder .ladder-ma { color: #999; margin-left: 6px; font-size: 11px; }
.sig-top { color: #e67e22; }
.sig-bot { color: #27ae60; }
.gauge-sectors { margin-top: 6px; }
.gauge-sector-tag { margin: 2px 4px 0 0; cursor: help; max-width: 100%; }
</style>
