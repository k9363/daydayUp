# Flask Application Factory
from flask import Flask
from flask_cors import CORS
from config import config
from extensions import db
from routes.review import review_bp
from routes.stock import stock_bp
from routes.sync import sync_bp
from routes.metadata import metadata_bp


def create_app(config_name=None):
    """应用工厂函数"""
    app = Flask(__name__)
    
    # 加载配置
    if config_name is None:
        config_name = 'default'
    app.config.from_object(config[config_name])
    
    # 初始化SQLAlchemy
    db.init_app(app)
    
    # 初始化CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册蓝图
    app.register_blueprint(review_bp, url_prefix='/api/review')
    app.register_blueprint(stock_bp, url_prefix='/api/stock')
    app.register_blueprint(sync_bp, url_prefix='/api/sync')
    app.register_blueprint(metadata_bp, url_prefix='/api/metadata')
    
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


if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5001, debug=True)
