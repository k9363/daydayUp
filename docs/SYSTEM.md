# daydayUp 复盘系统：统一系统文档

> 后端 Flask + MySQL + APScheduler 的 A 股每日复盘系统。本文是架构与**关键设计决策/历史坑**的权威说明，按子系统组织，函数名/文件均可溯源。
> 配套：全市场综合分析报告由 TA-CN（TradingAgents）生成，daydayUp 调用并嵌入复盘邮件，见七。TA-CN 侧文档 `TradingAgents/docs/research/topbottom_dashboard_system.md`。

---

## 一、系统定位与技术栈

- **定位**：每个交易日盘后自动复盘——拉全市场日K → 选股 → 灌分时 → 算因子 → 选 Top 个股/板块 → 触发 TA-CN 全市场分析 → 发复盘邮件。
- **技术栈**：Flask 3 + SQLAlchemy + MySQL；APScheduler 定时；数据源 Tushare / akshare / baostock 分层（见二）。
- **部署**：Docker，后端容器 `daydayup-backend`(:5000)、前端 `daydayup-frontend`(:20080)。源码 bind mount，改代码 rsync+restart 秒级；改 env 须 compose recreate（见十一）。
- **服务器连接纪律**：一律 `ssh ta-prod`（用户非 jxh）+ Keychain，细节见项目 memory。

---

## 二、数据源分层（核心约定）

| 数据 | 主源 | 兜底 | 关键函数 |
|---|---|---|---|
| 当日日K（全市场，EOD） | **Tushare**（经 TA-CN `/api/sync/market-daily` 一次拉齐股票+ETF+指数，<10s） | 无 | `data_sync_service.sync_market_daily_via_tushare()` |
| 个股 5 分钟分时 | **akshare/sina**（`stock_zh_a_minute period=5`，5 并发） | baostock（串行 + 30s 超时，北交所跳过） | `data_sync_service.ingest_intraday_to_tacn()` |
| 历史K线回填 | Tushare 快速路径 | baostock | `data_sync_service.sync_kline_data()` / `scripts/backfill_history.py` |
| 交易日历 / 股票列表 | baostock | — | `baostock_service` |

**为什么这样分**：日K 若走 baostock 要串行拉 7000+ 只（20+min 且 socket 易卡死）；Tushare 一次 batch 齐全。分时 akshare 并发（~2s/只）远快于 baostock 串行（~8s/只 + 卡死风险）。baostock 退居兜底与低频元数据。详见十二「历史坑」。

日K 落库：就绪校验（返回股票数 ≥ 4000 才算齐，否则重试，防半截数据）+ 完整性校验（剔 OHLC/涨跌幅空行）+ 分块 upsert（唯一索引去重），见 `save_kline_data()`。

---

## 三、复盘主流程

**触发**：`scheduler_service` CronTrigger `day_of_week=0-4, hour=18, minute=0`（周一~五 18:00）→ `execute_daily_review()`。
**交易日门控**：`_execute_review_logic()` 先用 baostock `query_trade_dates()` 校验 `is_trading_day`，非交易日直接跳过（多层重试）。定时任务 `task_name` 末尾打 `[定时]` 标记，区分自动发邮件 vs 手动重跑。

**`execute_baostock_task()` 六步**（`review_service.py`，名字含 baostock 是历史遗留，现日K已全 Tushare）：

1. **日K获取**：`_fetch_daily_data()` → `sync_market_daily_via_tushare()` 全 Tushare 拉齐当日，就绪+完整性校验后 upsert。
2. **股票筛选**：解析 `stock_filter`（默认 `type=top_by_amount, value=100`）→ `_filter_top_stocks()` 按成交额取前 N。
3. **步骤 2.5 — 分时数据填充**：`_ingest_intraday_data()` → `ingest_intraday_to_tacn()`，akshare 并发主拉 + baostock 兜底，POST 给 TA-CN `/api/sync/intraday-quotes`。**失败不阻断复盘**。（此步与因子计算**解耦**，是独立的"步骤 2.5"。）
4. **因子计算**：`factor_calculator.calculate_stock_factors(pool, trade_date, session)` → DataFrame(total_score, factor1-6 …)。
5. **Top 个股 + 板块**：`nlargest(10, total_score)`；`calculate_sector_factors()` 算板块因子。
6. **保存 + 触发 TA-CN**：`_save_review_results()` 后调 `trigger_tacn_batch_analysis(trade_date)`（非阻塞 POST，失败仅 warn，不影响复盘成功）。

---

## 四、baostock 稳定性处理（锁 / 超时 / 重连 / 熔断）

**根因**：baostock 是模块级全局**单 socket 单例**、非线程安全、socket 无读超时、login 无超时。并发多线程在同一 socket 上 login/query → 协议串话；socket 卡死时 login/query **无限阻塞** → 整个同步死锁。

