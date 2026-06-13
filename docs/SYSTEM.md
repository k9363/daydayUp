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

---

## 十三、因子有效性回测框架与结论（2026-06-13）

把"选股因子到底有没有预测力 / 能不能挖出可交易的正向因子"系统性回测了一轮。脚本都在 `backend/scripts/`，可复用。

### 13.1 四个回测脚本（用途 + 跑法）

| 脚本 | 干什么 | 跑法（容器内） |
|---|---|---|
| `stock_factor_efficacy_backtest.py` | 选股 total_score 及分项的**横截面有效性**：Rank IC / Top10超额 / 五分位 / 年代分段 + 新高分组 + 取反 + T+1。支持**分片并行**(`worker` 各跑 `sampled[i::N]`→pkl，`agg` 合并) | `python ... 10 100 <i> <N>` 起 N 片，再 `python ... agg <N>` 聚合 |
| `factor_mining_ic_scan.py` | **候选因子批量 IC 扫描**（rev5/10/20、vol20、流动性、放量、乖离…），全样本 vs 近一年。纯K线向量化，快 | `python ... <interval> <pool>`；`SFE_START` env 不适用，用 RECENT 参数标近一年 |
| `factor_long_strategy_backtest.py` | **因子多头**(前TOPQ等权、REBAL换仓) + 多空(纸面) + **大盘顶底择时**(`M5_MODE=trend/avoidtop`)，全样本+近一年 | `python ... <rebal> <topq> <pool> <cost>`，env `M5_MODE`/`M5_TREND` |
| `stock_pool_m5_strategy_backtest.py` | **事件驱动策略**：高分池滚动watchlist + 回调M5买/跌破M5卖 + 限仓/止损/T+1。两阶段(`pool`分片算每日Top10→pkl，`sim`秒级重跑) | `python ... pool <start> <end> <i> <N>` 再 `python ... sim <start> <end> <N> [band] [cost]` |

通用跑法：`docker exec -d -w /app -e PYTHONPATH=/app daydayup-backend sh -c "python /tmp/x.py ... > /tmp/x.log 2>&1"`（`-d` 分离，PYTHONPATH 必须=/app，stdin 不能管道脚本否则跟 baostock 抢 fd）。

### 13.2 回测踩过的坑（写脚本前必看，省时间）
- **慢查询**：`trade_date IN (一串日期)` 让优化器选错索引(3s/次)；改 `trade_date BETWEEN a AND b`(走 (stock_code,trade_date) 唯一索引,0.1s)。
- **越跑越慢**：循环里 `bts` 长事务不刷新 → InnoDB 读视图老化、undo 累积 → 每轮加 `bts.rollback()`。
- **60s 读超时**：app 默认连接 read_timeout 60s，全表聚合(无 WHERE 的 COUNT/MIN/MAX)会超时；回测自建 `create_engine(..., connect_args={'read_timeout':1800})`。
- **历史无分时**：`calculate_stock_factors` 每日调 TA-CN `/sync/intraday-deviation`,历史日 90s 超时；回测里 monkeypatch `factor_calculator._fetch_intraday_deviation = lambda *a,**k: {}`(它本不在 total_score 表达式里)。
- **容器无 scipy**：pandas `corr(method='spearman')` 会炸；用"排名后 Pearson"代替。
- **容器无 pgrep**：判断进程用 `/proc/*/cmdline`；杀残留用 `kill -9`(多个并发进程会抢 DB 拖慢，跑前先清)。
- 池口径 = 当日 `stock_basic.stock_type='stock'` 的成交额前 100（与生产 `_filter_top_stocks` 一致）。

### 13.3 结论（详见 memory `project_daydayup_stock_factors_anti_predictive`）
1. **选股 total_score 是反向信号**（短期反转）：池内 Rank IC −0.04~−0.075（t 到 −8.7）、Top10 跑输池、扛 T+1、两个年代都负。**是规避/见顶预警，不是买入信号**；新高/剩余偏离两个分项中性（噪声）。
2. **挖到 3 个正向因子**：`rev5`(5日反转)、`ln_turn_avg20`(流动性)、低 `vol20`(低波)——全样本+近一年 IC 都显著为正，**正好是 total_score 奖励特质(强势/放量/追高/新高)的镜像**。
3. **但做不成可交易多头**：edge 全在多空(A股个股不可做空+涨跌停不可成交+集中小盘→纸面)；**多头 long-only 20 年是灾难**(−80%以上回撤、跑输买入持有沪深300)；近一年好看=regime 运气。
4. **大盘顶底/趋势择时叠加反转多头 → 更差**(趋势版 −92%、只躲顶版 −87%)：长周期 long-only 反转亏损是结构性的，择时改不了"篮子本身是坏的"。
5. **终论**：无稳健可交易的多头 alpha。**两套系统各司其职**——TA-CN 顶底管大盘择时、daydayUp 因子管规避/见顶预警，**别强行合成个股做多策略**。

