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

export function getReviewReport(id) {
  return request.get(`/review/task/${id}/report`)
}

// 创建 Baostock 复盘任务
export function createBaostockReviewTask(data) {
  const taskData = {
    task_name: data.taskName,
    trade_date: data.tradeDate,
    review_type: data.reviewType || 'daily',
    dimensions: data.dimensions || [],
    rules: data.rules || []
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

// ==================== 数据同步相关API ====================

// 创建数据同步任务
export function createSyncTask(data) {
  const taskData = {
    task_name: data.taskName,
    start_date: data.startDate,
    end_date: data.endDate,
    frequency: data.frequency,
    stock_type: data.stockType || 'all'
  }
  return request.post('/sync/task', taskData)
}

// 获取同步任务列表
export function getSyncTaskList(params) {
  return request.get('/sync/tasks', { params })
}

// 获取同步任务详情
export function getSyncTaskDetail(id) {
  return request.get(`/sync/task/${id}`)
}

// 启动同步任务
export function startSyncTask(id) {
  return request.post(`/sync/task/${id}/start`)
}

// 删除同步任务
export function deleteSyncTask(id) {
  return request.delete(`/sync/task/${id}`)
}

// 获取K线频率选项
export function getFrequencyOptions() {
  return request.get('/sync/frequency/options')
}

// 获取股票类型选项
export function getStockTypeOptions() {
  return request.get('/sync/stock-type/options')
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
export function getSectorStocks(sectorCode) {
  return request.get(`/metadata/sectors/${sectorCode}/stocks`)
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
