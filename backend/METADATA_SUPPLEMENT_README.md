# 元数据自动补充功能说明

## 📋 功能概述

本系统支持在数据加载和复盘时自动补充元数据，包括：
- **股票基本信息**：公司名称、上市日期、交易所、行业等
- **板块信息**：行业分类、概念板块、地区板块
- **股票-板块关联**：记录每只股票所属的板块

## ⚙️ 配置选项

### 默认配置

```python
METADATA_SUPPLEMENT_CONFIG = {
    # 是否在数据同步时自动补充元数据
    'auto_supplement_on_sync': True,

    # 是否在复盘时自动补充元数据
    'auto_supplement_on_review': True,

    # 是否更新已存在的股票信息（False=只新增，True=同时更新）
    'update_existing_stocks': False,

    # 是否补充板块信息
    'supplement_sectors': True,

    # 是否补充股票-板块关联
    'supplement_relations': True,

    # 是否补充股票基本信息
    'supplement_stock_basic': True,

    # 板块类型配置
    'sector_types': ['industry', 'area'],

    # 批量处理大小
    'batch_size': 100,

    # 请求间隔（秒）
    'request_interval': 0.5,
}
```

### API 接口

#### 获取当前配置

```http
GET /api/metadata/config
```

#### 更新配置

```http
PUT /api/metadata/config
Content-Type: application/json

{
    "auto_supplement_on_sync": true,
    "auto_supplement_on_review": true,
    "update_existing_stocks": true
}
```

## 🚀 自动化场景

### 1. 数据同步时自动补充

在执行 K 线数据同步任务时，系统会自动补充元数据：

```python
# services/data_sync_service.py
def sync_kline_data(self, db_session, task_id, ...):
    # ... 同步数据 ...

    # 补充元数据
    metadata_service.supplement_metadata(
        stock_codes=stock_codes,
        db_session=db_session,
        context='sync'
    )
```

### 2. 复盘时自动补充

在执行复盘任务时，系统会自动补充元数据：

```python
# services/review_service.py
def execute_baostock_task(self, task_id):
    # ... 获取数据 ...

    # 补充元数据
    metadata_service.supplement_metadata(
        stock_codes=stock_codes,
        db_session=db.session,
        context='review'
    )
```

### 3. Baostock 日线数据获取时补充

在获取指定日期的 A 股日线数据时，系统会自动补充元数据：

```python
# services/baostock_service.py
def fetch_and_save_daily_data(self, date, db_session):
    # ... 获取数据 ...

    # 补充元数据
    metadata_service.supplement_metadata(
        stock_codes=stock_codes,
        db_session=db_session,
        context='sync'
    )
```

## 📖 使用示例

### 1. 手动触发元数据补充

```python
from services.metadata_service import get_metadata_service

service = get_metadata_service()

# 补充所有板块信息
result = service.supplement_sectors()

# 补充指定股票的元数据
stock_codes = ['sh.600000', 'sz.000001']
result = service.supplement_metadata(stock_codes=stock_codes, context='manual')

# 补充单只股票的关联
service.sync_stock_with_sectors('sh.600000')
```

### 2. 查看元数据统计

```python
from services.metadata_service import get_metadata_service

service = get_metadata_service()
summary = service.get_metadata_summary()

print(f"股票数量: {summary['stock_basic_count']}")
print(f"板块数量: {summary['sector_count']}")
print(f"关联数量: {summary['stock_sector_relation_count']}")
```

### 3. 获取股票信息

```python
from services.metadata_service import get_metadata_service

service = get_metadata_service()

# 获取股票基本信息
stock = service.get_stock_basic('sh.600000')
print(f"股票名称: {stock.stock_name}")
print(f"所属行业: {stock.industry}")
print(f"所在地区: {stock.area}")

# 获取股票所属板块
sectors = service.get_stock_sectors('sh.600000')
for sector in sectors:
    print(f"板块: {sector['sector_name']}")
```

### 4. 配置控制示例

```python
from services.metadata_config import (
    get_metadata_config,
    set_metadata_config,
    is_auto_supplement_enabled
)

# 检查是否启用
if is_auto_supplement_enabled('sync'):
    print("数据同步时自动补充已启用")
else:
    print("数据同步时自动补充已禁用")

# 禁用数据同步时的自动补充
set_metadata_config('auto_supplement_on_sync', False)

# 启用增量更新
set_metadata_config('update_existing_stocks', True)
```

## 📊 返回结果格式

### 元数据补充结果

```python
{
    'stock_basic': {
        'added': 10,      # 新增数量
        'updated': 5,     # 更新数量
        'skipped': 3      # 跳过数量
    },
    'sectors': {
        'added': 50,      # 新增板块数
        'updated': 10     # 更新板块数
    },
    'stock_sector_relations': {
        'added': 100,     # 新增关联数
        'updated': 20,    # 更新关联数
        'skipped': 5     # 跳过数量
    }
}
```

### 元数据统计摘要

```python
{
    'stock_basic_count': 5000,      # 股票总数
    'sector_count': 200,            # 板块总数
    'sector_industry_count': 100,    # 行业板块数
    'sector_area_count': 50,         # 地区板块数
    'stock_sector_relation_count': 15000  # 关联总数
}
```

## ⚠️ 注意事项

1. **API 限流**：Baostock 免费版有请求频率限制，系统默认设置了 0.5 秒的请求间隔
2. **增量更新**：默认只新增不更新，如需更新已存在的股票信息，请设置 `update_existing_stocks=True`
3. **错误处理**：元数据补充失败不会影响主流程，但会记录错误日志
4. **数据源**：元数据主要来源于 Baostock 开放的免费数据接口

## 🔧 高级配置

### 自定义批量大小

```python
set_metadata_config('batch_size', 200)  # 增大批量处理大小
```

### 禁用特定类型补充

```python
# 只补充板块信息，不补充股票和关联
set_metadata_config('supplement_sectors', True)
set_metadata_config('supplement_stock_basic', False)
set_metadata_config('supplement_relations', False)
```

### 完全禁用自动补充

```python
# 禁用所有自动补充
set_metadata_config('auto_supplement_on_sync', False)
set_metadata_config('auto_supplement_on_review', False)
```

## 📝 版本历史

- **v1.0** (2024-01): 初始版本
- **v1.1** (2024-02): 添加配置开关和增量更新支持
- **v1.2** (2024-03): 统一元数据补充接口，添加 API 配置接口

