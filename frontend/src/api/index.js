import request from './request'

// ==================== 复盘任务相关API ====================

// 创建复盘任务
export function createReviewTask(data) {
  // 转换字段名为snake_case
  const taskData = {
    task_name: data.taskName,
    trade_date: data.tradeDate,
    review_type: data.reviewType,
    dimensions: data.dimensions || [],
    rules: data.rules || [],
    data_source_type: data.dataSourceType || 'baostock',
    data_source_name: data.dataSourceName || '',
    data_source_desc: data.dataSourceDesc || ''
  }
  return request.post('/review/task', taskData)
}

export function executeReviewTask(id) {
  return request.post(`/review/task/${id}/execute`)
}

export function getReviewTaskList(params) {
  return request.get('/review/task/list', { params })
}

export function getReviewTaskDetail(id) {
  return request.get(`/review/task/${id}`)
}

export function getReviewTaskResults(id) {
  return request.get(`/review/task/${id}/results`)
}

// 创建 Baostock 复盘任务
export function createBaostockBatchReviewTask(data) {
  return request.post('/review/task/baostock/batch', {
    start_date: data.startDate,
    end_date: data.endDate,
    stock_filter: data.stockFilter || null,
    overwrite: data.overwrite || false
  })
}

export function createBaostockReviewTask(data) {
  const taskData = {
    task_name: data.taskName,
    trade_date: data.tradeDate,
    review_type: data.reviewType || 'daily',
    dimensions: data.dimensions || [],
    rules: data.rules || []
  }
  // 如果有 stock_filter 参数
  if (data.stockFilter) {
    taskData.stock_filter = data.stockFilter
  }
  // 如果有 overwrite 参数
  if (data.overwrite) {
    taskData.overwrite = true
  }
  return request.post('/review/task/baostock', taskData)
}

// 获取复盘任务图表数据
export function getReviewTaskChart(id) {
  return request.get(`/review/task/${id}/chart`)
}

// 删除复盘任务
export function deleteReviewTask(id) {
  return request.delete(`/review/task/${id}`)
}

// 获取首页仪表盘数据
export function getDashboardData(params) {
  return request.get('/review/dashboard', { params })
}

// ==================== 股票相关API ====================

export function getStockList(date) {
  return request.get('/stock/list', { params: { date } })
}

export function getStockInfo(stockCode) {
  return request.get(`/stock/info/${stockCode}`)
}

export function getStockHistory(symbol, startDate, endDate, frequency, adjustType) {
  return request.get('/stock/history', {
    params: { symbol, startDate, endDate, frequency, adjustType }
  })
}

export function importStockData(data) {
  return request.post('/stock/import', data)
}

export function getStockRealtime(symbols) {
  return request.get('/stock/realtime', { params: { symbols } })
}

// ==================== 数据同步相关API（只读查询） ====================
// 2026-06-10：移除手动同步任务管理 API（createSyncTask/start/stop/delete/task list/options）。
// 大历史数据同步改用独立临时脚本灌入；每日复盘增量同步由后端 review 内部直接触发，不经此前端入口。

// 获取股票K线数据
export function getStockKline(stockCode, frequency = 'd', limit = 100) {
  return request.get(`/sync/kline/${stockCode}`, {
    params: { frequency, limit }
  })
}

// ==================== 元数据相关API ====================

// 获取元数据统计
export function getMetadataSummary() {
  return request.get('/metadata/summary')
}

// 测试AKShare连接
export function testAKShare() {
  return request.get('/metadata/akshare/test')
}

// 直接测试东方财富API
export function directTestAKShare() {
  return request.get('/metadata/akshare/direct-test')
}

// 从AKShare初始化行业板块
export function initIndustryFromAKShare() {
  return request.post('/metadata/init/industry-from-akshare')
}

// 从AKShare初始化概念板块
export function initConceptFromAKShare() {
  return request.post('/metadata/init/concept-from-akshare')
}

// 从AKShare初始化全部板块
export function initAllFromAKShare() {
  return request.post('/metadata/init/all-from-akshare')
}

// 获取板块列表
export function getSectors(params) {
  return request.get('/metadata/sectors', { params })
}

// 获取板块成分股
export function getSectorStocks(sectorCode, params) {
  return request.get(`/metadata/sectors/${sectorCode}/stocks`, { params })
}

