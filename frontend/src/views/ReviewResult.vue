<template>
  <div class="review-result">
    <!-- 头部信息 -->
    <div class="header">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">复盘分析结果</span>
        </template>
        <template #extra>
          <el-button :loading="sendingEmail" :disabled="!taskId" @click="sendEmail">
            <el-icon><Message /></el-icon>
            发送邮件
          </el-button>
          <el-button type="primary" @click="refreshData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </template>
      </el-page-header>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 错误提示 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon class="error-alert" />

    <!-- 数据内容 -->
    <div v-else-if="chartData" class="content">
      <!-- 周期信息 -->
      <CycleInfoCard v-if="cycleInfo" :cycle-info="cycleInfo" />

      <!-- 每日笔记区域 -->
      <NoteEditor
        v-if="currentTradeDate"
        :trade-date="currentTradeDate"
        @save="handleSaveNote"
      />
      <!-- 大盘指数 + 主要指数行情 一行展示 -->
      <el-row :gutter="12" class="market-row" v-if="indexData.length > 0 || Object.keys(marketData).length > 0">
        <!-- 大盘指数 -->
        <el-col :span="8" v-if="Object.keys(marketData).length > 0">
          <el-card shadow="hover" class="market-card">
            <template #header>
              <div class="card-header">
                <span>大盘指数</span>
                <el-button v-if="marketDetail" type="primary" link @click="showMarketDetailDialog = true">
                  <el-icon><Grid /></el-icon> 因子详情
                </el-button>
              </div>
            </template>
            
            <!-- 综合得分（后端 factors.market_score，非中文键） -->
            <div class="market-score">
              <div class="score-value" :class="marketCompositeScore >= 0 ? 'positive' : 'negative'">
                {{ Number(marketCompositeScore).toFixed(3) }}
              </div>
              <div class="score-label">综合得分</div>
            </div>

            <!-- 子因子列表 -->
            <template v-if="marketKeyFactors.length > 0">
              <el-divider style="margin: 10px 0" />
              <el-row :gutter="8">
                <el-col
                  v-for="factor in marketKeyFactors"
                  :key="factor.code"
                  :span="12"
                  class="key-factor-col"
                >
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
        <el-col :span="16" v-if="indexData.length > 0">
          <el-card shadow="hover" class="index-card">
            <template #header>
              <span>主要指数行情</span>
            </template>
            <el-table :data="indexData" stripe size="small" style="width: 100%">
              <el-table-column prop="name" label="指数名称" min-width="90" />
              <el-table-column label="代码" min-width="80">
                <template #default="{ row }">
                  <StockCodeLink :code="row.code" />
                </template>
              </el-table-column>
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
                  {{ formatIndexTurnoverYi(row.amount || row.turnover || 0) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 因子得分排名 Top 10 -->
      <el-card shadow="hover" class="stock-table-card" v-if="top10FactorStocks.length > 0">
        <template #header>
          <div class="card-header">
            <span>因子得分 Top 10 股票</span>
            <el-button 
              v-if="factorTree && factorTree.factors" 
              text 
              @click="showFactorTreeDialog = true"
            >
              <el-icon><Grid /></el-icon>
              因子体系
            </el-button>
          </div>
        </template>
        <el-table :data="top10FactorStocks" stripe>
          <el-table-column type="index" label="排名" width="60" align="center" />
          <el-table-column label="代码" width="100">
            <template #default="{ row }">
              <StockCodeLink :code="row.code" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" width="80" />
          <el-table-column label="成交额(亿)" width="90" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="所属板块" min-width="280">
            <template #default="{ row }">
              <div v-if="rowSectors(row.code).length > 0">
                <el-popover
                  v-for="sector in rowSectors(row.code)"
                  :key="sector.sector_code"
                  trigger="click"
                  :width="230"
                  placement="top"
                >
                  <template #reference>
                    <el-tag
                      :type="sectorTagType(sector.sector_type)"
                      size="small"
                      :effect="sector.priority > 0 ? 'dark' : 'light'"
                      class="sector-tag clickable"
                    >
                      {{ sector.sector_name }}<template v-if="sector.priority > 0"> ·{{ sector.priority }}</template>
                    </el-tag>
                  </template>
                  <div>
                    <div style="font-weight:600;margin-bottom:6px">{{ sector.sector_name }}</div>
                    <div style="display:flex;align-items:center;gap:6px">
                      <span>优先级</span>
                      <el-select :model-value="sector.priority || 0" size="small" style="width:80px"
                                 @change="(v) => updateSectorPriority(sector, v, row.code)">
                        <el-option v-for="n in 11" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
                      </el-select>
                    </div>
                  </div>
                </el-popover>
              </div>
              <span v-else>{{ row.sector || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="标签" min-width="150">
            <template #default="{ row }">
              <div v-if="stockTags[row.code] && stockTags[row.code].length > 0" class="stock-tag-list">
                <el-tag
                  v-for="tag in stockTags[row.code]"
                  :key="tag.id"
                  :color="tag.color"
                  :style="{ color: getTagTextColor(tag.color) }"
                  size="small"
                  closable
                  @close.stop="removeStockTagDirect(row.code, tag)"
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
          
          <!-- 操作列 -->
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="showStockFactorTree(row)">
                因子详情
              </el-button>
              <el-button type="info" link size="small" @click="openSectorDialog(row)">
                板块
              </el-button>
              <el-button type="warning" link size="small" @click="openTagDialog(row)">
                标签
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 当日全市场综合分析（TA-CN 工作日 18:45 自动 cron + 手动可补；2026-05-24 新增）-->
      <!-- 用 useReviewData 暴露的 tradeDate（兼容 chartData 为 array / object 两种格式）-->
      <BatchMarketSummary :trade-date="tradeDate" />

      <!-- 淘股吧手机端热帖聚合（每日 17:00 cron 拉 m.tgb.cn/getMZh 聚合 Top10）-->
      <TgbHotPostsSummary :trade-date="tradeDate" />

      <!-- 淘股吧特别关注流（每日 17:05 cron 拉 spefocus/friendActions 时间线）-->
      <TgbSpecialFocusSummary :trade-date="tradeDate" />

      <!-- AI 多代理分析报告（TradingAgents-CN 推送） -->
      <ExternalAnalysisPanel
        :stock-codes="top10FactorStocks.map(s => s.code)"
        :name-lookup="top10NameLookup"
      />

      <!-- 因子树详情对话框 - 树形结构展示 -->
      <el-dialog
        v-model="showFactorTreeDialog"
        :title="currentStock ? `${currentStock.name} (${currentStock.code}) 因子得分详情` : '因子体系'"
        width="900px"
        destroy-on-close
      >
        <div v-if="factorTree && factorTree.factors" class="factor-tree-dialog">
          <!-- 综合得分展示 -->
          <div class="total-score" v-if="currentStock">
            <span class="score-label">综合得分</span>
            <span class="score-value">{{ (currentStock.totalScore || 0).toFixed(2) }}</span>
          </div>
          
          <!-- 树形结构 -->
          <div class="tree-visualization">
            <el-tree
              :data="stockFactorTreeData"
              :props="treeVisualProps"
              default-expand-all
              node-key="id"
              class="factor-visual-tree"
            >
              <template #default="{ node, data }">
                <div class="visual-node" :class="[data.levelClass, { 'has-value': data.value !== undefined }]">
                  <!-- 节点图标 -->
                  <span class="node-icon">
                    <el-icon v-if="data.level === 1"><Monitor /></el-icon>
                    <el-icon v-else-if="data.level === 2"><Connection /></el-icon>
                    <el-icon v-else-if="data.level === 3"><Trophy /></el-icon>
                  </span>
                  
                  <!-- 节点内容 -->
                  <span class="node-content">
                    <span class="node-label">{{ data.name }}</span>
                    <span class="node-code">({{ data.code }})</span>
                  </span>
                  
                  <!-- 节点值 -->
                  <span v-if="data.value !== undefined" class="node-value" :class="data.value >= 0 ? 'positive' : 'negative'">
                    {{ data.value >= 0 ? '+' : '' }}{{ data.value.toFixed(2) }}
                  </span>
                  
                  <!-- 公式 -->
                  <span v-if="data.expression" class="node-formula">{{ data.expression }}</span>
                  
                  <!-- 连接线说明 -->
                  <span v-if="data.isDependency" class="dep-arrow">←</span>
                </div>
              </template>
            </el-tree>
          </div>
          
          <!-- 图例说明 -->
          <div class="tree-legend">
            <span class="legend-item"><el-icon><Monitor /></el-icon> 数据源</span>
            <span class="legend-item"><el-icon><Connection /></el-icon> 中间因子</span>
            <span class="legend-item"><el-icon><Trophy /></el-icon> 综合得分</span>
          </div>
        </div>
        <template #footer>
          <el-button @click="showFactorTreeDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 大盘指数详情弹窗 - 与股票保持一致的树形结构 -->
      <el-dialog
        v-model="showMarketDetailDialog"
        title="大盘指数详情"
        width="900px"
        destroy-on-close
      >
        <div v-if="marketDetail" class="factor-tree-dialog">
          <!-- 综合得分展示 -->
          <div class="total-score">
            <span class="score-label">大盘综合得分</span>
            <span class="score-value">{{ Number(marketCompositeScore).toFixed(4) }}</span>
          </div>
          
          <!-- 树形结构 -->
          <div class="tree-visualization">
            <el-tree
              :data="marketFactorTreeData"
              :props="treeVisualProps"
              default-expand-all
              node-key="id"
              class="factor-visual-tree"
            >
              <template #default="{ node, data }">
                <div class="visual-node" :class="[data.levelClass, { 'has-value': data.value !== undefined }]">
                  <!-- 节点图标 -->
                  <span class="node-icon">
                    <el-icon v-if="data.level === 1"><Monitor /></el-icon>
                    <el-icon v-else-if="data.level === 2"><Connection /></el-icon>
                    <el-icon v-else-if="data.level === 3"><Trophy /></el-icon>
                  </span>
                  
                  <!-- 节点内容 -->
                  <span class="node-content">
                    <span class="node-label">{{ data.name }}</span>
                    <span class="node-code" v-if="data.code">({{ data.code }})</span>
                  </span>
                  
                  <!-- 节点值 -->
                  <span v-if="data.value !== undefined" class="node-value" :class="data.value >= 0 ? 'positive' : 'negative'">
                    {{ typeof data.value === 'number' ? (data.value >= 0 ? '+' : '') + data.value.toFixed(2) : data.value
                    }}{{ data.valueUnit || '' }}
                  </span>
                  
                  <!-- 公式 -->
                  <span v-if="data.expression" class="node-formula">{{ data.expression }}</span>
                  
                  <!-- 连接线说明 -->
                  <span v-if="data.isDependency" class="dep-arrow">←</span>
                </div>
              </template>
            </el-tree>
          </div>
        </div>
        <template #footer>
          <el-button @click="showMarketDetailDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 板块得分因子详情弹窗 - 与股票/大盘因子保持一致的树形结构 -->
      <el-dialog
        v-model="showSectorFactorDialog"
        :title="currentSector ? `${currentSector.sector} 板块得分详情` : '板块因子'"
        width="900px"
        destroy-on-close
      >
        <div v-if="currentSector" class="factor-tree-dialog">
          <!-- 综合得分展示 -->
          <div class="total-score">
            <span class="score-label">{{ sectorScoreExpressionName }}</span>
            <span class="score-value">{{ Number(currentSector.score || 0).toFixed(2) }}</span>
          </div>

          <!-- 树形结构 -->
          <div class="tree-visualization">
            <el-tree
              :data="sectorFactorTreeData"
              :props="treeVisualProps"
              default-expand-all
              node-key="id"
              class="factor-visual-tree"
            >
              <template #default="{ node, data }">
                <div class="visual-node" :class="[data.levelClass, { 'has-value': data.value !== undefined }]">
                  <span class="node-icon">
                    <el-icon v-if="data.level === 1"><Monitor /></el-icon>
                    <el-icon v-else-if="data.level === 2"><Connection /></el-icon>
                    <el-icon v-else-if="data.level === 3"><Trophy /></el-icon>
                  </span>
                  <span class="node-content">
                    <span class="node-label">{{ data.name }}</span>
                    <span class="node-code">({{ data.code }})</span>
                  </span>
                  <span v-if="data.value !== undefined" class="node-value" :class="data.value >= 0 ? 'positive' : 'negative'">
                    {{ data.value >= 0 ? '+' : '' }}{{ data.value.toFixed(2) }}
                  </span>
                  <span v-if="data.expression" class="node-formula">{{ data.expression }}</span>
                </div>
              </template>
            </el-tree>
          </div>

          <!-- 图例说明 -->
          <div class="tree-legend">
            <span class="legend-item"><el-icon><Monitor /></el-icon> 因子</span>
            <span class="legend-item"><el-icon><Trophy /></el-icon> 板块得分</span>
          </div>
        </div>
        <template #footer>
          <el-button @click="showSectorFactorDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 板块统计详情：行业 / 概念 各自独立排名取前10，左右并排占满 -->
      <el-row :gutter="16" class="sector-detail-row">
        <el-col :xs="24" :md="12">
          <el-card shadow="hover" class="sector-table-card">
            <template #header>
              <span>板块统计详情 · 行业</span>
            </template>
            <el-table :data="industrySectors" stripe style="width: 100%">
              <el-table-column type="index" label="排名" width="70" align="center" />
              <el-table-column prop="sector" label="板块" min-width="110" show-overflow-tooltip />
              <el-table-column label="得分" width="90" align="center">
                <template #default="{ row }">
                  <el-tag type="warning" class="clickable-tag" @click="showSectorFactorTree(row)">{{ Math.round(row.score) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="股票数量" width="100" align="center">
                <template #default="{ row }">
                  <el-tag type="info" class="clickable-tag" @click="handleShowSectorStocks(row)">{{ row.count }}只</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card shadow="hover" class="sector-table-card">
            <template #header>
              <span>板块统计详情 · 概念</span>
            </template>
            <el-table :data="conceptSectors" stripe style="width: 100%">
              <el-table-column type="index" label="排名" width="70" align="center" />
              <el-table-column prop="sector" label="板块" min-width="110" show-overflow-tooltip />
              <el-table-column label="得分" width="90" align="center">
                <template #default="{ row }">
                  <el-tag type="warning" class="clickable-tag" @click="showSectorFactorTree(row)">{{ Math.round(row.score) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="股票数量" width="100" align="center">
                <template #default="{ row }">
                  <el-tag type="info" class="clickable-tag" @click="handleShowSectorStocks(row)">{{ row.count }}只</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- Top100 股票明细 -->
      <el-card shadow="hover" class="stock-table-card">
        <template #header>
          <span>成交额 Top 100 股票明细</span>
        </template>
        <el-table :data="top100Detail" stripe style="width: 100%" max-height="500" :row-class-name="getRowClass">
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column label="代码" width="110">
            <template #default="{ row }">
              <StockCodeLink :code="row.code" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column label="所属板块" min-width="320">
            <template #default="{ row }">
              <div v-if="rowSectors(row.code).length > 0">
                <el-popover
                  v-for="sector in rowSectors(row.code)"
                  :key="sector.sector_code"
                  trigger="click"
                  :width="230"
                  placement="top"
                >
                  <template #reference>
                    <el-tag
                      :type="sectorTagType(sector.sector_type)"
                      size="small"
                      :effect="sector.priority > 0 ? 'dark' : 'light'"
                      class="sector-tag clickable"
                    >
                      {{ sector.sector_name }}<template v-if="sector.priority > 0"> ·{{ sector.priority }}</template>
                    </el-tag>
                  </template>
                  <div>
                    <div style="font-weight:600;margin-bottom:6px">{{ sector.sector_name }}</div>
                    <div style="display:flex;align-items:center;gap:6px">
                      <span>优先级</span>
                      <el-select :model-value="sector.priority || 0" size="small" style="width:80px"
                                 @change="(v) => updateSectorPriority(sector, v, row.code)">
                        <el-option v-for="n in 11" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
                      </el-select>
                    </div>
                  </div>
                </el-popover>
              </div>
              <span v-else>{{ row.sector || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="industry" label="所属行业" width="120" />
          <el-table-column label="成交额(亿)" width="150" align="right">
            <template #default="{ row }">
              {{ formatAmount(row.amount || row.turnover || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="center">
            <template #default="{ row }">
              <span :class="row.changePercent >= 0 ? 'positive' : 'negative'">
                {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 板块成分股对话框 -->
      <el-dialog
        v-model="showSectorStocksDialog"
        :title="currentSectorName + ' - 成分股'"
        width="600px"
      >
        <el-table :data="sectorStocksList" stripe>
          <el-table-column type="index" label="排名" width="80" align="center" />
          <el-table-column prop="stock_code" label="代码" width="120" />
          <el-table-column prop="stock_name" label="名称" width="150" />
          <el-table-column label="得分" width="100" align="center">
            <template #default="{ row }">
              <el-tag type="warning">{{ row.total_score?.toFixed(2) || row.totalScore?.toFixed(2) || 0 }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="showSectorStocksDialog = false">关闭</el-button>
          </span>
        </template>
      </el-dialog>

      <!-- 板块管理弹窗 -->
      <el-dialog
        v-model="showSectorDialog"
        :title="'选择板块 - ' + (currentSectorStock ? currentSectorStock.code + ' ' + currentSectorStock.name : '')"
        width="600px"
      >
        <div v-loading="sectorDialogLoading">
          <!-- 已选板块 -->
          <div v-if="currentSectorStock && stockSectorsMap[currentSectorStock.code] && stockSectorsMap[currentSectorStock.code].length > 0" class="selected-sectors">
            <div class="section-title">已选板块：</div>
            <div
              v-for="sector in stockSectorsMap[currentSectorStock.code]"
              :key="sector.sector_code"
              style="display:inline-flex;align-items:center;gap:6px;margin:0 10px 8px 0"
            >
              <el-tag
                :type="sector.sector_type === 'concept' ? 'success' : 'primary'"
                size="large"
                closable
                class="sector-tag"
                @close="handleRemoveFromSector(sector.sector_code)"
              >
                {{ sector.sector_name }}<template v-if="sector.priority > 0"> ·{{ sector.priority }}</template>
              </el-tag>
              <el-select :model-value="sector.priority || 0" size="small" style="width:64px"
                         @change="(v) => updateSectorPriority(sector, v)">
                <el-option v-for="n in 11" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
              </el-select>
            </div>
          </div>
          <div v-else class="no-sectors">
            暂无所属板块
          </div>

          <el-divider />

          <!-- 添加板块 -->
          <div class="add-sector">
            <div class="section-title">添加板块：</div>
            <el-select
              v-model="selectedSectorId"
              placeholder="请选择或搜索板块"
              size="large"
              style="width: 100%"
              filterable
              :filter-method="sectorFilterMethod"
              @change="handleAddToSector"
            >
              <el-option
                v-for="sector in filteredSectors"
                :key="sector.id"
                :label="sector.sector_name"
                :value="sector.id"
              />
            </el-select>
          </div>
        </div>
      </el-dialog>

      <!-- 标签管理弹窗 -->
      <el-dialog
        v-model="showTagDialog"
        :title="'管理标签 - ' + (currentTagStock ? currentTagStock.code + ' ' + currentTagStock.name : '')"
        width="700px"
      >
        <!-- 标签列表 -->
        <div class="tag-management">
          <div class="section-title">选择标签：<span class="tag-hint">点击标签切换关联（已关联→点击解除，未关联→点击添加）；悬停显示编辑/删除</span></div>
          <div class="tag-list">
            <div
              v-for="tag in allTags"
              :key="tag.id"
              class="tag-item-wrap"
            >
              <!-- 正常展示模式 -->
              <template v-if="editingTagId !== tag.id">
                <el-tag
                  :color="tag.color"
                  :style="{ color: getTagTextColor(tag.color) }"
                  :effect="stockTags[currentTagStock?.code]?.some(t => t.id === tag.id) ? 'dark' : 'plain'"
                  class="selectable-tag"
                  @click="toggleStockTag(tag)"
                >
                  {{ tag.name }}
                </el-tag>
                <span class="tag-actions">
                  <el-icon class="tag-action-btn edit-btn" @click.stop="startEditTag(tag)"><Edit /></el-icon>
                  <el-icon class="tag-action-btn delete-btn" @click.stop="handleDeleteTag(tag)"><Delete /></el-icon>
                </span>
              </template>

              <!-- 内联编辑模式 -->
              <template v-else>
                <div class="tag-edit-form">
                  <el-input v-model="editTagForm.name" size="small" style="width: 120px" />
                  <el-color-picker v-model="editTagForm.color" size="small" />
                  <el-icon class="tag-action-btn confirm-btn" @click.stop="confirmEditTag(tag)"><Check /></el-icon>
                  <el-icon class="tag-action-btn cancel-btn" @click.stop="cancelEditTag()"><Close /></el-icon>
                </div>
              </template>
            </div>
          </div>
          
          <el-divider />
          
          <!-- 创建新标签 -->
          <div class="create-tag">
            <div class="section-title">创建新标签：</div>
            <el-form :inline="true" :model="newTagForm">
              <el-form-item label="标签名称">
                <el-input v-model="newTagForm.name" placeholder="请输入标签名称" style="width: 150px" />
              </el-form-item>
              <el-form-item label="标签颜色">
                <el-color-picker v-model="newTagForm.color" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleCreateTag">创建</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Grid, Monitor, Connection, Trophy, DocumentChecked, Edit, Delete, Check, Close, Message } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { getSectorStocks, getAllSectors, getStockSectors, getBatchStockSectors, addStockToSector, removeStockFromSector, getTags, addTag, updateTag, deleteTag, addStockTag, removeStockTag, getBatchStockTags, saveDailyNote, getCycleByDate, updateRelationPriority } from '@/api'
import { useReviewData } from '@/composables/useReviewData'

// 组件
import CycleInfoCard from './components/review/CycleInfoCard.vue'
import NoteEditor from './components/review/NoteEditor.vue'
import MarketOverview from './components/review/MarketOverview.vue'
import Top10FactorStocks from './components/review/Top10FactorStocks.vue'
import ExternalAnalysisPanel from './components/review/ExternalAnalysisPanel.vue'
import BatchMarketSummary from './components/review/BatchMarketSummary.vue'
import TgbHotPostsSummary from './components/review/TgbHotPostsSummary.vue'
import TgbSpecialFocusSummary from './components/review/TgbSpecialFocusSummary.vue'
import StockCodeLink from '@/components/StockCodeLink.vue'
import SectorAnalysis from './components/review/SectorAnalysis.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id
const highlightStockCode = ref(route.query.stock_code || '')
const highlightRowRef = ref(null)

// 响应式数据
const loading = ref(true)
const error = ref(null)
const chartData = ref(null)
const activeFactorTab = ref('1')
const showFactorTreeDialog = ref(false)
const currentStock = ref(null)
// 板块得分因子详情弹窗
const showSectorFactorDialog = ref(false)
const currentSector = ref(null)

// 大盘指数详情弹窗
const showMarketDetailDialog = ref(false)

// 富文本编辑器相关（NoteEditor 组件自行管理）
const currentTradeDate = ref('')

// 周期信息
const cycleInfo = ref(null)

// 板块管理
const showSectorDialog = ref(false)
const sectorDialogLoading = ref(false)
const currentSectorStock = ref(null)
const allSectors = ref([])
const selectedSectorId = ref(null)
const stockSectorsMap = ref({})
const sectorSearchText = ref('')

// 使用 composable 处理复盘数据
const {
  indexData,
  top100Stocks,
  top10FactorStocks,
  sectorScores,
  factorTree,
  marketAnalysis,
  marketData,
  marketCompositeScore,
  marketKeyFactors,
  tradeDate
} = useReviewData(chartData)

// Top10 stock_code → name 查表，供 ExternalAnalysisPanel 用
const top10NameLookup = computed(() => {
  const map = {}
  for (const s of top10FactorStocks.value || []) {
    if (!s || !s.code) continue
    const raw = String(s.code)
    const six = raw.includes('.') ? raw.split('.').pop() : raw
    map[six] = s.name
  }
  return map
})

// 过滤后的板块列表
const filteredSectors = computed(() => {
  if (!sectorSearchText.value) {
    return allSectors.value
  }
  const search = sectorSearchText.value.toLowerCase()
  return allSectors.value.filter(s =>
    s.sector_name.toLowerCase().includes(search) ||
    (s.sector_code && s.sector_code.toLowerCase().includes(search))
  )
})

// 板块搜索过滤方法
const sectorFilterMethod = (value) => {
  sectorSearchText.value = value
}

const periodTypeMap = {
  chaos: { name: '混沌', type: 'warning' },
  rise: { name: '主升', type: 'success' },
  oscillation: { name: '震荡', type: 'primary' },
  decline: { name: '退潮', type: 'danger' }
}

const getPeriodTypeName = (type) => periodTypeMap[type]?.name || type || ''
const getPeriodTypeTag = (type) => periodTypeMap[type]?.type || 'info'

// 加载周期信息
const loadCycleInfo = async (tradeDate) => {
  if (!tradeDate) return
  try {
    const res = await getCycleByDate(tradeDate)
    if (res.code === 200 && res.data) {
      cycleInfo.value = res.data
    }
  } catch (e) {
    console.log('该交易日暂无周期信息')
  }
}

const pieChartRef = ref(null)
const barChartRef = ref(null)
const top10ChartRef = ref(null)
let pieChart = null
let barChart = null
let top10Chart = null

// 板块成分股相关
const showSectorStocksDialog = ref(false)
const sectorStocksLoading = ref(false)
const sectorStocksList = ref([])
const currentSectorName = ref('')
const sectorStocksTotal = ref(0)

// 标签管理
const showTagDialog = ref(false)
const allTags = ref([])
const stockTags = ref({})  // { stock_code: [tag1, tag2, ...] }
const currentTagStock = ref(null)
const newTagForm = ref({
  name: '',
  color: '#409EFF'
})
const editingTagId = ref(null)
const editTagForm = ref({ name: '', color: '#409EFF' })

// 计算属性
const summary = computed(() => chartData.value?.summary || {})
const sectors = computed(() => chartData.value?.sectors || [])
// 行业 / 概念 板块（各自独立排名取前10）；兼容旧数据：从混合 sectors 按 sectorType 切分
const industrySectors = computed(() => {
  if (chartData.value?.sectorsIndustry?.length) return chartData.value.sectorsIndustry
  return (chartData.value?.sectors || []).filter(s => (s.sectorType || s.sector_type) === 'industry')
})
const conceptSectors = computed(() => {
  if (chartData.value?.sectorsConcept?.length) return chartData.value.sectorsConcept
  return (chartData.value?.sectors || []).filter(s => (s.sectorType || s.sector_type) === 'concept')
})
const sectorScoreExpression = computed(() => chartData.value?.sectorScoreExpression || '')
const sectorScoreExpressionName = computed(() => chartData.value?.sectorScoreExpressionName || '板块得分')
const sectorScoreFactors = computed(() => chartData.value?.sectorScoreFactors || [])
const top100Detail = computed(() => chartData.value?.top100Detail || [])

// 大盘指数详情（树状结构）
const marketDetail = computed(() => chartData.value?.marketDetail || null)

// 转换为表格数据
const marketIndexTableData = computed(() => {
  if (!marketDetail.value?.indexPrices) return []
  return Object.entries(marketDetail.value.indexPrices).map(([code, info]) => ({
    code,
    ...info
  }))
})

const MARKET_ONE_YI = 100000000

/** 树节点/卡片：成交额类展示为亿元（与 useReviewData 规则一致） */
const isMarketTurnoverTreeNode = (code, factorName) => {
  const c = String(code)
  // 排除已知非金额因子
  if (c === 'top20_avg_price' || c === 'turnover_growth') return false
  if (/turnover|amount/i.test(c)) return true
  if (/成交额/.test(c)) return true
  if (factorName && /成交额/.test(String(factorName))) return true
  return false
}

// 大盘因子树数据 - 完全动态生成，根据后端返回的 dependencies 构建树形结构
const marketFactorTreeData = computed(() => {
  if (!marketDetail.value || !marketDetail.value.factors) return []
  
  const factors = marketDetail.value.factors
  const result = []
  
  // 根节点：大盘综合得分
  const marketScore = factors['market_score']
  if (!marketScore) return []
  
  // 递归构建树节点（带去重）
  const visited = new Set()
  const buildTreeNode = (factorCode, level, parentId) => {
    const factor = factors[factorCode]
    if (!factor) return null
    
    // 去重：同一因子只展示一次
    if (visited.has(factorCode)) return null
    visited.add(factorCode)
    
    const fname = factor.factor_name || ''
    const scaleYi = isMarketTurnoverTreeNode(factorCode, fname)
    const n = Number(factor.value)
    let displayVal = factor.value
    if (scaleYi && factor.value != null && factor.value !== '' && !Number.isNaN(n)) {
      displayVal = n / MARKET_ONE_YI
    }

    const node = {
      id: parentId ? `${parentId}-${factorCode}` : factorCode,
      name: fname || factorCode,
      code: factorCode,
      value: displayVal,
      valueUnit: scaleYi ? '亿元' : '',
      expression: factor.expression || '',
      level,
      levelClass: `level-${level}`,
      children: []
    }
    
    // 如果有依赖，递归构建子节点
    const deps = factor.dependencies || []
    for (const depCode of deps) {
      const childNode = buildTreeNode(depCode, level - 1, node.id)
      if (childNode) {
        childNode.isDependency = true
        node.children.push(childNode)
      }
    }
    
    return node
  }
  
  // 从根节点开始构建
  const rootNode = buildTreeNode('market_score', 3, '')
  if (rootNode) {
    result.push(rootNode)
  }
  
  return result
})

// 动态因子配置
const factorConfig = computed(() => chartData.value?.factorConfig || { columns: [], expression: '', expressionName: '' })

// 树形组件属性
const treeProps = {
  children: 'children',
  label: 'name'
}

// 树形可视化属性
const treeVisualProps = {
  children: 'children',
  label: 'name'
}

// 点击板块得分 -> 展示该板块得分的因子详情（与股票/大盘因子树一致）
const showSectorFactorTree = (row) => {
  currentSector.value = row
  showSectorFactorDialog.value = true
}

// 板块得分因子树：根节点=板块得分(含表达式)，子节点=各引用因子及其取值
const sectorFactorTreeData = computed(() => {
  const sec = currentSector.value
  if (!sec) return []
  const fv = sec.factorValues || {}
  const children = (sectorScoreFactors.value || []).map(f => ({
    id: `sf_${f.code}`,
    name: f.name || f.code,
    code: f.code,
    level: 1,
    levelClass: 'level-source',
    value: typeof fv[f.code] === 'number' ? fv[f.code] : undefined
  }))
  return [{
    id: 'sector_score',
    name: sectorScoreExpressionName.value,
    code: sec.sectorCode || sec.sector || '',
    level: 3,
    levelClass: 'level-score',
    value: typeof sec.score === 'number' ? sec.score : undefined,
    expression: sectorScoreExpression.value,
    children
  }]
})

// 从表达式中提取因子代码列表
const getFactorCodesFromExpression = (expr) => {
  if (!expr) return []
  // 匹配变量名（字母开头，后面可以是字母数字下划线）
  const matches = expr.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || []
  // 排除常见函数名
  const excludeFuncs = ['ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG',
    'abs', 'sqrt', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log', 'AND', 'OR']
  return [...new Set(matches.filter(m => !excludeFuncs.includes(m)))]
}

// 股票因子树数据 - 真正的树形结构（得分因子 -> 中间因子 -> 数据源）
// 根据 factorConfig 动态构建股票因子树（包括依赖的原子因子）
const stockFactorTreeData = computed(() => {
  if (!factorTree.value || !factorTree.value.factors || !currentStock.value) return []
  
  const stock = currentStock.value
  
  // 从 factorConfig.columns 获取所有因子定义（包括依赖的原子因子）
  const allFactorDefs = factorConfig.value.columns || []
  console.log('所有因子定义:', allFactorDefs)
  
  // 构建因子代码到定义的映射
  const factorDefMap = {}
  for (const f of allFactorDefs) {
    factorDefMap[f.code] = f
  }
  
  // 从 levels 获取因子值信息
  const levels = factorTree.value.factors
  const levelFactorMap = {}
  for (const level of levels) {
    for (const f of (level.factors || [])) {
      levelFactorMap[f.code] = { ...f, level: level.level, levelName: level.levelName }
    }
  }
  
  // 合并两个映射
  const mergedFactorMap = {}
  for (const code of Object.keys(factorDefMap)) {
    mergedFactorMap[code] = {
      ...(levelFactorMap[code] || {}),
      ...factorDefMap[code]
    }
  }
  
  // 获取因子值
  const getValue = (code) => {
    const val = stock[code]
    return val !== undefined && val !== null ? parseFloat(val) : undefined
  }
  
  // 递归查找依赖（基于 expression）
  const findDeps = (code, visited = new Set()) => {
    if (visited.has(code)) return []
    visited.add(code)
    
    const deps = []
    const factor = mergedFactorMap[code]
    if (!factor || !factor.expression) return deps
    
    // 从表达式中提取依赖的因子代码
    const depCodes = getFactorCodesFromExpression(factor.expression)
    for (const depCode of depCodes) {
      if (depCode === code) continue
      if (mergedFactorMap[depCode]) {
        deps.push(depCode)
        // 递归查找更深层的依赖
        const subDeps = findDeps(depCode, new Set(visited))
        deps.push(...subDeps)
      }
    }
    return [...new Set(deps)]
  }
  
  // 获取表达式中使用的因子代码
  const expression = factorConfig.value.expression || ''
  const scoreFactorCodes = getFactorCodesFromExpression(expression)
  
  // 为每个得分因子构建树
  const result = []
  for (const code of scoreFactorCodes) {
    const factor = mergedFactorMap[code]
    if (!factor) continue
    
    // 获取所有依赖
    const allDeps = findDeps(code)
    
    // 构建根节点
    const rootNode = {
      id: `root-${code}`,
      name: factor.name || code,
      code: code,
      value: getValue(code),
      expression: factor.expression,
      level: 3,
      levelClass: 'level-3',
      children: []
    }
    
    // 添加直接依赖的因子（第二层）
    for (const depCode of allDeps) {
      const depFactor = mergedFactorMap[depCode]
      if (!depFactor) continue
      
      // 检查是否是顶层得分因子的直接依赖（即表达式中直接使用的因子）
      const isDirectDep = factor.expression && factor.expression.includes(depCode)
      
      if (isDirectDep) {
        const depNode = {
          id: `dep-${code}-${depCode}`,
          name: depFactor.name || depCode,
          code: depCode,
          value: getValue(depCode),
          expression: depFactor.expression,
          level: 2,
          levelClass: 'level-2',
          children: []
        }
        
        // 添加基础数据因子（第三层）- 没有 expression 的因子
        for (const [baseCode, baseFactor] of Object.entries(mergedFactorMap)) {
          if (baseCode === code || baseCode === depCode) continue
          if (!baseFactor.expression && baseFactor.calculation_method) {
            // 检查这个基础因子是否被依赖
            if (depFactor.expression && depFactor.expression.includes(baseCode)) {
              depNode.children.push({
                id: `base-${depCode}-${baseCode}`,
                name: baseFactor.name || baseCode,
                code: baseCode,
                value: getValue(baseCode),
                level: 1,
                levelClass: 'level-1',
                children: []
              })
            }
          }
        }
        
        rootNode.children.push(depNode)
      }
    }
    
    // 如果没有子节点，尝试添加基础因子
    if (rootNode.children.length === 0) {
      for (const [baseCode, baseFactor] of Object.entries(mergedFactorMap)) {
        if (baseCode === code) continue
        if (!baseFactor.expression && baseFactor.calculation_method) {
          rootNode.children.push({
            id: `base-${code}-${baseCode}`,
            name: baseFactor.name || baseCode,
            code: baseCode,
            value: getValue(baseCode),
            level: 1,
            levelClass: 'level-1',
            children: []
          })
        }
      }
    }
    
    result.push(rootNode)
  }
  
  console.log('股票因子树:', result)
  return result
})

// 显示股票因子树
const showStockFactorTree = (row) => {
  currentStock.value = row
  showFactorTreeDialog.value = true
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 刷新数据
const refreshData = () => {
  fetchChartData()
}

// 发送复盘邮件（手动触发；定时任务复盘会自动发，这里只处理手动 & 重发场景）
const sendingEmail = ref(false)
const sendEmail = async () => {
  if (!taskId) { ElMessage.warning('未识别到复盘任务 ID'); return }
  try {
    await ElMessageBox.confirm(
      '确认将本次复盘报告发送到默认收件人邮箱?（收件人在后端 EMAIL_REVIEW_RECIPIENTS 配置）',
      '发送复盘邮件',
      { confirmButtonText: '发送', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return /* 用户取消 */ }
  sendingEmail.value = true
  try {
    const r = await fetch(`/api/email/send-review/${taskId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    const j = await r.json().catch(() => ({}))
    const ok = r.ok && (j.code === 200 || j?.data?.success)
    if (ok) {
      const to = (j?.data?.recipients || []).join(', ')
      ElMessage.success(`邮件已发送${to ? ' → ' + to : ''}`)
    } else {
      const err = j?.data?.error || j?.message || `HTTP ${r.status}`
      ElMessage.error(`发送失败: ${err}`)
    }
  } catch (e) {
    ElMessage.error('发送失败: ' + (e?.message || e))
  } finally {
    sendingEmail.value = false
  }
}

// 点击查看板块成分股
const handleShowSectorStocks = async (row) => {
  // 只展示「参与复盘计算（成交额 top100）」的成分股 —— 它们才有得分。
  // 不再 fallback 拉全部成分股：没进 top100 的没参与因子计算、得分恒为 0，展示出来只是一堆 0 干扰。
  const tops = row.topStocks || []
  sectorStocksList.value = tops.map(s => ({
    stock_code: s.code,
    stock_name: s.name,
    total_score: s.totalScore,
    rank: s.rank
  }))
  sectorStocksTotal.value = tops.length
  currentSectorName.value = row.sector || row.name
  showSectorStocksDialog.value = true
}

// 格式化金额（后端已转为亿，直接展示）
const formatAmount = (value) => {
  if (!value && value !== 0) return '-'
  return `${parseFloat(value).toFixed(2)}亿`
}

/** 指数行情：后端 review_service.py 已把 turnover 除 1e8 转为亿元，前端不再换算
 *  2026-05-26 修复双重换算 bug（14616.85 亿 / 1e8 = 0.00 显示为 0.00）
 */
const formatIndexTurnoverYi = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  const n = Number(value)
  if (Number.isNaN(n)) return '-'
  return `${n.toFixed(2)}`
}

// 格式化市值（直接是元，转为亿/万亿显示）
const formatMarketValue = (value) => {
  if (!value && value !== 0) return '-'
  if (value >= 100000000) {
    // 转换为万亿
    return `${(value / 100000000).toFixed(2)}万亿`
  } else if (value >= 10000000000) {
    // 转换为亿
    return `${(value / 100000000).toFixed(2)}亿`
  }
  return `${(value / 100000000).toFixed(2)}亿`
}

// 加载所有标签
const loadAllTags = async () => {
  try {
    const res = await getTags()
    if (res.code === 200) {
      allTags.value = res.data || []
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

// 批量加载股票标签
const loadBatchStockTags = async (stockCodes) => {
  if (!stockCodes || stockCodes.length === 0) return
  try {
    const res = await getBatchStockTags(stockCodes)
    if (res.code === 200) {
      stockTags.value = res.data || {}
    }
  } catch (error) {
    console.error('获取股票标签失败:', error)
  }
}

// 批量加载股票板块
const loadBatchStockSectors = async (stockCodes) => {
  if (!stockCodes || stockCodes.length === 0) return
  try {
    const res = await getBatchStockSectors(stockCodes)
    if (res.code === 200) {
      // 将 { stock_code: [sectors] } 转换为 stockSectorsMap 格式
      stockSectorsMap.value = res.data || {}
    }
  } catch (error) {
    console.error('获取股票板块失败:', error)
  }
}

// 打开标签管理弹窗
const openTagDialog = async (stock) => {
  currentTagStock.value = stock
  showTagDialog.value = true
  // 加载所有标签
  await loadAllTags()
  // 加载当前股票的标签
  await loadBatchStockTags([stock.code])
}

// 打开板块管理弹窗
const openSectorDialog = async (stock) => {
  currentSectorStock.value = stock
  showSectorDialog.value = true
  sectorDialogLoading.value = true
  selectedSectorId.value = null
  sectorSearchText.value = ''
  try {
    // 加载所有板块
    const sectorRes = await getAllSectors()
    if (sectorRes.code === 200) {
      allSectors.value = sectorRes.data || []
    }
    // 加载当前股票的板块信息
    await loadStockSectors(stock.code)
  } catch (e) {
    console.error('加载板块数据失败:', e)
  } finally {
    sectorDialogLoading.value = false
  }
}

// 加载单个股票的板块信息
const loadStockSectors = async (stockCode) => {
  try {
    const res = await getStockSectors(stockCode)
    if (res.code === 200) {
      stockSectorsMap.value[stockCode] = res.data || []
    } else {
      stockSectorsMap.value[stockCode] = []
    }
  } catch (e) {
    console.error('获取股票板块失败:', e)
    stockSectorsMap.value[stockCode] = []
  }
}

// 添加股票到板块
const handleAddToSector = async () => {
  if (!currentSectorStock.value || !selectedSectorId.value) return
  try {
    const res = await addStockToSector({
      stock_code: currentSectorStock.value.code,
      sector_id: selectedSectorId.value
    })
    if (res.code === 200) {
      ElMessage.success('添加板块成功')
      // 刷新板块信息 - 直接更新 stockSectorsMap
      const sectorsRes = await getStockSectors(currentSectorStock.value.code)
      if (sectorsRes.code === 200) {
        stockSectorsMap.value[currentSectorStock.value.code] = sectorsRes.data || []
      }
      // 更新表格中的板块显示
      updateStockSectorInTable(currentSectorStock.value.code)
      selectedSectorId.value = null
      sectorSearchText.value = ''
    } else {
      ElMessage.error(res.message || '添加板块失败: ' + res.message)
    }
  } catch (e) {
    console.error('添加板块失败:', e)
    ElMessage.error('添加板块失败')
  }
}

// 从板块移除股票
// 板块标签按类型配色（行业=蓝/概念=绿/未知=灰），与元数据管理一致
const sectorTagType = (sType) => {
  if (sType === 'concept') return 'success'
  if (sType === 'industry') return 'primary'
  return 'info'
}

// 股票所属板块（结构化，来自元数据，按人工优先级降序）——与「元数据管理」展示一致
const rowSectors = (code) => {
  const list = stockSectorsMap.value[code] || []
  return [...list].sort((a, b) => (b.priority || 0) - (a.priority || 0))
}

const updateSectorPriority = async (sector, priority, stockCode) => {
  try {
    const res = await updateRelationPriority({
      stock_code: stockCode || currentSectorStock.value?.code,
      sector_code: sector.sector_code,
      priority
    })
    if (res.code === 200) {
      sector.priority = priority
      ElMessage.success(`已设「${sector.sector_name}」优先级 ${priority}`)
    } else {
      ElMessage.error(res.message || '设置优先级失败')
    }
  } catch (e) {
    ElMessage.error('设置优先级失败')
  }
}

const handleRemoveFromSector = async (sectorCode) => {
  if (!currentSectorStock.value) return
  // 找到对应的 sector_id
  const sector = allSectors.value.find(s => s.sector_code === sectorCode)
  if (!sector) {
    // 如果找不到，尝试用 sector_name 查找（兼容旧数据）
    const sectorByName = allSectors.value.find(s => s.sector_name === sectorCode)
    if (!sectorByName) {
      ElMessage.error('未找到对应板块')
      return
    }
    sector.id = sectorByName.id
  }
  try {
    const res = await removeStockFromSector({
      stock_code: currentSectorStock.value.code,
      sector_id: sector.id
    })
    if (res.code === 200) {
      ElMessage.success('移除板块成功')
      // 刷新板块信息
      await loadStockSectors(currentSectorStock.value.code)
      // 更新表格中的板块显示
      updateStockSectorInTable(currentSectorStock.value.code)
    } else {
      ElMessage.error(res.message || '移除失败')
    }
  } catch (e) {
    console.error('移除板块失败:', e)
    ElMessage.error('移除板块失败')
  }
}

// 更新表格中的板块显示
const updateStockSectorInTable = (stockCode) => {
  const sectors = stockSectorsMap.value[stockCode] || []
  const sectorStr = sectors.map(s => s.sector_name).join(',')
  // 更新 chartData 中的数据
  if (chartData.value?.top10FactorStocks) {
    const stock = chartData.value.top10FactorStocks.find(s => s.code === stockCode)
    if (stock) {
      stock.sector = sectorStr
    }
  }
}

// 直接从股票行删除标签关联
const removeStockTagDirect = async (stockCode, tag) => {
  try {
    await removeStockTag(stockCode, tag.id)
    stockTags.value[stockCode] = stockTags.value[stockCode].filter(t => t.id !== tag.id)
    ElMessage.success(`已移除标签「${tag.name}」`)
  } catch (e) {
    ElMessage.error('移除标签失败')
  }
}

// 切换股票的标签
const toggleStockTag = async (tag) => {
  if (!currentTagStock.value) return
  const stockCode = currentTagStock.value.code
  const hasTag = stockTags.value[stockCode]?.some(t => t.id === tag.id)
  
  try {
    if (hasTag) {
      await removeStockTag(stockCode, tag.id)
      stockTags.value[stockCode] = stockTags.value[stockCode].filter(t => t.id !== tag.id)
    } else {
      await addStockTag(stockCode, tag.id)
      if (!stockTags.value[stockCode]) {
        stockTags.value[stockCode] = []
      }
      stockTags.value[stockCode].push(tag)
    }
  } catch (error) {
    console.error('更新标签失败:', error)
  }
}

// 开始编辑标签
const startEditTag = (tag) => {
  editingTagId.value = tag.id
  editTagForm.value = { name: tag.name, color: tag.color }
}

// 取消编辑
const cancelEditTag = () => {
  editingTagId.value = null
}

// 确认编辑标签
const confirmEditTag = async (tag) => {
  if (!editTagForm.value.name.trim()) {
    ElMessage.warning('标签名称不能为空')
    return
  }
  try {
    const res = await updateTag(tag.id, editTagForm.value)
    if (res.code === 200) {
      ElMessage.success('更新成功')
      await loadAllTags()
      // 同步已关联的标签数据
      for (const code in stockTags.value) {
        stockTags.value[code] = stockTags.value[code].map(t =>
          t.id === tag.id ? { ...t, ...editTagForm.value } : t
        )
      }
      editingTagId.value = null
    } else {
      ElMessage.error(res.message || '更新失败')
    }
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 删除标签
const handleDeleteTag = async (tag) => {
  try {
    await ElMessageBox.confirm(`确定删除标签「${tag.name}」吗？删除后与股票的关联也会移除。`, '提示', { type: 'warning' })
    const res = await deleteTag(tag.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await loadAllTags()
      // 从所有股票的标签缓存中移除
      for (const code in stockTags.value) {
        stockTags.value[code] = stockTags.value[code].filter(t => t.id !== tag.id)
      }
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 创建新标签
const handleCreateTag = async () => {
  if (!newTagForm.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  try {
    const res = await addTag(newTagForm.value)
    if (res.code === 200) {
      ElMessage.success('标签创建成功')
      await loadAllTags()
      newTagForm.value.name = ''
      newTagForm.value.color = '#409EFF'
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (error) {
    console.error('创建标签失败:', error)
  }
}

// 计算标签文字颜色
const getTagTextColor = (color) => {
  if (!color) return '#fff'
  const hex = color.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000' : '#fff'
}

// 行高亮样式（从笔记跳转时定位）
const getRowClass = ({ row }) => {
  if (highlightStockCode.value && row.code === highlightStockCode.value) {
    return 'highlighted-row'
  }
  return ''
}

// 滚动到目标行
const scrollToHighlightedRow = () => {
  nextTick(() => {
    const el = document.querySelector('.highlighted-row')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

// 初始化富文本编辑器
// （已移除，NoteEditor 组件自行管理 Quill 实例）

// 加载每日笔记
// （已移除，NoteEditor 组件自行管理笔记加载）

// 保存每日笔记
const handleSaveNote = async ({ marketAnalysis, nextAction }) => {
  if (!currentTradeDate.value) {
    ElMessage.warning('无法获取交易日期')
    return
  }

  try {
    const res = await saveDailyNote({
      tradeDate: currentTradeDate.value,
      marketAnalysis,
      nextAction
    })

    if (res.code === 200) {
      ElMessage.success('笔记保存成功')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (error) {
    console.error('保存笔记失败:', error)
    ElMessage.error('保存失败')
  }
}

// 获取图表数据
const fetchChartData = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch(`/api/review/task/${taskId}/chart`)
    const result = await response.json()
    
    if (result.code === 200) {
      chartData.value = result.data
      
      // 从summary中获取交易日期
      const tradeDate = chartData.value?.summary?.tradeDate
      if (tradeDate) {
        currentTradeDate.value = tradeDate
        // 加载周期信息
        await loadCycleInfo(tradeDate)
      }
      
      // 数据加载后初始化图表
      await nextTick()
      initCharts()
      
      // 数据加载完成，设置 loading 为 false
      loading.value = false

      // 如果是从笔记跳转来的，滚动到目标行
      if (highlightStockCode.value) {
        scrollToHighlightedRow()
      }
      
      // 加载股票标签
      const top10Codes = (chartData.value?.top10FactorStocks || []).map(s => s.code)
      if (top10Codes.length > 0) {
        await loadBatchStockTags(top10Codes)
      }
      // 批量加载股票板块：覆盖前10因子股 + 成交额Top100明细，二表所属板块均按元数据结构化展示
      const sectorCodes = [...new Set([
        ...top10Codes,
        ...(chartData.value?.top100Detail || []).map(s => s.code)
      ].filter(Boolean))]
      if (sectorCodes.length > 0) {
        await loadBatchStockSectors(sectorCodes)
      }
    } else {
      error.value = result.message || '获取数据失败'
      loading.value = false
    }
  } catch (e) {
    error.value = '网络错误，请检查后端服务'
    console.error('获取图表数据失败:', e)
    loading.value = false
  } finally {
    // loading 状态在数据加载成功/失败后由上面的代码处理
  }
}

// 初始化图表
const initCharts = () => {
  initPieChart()
  initBarChart()
  initTop10Chart()
}

// 初始化饼图
const initPieChart = () => {
  if (!pieChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorPie || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}亿 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [{
      name: '成交额',
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}: {d}%'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      data: labels.map((label, index) => ({
        value: data[index],
        name: label
      }))
    }]
  })
}

// 初始化柱状图
const initBarChart = () => {
  if (!barChartRef.value) return
  
  const chartsData = chartData.value?.charts?.sectorBar || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  barChart = echarts.init(barChartRef.value)
  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        rotate: 30,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      name: '股票数量'
    },
    series: [{
      name: '股票数量',
      type: 'bar',
      data: data,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#83bff6' },
          { offset: 0.5, color: '#188df0' },
          { offset: 1, color: '#188df0' }
        ])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2378f7' },
            { offset: 1, color: '#2378f7' }
          ])
        }
      }
    }]
  })
}

// 初始化Top10图表
const initTop10Chart = () => {
  if (!top10ChartRef.value) return
  
  const chartsData = chartData.value?.charts?.amountTop10 || {}
  const labels = chartsData.labels || []
  const data = chartsData.data || []
  
  top10Chart = echarts.init(top10ChartRef.value)
  top10Chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '成交额(亿)',
      axisLabel: {
        formatter: (value) => value.toFixed(0)
      }
    },
    yAxis: {
      type: 'category',
      data: labels.reverse(),
      axisLabel: {
        fontSize: 11
      }
    },
    series: [{
      name: '成交额',
      type: 'bar',
      data: data.reverse(),
      itemStyle: {
        color: (params) => {
          const colors = ['#FF6B6B', '#FF8E72', '#FFA940', '#FFC53D', '#FFEC3D', '#A0D911', '#52C41A', '#13C2C2', '#1890FF', '#2F54EB']
          return colors[params.dataIndex] || '#1890FF'
        }
      },
      label: {
        show: true,
        position: 'right',
        formatter: (params) => formatAmount(params.value)
      }
    }]
  })
}

// 监听窗口大小变化
const handleResize = () => {
  pieChart?.resize()
  barChart?.resize()
  top10Chart?.resize()
}

// 生命周期
onMounted(() => {
  fetchChartData()
  window.addEventListener('resize', handleResize)
})

// 清理
watch(() => chartData.value, () => {
  if (chartData.value) {
    nextTick(() => {
      initCharts()
    })
  }
})
</script>

<style scoped>
.review-result {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.loading-container {
  padding: 40px;
}

.error-alert {
  margin: 20px;
}

.content {
  padding: 0 10px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-card :deep(.el-card__header) {
  font-weight: 500;
  color: #666;
}

.card-value {
  font-size: 24px;
  font-weight: bold;
  color: #1890ff;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.chart-container-large {
  height: 400px;
  width: 100%;
}

.top10-chart-card,
.sector-table-card,
.stock-table-card,
.factor-tree-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.positive {
  color: #f56c6c;
  font-weight: 500;
}

.negative {
  color: #52c41a;
  font-weight: 500;
}

/* 大盘指数 + 主要指数行情 等高对齐 */
.market-row {
  margin-top: 20px;
  display: flex;
  align-items: stretch;
}

.market-row > .el-col {
  display: flex;
  flex-direction: column;
}

.market-row > .el-col > .el-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.market-row > .el-col > .el-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* 大盘指数卡片样式 */
.market-card {
  margin-top: 0;
}

.market-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 指数行情展示 */
.index-prices {
  margin-bottom: 10px;
}

.index-item {
  text-align: center;
  padding: 10px 5px;
  background: #f5f7fa;
  border-radius: 4px;
}

.index-item .index-name {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.index-item .index-close {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.index-item .index-pct {
  font-size: 12px;
  margin-top: 2px;
}

.index-item .index-pct.up {
  color: #f56c6c;
}

.index-item .index-pct.down {
  color: #67c23a;
}

.market-score {
  text-align: center;
  padding: 14px 0 8px;
}

.market-score .score-value {
  font-size: 36px;
  font-weight: bold;
}

.market-score .score-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.key-factor-col {
  margin-bottom: 8px;
}

.key-factor-item {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 6px;
  text-align: center;
}

.key-factor-value {
  font-size: 15px;
  font-weight: 600;
}

.key-factor-name {
  font-size: 11px;
  color: #909399;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.market-factors {
  padding: 10px 0;
}

.factor-item {
  text-align: center;
  padding: 15px 10px;
}

.factor-item .factor-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.factor-item.small .factor-value {
  font-size: 18px;
}

.factor-item .factor-label {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

/* 因子树样式 */
.factor-tree {
  margin-top: 10px;
}

.level-description {
  color: #666;
  font-size: 13px;
  margin-bottom: 15px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.dependency-tag {
  margin-right: 5px;
  margin-bottom: 3px;
}

.expression {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 2px 6px;
  border-radius: 3px;
}

.factor-tree-dialog {
  max-height: 500px;
  overflow-y: auto;
}

.factor-tree-dialog .total-score {
  text-align: center;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  margin-bottom: 20px;
  color: white;
}

.factor-tree-dialog .score-label {
  font-size: 14px;
  margin-right: 10px;
}

.factor-tree-dialog .score-value {
  font-size: 32px;
  font-weight: bold;
}

.tree-visualization {
  padding: 10px;
  background: #fafafa;
  border-radius: 8px;
  min-height: 300px;
}

.factor-visual-tree {
  background: transparent;
}

.visual-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  flex: 1;
}

.visual-node.level-1 {
  background: #e6f7ff;
  border-left: 3px solid #1890ff;
}

.visual-node.level-2 {
  background: #fff7e6;
  border-left: 3px solid #fa8c16;
}

.visual-node.level-3 {
  background: #f6ffed;
  border-left: 3px solid #52c41a;
}

.visual-node .node-icon {
  font-size: 16px;
}

.visual-node.level-1 .node-icon { color: #1890ff; }
.visual-node.level-2 .node-icon { color: #fa8c16; }
.visual-node.level-3 .node-icon { color: #52c41a; }

.visual-node .node-content {
  display: flex;
  align-items: center;
  gap: 4px;
}

.visual-node .node-label {
  font-weight: 500;
  color: #333;
}

.visual-node .node-code {
  color: #999;
  font-size: 12px;
}

.visual-node .node-value {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
}

.visual-node .node-value.positive {
  background: #fdf6ec;
  color: #e6a23c;
}

.visual-node .node-value.negative {
  background: #f0f9eb;
  color: #67c23a;
}

.visual-node .node-formula {
  font-size: 11px;
  color: #666;
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
}

.visual-node .dep-arrow {
  color: #999;
  font-weight: bold;
}

.tree-legend {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.tree-legend .legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #666;
  font-size: 13px;
}

.factor-tree-component {
  background: transparent;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.node-name {
  font-weight: 500;
}

.node-value {
  padding: 2px 8px;
  border-radius: 3px;
  font-weight: 600;
}

.node-value.positive {
  background: #fdf6ec;
  color: #e6a23c;
}

.node-value.negative {
  background: #f0f9eb;
  color: #67c23a;
}

.node-expression {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
  color: #909399;
  background: #f5f7fa;
  padding: 1px 4px;
  border-radius: 2px;
}

.node-method {
  font-size: 11px;
  color: #909399;
}

.no-dep,
.no-expression {
  color: #999;
  font-size: 12px;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.clickable-tag:hover {
  color: #409eff;
  transform: scale(1.05);
}

/* 大盘指数详情弹窗 */
.factor-tree-dialog .detail-section {
  margin-bottom: 20px;
}

.factor-tree-dialog .detail-section h4 {
  margin-bottom: 15px;
  color: #303133;
  font-size: 16px;
}

/* 标签管理样式 */
.tag-management {
  padding: 10px 0;
}

/* 板块管理样式 */
.selected-sectors {
  margin-bottom: 16px;
}

.selected-sectors .section-title,
.add-sector .section-title {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  margin-bottom: 12px;
}

.sector-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.no-sectors {
  color: #909399;
  font-size: 14px;
  padding: 10px 0;
}

.add-sector {
  margin-top: 10px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.tag-item-wrap {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

.tag-item-wrap .tag-actions {
  display: none;
  align-items: center;
  gap: 2px;
}

.tag-item-wrap:hover .tag-actions {
  display: inline-flex;
}

.tag-action-btn {
  cursor: pointer;
  font-size: 13px;
  padding: 2px;
  border-radius: 3px;
  transition: background 0.2s;
}

.edit-btn {
  color: #409eff;
}

.edit-btn:hover {
  background: #ecf5ff;
}

.delete-btn {
  color: #f56c6c;
}

.delete-btn:hover {
  background: #fef0f0;
}

.confirm-btn {
  color: #67c23a;
}

.confirm-btn:hover {
  background: #f0f9eb;
}

.cancel-btn {
  color: #909399;
}

.cancel-btn:hover {
  background: #f4f4f5;
}

.tag-edit-form {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 4px 8px;
}

.selectable-tag {
  cursor: pointer;
  padding: 8px 15px;
  border-radius: 4px;
  transition: all 0.3s;
}

.selectable-tag:hover {
  transform: scale(1.05);
}

.no-tag {
  color: #909399;
  font-size: 12px;
}

.stock-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag-hint {
  font-size: 11px;
  color: #909399;
  font-weight: normal;
  margin-left: 6px;
}

.create-tag {
  margin-top: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #303133;
}

/* 每日笔记样式 */
.note-card {
  margin-bottom: 20px;
}

/* 周期信息样式 */
.cycle-info-card {
  margin-bottom: 20px;
}

.cycle-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cycle-info .cycle-title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.cycle-info .cycle-period {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cycle-info .cycle-date {
  color: #909399;
  font-size: 14px;
}

.cycle-info .cycle-features {
  color: #606266;
  font-size: 14px;
  margin-top: 5px;
}

.note-section {
  display: flex;
  flex-direction: column;
}

.note-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
}

.rich-editor {
  min-height: 200px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

.rich-editor :deep(.ql-container) {
  min-height: 180px;
  font-size: 14px;
}

.rich-editor :deep(.ql-toolbar) {
  border-radius: 4px 4px 0 0;
}

.rich-editor :deep(.ql-container) {
  border-radius: 0 0 4px 4px;
}

/* 从笔记跳转时高亮目标股票行 */
:deep(.highlighted-row) {
  background-color: #ecf5ff !important;
}

:deep(.highlighted-row td) {
  background-color: #ecf5ff !important;
  color: #409eff;
  font-weight: 600;
}
</style>
