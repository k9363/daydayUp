"""
因子定义模型
支持三种因子类型：股票因子(stock)、板块因子(sector)、大盘因子(market)
"""
from extensions import db
from datetime import datetime


class FactorDefine(db.Model):
    """因子定义表"""
    __tablename__ = 'factor_define'
    
    id = db.Column(db.Integer, primary_key=True)
    factor_code = db.Column(db.String(50), unique=True, nullable=False, index=True, comment='因子代码')
    factor_name = db.Column(db.String(100), nullable=False, comment='因子名称')
    
    # 因子作用域: stock-股票因子, sector-板块因子, market-大盘因子
    factor_scope = db.Column(db.String(20), nullable=False, default='stock', comment='因子作用域')
    
    # 数据来源: kline-原始K线数据, stock_factor-股票因子得分, sector_factor-板块因子得分, calculated-表达式计算
    source = db.Column(db.String(50), comment='数据来源')
    
    # 计算方法: kline_field-直接取字段, rank-排名得分, ma_trend-均线趋势, volume_compared-成交量对比, burst-爆量, extreme-极限量, trend-趋势, expression-表达式
    calculation_method = db.Column(db.String(50), comment='计算方法')
    
    # 筛选条件: top100-成交额前100, rank-排名计算, all-全部
    filter_condition = db.Column(db.String(50), comment='筛选条件')
    
    # 字段名 (对应K线表的字段或因子代码)
    field_name = db.Column(db.String(50), comment='字段名')
    
    # 天数区间配置，支持: "1_3", "1_5", "4_20", "11_30", "1_120" 等
    # 用于动态计算平均成交额等时间窗口因子
    days_range = db.Column(db.String(20), comment='天数区间，如 1_3 表示最近3天，4_20 表示第4-20天')
    
    # 日期偏移配置，支持: 1=昨日, 2=前日, 3=前3日...
    # 用于获取历史某日的K线数据
    days_offset = db.Column(db.Integer, default=0, comment='日期偏移，0=当日, 1=昨日, 2=前日, 以此类推')
    
    # 聚合方式 (仅板块因子使用): SUM/AVG/MAX/MIN/COUNT
    aggregation = db.Column(db.String(20), comment='聚合方式')
    
    # 指数代码 (仅大盘因子使用): 如 sh.000001, sz.399001
    index_code = db.Column(db.String(20), comment='指数代码')
    
    # 表达式 (用于calculated类型)
    expression = db.Column(db.Text, comment='表达式')
    
    # 描述
    description = db.Column(db.String(500), comment='描述')
    
    # 状态
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 关联
    # expressions = db.relationship('ScoreExpression', secondary='expression_factor', back_populates='factors')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'factor_code': self.factor_code,
            'factor_name': self.factor_name,
            'factor_scope': self.factor_scope,
            'source': self.source,
            'calculation_method': self.calculation_method,
            'filter_condition': self.filter_condition,
            'field_name': self.field_name,
            'days_range': self.days_range,
            'days_offset': self.days_offset,
            'aggregation': self.aggregation,
            'index_code': self.index_code,
            'expression': self.expression,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<FactorDefine {self.factor_code}: {self.factor_name}>'


# 因子作用域常量
class FactorScope:
    STOCK = 'stock'      # 股票因子
    SECTOR = 'sector'    # 板块因子
    MARKET = 'market'    # 大盘因子
    
    CHOICES = [
        (STOCK, '股票因子'),
        (SECTOR, '板块因子'),
        (MARKET, '大盘因子'),
    ]


# 数据来源常量
class FactorSource:
    KLINE = 'kline'              # K线原始数据
    STOCK_FACTOR = 'stock_factor'  # 股票因子得分
    SECTOR_FACTOR = 'sector_factor'  # 板块因子得分
    MARKET_FACTOR = 'market_factor'  # 大盘因子得分
    CALCULATED = 'calculated'    # 表达式计算
    PYTHON = 'python'             # Python硬编码计算
    
    CHOICES = [
        (KLINE, 'K线原始数据'),
        (STOCK_FACTOR, '股票因子得分'),
        (SECTOR_FACTOR, '板块因子得分'),
        (MARKET_FACTOR, '大盘因子得分'),
        (CALCULATED, '表达式计算'),
        (PYTHON, 'Python计算'),
    ]


# 聚合方式常量
class AggregationType:
    NONE = ''       # 无聚合
    SUM = 'SUM'     # 求和
    AVG = 'AVG'     # 平均值
    MAX = 'MAX'     # 最大值
    MIN = 'MIN'     # 最小值
    COUNT = 'COUNT' # 计数
    
    CHOICES = [
        (NONE, '无（原始值）'),
        (SUM, '求和'),
        (AVG, '平均值'),
        (MAX, '最大值'),
        (MIN, '最小值'),
        (COUNT, '计数'),
    ]


# 常用指数代码
class IndexCode:
    SH_000001 = ('sh.000001', '上证指数')
    SZ_399001 = ('sz.399001', '深证成指')
    SZ_399006 = ('sz.399006', '创业板指')
    SH_000300 = ('sh.000300', '沪深300')
    SH_000905 = ('sh.000905', '中证500')
    SH_000016 = ('sh.000016', '上证50')
    SZ_399300 = ('sz.399300', '创业板50')
    
    MAIN_INDICES = [
        ('sh.000001', '上证指数'),
        ('sz.399001', '深证成指'),
        ('sz.399006', '创业板指'),
    ]
    
    ALL_INDICES = [
        ('sh.000001', '上证指数'),
        ('sz.399001', '深证成指'),
        ('sz.399006', '创业板指'),
        ('sh.000300', '沪深300'),
        ('sh.000905', '中证500'),
        ('sh.000016', '上证50'),
        ('sz.399300', '创业板50'),
    ]
