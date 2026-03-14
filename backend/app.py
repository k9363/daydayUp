# Flask Application Factory
import logging
import sys
import atexit
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
    """应用启动时初始化 Baostock 登录"""
    global _baostock_lg
    import baostock as bs
    _baostock_lg = bs.login()
    if _baostock_lg.error_code != '0':
        logging.warning(f"⚠️ Baostock 初始登录失败: {_baostock_lg.error_msg}")
    else:
        logging.info("✅ Baostock 已登录（应用全局会话）")


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

    # 启动时登录 Baostock
    _init_baostock_login()

    # 注册退出时登出 Baostock
    atexit.register(_cleanup_baostock)

    # 根路径健康检查
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'message': 'DaydayUp API is running'}
    
    # 错误处理
    @app.errorhandler(400)
    def bad_request(error):
        return {'code': 400, 'message': str(error)}, 400
    
    @app.errorhandler(404)
    def not_found(error):
        return {'code': 404, 'message': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'code': 500, 'message': 'Internal server error'}, 500
    
    return app


# 全局调度器（应用启动时初始化）
_scheduler_service = None


def init_scheduler(app):
    """初始化定时任务调度器"""
    global _scheduler_service
    try:
        from services.scheduler_service import scheduler_service as ss
        _scheduler_service = ss
        _scheduler_service.start()
        app.logger.info("✅ 定时任务调度器已初始化")
    except Exception as e:
        app.logger.warning(f"⚠️ 定时任务调度器初始化失败: {e}")


def stop_scheduler():
    """停止定时任务调度器"""
    global _scheduler_service
    if _scheduler_service:
        _scheduler_service.stop()


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
