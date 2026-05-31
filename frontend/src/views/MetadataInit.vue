<template>
  <div class="metadata-init">
    <!-- 页面标题栏 -->
    <div class="page-header">
      <span class="page-title">元数据管理</span>
      <div class="header-actions">
        <el-button
          type="primary"
          size="small"
          :loading="stockLoading"
          @click="initStock"
        >
          {{ stockResult ? '股票已初始化' : '初始化股票' }}
        </el-button>
        <el-button
          type="success"
          size="small"
          :loading="sectorLoading"
          @click="initAllSectors"
        >
          {{ sectorResult ? '板块已初始化' : '初始化板块' }}
        </el-button>
      </div>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="股票总数" :value="summary.stock_basic_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="板块" :value="summary.sector_industry_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="关联总数" :value="summary.stock_sector_relation_count" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 板块列表 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>板块列表</span>
          <div class="header-actions">
            <el-input
              v-model="sectorSearch"
              placeholder="搜索板块名称"
              clearable
              size="small"
              style="width: 180px; margin-left: 10px"
              @keyup.enter="loadSectors"
              @clear="loadSectors"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" size="small" @click="loadSectors" style="margin-left: 5px">
              搜索
            </el-button>
            <el-button type="primary" size="small" @click="showCreateSectorDialog = true" style="margin-left: 10px">
              创建板块
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="sectorList" v-loading="sectorLoading" stripe height="calc(100vh - 480px)" style="width: 100%">
        <el-table-column prop="sector_code" label="板块代码" width="120" />
        <el-table-column prop="sector_name" label="板块名称" min-width="200" />
        <el-table-column prop="stock_count" label="成分股数量" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.stock_count }} 只</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="showSectorStocks(row)"
            >
              查看成分股
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 板块分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="sectorCurrentPage"
          v-model:page-size="sectorPageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="sectorTotal"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSectorSizeChange"
          @current-change="handleSectorPageChange"
        />
      </div>
    </el-card>

    <!-- 股票列表 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>股票列表</span>
          <div class="header-actions">
            <el-input
              v-model="stockSearch"
              placeholder="搜索代码或名称"
              clearable
              size="small"
              style="width: 150px"
              @input="handleStockSearch"
              @clear="handleStockSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-radio-group v-model="stockTypeFilter" size="small" @change="handleStockTypeChange">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="stock">股票</el-radio-button>
              <el-radio-button value="index">指数</el-radio-button>
              <el-radio-button value="bond">可转债</el-radio-button>
              <el-radio-button value="etf">ETF</el-radio-button>
              <el-radio-button value="other">其它</el-radio-button>
            </el-radio-group>
            <el-button type="primary" size="small" :loading="stockListLoading" @click="loadStocks" style="margin-left: 10px">
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="stockList" v-loading="stockListLoading" stripe max-height="500" style="width: 100%">
        <el-table-column label="股票代码" width="110">
          <template #default="{ row }">
            <StockCodeLink :code="row.stock_code" />
          </template>
        </el-table-column>
        <el-table-column prop="stock_name" label="股票名称" min-width="100" />
        <el-table-column prop="market" label="市场/类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getMarketTagType(row.market)" size="small">
              {{ formatMarket(row.market) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_market_value" label="总市值(亿)" width="120">
          <template #default="{ row }">
            {{ formatMarketValue(row.total_market_value) }}
          </template>
        </el-table-column>
        <el-table-column prop="circulate_market_value" label="流通市值(亿)" width="120">
          <template #default="{ row }">
            {{ formatMarketValue(row.circulate_market_value) }}
          </template>
        </el-table-column>
        <el-table-column label="所属板块" min-width="180">
          <template #default="{ row }">
            <div v-if="row.sectors && row.sectors.length > 0">
              <el-tag
                v-for="sector in row.sectors.slice(0, 3)"
                :key="sector.sector_code"
                type="info"
                size="small"
                class="sector-tag clickable"
                @click="handleSectorTagClick(sector)"
              >
                {{ sector.sector_name }}
              </el-tag>
              <el-tag v-if="row.sectors.length > 3" type="info" size="small">
                +{{ row.sectors.length - 3 }}
              </el-tag>
            </div>
            <el-tag v-else type="info" size="small" effect="plain">
              点击"选择板块"添加
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="150">
          <template #default="{ row }">
            <div v-if="stockTags[row.stock_code] && stockTags[row.stock_code].length > 0">
              <el-tag
                v-for="tag in stockTags[row.stock_code].slice(0, 3)"
                :key="tag.id"
                :color="tag.color"
                :style="{ color: getTagTextColor(tag.color) }"
                size="small"
                class="tag-item"
              >
                {{ tag.name }}
              </el-tag>
              <el-tag v-if="stockTags[row.stock_code].length > 3" type="info" size="small">
                +{{ stockTags[row.stock_code].length - 3 }}
              </el-tag>
            </div>
            <span v-else class="no-tag">无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="showStockKline(row)"
            >
              查看K线
            </el-button>
            <el-button
              type="primary"
              link
              size="small"
              @click="supplementStockInfo(row)"
              :loading="row.supplementing"
            >
              补充信息
            </el-button>
            <el-button
              type="primary"
              link
              size="small"
              @click="openSectorDialog(row)"
            >
              选择板块
            </el-button>
            <el-button
              type="warning"
              link
              size="small"
              @click="openTagDialog(row)"
            >
              管理标签
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 股票分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="stockCurrentPage"
          v-model:page-size="stockPageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="stockTotal"
          layout="total, sizes, prev, pager, next"
          @size-change="handleStockSizeChange"
          @current-change="handleStockPageChange"
        />
      </div>
    </el-card>

    <!-- 交割单导入 -->
    <el-card class="box-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>交割单导入</span>
          <div>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              :on-change="handleFileChange"
              :on-exceed="handleExceed"
              accept=".xls,.xlsx,.txt"
              action="#"
              style="display: inline-block; margin-right: 10px"
            >
              <el-button type="primary" size="small">
                选择文件
              </el-button>
            </el-upload>
            <el-button 
              type="success" 
              size="small" 
              :loading="importLoading" 
              :disabled="!selectedFile"
              @click="handleImport"
            >
              导入
            </el-button>
            <el-button size="small" @click="loadDeliveryStats" :loading="statsLoading">
              刷新统计
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 统计信息 -->
      <el-row :gutter="20" v-if="deliveryStats.total > 0">
        <el-col :span="6">
          <el-statistic title="总记录数" :value="deliveryStats.total" />
        </el-col>
        <el-col :span="18">
          <el-statistic title="按操作类型统计">
            <template #default>
              <el-tag v-for="op in deliveryStats.operations" :key="op.operation" type="info" style="margin-right: 8px">
                {{ op.operation }}: {{ op.count }}
              </el-tag>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
      <div v-else style="color: #999; padding: 20px">
        暂无交割单数据，请上传文件导入
      </div>
      
      <!-- 交割单列表 -->
      <el-table v-if="deliveryList.length > 0" :data="deliveryList" stripe max-height="300" style="width: 100%; margin-top: 20px">
        <el-table-column prop="trade_date" label="成交日期" width="100" />
        <el-table-column prop="trade_time" label="成交时间" width="80" />
        <el-table-column prop="security_code" label="证券代码" width="100" />
        <el-table-column prop="security_name" label="证券名称" min-width="100" />
        <el-table-column prop="operation" label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="row.operation === '买入' || row.operation === '证券买入' ? 'success' : 'danger'" size="small">
              {{ row.operation }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="price" label="价格" width="80" />
        <el-table-column prop="amount" label="成交金额" width="100">
          <template #default="{ row }">
            {{ row.amount ? row.amount.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="occur_amount" label="发生金额" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.occur_amount < 0 ? '#67c23a' : '#f56c6c' }">
              {{ row.occur_amount ? row.occur_amount.toFixed(2) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="market" label="市场" width="100" />
      </el-table>
      
      <!-- 交割单分页 -->
      <div class="pagination-container" v-if="deliveryStats.total > 0">
        <el-pagination
          v-model:current-page="deliveryPage"
          v-model:page-size="deliveryPageSize"
          :page-sizes="[20, 50, 100]"
          :total="deliveryStats.total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleDeliverySizeChange"
          @current-change="handleDeliveryPageChange"
        />
      </div>
    </el-card>

    <!-- 成分股弹窗 -->
    <el-dialog
      v-model="showStockDialog"
      :title="(currentSector && currentSector.sector_name) ? currentSector.sector_name + ' - 成分股列表' : '成分股列表'"
      width="900px"
    >
      <!-- 搜索栏 -->
      <div class="sector-stocks-toolbar">
        <el-input
          v-model="sectorStocksSearch"
          placeholder="搜索股票代码或名称"
          clearable
          size="small"
          style="width: 200px"
          @keyup.enter="loadSectorStocks"
          @clear="loadSectorStocks"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="small" @click="loadSectorStocks" style="margin-left: 10px">
          搜索
        </el-button>
        <span class="stocks-count">共 {{ sectorStocksTotal }} 只成分股</span>
        <el-button
          type="success"
          size="small"
          style="margin-left: auto"
          @click="openBatchAddDialog"
        >
          + 批量添加成分股
        </el-button>
      </div>
      
      <el-table :data="sectorStocks" v-loading="stocksLoading" height="calc(100vh - 500px)" style="width: 100%">
        <el-table-column label="股票代码" width="130">
          <template #default="{ row }">
            <StockCodeLink :code="row.stock_code" />
          </template>
        </el-table-column>
        <el-table-column prop="stock_name" label="股票名称" min-width="150" />
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            {{ formatMarket(row.market) }}
          </template>
        </el-table-column>
        <el-table-column label="所属板块" min-width="200">
          <template #default="{ row }">
            <div v-if="row.sectors && row.sectors.length > 0">
              <el-tag
                v-for="sector in row.sectors"
                :key="sector.sector_code"
                type="info"
                size="small"
                class="sector-tag clickable"
                @click="handleSectorTagClick(sector)"
              >
                {{ sector.sector_name }}
              </el-tag>
            </div>
            <span v-else class="no-sector">-</span>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 成分股分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="sectorStocksPage"
          v-model:page-size="sectorStocksPageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="sectorStocksTotal"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSectorStocksSizeChange"
          @current-change="handleSectorStocksPageChange"
        />
      </div>
    </el-dialog>

    <!-- 批量添加成分股子弹窗 -->
    <el-dialog
      v-model="showBatchAddDialog"
      :title="'批量添加成分股 - ' + (currentSector ? currentSector.sector_name : '')"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="支持多种输入方式"
        type="info"
        :closable="false"
        style="margin-bottom: 12px"
      >
        <template #default>
          <div style="font-size: 13px; line-height: 1.6">
            <strong>方式 1 - 下拉多选</strong>：从已有股票列表里筛选选择（输入代码或名称搜索）<br>
            <strong>方式 2 - 粘贴代码</strong>：在文本框粘贴 6 位代码（每行一个或逗号分隔），如 <code>600519,000858,300750</code>
          </div>
        </template>
      </el-alert>

      <el-form label-width="100px">
        <el-form-item label="股票选择">
          <el-select
            v-model="batchAddSelected"
            multiple
            filterable
            remote
            reserve-keyword
            placeholder="输入股票代码或名称搜索"
            :remote-method="searchStocksForBatchAdd"
            :loading="batchSearchLoading"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="3"
          >
            <el-option
              v-for="s in batchSearchOptions"
              :key="s.stock_code"
              :label="`${s.stock_code} ${s.stock_name}`"
              :value="s.stock_code"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="粘贴代码">
          <el-input
            v-model="batchAddRawText"
            type="textarea"
            :rows="3"
            placeholder="600519, 000858, 300750  或一行一个代码"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showBatchAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchAddSubmitting" @click="submitBatchAdd">
          确认添加（{{ batchAddTotalCount }} 只）
        </el-button>
      </template>
    </el-dialog>

    <!-- 选择板块弹窗 -->
    <el-dialog
      v-model="showSectorDialog"
      :title="'选择板块 - ' + (currentStock ? currentStock.stock_code + ' ' + currentStock.stock_name : '')"
      width="600px"
    >
      <div v-loading="sectorDialogLoading">
        <!-- 已选板块 -->
        <div v-if="currentStock && currentStock.sectors && currentStock.sectors.length > 0" class="selected-sectors">
          <div class="section-title">已选板块：</div>
          <el-tag
            v-for="sector in currentStock.sectors"
            :key="sector.sector_code"
            type="info"
            size="large"
            closable
            class="sector-tag"
            @close="handleRemoveFromSector(sector.sector_code)"
          >
            {{ sector.sector_name }}
          </el-tag>
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
            placeholder="请选择板块"
            size="large"
            style="width: 100%"
            @change="handleAddToSector"
          >
            <el-option
              v-for="sector in allSectors"
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
      :title="'管理标签 - ' + (currentStock ? currentStock.stock_code + ' ' + currentStock.stock_name : '')"
      width="700px"
    >
      <!-- 标签列表 -->
      <div class="tag-management">
        <div class="section-title">选择标签：</div>
        <div class="tag-list">
          <el-tag
            v-for="tag in allTags"
            :key="tag.id"
            :color="tag.color"
            :style="{ color: getTagTextColor(tag.color) }"
            :effect="stockTags[currentStock?.stock_code]?.some(t => t.id === tag.id) ? 'dark' : 'plain'"
            class="selectable-tag"
            @click="toggleStockTag(tag)"
          >
            {{ tag.name }}
          </el-tag>
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

    <!-- 创建板块弹窗 -->
    <el-dialog
      v-model="showCreateSectorDialog"
      title="创建新板块"
      width="500px"
    >
      <el-form :model="createSectorForm" label-width="80px">
        <el-form-item label="板块代码" required>
          <el-input v-model="createSectorForm.sector_code" placeholder="请输入板块代码（如：IND001）" />
        </el-form-item>
        <el-form-item label="板块名称" required>
          <el-input v-model="createSectorForm.sector_name" placeholder="请输入板块名称" />
        </el-form-item>
        <el-form-item label="板块类型">
          <el-radio-group v-model="createSectorForm.sector_type">
            <el-radio-button label="industry">行业</el-radio-button>
            <el-radio-button label="concept">概念</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="createSectorForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入板块描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateSectorDialog = false">取消</el-button>
        <el-button type="primary" :loading="createSectorLoading" @click="handleCreateSector">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看K线弹窗 -->
    <el-dialog
      v-model="showKlineDialog"
      :title="`${klineStockName} K线数据`"
      width="900px"
      top="5vh"
    >
      <div class="kline-header">
        <el-radio-group v-model="klineFrequency" size="small" @change="loadStockKline">
          <el-radio-button label="d">日线</el-radio-button>
          <el-radio-button label="w">周线</el-radio-button>
          <el-radio-button label="m">月线</el-radio-button>
        </el-radio-group>
        <span class="kline-count">共 {{ klineData.length }} 条</span>
      </div>
      
      <el-table :data="klineData" stripe height="500" style="width: 100%">
        <el-table-column prop="trade_date" label="交易日期" width="120" />
        <el-table-column prop="open" label="开盘价" width="100">
          <template #default="{ row }">
            {{ row.open?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="high" label="最高价" width="100">
          <template #default="{ row }">
            {{ row.high?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="low" label="最低价" width="100">
          <template #default="{ row }">
            {{ row.low?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价" width="100">
          <template #default="{ row }">
            {{ row.close?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量" width="120">
          <template #default="{ row }">
            {{ formatVolume(row.volume) }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="140">
          <template #default="{ row }">
            {{ formatAmount(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="涨跌幅" width="100">
          <template #default="{ row }">
            <span :class="row.pct_chg > 0 ? 'positive' : row.pct_chg < 0 ? 'negative' : ''">
              {{ row.pct_chg?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { Document, Grid } from '@element-plus/icons-vue'
import StockCodeLink from '@/components/StockCodeLink.vue'
import {
  getMetadataSummary,
  initStockFromAKShare,
  initIndustryFromAKShare,
  initConceptFromAKShare,
  getSectors,
  getSectorStocks,
  getStocks,
  getAllSectors,
  addStockToSector,
  removeStockFromSector,
  createSector,
  importDelivery,
  getDeliveryList,
  getDeliveryStats,
  getStockKline,
  getTags,
  getStockTags,
  addStockTag,
  removeStockTag,
  getBatchStockTags
} from '@/api'

// 统计数据
const summary = ref({
  stock_basic_count: 0,
  sector_industry_count: 0,
  stock_sector_relation_count: 0
})

// 初始化状态
const stockLoading = ref(false)
const stockResult = ref(null)
const sectorLoading = ref(false)
const sectorResult = ref(null)

// 板块列表
const sectorType = ref('')
const sectorList = ref([])
const sectorSearch = ref('')

// 批量添加成分股
const showBatchAddDialog = ref(false)
const batchAddSelected = ref([])
const batchAddRawText = ref('')
const batchSearchOptions = ref([])
const batchSearchLoading = ref(false)
const batchAddSubmitting = ref(false)
const batchAddTotalCount = computed(() => {
  const fromText = batchAddRawText.value
    .split(/[\s,，;；\n\r]+/)
    .map(s => s.trim())
    .filter(s => s.length >= 6)
  const merged = new Set([...batchAddSelected.value, ...fromText])
  return merged.size
})

const openBatchAddDialog = () => {
  batchAddSelected.value = []
  batchAddRawText.value = ''
  batchSearchOptions.value = []
  showBatchAddDialog.value = true
}

const searchStocksForBatchAdd = async (query) => {
  if (!query || query.length < 2) {
    batchSearchOptions.value = []
    return
  }
  batchSearchLoading.value = true
  try {
    // daydayUp request 拦截器：200 直接 return ApiResponse(已 unwrap response.data)
    // request 已配 baseURL=/api，路径不加 /api 前缀
    const res = await request.get('/metadata/stock/list', {
      params: { page: 1, pageSize: 30, keyword: query }
    })
    batchSearchOptions.value = res?.data?.items || res?.data?.list || res?.data || []
  } catch (e) {
    console.warn('搜索股票失败', e)
  } finally {
    batchSearchLoading.value = false
  }
}

const submitBatchAdd = async () => {
  if (!currentSector.value || !currentSector.value.sector_code) {
    ElMessage.warning('未指定板块')
    return
  }
  const fromText = batchAddRawText.value
    .split(/[\s,，;；\n\r]+/)
    .map(s => s.trim())
    .filter(s => s.length >= 6)
  const codes = Array.from(new Set([...batchAddSelected.value, ...fromText]))
  if (codes.length === 0) {
    ElMessage.warning('请至少选择/粘贴 1 只股票')
    return
  }
  batchAddSubmitting.value = true
  try {
    const res = await request.post(
      `/metadata/sectors/${encodeURIComponent(currentSector.value.sector_code)}/stocks`,
      { stock_codes: codes }
    )
    // 拦截器 200 才会到这里，非 200 走 catch
    const d = res?.data || {}
    ElMessage.success(
      `添加 ${d.added} 只 · 已存在 ${d.skipped_exists} · 格式错 ${d.skipped_invalid_format} · 未知股 ${d.skipped_unknown_stock}`
    )
    showBatchAddDialog.value = false
    // 刷新成分股列表 + 主板块列表
    loadSectorStocks()
    loadSectors()
  } catch (e) {
    ElMessage.error(`添加失败: ${e?.response?.data?.message || e.message || e}`)
  } finally {
    batchAddSubmitting.value = false
  }
}

// 成分股弹窗
const showStockDialog = ref(false)
const currentSector = ref(null)
const sectorStocks = ref([])
const stocksLoading = ref(false)
const sectorStocksTotal = ref(0)
const sectorStocksPage = ref(1)
const sectorStocksPageSize = ref(50)
const sectorStocksSearch = ref('')

// 股票列表
const stockList = ref([])
const stockListLoading = ref(false)
const stockTotal = ref(0)
const stockCurrentPage = ref(1)
const stockPageSize = ref(50)
const stockTypeFilter = ref('')  // 股票类型过滤: '', 'stock', 'index', 'etf'
const stockSearch = ref('')  // 股票搜索
let stockSearchTimer = null  // 搜索防抖定时器

// 搜索防抖处理
const handleStockSearch = () => {
  if (stockSearchTimer) {
    clearTimeout(stockSearchTimer)
  }
  stockSearchTimer = setTimeout(() => {
    stockCurrentPage.value = 1  // 搜索时重置到第一页
    loadStocks()
  }, 300)  // 300ms 防抖
}

// 交割单相关
const uploadRef = ref(null)
const selectedFile = ref(null)
const importLoading = ref(false)
const deliveryStats = ref({ total: 0, operations: [] })
const deliveryList = ref([])
const deliveryPage = ref(1)
const deliveryPageSize = ref(50)
const statsLoading = ref(false)

// 市场/类型映射
const marketMap = {
  'stock_sh': '沪市股票',
  'stock_sz': '深市股票',
  'index_sh': '沪市指数',
  'index_sz': '深市指数',
  'other_sh': '沪市其它',
  'other_sz': '深市其它',
  'bond_sh': '沪市可转债',
  'bond_sz': '深市可转债',
  'etf_sh': '沪市ETF',
  'etf_sz': '深市ETF',
  'sh': '沪市',
  'sz': '深市'
}

// 格式化市场
const formatMarket = (market) => {
  if (!market) return '-'
  return marketMap[market] || market
}

// 格式化市值（单位：亿元）
const formatMarketValue = (value) => {
  if (!value) return '-'
  // 原始数据是元，转换为亿元
  const yi = value / 100000000
  if (yi >= 10000) {
    return (yi / 10000).toFixed(2) + '万亿'
  }
  return yi.toFixed(2) + '亿'
}

// 获取市场标签类型
const getMarketTagType = (market) => {
  if (!market) return 'info'
  if (market.includes('stock')) return 'success'   // 股票用绿色
  if (market.includes('index')) return 'danger'     // 指数用红色
  if (market.includes('bond')) return 'warning'     // 可转债用橙色
  if (market.includes('etf')) return 'info'         // ETF用蓝色
  if (market.includes('other')) return 'info'        // 其它用灰色
  return 'info'
}

// 所有板块列表（用于下拉选择）
const allSectors = ref([])
const allSectorsLoading = ref(false)
const selectedSectorId = ref('')

// 当前操作的股票
const currentStock = ref(null)
const showSectorDialog = ref(false)
const sectorDialogLoading = ref(false)

// 标签管理
const showTagDialog = ref(false)
const allTags = ref([])
const stockTags = ref({})  // { stock_code: [tag1, tag2, ...] }
const newTagForm = ref({
  name: '',
  color: '#409EFF'
})

// 创建板块弹窗
const showCreateSectorDialog = ref(false)
const createSectorForm = ref({
  sector_code: '',
  sector_name: '',
  sector_type: 'industry',
  description: ''
})
const createSectorLoading = ref(false)

// K线查看弹窗
const showKlineDialog = ref(false)
const klineStockCode = ref('')
const klineStockName = ref('')
const klineFrequency = ref('d')
const klineData = ref([])
const klineLoading = ref(false)

// 板块分页
const sectorCurrentPage = ref(1)
const sectorPageSize = ref(20)
const sectorTotal = ref(0)

// 加载统计
const loadSummary = async () => {
  try {
    const res = await getMetadataSummary()
    // API拦截器直接返回res.data，所以直接用res.code和res.data
    if (res.code === 200) {
      summary.value = res.data
    }
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

// 初始化股票
const initStock = async () => {
  stockLoading.value = true
  try {
    const res = await initStockFromAKShare({ update_existing: true })
    if (res.code === 200) {
      stockResult.value = res.data
      ElMessage.success('股票信息初始化完成')
      await loadSummary()
    } else {
      ElMessage.error(res.message || '初始化失败')
    }
  } catch (error) {
    console.error('初始化股票失败:', error)
    ElMessage.error('初始化失败')
  } finally {
    stockLoading.value = false
  }
}

// 初始化全部板块（行业+概念）
const initAllSectors = async () => {
  sectorLoading.value = true
  sectorResult.value = null
  try {
    // 1. 先初始化行业板块
    const industryRes = await initIndustryFromAKShare()
    if (industryRes.code !== 200) {
      ElMessage.error(industryRes.message || '行业板块初始化失败')
      sectorLoading.value = false
      return
    }

    // 2. 再初始化概念板块
    const conceptRes = await initConceptFromAKShare()
    if (conceptRes.code !== 200) {
      ElMessage.error(conceptRes.message || '概念板块初始化失败')
      sectorLoading.value = false
      return
    }

    sectorResult.value = {
      industry: industryRes.data,
      concept: conceptRes.data
    }
    ElMessage.success('全部板块初始化完成')
    await loadSummary()
    await loadSectors()
  } catch (error) {
    console.error('初始化板块失败:', error)
    ElMessage.error('初始化失败')
  } finally {
    sectorLoading.value = false
  }
}

// 板块分页变化
const handleSectorPageChange = (page) => {
  sectorCurrentPage.value = page
  loadSectors()
}

const handleSectorSizeChange = (size) => {
  sectorPageSize.value = size
  sectorCurrentPage.value = 1
  loadSectors()
}

// 加载板块列表
const loadSectors = async () => {
  sectorLoading.value = true
  try {
    const params = { 
      type: sectorType.value,
      page: sectorCurrentPage.value,
      page_size: sectorPageSize.value
    }
    if (sectorSearch.value) {
      params.keyword = sectorSearch.value
    }
    const res = await getSectors(params)
    if (res.code === 200) {
      sectorList.value = res.data || []
      sectorTotal.value = res.total || 0
    }
  } catch (error) {
    console.error('获取板块列表失败:', error)
  } finally {
    sectorLoading.value = false
  }
}

// 查看成分股
const showSectorStocks = async (sector) => {
  currentSector.value = sector
  showStockDialog.value = true
  sectorStocksSearch.value = ''
  sectorStocksPage.value = 1
  loadSectorStocks()
}

const loadSectorStocks = async () => {
  if (!currentSector.value) return
  stocksLoading.value = true
  try {
    const params = {
      page: sectorStocksPage.value,
      page_size: sectorStocksPageSize.value
    }
    if (sectorStocksSearch.value) {
      params.keyword = sectorStocksSearch.value
    }
    const res = await getSectorStocks(currentSector.value.sector_code, params)
    if (res.code === 200) {
      sectorStocks.value = res.data.stocks || []
      sectorStocksTotal.value = res.data.total || 0
    }
  } catch (error) {
    console.error('获取成分股失败:', error)
  } finally {
    stocksLoading.value = false
  }
}

const handleSectorStocksPageChange = (page) => {
  sectorStocksPage.value = page
  loadSectorStocks()
}

const handleSectorStocksSizeChange = (size) => {
  sectorStocksPageSize.value = size
  sectorStocksPage.value = 1
  loadSectorStocks()
}

// 点击板块标签查看成分股
const handleSectorTagClick = (sector) => {
  showSectorStocks(sector)
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 股票分页变化
const handleStockPageChange = (page) => {
  stockCurrentPage.value = page
  loadStocks()
}

const handleStockSizeChange = (size) => {
  stockPageSize.value = size
  stockCurrentPage.value = 1
  loadStocks()
}

// 加载股票列表（分页）
const loadStocks = async () => {
  stockListLoading.value = true
  try {
    // 后端分页：只取当页 + 当页股票的板块关联（不再全表拉 ~5500 股票 + ~16722 关联）
    const res = await getStocks(stockTypeFilter.value, stockSearch.value, stockCurrentPage.value, stockPageSize.value)
    if (res.code === 200) {
      stockList.value = res.data || []
      stockTotal.value = res.total || 0
      // 只加载当页股票的标签
      await loadBatchStockTags(stockList.value.map(s => s.stock_code))
    }
  } catch (error) {
    console.error('获取股票列表失败:', error)
  } finally {
    stockListLoading.value = false
  }
}

// 加载所有标签
const loadAllTags = async () => {
  try {
    const res = await getTags()
    if (res.code === 200) {
      allTags.value = res.data || []
      console.log('loadAllTags result:', allTags.value)
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

// 批量加载股票标签
const loadBatchStockTags = async (stockCodes) => {
  if (!stockCodes || stockCodes.length === 0) return
  console.log('loadBatchStockTags called with:', stockCodes.length, 'stocks, first 5:', stockCodes.slice(0, 5))
  try {
    const res = await getBatchStockTags(stockCodes)
    console.log('loadBatchStockTags response code:', res.code, 'data:', res.data)
    if (res.code === 200) {
      stockTags.value = res.data || {}
      console.log('stockTags updated, keys:', Object.keys(stockTags.value))
      // 检查北方稀土
      if (stockTags.value['sh.600111']) {
        console.log('北方稀土标签:', stockTags.value['sh.600111'])
      }
    } else {
      console.error('loadBatchStockTags failed:', res)
    }
  } catch (error) {
    console.error('获取股票标签失败:', error)
  }
}

// 打开标签管理弹窗
const openTagDialog = async (stock) => {
  console.log('openTagDialog called, stock:', stock.stock_code, stock.stock_name)
  currentStock.value = stock
  showTagDialog.value = true
  // 加载所有标签
  await loadAllTags()
  console.log('allTags loaded:', allTags.value.length)
  // 加载当前股票的标签
  await loadStockTags(stock.stock_code)
  console.log('stockTags for', stock.stock_code, ':', stockTags.value[stock.stock_code])
}

// 加载单个股票标签
const loadStockTags = async (stockCode) => {
  try {
    const res = await getStockTags(stockCode)
    if (res.code === 200) {
      stockTags.value[stockCode] = res.data || []
    }
  } catch (error) {
    console.error('获取股票标签失败:', error)
  }
}

// 切换股票的标签
const toggleStockTag = async (tag) => {
  if (!currentStock.value) return
  const stockCode = currentStock.value.stock_code
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

// 计算标签文字颜色（根据背景色判断）
const getTagTextColor = (color) => {
  if (!color) return '#fff'
  // 简单判断：如果是深色返回白色文字，浅色返回黑色文字
  const hex = color.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000' : '#fff'
}

// 切换股票类型过滤
const handleStockTypeChange = (type) => {
  stockTypeFilter.value = type
  stockCurrentPage.value = 1
  loadStocks()
}

// 加载所有板块列表（用于下拉选择）
const loadAllSectors = async () => {
  allSectorsLoading.value = true
  try {
    const res = await getAllSectors()
    if (res.code === 200) {
      allSectors.value = res.data || []
    }
  } catch (error) {
    console.error('获取板块列表失败:', error)
  } finally {
    allSectorsLoading.value = false
  }
}

// 打开选择板块弹窗
const openSectorDialog = (stock) => {
  currentStock.value = stock
  showSectorDialog.value = true
}

// 查看股票K线
const showStockKline = async (stock) => {
  klineStockCode.value = stock.stock_code
  klineStockName.value = stock.stock_name
  klineFrequency.value = 'd'
  showKlineDialog.value = true
  await loadStockKline()
}

// 加载股票K线数据
const loadStockKline = async () => {
  klineLoading.value = true
  try {
    const res = await getStockKline(klineStockCode.value, klineFrequency.value, 100)
    if (res.code === 200) {
      klineData.value = res.data || []
    } else {
      ElMessage.error(res.message || '获取K线数据失败')
    }
  } catch (error) {
    console.error('获取K线数据失败:', error)
    ElMessage.error('获取K线数据失败')
  } finally {
    klineLoading.value = false
  }
}

// 格式化成交量
const formatVolume = (volume) => {
  if (!volume) return '-'
  if (volume >= 100000000) {
    return (volume / 100000000).toFixed(2) + '亿'
  } else if (volume >= 10000) {
    return (volume / 10000).toFixed(2) + '万'
  }
  return volume.toString()
}

// 格式化成交额
const formatAmount = (amount) => {
  if (!amount) return '-'
  if (amount >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (amount >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

// 将股票添加到板块
const handleAddToSector = async (sectorId) => {
  if (!currentStock.value || !sectorId) return
  
  sectorDialogLoading.value = true
  try {
    const res = await addStockToSector({
      stock_code: currentStock.value.stock_code,
      sector_id: sectorId
    })
    if (res.code === 200) {
      ElMessage.success('添加成功')
      // 更新当前股票的板块列表
      const sector = allSectors.value.find(s => s.id === sectorId)
      if (sector) {
        currentStock.value.sectors.push({
          sector_code: sector.sector_code,
          sector_name: sector.sector_name,
          sector_type: sector.sector_type
        })
      }
      await loadStocks()
    } else {
      ElMessage.error(res.message || '添加失败')
    }
  } catch (error) {
    console.error('添加失败:', error)
    ElMessage.error('添加失败')
  } finally {
    sectorDialogLoading.value = false
  }
}

// 补充股票详细信息
const supplementStockInfo = async (row) => {
  if (!row || !row.stock_code) return
  
  // 设置 loading 状态
  row.supplementing = true
  
  try {
    ElMessage.info(`正在获取 ${row.stock_code} ${row.stock_name} 的详细信息...`)
    
    const res = await request.post('/metadata/stock/supplement-info', {
      stock_codes: [row.stock_code]
    })
    
    if (res.code === 200) {
      const result = res.data
      ElMessage.success(`成功获取 ${result.success} 只股票信息，失败 ${result.failed} 只`)
      // 刷新列表
      await loadStocks()
    } else {
      ElMessage.error(res.message || '获取失败')
    }
  } catch (error) {
    console.error('获取股票信息失败:', error)
    ElMessage.error('获取股票信息失败')
  } finally {
    row.supplementing = false
  }
}

// 将股票从板块移除
const handleRemoveFromSector = async (sectorCode) => {
  if (!currentStock.value || !sectorCode) return
  
  try {
    const sector = currentStock.value.sectors.find(s => s.sector_code === sectorCode)
    if (!sector) return
    
    const res = await removeStockFromSector({
      stock_code: currentStock.value.stock_code,
      sector_id: sectorCode
    })
    if (res.code === 200) {
      ElMessage.success('移除成功')
      // 更新当前股票的板块列表
      currentStock.value.sectors = currentStock.value.sectors.filter(s => s.sector_code !== sectorCode)
      await loadStocks()
    } else {
      ElMessage.error(res.message || '移除失败')
    }
  } catch (error) {
    console.error('移除失败:', error)
    ElMessage.error('移除失败')
  }
}

// 创建新板块
const handleCreateSector = async () => {
  if (!createSectorForm.value.sector_name) {
    ElMessage.warning('请输入板块名称')
    return
  }
  if (!createSectorForm.value.sector_code) {
    ElMessage.warning('请输入板块代码')
    return
  }
  
  createSectorLoading.value = true
  try {
    const res = await createSector(createSectorForm.value)
    if (res.code === 200) {
      ElMessage.success('板块创建成功')
      showCreateSectorDialog.value = false
      createSectorForm.value = {
        sector_code: '',
        sector_name: '',
        sector_type: 'industry',
        description: ''
      }
      await loadSectors()
      await loadAllSectors()
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (error) {
    console.error('创建板块失败:', error)
    ElMessage.error('创建失败')
  } finally {
    createSectorLoading.value = false
  }
}

// 生命周期
// 加载交割单统计
const loadDeliveryStats = async () => {
  statsLoading.value = true
  try {
    const res = await getDeliveryStats()
    if (res.code === 200) {
      deliveryStats.value = res.data
      if (res.data.total > 0) {
        await loadDeliveryList()
      }
    }
  } catch (error) {
    console.error('获取交割单统计失败:', error)
  } finally {
    statsLoading.value = false
  }
}

// 加载交割单列表
const loadDeliveryList = async () => {
  try {
    const res = await getDeliveryList({
      page: deliveryPage.value,
      page_size: deliveryPageSize.value
    })
    if (res.code === 200) {
      deliveryList.value = res.data.items || []
    }
  } catch (error) {
    console.error('获取交割单列表失败:', error)
  }
}

// 文件选择变化
const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

// 文件数量超出
const handleExceed = () => {
  ElMessage.warning('只能选择一个文件')
}

// 导入交割单
const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  importLoading.value = true
  try {
    const res = await importDelivery(selectedFile.value)
    if (res.code === 200) {
      ElMessage.success(`导入成功！共导入 ${res.data.imported} 条记录`)
      // 清空文件选择
      selectedFile.value = null
      if (uploadRef.value) {
        uploadRef.value.clearFiles()
      }
      // 刷新统计
      await loadDeliveryStats()
    } else {
      ElMessage.error(res.message || '导入失败')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败')
  } finally {
    importLoading.value = false
  }
}

// 交割单分页
const handleDeliverySizeChange = (size) => {
  deliveryPageSize.value = size
  deliveryPage.value = 1
  loadDeliveryList()
}

const handleDeliveryPageChange = (page) => {
  deliveryPage.value = page
  loadDeliveryList()
}

onMounted(async () => {
  await loadSummary()
  await loadSectors()
  await loadAllSectors()
  await loadStocks()
  await loadDeliveryStats()
})
</script>

<style scoped>
.metadata-init {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 16px;
  font-weight: bold;
}

:deep(.el-table) {
  margin-top: 0;
}

.sector-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.sector-tag.clickable {
  cursor: pointer;
}

.sector-tag.clickable:hover {
  color: #409eff;
  border-color: #409eff;
}

.no-sector {
  color: #909399;
}

.box-card {
  margin-bottom: 20px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.sector-stocks-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.stocks-count {
  margin-left: auto;
  color: #909399;
  font-size: 14px;
}

.selected-sectors {
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  margin-bottom: 12px;
}

.no-sectors {
  color: #909399;
  font-size: 14px;
  padding: 20px 0;
  text-align: center;
}

.sector-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.kline-count {
  color: #909399;
  font-size: 14px;
}

.positive {
  color: #f56c6c;
}

.negative {
  color: #67c23a;
}

/* 标签管理样式 */
.tag-management {
  padding: 10px 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
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

.tag-item {
  margin-right: 4px;
  margin-bottom: 2px;
}

.no-tag {
  color: #909399;
  font-size: 12px;
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
</style>
