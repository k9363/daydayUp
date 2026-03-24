"""
配置文件
"""
import os
from dotenv import load_dotenv
from typing import Dict

load_dotenv()


# ========== 常量配置 ==========

# 市场指数代码映射
MARKET_INDEX_CODES: Dict[str, str] = {
    'sh.000001': '上证指数',
    'sz.399001': '深证成指',
    'sz.399006': '创业板指',
    'sh.000300': '沪深300',
    'sh.000905': '中证500',
    'sh.000852': '中证1000',
}

MARKET_INDEX_CODE_LIST = list(MARKET_INDEX_CODES.keys())

FACTOR_NAME_MAP: Dict[str, str] = {
    'close_price': '收盘价',
    'volume': '成交量',
    'turnover': '成交额',
    'pct_change': '涨跌幅',
    'ma5': '5日均线',
    'ma10': '10日均线',
    'ma20': '20日均线',
    'ma20_y1': '昨日20日均线',
    'volume_y1': '昨日成交量',
    'turnover_y1': '昨日成交额',
    'amount_rank': '成交额排名',
    'avg_amount_3d': '近3日平均成交额',
    'avg_amount_5d': '近5日平均成交额',
    'avg_amount_10d': '近10日平均成交额',
    'avg_amount_20d': '近20日平均成交额',
    'avg_amount_4_20d': '4-20日平均成交额',
    'avg_amount_11_30d': '11-30日平均成交额',
    'avg_amount_4_120d': '4-120日平均成交额',
    'price_ma5_diff': '股价与5日线差值',
    'price_ma10_diff': '股价与10日线差值',
    'factor1_rank': '成交额权重',
    'factor2_ma': '短线趋势',
    'factor3_vol': '昨日同比',
    'factor4_burst': '爆量',
    'factor5_extreme': '极限量',
    'factor6_trend': '多头趋势',
    'deviation_10d': '10日偏离值累计',
    'deviation_30d': '30日偏离值累计',
    'remaining_deviation': '剩余偏离值',
}

CALCULATION_METHOD_MAP: Dict[str, str] = {
    'close_price': 'kline_field',
    'volume': 'kline_field',
    'turnover': 'kline_field',
    'pct_change': 'kline_field',
    'ma5': 'kline_field',
    'ma10': 'kline_field',
    'ma20': 'kline_field',
    'volume_y1': 'kline_field',
    'turnover_y1': 'kline_field',
    'amount_rank': 'rank',
    'turnover_rank': 'rank',
    'avg_amount_3d': 'avg',
    'avg_amount_5d': 'avg',
    'avg_amount_10d': 'avg',
    'avg_amount_20d': 'avg',
    'avg_amount_4_20d': 'avg',
    'avg_amount_11_30d': 'avg',
    'avg_amount_4_120d': 'avg',
    'price_ma5_diff': 'expression',
    'price_ma10_diff': 'expression',
}

FACTOR_DEPENDENCIES: Dict[str, list] = {
    'avg_amount_3d': ['turnover'],
    'avg_amount_5d': ['turnover'],
    'avg_amount_10d': ['turnover'],
    'avg_amount_20d': ['turnover'],
    'avg_amount_4_20d': ['turnover'],
    'avg_amount_11_30d': ['turnover'],
    'avg_amount_4_120d': ['turnover'],
    'amount_rank': ['turnover'],
    'turnover_rank': ['turnover'],
    'volume_y1': ['volume'],
    'turnover_y1': ['turnover'],
    'price_ma5_diff': ['close_price', 'ma5'],
    'price_ma10_diff': ['close_price', 'ma10'],
    'factor1_rank': ['turnover_rank'],
    'factor2_ma': ['close_price', 'ma5', 'ma10', 'ma20', 'ma20_y1'],
    'factor3_vol': ['volume', 'volume_y1'],
    'factor4_burst': ['avg_amount_3d', 'avg_amount_4_20d'],
    'factor5_extreme': ['avg_amount_10d', 'avg_amount_11_30d'],
    'factor6_trend': ['close_price', 'ma5', 'ma10'],
    'deviation_10d': ['close_price', 'ma20'],
    'deviation_30d': ['close_price', 'ma20'],
    'remaining_deviation': ['close_price', 'ma20'],
}

EXPR_BUILTINS = {'IF', 'ABS', 'MAX', 'MIN', 'SUM', 'AVG', 'SQRT', 'LOG', 'ROUND', 'POW'}
EXPR_FUNCTION_NAMES = EXPR_BUILTINS | {'abs', 'sqrt', 'max', 'min', 'avg', 'sum', 'round', 'pow', 'if', 'log', 'AND', 'OR', 'NOT'}

STOCK_TYPE_STOCK = 'stock'
STOCK_TYPE_ETF = 'etf'
STOCK_TYPE_INDEX = 'index'
STOCK_TYPE_BOND = 'bond'

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_TOP_N = 100
TOP_N_FOR_SECTOR = 30
TOP_N_FOR_DISPLAY = 10

FACTOR_CATEGORY_KLINE_FIELD = 'kline_field'
FACTOR_CATEGORY_RANK = 'rank'
FACTOR_CATEGORY_AVG = 'avg'
FACTOR_CATEGORY_EXPRESSION = 'expression'


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

        # 连接池配置 - 解决 MySQL 连接超时/失效问题
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,              # 连接池大小
            'max_overflow': 5,            # 允许超出的连接数
            'pool_recycle': 1800,         # 30分钟回收连接，避免 MySQL wait_timeout 超时
            'pool_pre_ping': True,        # 每次使用连接前检查连接是否有效
            'connect_args': {
                'connect_timeout': 10,    # 连接超时时间
                'read_timeout': 30,      # 读取超时
                'write_timeout': 30,     # 写入超时
            }
        }
    
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
    SQLALCHEMY_ECHO = False


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
