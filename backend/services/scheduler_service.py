"""
定时任务调度服务
用于自动执行复盘任务
"""
import logging
from datetime import datetime, time
import pandas as pd

logger = logging.getLogger(__name__)

class SchedulerService:
    """定时任务调度服务"""
    
    def __init__(self):
        self.scheduler = None
        self._init_scheduler()
    
    def _init_scheduler(self):
        """初始化调度器"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = BackgroundScheduler()
            
            # 添加定时任务：周一到周五18:00执行复盘任务
            # cron: 0=周一, 1=周二, ..., 4=周五
            trigger = CronTrigger(
                day_of_week='0-4',  # 周一到周五
                hour=18,
                minute=0
            )
            
            self.scheduler.add_job(
                self.execute_daily_review,
                trigger,
                id='daily_review_task',
                name='每日复盘任务',
                replace_existing=True
            )

            # 周一到周六 17:30 通过东财增量补充板块（行业 + 概念）+ 关联 + 新股
            # 工作日紧贴 18:00 复盘前，让复盘用上当天新增板块/股票；
            # 周六（非交易日、东财压力小）那次对概念板块触发 full_sync 全量比对，
            # 补漏平日断点续传跳过的成分股增删/改名（concept 内按 weekday()==5 判定）
            # supplement_*_from_akshare 内部有断点续传/增量 diff，重复跑只补差异，开销可控
            metadata_trigger = CronTrigger(
                day_of_week='0-5',
                hour=17,
                minute=30,
            )
            self.scheduler.add_job(
                self.execute_akshare_metadata_supplement,
                metadata_trigger,
                id='akshare_metadata_supplement',
                name='AKShare 元数据增量补充',
                replace_existing=True,
            )

            # 每日 17:00（盘后 15 分钟内淘股吧热帖榜单已稳定）拉手机端热帖聚合
            # 每 2 小时跑热帖（0/2/4/.../22 整点；不限工作日）
            # 高频更新让"今日热帖"接近实时
            tgb_hot_trigger = CronTrigger(hour='*/2', minute=0)
            self.scheduler.add_job(
                self.execute_tgb_hot_fetch,
                tgb_hot_trigger,
                id='tgb_hot_fetch',
                name='淘股吧手机端热帖聚合',
                replace_existing=True,
            )

            # 每 2 小时跑特别关注流（错开 5 分钟避免同 cookie 同时高频请求触发风控）
            tgb_spefocus_trigger = CronTrigger(hour='*/2', minute=5)
            self.scheduler.add_job(
                self.execute_tgb_spefocus_fetch,
                tgb_spefocus_trigger,
                id='tgb_spefocus_fetch',
                name='淘股吧特别关注流',
                replace_existing=True,
            )

            logger.info(
                "✅ 定时任务调度器初始化完成: "
                "每 2 小时 :00 淘股吧热帖 / :05 特别关注 / "
                "周一到周六 17:30 元数据补充(周六概念全量比对) / 周一到周五 18:00 复盘"
            )
        except ImportError:
            logger.warning("⚠️ APScheduler未安装，定时任务功能不可用")
            self.scheduler = None
    
    def start(self):
        """启动调度器"""
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
            logger.info("▶️ 定时任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏹️ 定时任务调度器已停止")
    
    def execute_daily_review(self):
        """执行每日复盘任务"""
        logger.info("⏰ 定时任务触发: 开始执行每日复盘")
        
        try:
            from flask import current_app
            from app import create_app
            from models.reviewtask import ReviewTask
            from models.kline import StockDailyKLine
            from extensions import db
            
            # 创建应用上下文
            app = create_app()
            with app.app_context():
                return self._execute_review_logic(app)
        except Exception as e:
            logger.error(f"❌ 定时任务执行失败: {e}")
            return {"success": False, "error": str(e)}

    def execute_akshare_metadata_supplement(self):
        """通过 AKShare 增量补充板块（行业 + 概念）+ 关联。

        断点续传：每个 supplement_*_from_akshare 内部会跳过 DB 已有的
        板块且已有成分股关联的，开销随时间衰减。
        """
        logger.info("⏰ 定时任务触发: AKShare 元数据增量补充")
        try:
            from app import create_app
            from extensions import db
            from services.metadata_service import get_metadata_service

            app = create_app()
            with app.app_context():
                svc = get_metadata_service()
                logger.info("📥 [元数据补充] 开始: 行业板块 + 成分股")
                industry = svc.supplement_industry_sectors_from_akshare(db.session)
                logger.info(f"📥 [元数据补充] 行业完成: {industry}")
                logger.info("📥 [元数据补充] 开始: 概念板块 + 成分股")
                # 全量比对低频化：周六（非交易日、东财访问压力小）做一次全量覆盖刷新，
                # 补漏平日断点续传跳过的成分股增删/改名；其余日仅增量 + 时效板块每日刷
                from datetime import datetime as _dt
                _full = _dt.now().weekday() == 5  # 5 = 周六
                concept = svc.supplement_concept_sectors_from_akshare(db.session, full_sync=_full)
                logger.info(f"📥 [元数据补充] 概念完成(full_sync={_full}): {concept}")
                # 个股列表补缺（新股/北交所）：源 TA-CN stock-list（tushare+东财最全，含当天上市新股）
                # baostock 列表滞后/无北交所，靠这步每日补齐，新股上市当天即进元数据
                logger.info("📥 [元数据补充] 开始: 个股列表（新股/北交所）")
                stocks = None
                try:
                    from routes.metadata import _supplement_stocks_impl
                    stocks = _supplement_stocks_impl()
                    logger.info(f"📥 [元数据补充] 个股完成: {stocks}")
                except Exception as se:
                    logger.error(f"⚠️ 个股补缺失败（不影响板块补充）: {se}")
                logger.info(
                    f"✅ AKShare 元数据增量补充全部完成: industry={industry}, concept={concept}, stocks={stocks}"
                )
                return {"success": True, "industry": industry, "concept": concept, "stocks": stocks}
        except Exception as e:
            logger.error(f"❌ AKShare 元数据增量补充失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def execute_tgb_hot_fetch(self):
        """每日盘后拉淘股吧手机端热帖，聚合写入 external_analysis（source=tgb-mobile-hot）。"""
        logger.info("⏰ 定时任务触发: 淘股吧手机端热帖聚合")
        try:
            from app import create_app
            from services.tgb_hot_service import run_daily

            app = create_app()
            with app.app_context():
                result = run_daily(pages=5, dry_run=False)
                logger.info(f"✅ 淘股吧热帖聚合完成: {result}")
                return result
        except Exception as e:
            logger.error(f"❌ 淘股吧热帖聚合失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def execute_tgb_spefocus_fetch(self):
        """每日拉淘股吧特别关注流，写入 external_analysis（source=tgb-special-focus）。"""
        logger.info("⏰ 定时任务触发: 淘股吧特别关注流")
        try:
            from app import create_app
            from services.tgb_spefocus_service import run_daily

            app = create_app()
            with app.app_context():
                result = run_daily(pages=5, dry_run=False)
                logger.info(f"✅ 淘股吧特别关注流完成: {result}")
                return result
        except Exception as e:
            logger.error(f"❌ 淘股吧特别关注流失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute_review_logic(self, app):
        """执行复盘逻辑"""
        with app.app_context():
            from models.reviewtask import ReviewTask
            from extensions import db
            from services.review_service import ReviewTaskService
            import baostock as bs

            # 获取今天日期
            today = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"📅 检查 {today} 是否为交易日")

            # 复用应用全局 baostock 会话，不要重复 login
            # app.py 已在启动时完成 bs.login()，同一进程内重复 login 会报"网络接收错误"
            import time
            max_retries = 3
            rs = None
            for attempt in range(1, max_retries + 1):
                lg = bs.login()
                if lg.error_code != '0':
                    logger.warning(
                        f"⚠️ Baostock 登录失败（{attempt}/{max_retries}）: {lg.error_msg}"
                    )
                    if attempt < max_retries:
                        time.sleep(3)
                        continue
                    logger.error(f"❌ Baostock 多次登录失败")
                    return {"success": False, "message": f"Baostock 登录失败: {lg.error_msg}"}
                try:
                    rs = bs.query_trade_dates(start_date=today, end_date=today)
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())
                    break  # 查询成功，跳出重试循环
                except Exception as e:
                    logger.warning(
                        f"⚠️ 查询交易日失败（{attempt}/{max_retries}）: {e}"
                    )
                    if attempt < max_retries:
                        time.sleep(3)
                    else:
                        logger.error(f"❌ 查询交易日多次失败")
                        return {"success": False, "message": f"查询交易日失败: {e}"}
            # ⚠️ 注意：不调用 bs.logout()，因为 baostock 是进程级单会话
            # app.py 启动时已登录，scheduler 复用同一会话，logout 会导致复盘任务执行时断连
            
            is_trading_day = False
            if data_list and len(data_list) > 0:
                # data_list[0] = [calendar_date, is_trading_day]
                # is_trading_day: '0'-非交易日, '1'-交易日
                row = data_list[0]
                if len(row) >= 2:
                    is_trading_day = row[1] in ['1', 1]
            
            if not is_trading_day:
                logger.info(f"📅 {today} 不是交易日（通过baostock API查询），跳过复盘任务")
                return {
                    "success": False, 
                    "message": f"{today} 不是交易日",
                    "is_trading_day": False
                }
            
            # 复盘任务内部会检查并补充K线数据，无需在此处处理
            
            # 检查今天是否已经存在复盘任务
            existing_task = ReviewTask.query.filter_by(trade_date=today).first()
            if existing_task:
                logger.info(f"📅 {today} 已存在复盘任务，任务ID: {existing_task.id}, 状态: {existing_task.status}")
                return {
                    "success": True,
                    "message": f"{today} 已存在复盘任务",
                    "task_id": existing_task.id,
                    "task_status": existing_task.status,
                    "is_trading_day": True
                }
            
            # 创建新的复盘任务
            task = ReviewTask()
            # task_name 末尾的 [定时] 是给 review_service 完成钩子识别用的：
            # 只有带此标记的复盘才会自动发邮件，手动重跑不自动发（手动可在报告页点按钮发）
            task.task_name = f"{today} 日复盘 [定时]"
            task.trade_date = today
            task.review_type = 'daily'
            task.data_source_type = 'baostock'
            task.status = 'pending'
            
            db.session.add(task)
            db.session.commit()
            
            logger.info(f"✅ 已创建复盘任务: ID={task.id}, 日期={today}")
            
            # 执行复盘任务
            try:
                service = ReviewTaskService()
                service.execute_baostock_task(task.id)

                # 重新查询任务状态
                db.session.refresh(task)
                logger.info(f"✅ 复盘任务执行完成: ID={task.id}, 状态={task.status}")

                # 2026-05-27: TA-CN 触发已下沉到 review_service 的「复盘完成」处统一处理，
                # 覆盖定时/手动重跑/异步回调所有入口。此处不再触发，避免重复 + 漏触发。
                # （原 bug：异步复盘时此处 status 还不是 completed，触发被过早跳过）

                return {
                    "success": True,
                    "message": f"复盘任务执行完成",
                    "task_id": task.id,
                    "task_status": task.status,
                    "is_trading_day": True
                }
            except Exception as e:
                task.status = 'failed'
                task.error_message = str(e)
                db.session.commit()
                logger.error(f"❌ 复盘任务执行失败: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "task_id": task.id,
                    "is_trading_day": True
                }
    
    def _trigger_tacn_batch_analysis(self):
        """复盘成功后 HTTP 触发 TA-CN 全市场综合分析。

        非阻塞（5s timeout）— TA-CN 提交即返回 task_id，分析在后台跑。
        失败只 log warning，不影响 daydayUp 复盘成功状态。
        """
        import os
        import requests
        tacn_base = os.getenv('TACN_API_BASE', 'http://tradingagents-backend:8000')
        token = os.getenv('INTERNAL_TRIGGER_TOKEN', '')
        try:
            resp = requests.post(
                f'{tacn_base}/api/analysis/index/batch/internal/trigger',
                json={'date': None, 'model': 'deepseek-v4-pro'},
                headers={'X-Internal-Token': token} if token else {},
                timeout=5,
            )
            if resp.status_code == 200:
                body = resp.json()
                logger.info(
                    f"🌐 已触发 TA-CN 全市场综合分析 task_id={body.get('task_id')} "
                    f"(后台跑 LLM ~30-60s)"
                )
            else:
                logger.warning(
                    f"⚠️ TA-CN 触发返回 HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except requests.RequestException as e:
            logger.warning(f"⚠️ TA-CN 触发失败（不影响复盘）: {e}")

    def get_jobs(self):
        """获取所有定时任务"""
        if not self.scheduler:
            return []
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None
            })
        return jobs
    
    def trigger_now(self):
        """手动触发每日复盘任务（立即执行）"""
        logger.info("🔧 手动触发每日复盘任务")
        return self.execute_daily_review()


# 全局调度器实例
scheduler_service = SchedulerService()
