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
          <el-table-column prop="field_name" label="字段" width="120" />
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
          <el-select v-model="form.calculation_method" placeholder="选择计算方法">
            <el-option label="直接取字段值" value="kline_field" />
            <el-option label="排名得分" value="rank" />
            <el-option label="表达式计算" value="expression" />
            <el-option label="近3日平均成交额" value="avg_3d" />
            <el-option label="近5日平均成交额" value="avg_5d" />
            <el-option label="近10日平均成交额" value="avg_10d" />
            <el-option label="近20日平均成交额" value="avg_20d" />
            <el-option label="4-20日平均成交额(爆量用)" value="avg_4_20d" />
            <el-option label="11-30日平均成交额(极限量用)" value="avg_11_30d" />
          </el-select>
        </el-form-item>
        
        <!-- 表达式配置 -->
        <el-form-item v-if="form.source === 'kline' && form.calculation_method === 'expression'" label="表达式" prop="expression">
          <el-input v-model="form.expression" type="textarea" :rows="3" placeholder="AVG(turnover, 10) - 过去10天平均&#10;IF(amount_rank <= 50, 10, 0) - 条件表达式&#10;close_price - ma5 - 数学运算" />
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            支持函数: AVG(field, days), AVG(field, start, end), IF(cond, true, false), ABS, MAX, MIN, SUM
          </div>
        </el-form-item>
        
        <!-- K线字段选择 -->
        <el-form-item v-if="form.source === 'kline'" label="字段选择" prop="field_name">
          <el-select v-model="form.field_name" placeholder="选择字段" filterable>
            <el-option v-for="f in klineFields" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        
        <!-- 因子选择 -->
        <el-form-item v-if="['stock_factor', 'sector_factor', 'market_factor'].includes(form.source)" label="选择因子" prop="field_name">
          <el-select v-model="form.field_name" placeholder="选择因子" filterable>
            <el-option-group v-for="group in factorOptions" :key="group.label" :label="group.label">
              <el-option v-for="f in group.options" :key="f.factor_code" :label="`${f.factor_name} (${f.factor_code})`" :value="f.factor_code" />
            </el-option-group>
          </el-select>
        </el-form-item>
        
        <!-- 表达式 -->
        <el-form-item v-if="form.source === 'calculated'" label="表达式" prop="expression">
          <el-input v-model="form.expression" type="textarea" :rows="3" placeholder="如: volume / prev_volume" />
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
        aggregation: '',
        index_code: '',
        expression: '',
        description: ''
      },
      rules: {
        factor_code: [{ required: true, message: '请输入因子代码', trigger: 'blur' }],
        factor_name: [{ required: true, message: '请输入因子名称', trigger: 'blur' }],
        factor_scope: [{ required: true, message: '请选择因子作用域', trigger: 'change' }],
        source: [{ required: true, message: '请选择数据来源', trigger: 'change' }]
      },
      // 下拉选项
      factorOptions: [],
      // K线字段
      klineFields: ['close_price', 'volume', 'turnover', 'pct_change', 'open_price', 'high_price', 'low_price', 'change'],
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
        field_name: '',
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
      this.form.expression = ''
      this.form.calculation_method = ''
      this.form.filter_condition = ''
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
</style>