---

## 十四、底部择时 + 主线研究（轮回模式，进行中）

思路转向 **regime 条件化**:底部进场→上升期持有/主线轮动→顶部减仓→破位清仓,周而复始。修正了十三章"无条件因子做多失败"的根因(没择时)。脚本在 `backend/scripts/`。

### 14.1 底部信号复刻（`bottom_events_reconstruct.py`）
忠实复刻 TA-CN `build_market_gauge` 的**底部确认**:超卖门控(上证 `bias20≤-3` 或 `RSI6≤25`,RSI6 用 ewm com=5)+ ≥1 恐慌确认(跌停占比≥3% 或 top100中位涨幅<-3%)。
- 2007-2026 跑出 **57 个底部事件**,覆盖 2008/2013钱荒/2015/2016熔断/2018/2020COVID/2022/2024-02 等**全部历史大底**——信号忠实可用。
- 大底确认日成簇(2015 有 28 天)、小杀跌仅 1 天 → 用簇大小/跌停占比可分主次。

### 14.2 Phase 1 底部主线领涨延续性（`bottom_leadership_study.py`，55 有效事件）
底后 5 日按申万一级行业(去嵌套白名单30个,等权合成)反弹强度取前3=主线,测底后 20/40/60 日相对上证超额:

| 组别 | H20 | H40 | H60 |
|---|---|---|---|
| 主线前3 | +3.34%(胜76% t4.4) | +4.27%(69% t4.0) | +5.88%(73% t4.1) |
| 全行业均值 | +2.90%(71%) | +3.91%(67%) | +5.61%(67%) |
| 垫底3 | +2.05%(60%) | +2.74%(58%) | +4.11%(66%) |

**结论(分清主次)**:
1. **底部择时本身是强而稳的真 edge**:底部进场后任何行业 20-60 日都显著跑赢上证(t 2.5-4.4、胜率 58-76%)——印证顶底框架核心价值=大盘择时;也解释十三章无条件做多为何亏(没择时)、条件化(只底后持有)就转正。
2. **主线领涨能延续但只是小加分**:主线前3 仅比全行业均值多 +0.4~0.5pp(t 几乎一样),但 主线>全行业>垫底 三周期单调一致→真实但幅度小。**大头收益来自"在底部满仓",不是"选对主线"**。
- caveat:超额含"等权 vs 上证大盘股加权"成分(已用主线 vs 全行业等权剥离,纯选主线 alpha 仅 +0.4pp);当前成分有漂移/幸存者偏差;55 事件+窗口重叠 t 偏乐观。

### 14.3 Phase 2 完整轮回回测（`bottom_cycle_strategy.py`）
底部首个确认日进场(可实现)→ 持有 → 上证超买 或 跌破MA20(破位,需先收复MA再跌破)清仓 → 等下个底。篮子各宽基对比,费0.1%往返。

| 篮子 | 择时轮回 | 全程年化 | 回撤 | 胜率 | 买入持有 | 买持年化 | 买持回撤 |
|---|---|---|---|---|---|---|---|
| 上证 | +14% | 0.7% | −51% | 66% | +48% | 2.0% | −72% |
| 中证500 | +68% | 2.7% | −54% | 71% | +370% | 8.3% | −72% |
| 中证1000 | +76% | 3.1% | −56% | 73% | +454% | 9.7% | −72% |

**结论:裸轮回大幅跑输买入持有(中证1000 +76% vs +454%),回撤也没降多少。** 不矛盾于 Phase 1:① 退得太早(超买/破MA20一触发就清),吃不到主升浪;② 空仓 79% 时间,机会成本巨大;③ 熊市假底频发反复砍(2008/2011/2018),胜率73%但输的单笔大→ −51%回撤。
→ 底部择时**当全 in-out 系统不成立**;适合做**风险叠加**(顶减仓/底加仓),或需"挑剔进场+趋势退出"改造。
- bug 记录:破位退出必须"先收复MA再跌破"才算,否则底部进场(本在MA下方)进场次日即触发→1日持仓。

### 14.4 下一步
系统性测试:进场挑剔度(按跌停占比/簇大小过滤假底)× 退出(趋势MA20/30/60、是否超买退出)网格扫描,找能跑赢买入持有或显著降回撤的组合。