**对策**（`baostock_lock.py` + `data_sync_service.py`）：
- **进程级 RLock** `BAOSTOCK_LOCK`：所有 baostock 操作串行化。
- **登录超时** `safe_bs_login()`：ThreadPoolExecutor 包 login，15s 超时 + 指数退避重试。
- **查询超时** `_call_baostock_with_timeout()`：30s 包整段（query + `rs.next()` 消费）；超时标记会话失效（`lg=None`）。
- **反应式重连**：查询返回未登录/过期错误码（10002007/01/02/03）才重连重试——**替代每次主动探活**（探活在坏 socket 上也会卡死）。
- **熔断** `MAX_CONSECUTIVE_TIMEOUTS=5`：连续失败达阈值抛 `BaostockServiceUnavailable`，任务中止并保留断点，不逐只磨。

---

## 五、因子体系

因子定义与算式存 **DB**（`factor_define` / `score_expression` 表），非硬编码——可在不改代码下调权重/表达式。`review_service._build_factor_tree()` 负责把它们组织成依赖树供前端展示。分三层：

1. **K线原始字段**：close/volume/turnover/pct_change/ma5/ma10/ma20 + 昨值（ma20_y1/volume_y1…）。
2. **中间计算因子**：排名（成交额/换手排名）、历史平均（avg_amount_3d/5d/10d/20d、分段均量 4_20d/11_30d/4_120d）、中间表达式（price_ma 偏离、deviation_10d/30d 等）。
3. **最终综合得分**：`factor1`~`factor6`（成交额权重 / 短线趋势 / 昨日同比 / 爆量 / 极限量 / 多头趋势——具体算式见 DB 配置）加权汇总成 `total_score`，用于个股排序选 Top10。

- **板块得分**：`factor_service.calculate_sector_factors()` 对 Top 成交额个股按板块聚合 → 板块排序。
- **分时分离度因子**：`factor_service._fetch_intraday_deviation()` —— **只读** TA-CN 算好的结果（个股当日分时 vs 上证0.7+所属宽基0.3 的分离度，score∈[-20,20]，标主动领涨/抗跌/被动跟跌），数据与计算都在 TA-CN，daydayUp 只取；失败返回空、缺省因子为 0。

---

## 六、定时任务全集（`scheduler_service`）

| 任务 | 函数 | Cron | 门控 |
|---|---|---|---|
| 主复盘 | `execute_daily_review` | 周一~五 18:00 | 交易日（baostock 校验） |
| 元数据补充（行业+概念板块、新股/北交所） | `execute_akshare_metadata_supplement` | 周一~六 17:30 | 周六(`weekday==5`)做全量 diff 补漏 |
| 淘股吧热帖 | `execute_tgb_hot_fetch` | 每 2 小时 :00 | — |
| 淘股吧特别关注 | `execute_tgb_spefocus_fetch` | 每 2 小时 :05 | 错开热帖 5min 避风控 |
| 复盘邮件兜底 | `execute_review_email_backstop` | 周一~五 18:45 | `[定时]`任务 + 已完成 + `email_sent=False` |

> A 股定时任务一律「钟面对齐 cron + 精确时段 + 交易日历」三层门控，不裸用 weekday+interval（节假日会写错数据）。

---

## 七、与 TA-CN（TradingAgents）的联动

daydayUp 把"重活"外包给 TA-CN，自己专注因子计算与复盘编排：

- **日K**：TA-CN `/api/sync/market-daily` 一次 Tushare 拉齐（二）。
- **分时**：daydayUp 拉好 5min 分时 POST 给 TA-CN `/api/sync/intraday-quotes`（sink 端点，存 TA-CN mongo）。
- **分时分离度**：TA-CN 计算，daydayUp 只读取（五）。
- **全市场综合分析报告**：复盘末尾 `trigger_tacn_batch_analysis()` POST `/api/analysis/index/batch/internal/trigger`（带 `date`，分析同一交易日）。TA-CN 生成 13 章节报告，含顶底仪表盘/温度计/板块/主线 + 报告增量延续（见 TA-CN 文档）。
- **等待就绪**：`_wait_for_market_report()` 轮询 `external_analysis` 表（当日 batch 记录、报告 > 2000 字），超时 720s（每 20s 一次，期间 `session.rollback()` 切快照才能看到新插入），超时也照常发邮件。

---

## 八、复盘邮件（事件驱动 + 兜底）

`email_service.send_daily_review_email(task_id)`。内容：复盘摘要 + Top10 个股因子表 + Top 板块 + TA-CN 全市场分析（若到货）+ 复盘页链接。

