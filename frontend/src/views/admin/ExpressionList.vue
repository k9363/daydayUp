<template>
  <div class="expression-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>表达式配置</h2>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="股票表达式" name="stock">
        <div class="toolbar">
          <el-button type="primary" @click="handleAdd('stock')">新增表达式</el-button>
        </div>
        
        <el-table :data="stockExpressions" border v-loading="stockLoading">
          <el-table-column prop="expression_name" label="表达式名称" width="180" />
          <el-table-column prop="scope" label="作用域" width="100">
            <template #default="{ row }">
              <el-tag type="success">{{ getScopeLabel(row.scope) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="factors" label="使用因子" width="300">
            <template #default="{ row }">
              <el-tag v-for="f in row.factors" :key="f" size="small" class="factor-tag">{{ getFactorName(f) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="expression" label="表达式">
            <template #default="{ row }">
              <code class="expr-code">{{ row.expression }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="is_default" label="默认" width="60">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="handleTest(row)">测试</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="板块表达式" name="sector">
        <div class="toolbar">
          <el-button type="primary" @click="handleAdd('sector')">新增表达式</el-button>
        </div>
        
        <el-table :data="sectorExpressions" border v-loading="sectorLoading">
          <el-table-column prop="expression_name" label="表达式名称" width="180" />
          <el-table-column prop="scope" label="作用域" width="100">
            <template #default="{ row }">
              <el-tag type="warning">{{ getScopeLabel(row.scope) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="factors" label="使用因子" width="300">
            <template #default="{ row }">
              <el-tag v-for="f in row.factors" :key="f" size="small" class="factor-tag">{{ getFactorName(f) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="expression" label="表达式">
            <template #default="{ row }">
              <code class="expr-code">{{ row.expression }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="top_n" label="取前N" width="80" />
          <el-table-column prop="is_default" label="默认" width="60">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="handleTest(row)">测试</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="大盘表达式" name="market">
        <div class="toolbar">
          <el-button type="primary" @click="handleAdd('market')">新增表达式</el-button>
        </div>
        
        <el-table :data="marketExpressions" border v-loading="marketLoading">
          <el-table-column prop="expression_name" label="表达式名称" width="180" />
          <el-table-column prop="scope" label="作用域" width="100">
            <template #default="{ row }">
              <el-tag type="info">{{ getScopeLabel(row.scope) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="factors" label="使用因子" width="300">
            <template #default="{ row }">
              <el-tag v-for="f in row.factors" :key="f" size="small" class="factor-tag">{{ getFactorName(f) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="expression" label="表达式">
            <template #default="{ row }">
              <code class="expr-code">{{ row.expression }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="is_default" label="默认" width="60">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="handleTest(row)">测试</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 表达式编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑表达式' : '新增表达式'"
      width="800px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="表达式名称" prop="expression_name">
          <el-input v-model="form.expression_name" placeholder="如: 板块综合得分" />
        </el-form-item>
        
        <el-form-item label="作用域" prop="scope">
          <el-radio-group v-model="form.scope">
            <el-radio label="stock">股票</el-radio>
            <el-radio label="sector">板块</el-radio>
            <el-radio label="market">大盘</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item v-if="form.scope === 'sector'" label="取前N">
          <el-input-number v-model="form.top_n" :min="1" :max="100" />
          <span class="hint">只保留得分最高的前N个板块</span>
        </el-form-item>
        
        <!-- 使用因子 -->
        <el-form-item label="使用因子">
          <div class="factor-hint">提示：点击下方因子按钮可直接插入表达式中</div>
          <el-tabs v-model="factorTab">
            <el-tab-pane label="股票因子" name="stock">
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
            </el-tab-pane>
            <el-tab-pane label="板块因子" name="sector">
              <el-button 
                v-for="f in sectorFactors" 
                :key="f.factor_code"
                size="small" 
                type="warning"
                class="factor-btn"
                @click="insertFactor(f.factor_code)"
                :title="f.description"
              >
                {{ f.factor_code }}
              </el-button>
            </el-tab-pane>
            <el-tab-pane label="大盘因子" name="market">
              <el-button 
                v-for="f in marketFactors" 
                :key="f.factor_code"
                size="small" 
                type="success"
                class="factor-btn"
                @click="insertFactor(f.factor_code)"
                :title="f.description"
              >
                {{ f.factor_code }}
              </el-button>
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        
        <!-- 表达式编辑器 -->
        <el-form-item label="表达式" prop="expression">
          <div class="expr-editor">
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
              v-model="form.expression"
              type="textarea"
              :rows="4"
              class="expr-textarea"
              placeholder="使用因子代码编写表达式，如: sum_stock_score + stock_count * 5"
            />
            
            <!-- 语法检查 -->
            <div class="expr-validate">
              <el-alert v-if="exprError" type="error" :title="exprError" show-icon />
              <el-alert v-else-if="form.expression" type="success" title="表达式语法正确" show-icon />
            </div>
          </div>
        </el-form-item>
        
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
          <span class="hint">设为默认后，复盘任务将使用此表达式计算得分</span>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleValidate">验证表达式</el-button>
        <el-button type="success" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 测试表达式弹窗 -->
    <el-dialog
      v-model="testDialogVisible"
      title="测试表达式"
      width="800px"
    >
      <div class="test-panel">
        <!-- 左侧：测试数据 -->
        <div class="test-data">
          <h4>测试数据</h4>
          <el-input
            v-model="testDataJson"
            type="textarea"
            :rows="8"
            placeholder='{"stock_count": 50, "sum_stock_score": 1200, "avg_change_pct": 2.5}'
          />
          <el-button type="primary" @click="handleRunTest" style="margin-top: 10px">执行测试</el-button>
        </div>
        
        <!-- 右侧：测试结果 -->
        <div class="test-result">
          <h4>计算结果</h4>
          <div v-if="testResult" class="result-content">
            <div class="result-value">得分: <strong>{{ testResult.result }}</strong></div>
          </div>
          <div v-else class="result-empty">点击"执行测试"查看结果</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getExpressionList, createExpression, updateExpression, deleteExpression, testExpression, calculateExpression, getFactorOptions } from '@/api'

export default {
  name: 'ExpressionList',
  data() {
    return {
      activeTab: 'stock',
      factorTab: 'stock',
      // 股票表达式
      stockExpressions: [],
      stockLoading: false,
      // 板块表达式
      sectorExpressions: [],
      sectorLoading: false,
      // 大盘表达式
      marketExpressions: [],
      marketLoading: false,
      // 因子选项
      stockFactors: [],
      sectorFactors: [],
      marketFactors: [],
      // 弹窗
      dialogVisible: false,
      isEdit: false,
      submitLoading: false,
      form: {
        id: null,
        expression_name: '',
        scope: 'stock',
        factors: [],
        expression: '',
        top_n: 30,
        is_default: false,
        description: ''
      },
      rules: {
        expression_name: [{ required: true, message: '请输入表达式名称', trigger: 'blur' }],
        scope: [{ required: true, message: '请选择作用域', trigger: 'change' }],
        expression: [{ required: true, message: '请输入表达式', trigger: 'blur' }]
      },
      // 测试弹窗
      testDialogVisible: false,
      testDataJson: '',
      testResult: null,
      exprError: '',
      testExpressionId: null
    }
  },
  mounted() {
    this.loadExpressions()
    this.loadFactorOptions()
  },
  watch: {
    'form.scope'(newVal) {
      this.factorTab = newVal
    }
  },
  methods: {
    async loadExpressions() {
      const params = { active_only: 'false' }
      
      // 加载股票表达式
      this.stockLoading = true
      try {
        const res = await getExpressionList({ ...params, scope: 'stock' })
        if (res.code === 200) {
          this.stockExpressions = res.data
        }
      } finally {
        this.stockLoading = false
      }
      
      // 加载板块表达式
      this.sectorLoading = true
      try {
        const res = await getExpressionList({ ...params, scope: 'sector' })
        if (res.code === 200) {
          this.sectorExpressions = res.data
        }
      } finally {
        this.sectorLoading = false
      }
      
      // 加载大盘表达式
      this.marketLoading = true
      try {
        const res = await getExpressionList({ ...params, scope: 'market' })
        if (res.code === 200) {
          this.marketExpressions = res.data
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
          this.stockFactors = data.stock || []
          this.sectorFactors = data.sector || []
          this.marketFactors = data.market || []
        }
      } catch (e) {
        console.error('加载因子选项失败', e)
      }
    },
    
    handleTabChange(tab) {
      this.factorTab = tab
    },
    
    handleAdd(scope) {
      this.isEdit = false
      this.form = {
        id: null,
        expression_name: '',
        scope: scope,
        factors: [],
        expression: '',
        top_n: 30,
        is_default: false,
        description: ''
      }
      this.exprError = ''
      this.dialogVisible = true
    },
    
    handleEdit(row) {
      this.isEdit = true
      this.form = { 
        ...row,
        factors: row.factors || []
      }
      this.exprError = ''
      this.dialogVisible = true
    },
    
    async handleDelete(row) {
      try {
        await this.$confirm('确定要删除该表达式吗？', '提示', { type: 'warning' })
        const res = await deleteExpression(row.id)
        if (res.code === 200) {
          this.$message.success('删除成功')
          this.loadExpressions()
        }
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error('删除失败')
        }
      }
    },
    
    handleTest(row) {
      this.testExpressionId = row.id
      this.testDataJson = this.generateTestData(row.factors)
      this.testResult = null
      this.testDialogVisible = true
    },
    
    generateTestData(factors) {
      const data = {}
      if (factors) {
        factors.forEach(f => {
          data[f] = Math.random() * 100
        })
      }
      return JSON.stringify(data, null, 2)
    },
    
    async handleRunTest() {
      try {
        const factors = JSON.parse(this.testDataJson)
        const res = await calculateExpression({
          expression: this.getCurrentExpression(),
          factors
        })
        if (res.code === 200) {
          this.testResult = res.data
        } else {
          this.$message.error(res.message)
        }
      } catch (e) {
        this.$message.error('JSON格式错误')
      }
    },
    
    getCurrentExpression() {
      return this.form.expression
    },
    
    insertOperator(op) {
      this.form.expression += op
    },
    
    insertFactor(factorCode) {
      this.form.expression += factorCode
    },
    
    insertFunction(func) {
      if (func === 'ABS') {
        this.form.expression += 'ABS()'
      } else if (func === 'SQRT') {
        this.form.expression += 'SQRT()'
      } else if (func === 'MAX') {
        this.form.expression += 'MAX(,)'
      } else if (func === 'MIN') {
        this.form.expression += 'MIN(,)'
      } else if (func === 'AVG') {
        this.form.expression += 'AVG(,)'
      }
    },
    
    async handleValidate() {
      if (!this.form.expression) {
        this.exprError = '请输入表达式'
        return
      }
      
      try {
        const expr = this.form.expression
        const factorPattern = /\b([a-zA-Z_][a-zA-Z0-9_]*)\b/g
        const factors = {}
        const excludeFuncs = ['ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG', 'sqrt', 'abs', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log']
        let match
        
        while ((match = factorPattern.exec(expr)) !== null) {
          const factorCode = match[1]
          if (!excludeFuncs.includes(factorCode) && !factors[factorCode]) {
            factors[factorCode] = 0
          }
        }
        
        const res = await testExpression({
          expression: this.form.expression,
          factors
        })
        
        if (res.code === 200 && res.data.valid) {
          this.exprError = ''
          this.$message.success('表达式语法正确')
        } else {
          this.exprError = res.data?.error || '表达式语法错误'
        }
      } catch (e) {
        this.exprError = e.message || '验证失败'
      }
    },
    
    async handleSubmit() {
      try {
        await this.$refs.formRef.validate()
        this.submitLoading = true
        
        // 自动从表达式中提取因子代码
        const expr = this.form.expression
        const factorPattern = /\b([a-zA-Z_][a-zA-Z0-9_]*)\b/g
        const factors = []
        const excludeFuncs = ['ABS', 'SQRT', 'MAX', 'MIN', 'AVG', 'SUM', 'ROUND', 'POW', 'IF', 'LOG', 'sqrt', 'abs', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log']
        let match
        while ((match = factorPattern.exec(expr)) !== null) {
          const factorCode = match[1]
          if (!excludeFuncs.includes(factorCode) && !factors.includes(factorCode)) {
            factors.push(factorCode)
          }
        }
        
        const data = { 
          ...this.form,
          factors
        }
        
        let res
        if (this.isEdit) {
          res = await updateExpression(this.form.id, data)
        } else {
          res = await createExpression(data)
        }
        
        if (res.code === 200) {
          this.$message.success(this.isEdit ? '更新成功' : '创建成功')
          this.dialogVisible = false
          this.loadExpressions()
        }
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error(e.message || '操作失败')
        }
      } finally {
        this.submitLoading = false
      }
    },
    
    getScopeLabel(scope) {
      const map = {
        'stock': '股票',
        'sector': '板块',
        'market': '大盘'
      }
      return map[scope] || scope
    },
    
    getFactorName(factorCode) {
      const allFactors = [...this.stockFactors, ...this.sectorFactors, ...this.marketFactors]
      const factor = allFactors.find(f => f.factor_code === factorCode)
      return factor ? factor.factor_name : factorCode
    }
  }
}
</script>

<style scoped>
.expression-page {
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

.factor-tag {
  margin-right: 5px;
}

.factor-hint {
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
}

.factor-btn {
  margin: 3px;
  font-family: monospace;
}

.expr-code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.hint {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
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

.expr-validate {
  margin-top: 10px;
}

.test-panel {
  display: flex;
  gap: 20px;
}

.test-data, .test-result {
  flex: 1;
}

.test-data h4, .test-result h4 {
  margin: 0 0 10px 0;
}

.result-value {
  font-size: 16px;
}

.result-value strong {
  color: #67c23a;
  font-size: 24px;
}
</style>
