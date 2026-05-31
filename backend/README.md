# DaydayUp Python Backend

基于 Flask 框架的股票数据分析与复盘系统后端服务，使用 Baostock 获取股票数据。

## 技术栈

- **Web框架**: Flask 3.0
- **数据库**: MySQL + SQLAlchemy
- **股票数据**: Baostock
- **Excel处理**: pandas + openpyxl
- **CORS**: Flask-CORS

## 项目结构

```
backend/
├── app.py                 # 应用入口
├── config.py              # 配置文件
├── requirements.txt       # Python依赖
├── init_db.py            # 数据库初始化
├── run.sh / run.bat      # 启动脚本
├── .env.example          # 环境变量示例
│
├── extensions.py         # Flask扩展
├── models/               # 数据库模型
│   ├── __init__.py
│   ├── datasource.py     # 数据源模型
│   ├── datarecord.py     # 数据记录模型
│   ├── reviewtask.py     # 复盘任务模型
│   └── reviewresult.py   # 复盘结果模型
│
├── routes/               # API路由
│   ├── __init__.py
│   ├── datasource.py     # 数据源API
│   ├── review.py         # 复盘任务API
│   └── stock.py          # 股票数据API
│
├── services/            # 业务逻辑服务
│   ├── __init__.py
│   ├── datasource_service.py
│   ├── review_service.py
│   └── baostock_service.py
│
└── utils/               # 工具类
    ├── __init__.py
    └── excel_utils.py
```

## API接口

### 数据源管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/datasource/upload | 上传Excel文件 |
| GET | /api/datasource/list | 获取数据源列表 |
| GET | /api/datasource/{id} | 获取数据源详情 |
| GET | /api/datasource/{id}/preview | 获取数据预览 |
| DELETE | /api/datasource/{id} | 删除数据源 |

### 股票数据

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/stock/list | 获取股票列表 |
| GET | /api/stock/info/{code} | 获取股票基本信息 |
| GET | /api/stock/history | 获取股票历史数据 |
| POST | /api/stock/import | 导入股票数据 |
| GET | /api/stock/realtime | 获取实时行情 |

### 复盘任务

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/review/task | 创建复盘任务 |
| POST | /api/review/task/{id}/execute | 执行复盘任务 |
| GET | /api/review/task/list | 获取任务列表 |
| GET | /api/review/task/{id} | 获取任务详情 |
| GET | /api/review/task/{id}/results | 获取任务结果 |
| GET | /api/review/task/{id}/report | 获取分析报告 |
| DELETE | /api/review/task/{id} | 删除任务 |

## 定时任务（APScheduler）

> `day_of_week` 用 APScheduler 数字记法，**0=周一**（非 crontab 的周日）。

| 触发 | 任务 | 说明 |
|---|---|---|
| 周一~**六** 17:30 | 元数据增量补充 | 行业 + 概念（东财 BK 码作 `sector_code` 唯一键 + 关联层增量 diff）+ 个股补缺；概念时效板块每个交易日刷新；**周六**对行业+概念做全量 diff 补漏 |
| 周一~五 18:00 | 每日复盘 | 全市场 K 线（tushare market-daily 快速路径为主 + baostock 兜底）；成功后 HTTP 触发 TA-CN 全市场综合分析 |
| 每天 每 2 小时 :00 | 淘股吧手机端热帖聚合 | → `external_analysis`（source=tgb-mobile-hot）|
| 每天 每 2 小时 :05 | 淘股吧特别关注流 | → `external_analysis`（source=tgb-special-focus）|

元数据补充内部逻辑（唯一键、diff、断点续传、时效关键词、周六全量）及 **TA-CN 侧全部定时任务、数据流与排障**，
详见 TradingAgents 仓库 `docs/cron-and-data-flow.md`（两项目定时任务的权威文档）。

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置数据库

复制环境变量文件并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 MySQL 连接：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=daydayup
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 启动服务

```bash
# Linux/Mac
./run.sh

# Windows
run.bat

# 或者直接运行
python app.py
```

服务将在 `http://localhost:5000` 启动。

## 使用Baostock获取股票数据

### 获取股票历史数据

```python
import requests

# 获取股票历史K线数据
response = requests.get('http://localhost:5000/api/stock/history', params={
    'symbol': '600000',      # 股票代码
    'startDate': '2024-01-01',
    'endDate': '2024-12-31',
    'frequency': 'daily',    # daily/weekly/monthly
    'adjustType': 'qfq'      # qfq:前复权, hfq:后复权
})

data = response.json()
print(data['data'])
```

### 导入股票数据作为数据源

```python
import requests

response = requests.post('http://localhost:5000/api/stock/import', json={
    'name': '浦发银行股票数据',
    'stockCode': '600000',
    'description': '浦发银行2024年日K线数据',
    'startDate': '2024-01-01',
    'endDate': '2024-12-31'
})

data = response.json()
print(data['data'])  # 返回创建的数据源信息
```

## 创建复盘任务示例

```python
import requests

# 创建复盘任务
response = requests.post('http://localhost:5000/api/review/task', json={
    'taskName': '销售数据分析',
    'dataSourceId': 1,
    'reviewType': 'custom',
    'dimensions': ['产品类别', '销售区域'],
    'rules': [
        {
            'field': '销售额',
            'aggregation': 'sum',
            'ruleName': '总销售额',
            'threshold': 1000000,
            'level': 'warning',
            'suggestion': '销售额异常'
        }
    ]
})

task = response.json()
task_id = task['data']['id']

# 执行复盘任务
requests.post(f'http://localhost:5000/api/review/task/{task_id}/execute')

# 获取分析报告
response = requests.get(f'http://localhost:5000/api/review/task/{task_id}/report')
report = response.json()
print(report['data'])
```

## 响应格式

所有API响应统一使用以下格式：

```json
{
    "code": 200,
    "message": "操作成功",
    "data": { ... }
}
```

错误响应：

```json
{
    "code": 500,
    "message": "错误信息"
}
```

## License

MIT