- **主路径（事件驱动）**：TA-CN 全市场报告 push 到货 → `routes/external` 的 `_maybe_send_review_email_on_batch()` 即时触发发信。
- **兜底路径**：18:45 cron `execute_review_email_backstop()`，对当天 `[定时]` 已完成但 `email_sent=False` 的任务补发。
- **防重**：`ReviewTask.email_sent` 标记，防主+兜底双发。仅 `[定时]` 任务自动发；手动重跑/Excel 任务走报告页「发送邮件」按钮。
- **SMTP 配置**：在 `backend/.env.server`（非顶层 .env），改后必须 compose recreate（restart 不重载 env）；本地与服务器都要有，否则 rsync 丢。

---

## 九、淘股吧（tgb）采集

- `tgb_hot_service`（手机端热帖，`m.tgb.cn/getMZh?pageNo=N`，pageNo 从 2 起）、`tgb_spefocus_service`（特别关注流），各每 2 小时拉一次、错开 5min。
- `tgb_common`：`load_cookie()`（env `TGB_COOKIE` > `backend/.tgb_cookie`）、手机/桌面 UA、`http_get_json()`（gzip 兜底 + cookie 失效检测：302 跳 sso 或登录页 HTML → 抛 `CookieExpiredError`）。
- 结果写 `external_analysis`（source 区分 mobile-hot / special-focus），前端卡片消费。
- cookie 失效刷新流程见 memory（chrome-devtools 全自动；改完 cookie 须 `docker restart daydayup-backend`，因 bind mount 换 inode）。

---

## 十、数据模型与表

| 模型(文件) | 表 | 要点 |
|---|---|---|
| `kline.StockDailyKLine` | `stock_daily_kline` | OHLC + pre_close + volume/turnover + change_percent/change；唯一索引 (code, trade_date)。**含退市股、回填至 2007**（见十二） |
| `kline.StockWeekly/Monthly/MinuteKLine` | 周/月/分钟K | — |
| `kline.StockSector` / `StockSectorRelation` | 板块 / 成分关联 | sector_type ∈ industry/concept/area |
| `reviewtask.ReviewTask` | `review_task` | status(pending/running/completed/failed)、`email_sent`、stock_filter、trade_date |
| `reviewresult.ReviewResult` | `review_result` | 复盘结果明细 |
| `factor.FactorDefine` | `factor_define` | 因子定义（code/name/scope/算法/字段/表达式/is_active） |
| `expression.ScoreExpression` | `score_expression` | 得分表达式配置（scope/factors/expression/is_default） |
| `stockbasic.StockBasic` | `stock_basic` | 元数据（code/name/exchange/market/type/status） |

> `stock_daily_kline` 已删冗余索引 `idx_daily_stock_date`（与唯一索引重复，省空间+加快写入）。`history_data` 必须存全 open/low/涨跌幅/is_up，曾因漏存导致因子恒为 0（已修）。

---

## 十一、部署

- compose：源码目录 `daydayup_docker`（下划线），compose **project name 是 `daydayup-docker`（横线）**，所有命令须 `-p daydayup-docker`。
- 后端 `daydayup-backend`(:5000)，前端 `daydayup-frontend`(:20080)；后端源码 bind mount。
- **改后端代码**：rsync + `docker restart daydayup-backend` 秒级（bind mount 换 inode 必须 restart，否则看 ghost 旧文件）。
- **改 env**（`.env.server`）：必须 `compose up`/recreate，restart 不重载 env。
- **改前端/依赖**：才需 rebuild 镜像。
- 改完代码部署的同时 commit（与 TA-CN 一致）；commit 前跑 secrets 复核；push 用户自己做。

---

## 十二、关键设计决策与历史坑（防重复踩坑）

1. **日K 全 Tushare（2026-06-12）**：从 baostock 串行 7000+ 只（曾因 index→写超时回滚导致兜底 7434 只跑 7-11h）改为 TA-CN 一次 Tushare batch（<10s）。同时删 `stock_daily_kline` 冗余索引（15.5M 行表上 upsert 因双索引超时 "Lost connection"）。
2. **分时改 akshare/sina（2026-06）**：baostock 不启用、仅兜底，避免 akshare 限流时还能续上；baostock 全局单 socket 在停牌/问题股查询上会结构性卡死（不是"停牌股"本身，是任何不响应的查询）。
3. **复盘 18:00 不变**：日K EOD 傍晚即就绪，分时不再等 baostock 20:00 才入库——分时灌库失败也不阻断复盘。
4. **数据填充与因子计算解耦**：分时灌库独立为「步骤 2.5」，灌库失败不影响因子计算。
5. **跨牛熊回测口径**：个股日线原仅约 1 年；2026-06 起用 `backfill_history.py` 回填 2007 至今（含退市股，修幸存者偏差），板块=成分股日线等权合成。
6. **回填(写)与回测(读)别同时跑同表**；薄样本回测别声称精度（信度纪律）。

> 进 daydayUp 容器跑分析：`docker exec -i -w /app daydayup-backend python -`，脚本内 `from app import create_app; create_app("development")` 起 context。
