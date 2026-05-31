# Flask Application Factory
import logging
import sys
import atexit
import os
import fcntl
from flask import Flask
from flask_cors import CORS
from config import config
from extensions import db
from routes.review import review_bp
from routes.stock import stock_bp
from routes.sync import sync_bp
from routes.metadata import metadata_bp
from routes.scheduler import scheduler_bp
from routes.tag import tag_bp
from routes.factor import factor_bp
from routes.expression import expression_bp
from routes.cycle import cycle_bp
from routes.note import note_bp
from routes.external import external_bp
from routes.email import email_bp
from utils.error_handlers import register_error_handlers

# 配置根日志（gunicorn 会覆盖，但为 fallback 保留）
_root_handler = logging.StreamHandler(sys.stderr)
_root_handler.setFormatter(logging.Formatter(
    '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logging.basicConfig(
    level=logging.INFO,
    handlers=[_root_handler]
)

# 关闭 SQLAlchemy SQL 日志输出
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

# 设置所有 logger 级别
for name in logging.Logger.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.INFO)

# 全局 Baostock 登录状态
_baostock_lg = None


def _init_baostock_login():
    """应用启动时初始化 Baostock 登录（共享进程级锁 + 重试）。

    用 safe_bs_login（services.baostock_lock）统一登录：后台启动线程、复盘同步线程、
    定时任务线程共用一把进程级锁串行化 bs.login()，避免并发撞同一全局 socket 导致
    "网络接收错误"（这是 2026-05-26 启动登录改后台线程后才暴露的并发问题）。
    """
    global _baostock_lg
    try:
        from services.baostock_lock import safe_bs_login
        _baostock_lg = safe_bs_login()
        logging.info("✅ Baostock 已登录（应用全局会话）")
    except Exception as e:
        logging.error(f"❌ Baostock 多次登录失败，兜底功能可能不可用（不影响 tushare 主路径）: {e}")


def _cleanup_baostock():
    """应用退出时清理 Baostock 登录"""
    import baostock as bs
    global _baostock_lg
    if _baostock_lg:
        try:
            bs.logout()
            logging.info("✅ Baostock 已登出")
        except Exception as e:
            logging.warning(f"⚠️ Baostock 登出失败: {e}")


def create_app(config_name=None):
    """应用工厂函数"""
    app = Flask(__name__)

    # 加载配置
    if config_name is None:
        config_name = 'default'
    app.config.from_object(config[config_name])

    # gunicorn 会重置 logging，需要重新配置
    _root_handler.setFormatter(logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.addHandler(_root_handler)
    logging.root.setLevel(logging.INFO)

    # 关闭 SQLAlchemy SQL 日志输出
    logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

    # 初始化SQLAlchemy
    db.init_app(app)

    # 初始化CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    app.register_blueprint(review_bp, url_prefix='/api/review')
    app.register_blueprint(stock_bp, url_prefix='/api/stock')
    app.register_blueprint(sync_bp, url_prefix='/api/sync')
    app.register_blueprint(metadata_bp, url_prefix='/api/metadata')
    app.register_blueprint(scheduler_bp, url_prefix='/api/scheduler')
    app.register_blueprint(tag_bp, url_prefix='/api/tag')
    app.register_blueprint(factor_bp, url_prefix='/api/factor')
    app.register_blueprint(expression_bp, url_prefix='/api/expression')
    app.register_blueprint(cycle_bp, url_prefix='/api/cycle')
    app.register_blueprint(note_bp, url_prefix='/api/note')
    app.register_blueprint(external_bp, url_prefix='/api/external')
    app.register_blueprint(email_bp, url_prefix='/api/email')

    # 启动时登录 Baostock —— 放后台线程，避免 gunicorn 多 worker 并发 bs.login()。
    # 根因：gunicorn -w 4，每个 worker 启动都 create_app→bs.login()，baostock 同账户
    # 多 session 并发登录会"网络接收错误"，同步重试 3×3s 阻塞 worker 启动（restart 卡几分钟、
    # 健康检查迟迟不 200）。改后台线程：启动立即返回，登录失败不阻塞；baostock 兜底用时各自 login。
    import threading as _bs_th
    _bs_th.Thread(target=_init_baostock_login, daemon=True).start()

    # 注册退出时登出 Baostock
    atexit.register(_cleanup_baostock)

    # 根路径健康检查
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'message': 'DaydayUp API is running'}

    # 注册统一错误处理器
    register_error_handlers(app)

    return app


