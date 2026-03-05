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
            
            logger.info("✅ 定时任务调度器初始化完成: 周一到周五18:00执行复盘任务")
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
    
    def _execute_review_logic(self, app):
        """执行复盘逻辑"""
        with app.app_context():
            from models.reviewtask import ReviewTask
            from extensions import db
            from services.review_service import ReviewTaskService
            
            # 获取今天日期
            today = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"📅 检查 {today} 是否为交易日")
            
            # 使用baostock API检查是否是交易日
            import baostock as bs
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"❌ Baostock登录失败: {lg.error_msg}")
                return {"success": False, "message": f"Baostock登录失败"}
            
            # 查询指定日期是否为交易日
            rs = bs.query_trade_dates(start_date=today, end_date=today)
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            bs.logout()
            
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
            task.task_name = f"{today} 日复盘"
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