// 更新 股票-板块 关系的人工优先级（0-10）
export function updateRelationPriority(data) {
  return request.post('/metadata/relation/priority', data)
}

// 获取股票基本信息和板块（使用元数据接口）
export function getStockBasicInfo(stockCode) {
  return request.get(`/metadata/stock/${stockCode}`)
}

// ==================== AKShare 元数据初始化 API ====================

// 从AKShare初始化股票基本信息
export function initStockFromAKShare(data = {}) {
  return request.post('/metadata/init/stock-from-akshare', data)
}

// 从AKShare初始化全部元数据（股票 + 板块）
export function initFullFromAKShare(data = {}) {
  return request.post('/metadata/init/full-from-akshare', data)
}

// 获取股票列表（包含所属板块信息）
// type: 股票类型过滤 (stock-股票, index-指数, etf-ETF, 空=全部)
// search: 搜索关键词（代码或名称）
export function getStocks(type = '', search = '', page = 1, pageSize = 20) {
  const params = { page, pageSize }
  if (type) {
    params.type = type
  }
  if (search) {
    params.search = search
  }
  return request.get('/metadata/stocks', { params })
}

// 获取所有板块列表（用于下拉选择）
export function getAllSectors() {
  return request.get('/metadata/sectors/all')
}

// 将股票添加到板块
export function addStockToSector(data) {
  return request.post('/metadata/stock-sector', data)
}

// 将股票从板块移除
export function removeStockFromSector(data) {
  return request.delete('/metadata/stock-sector', { data })
}

// 获取单只股票的板块列表
export function getStockSectors(stockCode) {
  return request.get(`/metadata/stock/${stockCode}/sectors`)
}

// 批量获取多只股票的板块
export function getBatchStockSectors(stockCodes) {
  return request.post('/metadata/stocks/sectors', { stock_codes: stockCodes })
}

// 创建新板块
export function createSector(data) {
  return request.post('/metadata/sectors', data)
}

// ==================== 交割单相关API ====================