# 全局调度器（应用启动时初始化）
_scheduler_service = None
_scheduler_initialized = False

# 文件锁路径（用于多 worker 场景下确保只初始化一次 scheduler）
_scheduler_lock_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    '.scheduler_init.lock'
)
# 标记文件：初始化成功后创建，用于快速判断是否已初始化
_scheduler_flag_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    '.scheduler_initialized'
)


def _get_proc_starttime(pid):
    """读 /proc/<pid>/stat 第 22 字段拿进程启动时间（jiffies）。无法读取返回 None。"""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            return f.read().split()[21]
    except Exception:
        return None


def init_scheduler(app, force=False):
    """初始化定时任务调度器"""
    global _scheduler_service, _scheduler_initialized

    # 快速检查：先检查标记文件是否存在
    if os.path.exists(_scheduler_flag_file) and not force:
        # 标记文件格式：pid 或 pid:starttime（2026-05-26 后加 starttime 防 PID 复用）
        try:
            with open(_scheduler_flag_file, 'r') as f:
                content = f.read().strip()
            if ":" in content:
                saved_pid_str, saved_starttime = content.split(":", 1)
            else:
                saved_pid_str, saved_starttime = content, None
            saved_pid = int(saved_pid_str)
            stale = False
            if saved_pid > 0:
                try:
                    os.kill(saved_pid, 0)  # 信号0检查进程是否存在
                    # 进程存活 — 进一步校验 starttime 防 docker restart 后 PID 复用
                    if saved_starttime:
                        current_starttime = _get_proc_starttime(saved_pid)
                        if current_starttime and current_starttime != saved_starttime:
                            stale = True
                            app.logger.info("⏭️ PID 复用（同 PID 不同进程），标记文件 stale，重新初始化")
                    if not stale:
                        app.logger.info("⏭️ 定时任务调度器已跳过初始化（标记文件存在，进程存活）")
                        _scheduler_initialized = True
                        return
                except OSError:
                    # 进程不存在
                    stale = True
                    app.logger.info("⏭️ 标记文件中的进程已死亡，重新初始化")
            if stale:
                try:
                    os.remove(_scheduler_flag_file)
                except Exception:
                    pass
        except Exception:
            pass

    # 防止重复初始化（进程内检查）
    if _scheduler_initialized and not force:
        app.logger.info("⏭️ 定时任务调度器已跳过初始化（进程内已存在）")
        return

    # 使用文件锁确保只有一个 worker 初始化 scheduler
    lock_fd = None
    try:
        # 创建锁文件（如果不存在）
        lock_dir = os.path.dirname(_scheduler_lock_file)
        if not os.path.exists(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)

        lock_fd = open(_scheduler_lock_file, 'w')
        # 阻塞模式获取排他锁（确保其他 worker 等待）
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        # 获取到锁后，检查标记文件（可能有其他 worker 刚初始化完）
        if os.path.exists(_scheduler_flag_file) and not force:
            app.logger.info("⏭️ 定时任务调度器已跳过初始化（已被其他 worker 初始化）")
            _scheduler_initialized = True
            return

        # 执行初始化
        from services.scheduler_service import scheduler_service as ss
        _scheduler_service = ss
        _scheduler_service.start()
        _scheduler_initialized = True

        # 创建标记文件：pid:starttime（starttime 防 docker restart 后 PID 复用导致 stale lock）
        my_pid = os.getpid()
        my_starttime = _get_proc_starttime(my_pid) or ""
        with open(_scheduler_flag_file, 'w') as f:
            f.write(f"{my_pid}:{my_starttime}")

        app.logger.info("✅ 定时任务调度器已初始化")

    except Exception as e:
        app.logger.warning(f"⚠️ 定时任务调度器初始化失败: {e}")
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except:
                pass


def stop_scheduler():
    """停止定时任务调度器"""
    global _scheduler_service
    if _scheduler_service:
        _scheduler_service.stop()
    # 删除标记文件，确保下次启动时正常初始化
    try:
        if os.path.exists(_scheduler_flag_file):
            os.remove(_scheduler_flag_file)
    except Exception:
        pass


def get_scheduler_service():
    """获取调度器服务实例"""
    return _scheduler_service


if __name__ == '__main__':
    app = create_app('development')
    
    # 初始化定时任务调度器
    init_scheduler(app)
    
    app.run(host='0.0.0.0', port=5001, debug=True)

# 创建全局 app 实例供 gunicorn 使用
app = create_app('production')

# 初始化定时任务调度器（gunicorn 模式下也需要启动）
init_scheduler(app)
