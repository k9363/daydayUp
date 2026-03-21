<template>
  <div class="factor-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>因子管理</h2>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="股票因子" name="stock">
        <div class="toolbar">
          <el-input
            v-model="stockSearch"
            placeholder="搜索因子代码/名称"
            clearable
            style="width: 200px"
            @input="handleSearch('stock')"
          />
          <el-button type="primary" @click="handleAdd('stock')">新增因子</el-button>
          <el-button @click="handleBatchAdd('stock')">批量导入</el-button>
        </div>
        
        <el-table :data="stockFactors" border v-loading="stockLoading">
          <el-table-column prop="factor_code" label="因子代码" width="150" />
          <el-table-column prop="factor_name" label="因子名称" width="150" />
          <el-table-column prop="source" label="数据来源" width="120">
            <template #default="{ row }">
              <el-tag>{{ getSourceLabel(row.source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="calculation_method" label="计算方法" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.calculation_method" type="success">{{ row.calculation_method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="field_name" label="字段" width="80" />
          <el-table-column prop="days_range" label="天数区间" width="100">
            <template #default="{ row }">
              <span v-if="row.days_range">{{ row.days_range }}</span>
              <span v-else style="color: #909399;">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="days_offset" label="日期偏移" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.days_offset > 0" type="warning">-{{ row.days_offset }}日</el-tag>
              <span v-else style="color: #909399;">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="板块因子" name="sector">
        <div class="toolbar">
          <el-input
            v-model="sectorSearch"
            placeholder="搜索因子代码/名称"
            clearable
            style="width: 200px"
            @input="handleSearch('sector')"
          />
          <el-button type="primary" @click="handleAdd('sector')">新增因子</el-button>
          <el-button @click="handleBatchAdd('sector')">批量导入</el-button>
        </div>
        
        <el-table :data="sectorFactors" border v-loading="sectorLoading">
          <el-table-column prop="factor_code" label="因子代码" width="150" />
          <el-table-column prop="factor_name" label="因子名称" width="150" />
          <el-table-column prop="source" label="数据来源" width="120">
            <template #default="{ row }">
              <el-tag>{{ getSourceLabel(row.source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="field_name" label="字段" width="120" />
          <el-table-column prop="aggregation" label="聚合方式" width="100">
            <template #default="{ row }">
              {{ row.aggregation || '无' }}
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="大盘因子" name="market">
        <div class="toolbar">
          <el-input
            v-model="marketSearch"
            placeholder="搜索因子代码/名称"
            clearable
            style="width: 200px"
            @input="handleSearch('market')"
          />
          <el-button type="primary" @click="handleAdd('market')">新增因子</el-button>
          <el-button @click="handleBatchAdd('market')">批量导入</el-button>
        </div>
        
        <el-table :data="marketFactors" border v-loading="marketLoading">
          <el-table-column prop="factor_code" label="因子代码" width="150" />
          <el-table-column prop="factor_name" label="因子名称" width="150" />
          <el-table-column prop="source" label="数据来源" width="120">
            <template #default="{ row }">
              <el-tag>{{ getSourceLabel(row.source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="field_name" label="字段" width="120" />
          <el-table-column prop="index_code" label="指数代码" width="120" />
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 因子编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑因子' : '新增因子'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="因子代码" prop="factor_code">
          <el-input v-model="form.factor_code" placeholder="如: stock_score" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="因子名称" prop="factor_name">
          <el-input v-model="form.factor_name" placeholder="如: 股票得分" />
        </el-form-item>
        <el-form-item label="因子作用域" prop="factor_scope">
          <el-radio-group v-model="form.factor_scope">
            <el-radio label="stock">股票因子</el-radio>
            <el-radio label="sector">板块因子</el-radio>
            <el-radio label="market">大盘因子</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数据来源" prop="source">
          <el-select v-model="form.source" placeholder="选择数据来源" @change="handleSourceChange">
            <el-option label="K线原始数据" value="kline" />
            <el-option label="股票因子得分" value="stock_factor" />
            <el-option label="板块因子得分" value="sector_factor" />
            <el-option label="大盘因子得分" value="market_factor" />
            <el-option label="表达式计算" value="calculated" />
          </el-select>
        </el-form-item>
        
        <!-- 计算方法 -->
        <el-form-item v-if="form.source === 'kline'" label="计算方法" prop="calculation_method">
          <el-select v-model="form.calculation_method" placeholder="选择计算方法" @change="handleCalculationMethodChange">
            <el-option label="直接取字段值" value="kline_field" />
            <el-option label="排名得分" value="rank" />
            <el-option label="表达式计算" value="expression" />
            <el-option label="成交额均线" value="turnover_ma" />
            <el-option label="新高判断" value="new_high" />
          </el-select>
        </el-form-item>
        
        <!-- 新高判断配置 -->
        <el-form-item v-if="form.source === 'kline' && form.calculation_method === 'new_high'" label="天数配置" prop="days_range">
          <div class="new-high-config">
            <el-input-number v-model="newHighDays" :min="1" :max="250" @change="updateFactorCode" />
            <span class="hint">个交易日</span>
            <div style="margin-top: 5px; color: #909399; font-size: 12px;">
              预览因子代码: <code>{{ form.factor_code || 'new_high_X' }}</code>
            </div>
          </div>
        </el-form-item>
        
        <!-- 成交额均线配置 -->
        <el-form-item v-if="form.source === 'kline' && form.calculation_method === 'turnover_ma'" label="均线配置" prop="days_range">
          <div class="ma-config">
            <el-radio-group v-model="maConfigType" @change="handleMaConfigChange">
              <el-radio label="recent">最近N天</el-radio>
              <el-radio label="range">指定区间</el-radio>
            </el-radio-group>
            <div class="ma-inputs" style="margin-top: 10px;">
              <template v-if="maConfigType === 'recent'">
                <el-input-number v-model="maDays" :min="1" :max="250" @change="updateFactorCode" />
                <span class="hint">天</span>
              </template>
              <template v-else>
                <el-input-number v-model="maStart" :min="1" :max="250" @change="updateFactorCode" />
                <span class="hint"> - </span>
                <el-input-number v-model="maEnd" :min="1" :max="250" @change="updateFactorCode" />
                <span class="hint">天</span>
              </template>
            </div>
            <div style="margin-top: 5px; color: #909399; font-size: 12px;">
              预览因子代码: <code>{{ form.factor_code || 'avg_amount_Xd' }}</code>
            </div>
          </div>
        </el-form-item>
        
        <!-- 表达式配置：K线+表达式计算 或 数据来源=表达式计算 时都显示完整编辑器 -->
        <el-form-item v-if="(form.source === 'kline' && form.calculation_method === 'expression') || form.source === 'calculated'" label="表达式" prop="expression">
          <div class="expr-editor">
            <!-- 因子提示 -->
            <div class="factor-hint">提示：点击下方因子按钮可直接插入表达式中</div>
            <!-- 因子按钮 -->
            <div class="factor-buttons">
              <el-button 
                v-for="f in stockFactors" 
                :key="f.factor_code"
                size="small" 
                type="info"
                class="factor-btn"
                @click="insertFactor(f.factor_code)"
                :title="f.description"
              >
                {{ f.factor_code }}
              </el-button>
            </div>
            
            <!-- 工具栏 -->
            <div class="expr-toolbar">
              <el-button-group>
                <el-button size="small" @click="insertOperator('+')">+</el-button>
                <el-button size="small" @click="insertOperator('-')">-</el-button>
                <el-button size="small" @click="insertOperator('*')">×</el-button>
                <el-button size="small" @click="insertOperator('/')">÷</el-button>
                <el-button size="small" @click="insertOperator('(')">(</el-button>
                <el-button size="small" @click="insertOperator(')')">)</el-button>
              </el-button-group>
              <el-divider direction="vertical" />
              <!-- 插入因子按钮 -->
              <el-dropdown @command="insertFactor" trigger="click">
                <el-button size="small" type="success">
                  插入因子 ▼
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu style="max-height: 300px; overflow-y: auto;">
                    <el-dropdown-item disabled style="font-weight: bold;">股票因子</el-dropdown-item>
                    <el-dropdown-item v-for="f in stockFactors" :key="f.factor_code" :command="f.factor_code">
                      {{ f.factor_name }} ({{ f.factor_code }})
                    </el-dropdown-item>
                    <el-dropdown-item disabled style="font-weight: bold;">板块因子</el-dropdown-item>
                    <el-dropdown-item v-for="f in sectorFactors" :key="f.factor_code" :command="f.factor_code">
                      {{ f.factor_name }} ({{ f.factor_code }})
                    </el-dropdown-item>
                    <el-dropdown-item disabled style="font-weight: bold;">大盘因子</el-dropdown-item>
                    <el-dropdown-item v-for="f in marketFactors" :key="f.factor_code" :command="f.factor_code">
                      {{ f.factor_name }} ({{ f.factor_code }})
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-divider direction="vertical" />
              <!-- 插入字段按钮 -->
              <el-dropdown @command="insertField" trigger="click">
                <el-button size="small" type="warning">
                  插入字段 ▼
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu style="max-height: 200px; overflow-y: auto;">
                    <el-dropdown-item v-for="f in klineFields" :key="f" :command="f">
                      {{ f }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-divider direction="vertical" />
              <el-dropdown @command="insertFunction">
                <el-button size="small">
                  函数 ▼
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="IF">IF(条件, 真值, 假值)</el-dropdown-item>
                    <el-dropdown-item command="ABS">ABS(数值)</el-dropdown-item>
                    <el-dropdown-item command="SQRT">SQRT(数值)</el-dropdown-item>
                    <el-dropdown-item command="MAX">MAX(a, b)</el-dropdown-item>
                    <el-dropdown-item command="MIN">MIN(a, b)</el-dropdown-item>
                    <el-dropdown-item command="AVG">AVG(a, b)</el-dropdown-item>
                    <el-dropdown-item command="ROUND">ROUND(数值, 位数)</el-dropdown-item>
                    <el-dropdown-item command="POW">POW(底数, 指数)</el-dropdown-item>
                    <el-dropdown-item command="SUM">SUM(a, b, ...)</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            
            <!-- 编辑器 -->
            <el-input
              ref="exprTextarea"
              v-model="form.expression"
              type="textarea"
              :rows="4"
              class="expr-textarea"
              placeholder="使用因子代码或字段名编写表达式，如: avg_amount_3d / avg_amount_4_20d&#10;IF(close_price > ma5, 1, 0) - 条件表达式"
            />
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            支持函数: AVG(field, days), IF(cond, true, false), ABS, MAX, MIN, SUM, POW
          </div>
        </el-form-item>
        
        <!-- K线字段选择 -->
        <el-form-item v-if="form.source === 'kline' && form.calculation_method !== 'new_high' && form.calculation_method !== 'turnover_ma'" label="字段选择" prop="field_name">
          <el-select v-model="form.field_name" placeholder="选择字段" filterable @change="handleFieldChange">
            <el-optgroup v-for="group in klineFieldGroups" :key="group.label" :label="group.label">
              <el-option v-for="f in group.options" :key="f.value" :label="f.label" :value="f.value" />
            </el-optgroup>
          </el-select>
        </el-form-item>
        
        <!-- 日期偏移配置 -->
        <el-form-item v-if="form.source === 'kline' && form.calculation_method !== 'new_high' && form.calculation_method !== 'turnover_ma'" label="日期偏移" prop="days_offset">
          <div class="offset-config">
            <el-input-number v-model="form.days_offset" :min="0" :max="120" :step="1" />
            <span class="hint">
              <template v-if="form.days_offset === 0">当日</template>
              <template v-else-if="form.days_offset === 1">昨日</template>
              <template v-else-if="form.days_offset === 2">前日</template>
              <template v-else>前{{ form.days_offset }}日</template>
            </span>
            <div class="hint-text" v-if="form.field_name === 'ma5' || form.field_name === 'ma10' || form.field_name === 'ma20'">
              提示：均线因子会自动根据偏移量计算历史均线
            </div>
          </div>
        </el-form-item>
        
        <!-- 因子选择 -->
        <el-form-item v-if="['stock_factor', 'sector_factor', 'market_factor'].includes(form.source)" label="选择因子" prop="field_name">
          <el-select v-model="form.field_name" placeholder="选择因子" filterable>
            <el-option-group v-for="group in factorOptions" :key="group.label" :label="group.label">
              <el-option v-for="f in group.options" :key="f.factor_code" :label="`${f.factor_name} (${f.factor_code})`" :value="f.factor_code" />
            </el-option-group>
          </el-select>
        </el-form-item>
        
        <!-- 聚合方式（板块因子） -->
        <el-form-item v-if="form.factor_scope === 'sector'" label="聚合方式" prop="aggregation">
          <el-radio-group v-model="form.aggregation">
            <el-radio label="">无（原始值）</el-radio>
            <el-radio label="SUM">求和</el-radio>
            <el-radio label="AVG">平均值</el-radio>
            <el-radio label="MAX">最大值</el-radio>
            <el-radio label="MIN">最小值</el-radio>
            <el-radio label="COUNT">计数</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- 指数选择（大盘因子） -->
        <el-form-item v-if="form.factor_scope === 'market'" label="指数选择" prop="index_code">
          <el-select v-model="form.index_code" placeholder="选择指数" filterable>
            <el-option-group v-for="group in indexGroups" :key="group.label" :label="group.label">
              <el-option v-for="idx in group.options" :key="idx.code" :label="idx.name" :value="idx.code" />
            </el-option-group>
          </el-select>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { getFactorList, createFactor, updateFactor, deleteFactor, getFactorOptions } from '@/api'

export default {
  name: 'FactorList',
  data() {
    return {
      activeTab: 'stock',
      // 股票因子
      stockFactors: [],
      stockLoading: false,
      stockSearch: '',
      // 板块因子
      sectorFactors: [],
      sectorLoading: false,
      sectorSearch: '',
      // 大盘因子
      marketFactors: [],
      marketLoading: false,
      marketSearch: '',
      // 弹窗
      dialogVisible: false,
      isEdit: false,
      submitLoading: false,
      form: {
        id: null,
        factor_code: '',
        factor_name: '',
        factor_scope: 'stock',
        source: '',
        calculation_method: '',
        filter_condition: '',
        field_name: '',
        days_range: '',
        days_offset: 0,
        aggregation: '',
        index_code: '',
        expression: '',
        description: ''
      },
      // 成交额均线配置
      maConfigType: 'recent',
      maDays: 3,
      maStart: 4,
      maEnd: 20,
      // 新高判断配置
      newHighDays: 120,
      rules: {
        factor_code: [{ required: true, message: '请输入因子代码', trigger: 'blur' }],
        factor_name: [{ required: true, message: '请输入因子名称', trigger: 'blur' }],
        factor_scope: [{ required: true, message: '请选择因子作用域', trigger: 'change' }],
        source: [{ required: true, message: '请选择数据来源', trigger: 'change' }]
      },
      // 下拉选项
      factorOptions: [],
      // 因子选项（用于表达式编辑）
      stockFactors: [],
      sectorFactors: [],
      marketFactors: [],
      // K线字段
      // K线字段分组
      klineFieldGroups: [
        {
          label: '价格类',
          options: [
            { value: 'close_price', label: '收盘价' },
            { value: 'open_price', label: '开盘价' },
            { value: 'high_price', label: '最高价' },
            { value: 'low_price', label: '最低价' },
            { value: 'pct_change', label: '涨跌幅' },
            { value: 'change', label: '涨跌额' },
          ]
        },
        {
          label: '量价类',
          options: [
            { value: 'volume', label: '成交量' },
            { value: 'turnover', label: '成交额' },
          ]
        },
        {
          label: '均线类',
          options: [
            { value: 'ma5', label: 'MA5 (5日均线)' },
            { value: 'ma10', label: 'MA10 (10日均线)' },
            { value: 'ma20', label: 'MA20 (20日均线)' },
            { value: 'ma30', label: 'MA30 (30日均线)' },
            { value: 'ma60', label: 'MA60 (60日均线)' },
          ]
        }
      ],
      // 兼容旧版本
      klineFields: ['close_price', 'volume', 'turnover', 'pct_change', 'open_price', 'high_price', 'low_price', 'change', 'ma5', 'ma10', 'ma20'],
      // 指数组
      indexGroups: [
        { label: '主要指数', options: [
          { code: 'sh.000001', name: '上证指数' },
          { code: 'sz.399001', name: '深证成指' },
          { code: 'sz.399006', name: '创业板指' }
        ]},
        { label: '沪深300', options: [
          { code: 'sh.000300', name: '沪深300' },
          { code: 'sh.000905', name: '中证500' },
          { code: 'sh.000016', name: '上证50' }
        ]}
      ],
      sourceMap: {
        'kline': 'K线原始数据',
        'stock_factor': '股票因子得分',
        'sector_factor': '板块因子得分',
        'market_factor': '大盘因子得分',
        'calculated': '表达式计算'
      }
    }
  },
  mounted() {
    this.loadFactors()
    this.loadFactorOptions()
  },
  methods: {
    async loadFactors() {
      // 只加载活跃的因子
      const params = { active_only: 'true' }
      
      // 加载股票因子
      this.stockLoading = true
      try {
        const res = await getFactorList({ ...params, scope: 'stock' })
        if (res.code === 200) {
          this.stockFactors = res.data
        }
      } finally {
        this.stockLoading = false
      }
      
      // 加载板块因子
      this.sectorLoading = true
      try {
        const res = await getFactorList({ ...params, scope: 'sector' })
        if (res.code === 200) {
          this.sectorFactors = res.data
        }
      } finally {
        this.sectorLoading = false
      }
      
      // 加载大盘因子
      this.marketLoading = true
      try {
        const res = await getFactorList({ ...params, scope: 'market' })
        if (res.code === 200) {
          this.marketFactors = res.data
        }
      } finally {
        this.marketLoading = false
      }
    },
    
    async loadFactorOptions() {
      try {
        const res = await getFactorOptions()
        if (res.code === 200) {
          const data = res.data
          this.factorOptions = [
            { label: '股票因子', options: data.stock || [] },
            { label: '板块因子', options: data.sector || [] },
            { label: '大盘因子', options: data.market || [] }
          ]
          // 不要用 options 覆盖表格数据：options 只有 factor_code/name/source/field_name，没有 expression、id 等，会导致编辑时表达式不展示
          // 表格与表达式区的因子列表均使用 loadFactors() 返回的完整数据
        }
      } catch (e) {
        console.error('加载因子选项失败', e)
      }
    },
    
    handleTabChange(tab) {
      // 切换标签时可以做一些操作
    },
    
    handleSearch(scope) {
      // 实际搜索逻辑
      this.loadFactors()
    },
    
    handleAdd(scope) {
      this.isEdit = false
      this.form = {
        id: null,
        factor_code: '',
        factor_name: '',
        factor_scope: scope,
        source: '',
        calculation_method: '',
        field_name: '',
        days_range: '',
        days_offset: 0,
        aggregation: '',
        index_code: '',
        expression: '',
        description: ''
      }
      this.dialogVisible = true
    },
    
    handleEdit(row) {
      this.isEdit = true
      this.form = { ...row }
      
      // 如果是成交额均线因子，解析 days_range 并回显配置
      if (row.calculation_method === 'turnover_ma' && row.days_range) {
        const parts = row.days_range.split('_')
        if (parts.length === 2) {
          if (parts[0] === '1') {
            // 最近N天
            this.maConfigType = 'recent'
            this.maDays = parseInt(parts[1])
          } else {
            // 指定区间
            this.maConfigType = 'range'
            this.maStart = parseInt(parts[0])
            this.maEnd = parseInt(parts[1])
          }
        }
      }
      
      // 如果是新高判断因子，回显天数配置
      if (row.calculation_method === 'new_high' && row.days_range) {
        this.newHighDays = parseInt(row.days_range)
      }
      
      this.dialogVisible = true
    },
    
    async handleDelete(row) {
      try {
        await this.$confirm('确定要删除该因子吗？', '提示', { type: 'warning' })
        const res = await deleteFactor(row.id)
        if (res.code === 200) {
          this.$message.success('删除成功')
          this.loadFactors()
        }
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error('删除失败')
        }
      }
    },
    
    handleSourceChange() {
      this.form.field_name = ''
      // 只有切换到非「表达式计算」时才清空表达式，避免编辑时因 select 触发的 change 把已有表达式清空
      if (this.form.source !== 'calculated') {
        this.form.expression = ''
      }
      this.form.calculation_method = ''
      this.form.filter_condition = ''
      this.form.days_range = ''
      this.form.days_offset = 0
    },
    
    // 字段选择变化时自动更新因子代码
    handleFieldChange(fieldName) {
      if (!this.isEdit && this.form.source === 'kline') {
        const offset = this.form.days_offset || 0
        if (offset > 0 && fieldName) {
          // 根据字段名和偏移量自动生成因子代码
          this.form.factor_code = `${fieldName}_y${offset}`
          this.form.factor_name = `${this.getFieldLabel(fieldName)}前${offset}日`
        }
      }
    },
    
    getFieldLabel(fieldName) {
      for (const group of this.klineFieldGroups) {
        const found = group.options.find(o => o.value === fieldName)
        if (found) return found.label
      }
      return fieldName
    },
    
    handleCalculationMethodChange() {
      if (this.form.calculation_method === 'turnover_ma') {
        // 初始化均线配置
        this.maConfigType = 'recent'
        this.maDays = 3
        this.maStart = 4
        this.maEnd = 20
        this.updateFactorCode()
      } else if (this.form.calculation_method === 'new_high') {
        // 初始化新高判断配置
        this.newHighDays = 120
        this.updateFactorCode()
      }
    },
    
    handleMaConfigChange(type) {
      this.updateFactorCode()
    },
    
    updateFactorCode() {
      if (this.form.calculation_method === 'turnover_ma') {
        if (this.maConfigType === 'recent') {
          this.form.days_range = `1_${this.maDays}`
          this.form.factor_code = `avg_amount_${this.maDays}d`
          this.form.factor_name = `近${this.maDays}日平均成交额`
        } else {
          this.form.days_range = `${this.maStart}_${this.maEnd}`
          this.form.factor_code = `avg_amount_${this.maStart}_${this.maEnd}d`
          this.form.factor_name = `${this.maStart}-${this.maEnd}日平均成交额`
        }
        this.form.field_name = 'turnover'
      } else if (this.form.calculation_method === 'new_high') {
        this.form.days_range = String(this.newHighDays)
        this.form.factor_code = `new_high_${this.newHighDays}`
        this.form.factor_name = `新高${this.newHighDays}日`
        this.form.field_name = 'close_price'
      }
    },
    
    // 获取光标位置的辅助方法
    getTextareaCursorPos(textareaEl) {
      if (!textareaEl) return this.form.expression?.length || 0
      if (textareaEl.selectionStart !== undefined) {
        return textareaEl.selectionStart
      }
      return this.form.expression?.length || 0
    },

    // 在光标位置插入文本
    insertAtCursor(text) {
      const textarea = this.$refs.exprTextarea
      if (!textarea || !textarea.$el) {
        // 如果没有 ref，直接追加到末尾
        this.form.expression = (this.form.expression || '') + text
        return
      }
      
      // 获取 textarea 元素
      const textareaEl = textarea.$el.querySelector('textarea') || textarea.$el
      const cursorPos = this.getTextareaCursorPos(textareaEl)
      const currentExpr = this.form.expression || ''
      
      // 在光标位置插入文本
      this.form.expression = currentExpr.slice(0, cursorPos) + text + currentExpr.slice(cursorPos)
      
      // 设置光标位置到插入文本之后
      this.$nextTick(() => {
        const newPos = cursorPos + text.length
        if (textareaEl.setSelectionRange) {
          textareaEl.focus()
          textareaEl.setSelectionRange(newPos, newPos)
        }
      })
    },
    
    insertFactor(factorCode) {
      this.insertAtCursor(factorCode)
    },
    
    insertOperator(op) {
      this.insertAtCursor(op)
    },
    
    insertField(fieldName) {
      this.insertAtCursor(fieldName)
    },
    
    insertFunction(func) {
      const funcMap = {
        'ABS': 'ABS()',
        'SQRT': 'SQRT()',
        'MAX': 'MAX(,)',
        'MIN': 'MIN(,)',
        'AVG': 'AVG(,)',
        'ROUND': 'ROUND(,)',
        'POW': 'POW(,)',
        'SUM': 'SUM(,)',
        'IF': 'IF(, , )'
      }
      this.insertAtCursor(funcMap[func] || func + '()')
    },
    
    async handleSubmit() {
      try {
        await this.$refs.formRef.validate()
        this.submitLoading = true
        
        const data = { ...this.form }
        let res
        if (this.isEdit) {
          res = await updateFactor(this.form.id, data)
        } else {
          res = await createFactor(data)
        }
        
        if (res.code === 200) {
          this.$message.success(this.isEdit ? '更新成功' : '创建成功')
          this.dialogVisible = false
          this.loadFactors()
        }
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error(e.message || '操作失败')
        }
      } finally {
        this.submitLoading = false
      }
    },
    
    handleBatchAdd(scope) {
      this.$prompt('请输入批量因子JSON数组', '批量导入', {
        confirmButtonText: '导入',
        cancelButtonText: '取消',
        inputPlaceholder: '[{"factor_code": "test", "factor_name": "测试因子", "factor_scope": "stock", "source": "kline", "field_name": "close_price"}]'
      }).then(async ({ value }) => {
        try {
          const factors = JSON.parse(value)
          const res = await createFactor({ factors })
          if (res.code === 200) {
            this.$message.success(`成功创建 ${res.data.created?.length || 0} 个因子`)
            this.loadFactors()
          }
        } catch (e) {
          this.$message.error('JSON格式错误')
        }
      }).catch(() => {})
    },
    
    getSourceLabel(source) {
      return this.sourceMap[source] || source
    }
  }
}
</script>

<style scoped>
.factor-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.hint-text {
  color: #E6A23C;
  font-size: 12px;
  margin-top: 5px;
}

.offset-config {
  width: 100%;
}

.ma-config {
  width: 100%;
}

.new-high-config {
  width: 100%;
}

.ma-inputs {
  display: flex;
  align-items: center;
  gap: 5px;
}

.expr-editor {
  width: 100%;
}

.expr-toolbar {
  margin-bottom: 10px;
}

.expr-textarea {
  font-family: monospace;
}

.factor-hint {
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
}

.factor-buttons {
  margin-bottom: 10px;
  max-height: 80px;
  overflow-y: auto;
}

.factor-btn {
  margin: 3px;
  font-family: monospace;
  font-size: 11px;
}
</style>