// 导入交割单
export function importDelivery(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/metadata/delivery/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// 获取交割单列表
export function getDeliveryList(params) {
  return request.get('/metadata/delivery/list', { params })
}

// 获取交割单统计
export function getDeliveryStats() {
  return request.get('/metadata/delivery/stats')
}

// 根据股票代码获取交割单列表
export function getDeliveryByStock(stockCode, params) {
  return request.get(`/metadata/delivery/by-stock/${stockCode}`, { params })
}

// 获取交割单中涉及的股票列表
export function getDeliveryStocks(params) {
  return request.get('/metadata/delivery/stocks', { params })
}

// 获取指定股票的交割单汇总
export function getDeliverySummary(stockCode) {
  return request.get(`/metadata/delivery/summary/${stockCode}`)
}

// 更新交割单复盘记录
export function updateDeliveryReviewNote(deliveryId, reviewNote) {
  return request.put(`/metadata/delivery/${deliveryId}/review-note`, { review_note: reviewNote })
}

// 获取所有标签
export function getTags() {
  return request.get('/tag/list')
}

// 新增标签
export function addTag(data) {
  return request.post('/tag/add', data)
}

// 更新标签
export function updateTag(tagId, data) {
  return request.put(`/tag/update/${tagId}`, data)
}

// 删除标签
export function deleteTag(tagId) {
  return request.delete(`/tag/delete/${tagId}`)
}

// 获取股票的所有标签
export function getStockTags(stockCode) {
  return request.get(`/tag/stock/${stockCode}`)
}

// 为股票添加标签
export function addStockTag(stockCode, tagId) {
  return request.post('/tag/stock/add', { stock_code: stockCode, tag_id: tagId })
}

// 移除股票的标签
export function removeStockTag(stockCode, tagId) {
  return request.post('/tag/stock/remove', { stock_code: stockCode, tag_id: tagId })
}

// 批量获取股票的标签
export function getBatchStockTags(stockCodes) {
  return request.post('/tag/batch/stock/tags', { stock_codes: stockCodes })
}

// ==================== 因子管理API ====================

// 获取因子列表
export function getFactorList(params) {
  return request.get('/factor/list', { params })
}

// 获取单个因子
export function getFactor(factorId) {
  return request.get(`/factor/${factorId}`)
}

// 创建因子
export function createFactor(data) {
  return request.post('/factor', data)
}

// 更新因子
export function updateFactor(factorId, data) {
  return request.put(`/factor/${factorId}`, data)
}

// 删除因子
export function deleteFactor(factorId) {
  return request.delete(`/factor/${factorId}`)
}

// 批量创建因子
export function batchCreateFactors(data) {
  return request.post('/factor/batch', data)
}

// 获取因子下拉选项
export function getFactorOptions(params) {
  return request.get('/factor/options', { params })
}

// ==================== 表达式管理API ====================

// 获取表达式列表
export function getExpressionList(params) {
  return request.get('/expression/list', { params })
}

// 获取单个表达式
export function getExpression(exprId) {
  return request.get(`/expression/${exprId}`)
}

// 创建表达式
export function createExpression(data) {
  return request.post('/expression', data)
}

// 更新表达式
export function updateExpression(exprId, data) {
  return request.put(`/expression/${exprId}`, data)
}

// 删除表达式
export function deleteExpression(exprId) {
  return request.delete(`/expression/${exprId}`)
}

// 测试表达式
export function testExpression(data) {
  return request.post('/expression/test', data)
}

// 计算表达式
export function calculateExpression(data) {
  return request.post('/expression/calculate', data)
}

// 获取默认表达式
export function getDefaultExpression(scope) {
  return request.get(`/expression/default/${scope}`)
}

// ==================== 每日笔记API ====================

// 获取指定交易日的笔记
export function getDailyNote(tradeDate) {
  return request.get(`/review/note/${tradeDate}`)
}

// 保存每日笔记
export function saveDailyNote(data) {
  return request.post('/review/note', data)
}

// 获取最新笔记
export function getLatestNote() {
  return request.get('/review/note/latest')
}

// ==================== 周期管理API ====================

// 获取所有周期列表
export function getCycleList() {
  return request.get('/cycle')
}

// 获取单个周期详情
export function getCycleDetail(cycleId) {
  return request.get(`/cycle/${cycleId}`)
}

// 创建周期
export function createCycle(data) {
  return request.post('/cycle', data)
}

// 更新周期
export function updateCycle(cycleId, data) {
  return request.put(`/cycle/${cycleId}`, data)
}

// 删除周期
export function deleteCycle(cycleId) {
  return request.delete(`/cycle/${cycleId}`)
}

// 获取周期下的小周期列表
export function getSubPeriods(cycleId) {
  return request.get(`/cycle/${cycleId}/sub-periods`)
}

// 创建小周期
export function createSubPeriod(cycleId, data) {
  return request.post(`/cycle/${cycleId}/sub-periods`, data)
}

// 更新小周期
export function updateSubPeriod(subPeriodId, data) {
  return request.put(`/cycle/sub-periods/${subPeriodId}`, data)
}

// 删除小周期
export function deleteSubPeriod(subPeriodId) {
  return request.delete(`/cycle/sub-periods/${subPeriodId}`)
}

// 获取所有交易日关联
export function getTradeDays() {
  return request.get('/cycle/trade-days')
}

// 绑定交易日到小周期
export function bindTradeDay(data) {
  return request.post('/cycle/trade-days/bind', data)
}

// 批量绑定交易日
export function batchBindTradeDays(data) {
  return request.post('/cycle/trade-days/batch', data)
}

// 解绑交易日
export function unbindTradeDay(tradeDate) {
  return request.delete(`/cycle/trade-days/${tradeDate}`)
}

// 根据日期获取周期信息
export function getCycleByDate(tradeDate) {
  return request.get(`/cycle/by-date/${tradeDate}`)
}

// 获取最近周期信息
export function getLatestCycle() {
  return request.get('/cycle/latest')
}

// 股票搜索（自动补全）
export function searchStocks(q) {
  return request.get('/metadata/stocks/search', { params: { q } })
}

// ==================== 炒股笔记 API ====================

export function getNoteList(params) {
  return request.get('/note/notes', { params })
}

export function getNote(noteId) {
  return request.get(`/note/notes/${noteId}`)
}

export function createNote(data) {
  return request.post('/note/notes', data)
}

export function updateNote(noteId, data) {
  return request.put(`/note/notes/${noteId}`, data)
}

export function deleteNote(noteId) {
  return request.delete(`/note/notes/${noteId}`)
}

export function toggleNotePin(noteId) {
  return request.put(`/note/notes/${noteId}/pin`)
}

export function getNoteTags() {
  return request.get('/note/notes/tags')
}

