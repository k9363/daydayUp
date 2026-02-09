"""
配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # 数据库配置 - 默认使用MySQL
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')
    
    if DB_TYPE == 'sqlite':
        # SQLite 开发数据库
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DB_PATH = os.path.join(BASE_DIR, 'daydayup.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    else:
        # MySQL生产数据库
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = int(os.getenv('DB_PORT', 3306))
        DB_USER = os.getenv('DB_USER', 'root')
        DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
        DB_NAME = os.getenv('DB_NAME', 'daydayup')
        
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?charset=utf8mb4&auth_plugin_map=mysql_native_password"
        )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 文件上传配置
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    
    # 确保上传目录存在
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')  # 开发环境默认使用MySQL
    if DB_TYPE == 'sqlite':
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DB_PATH = os.path.join(BASE_DIR, 'daydayup.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
