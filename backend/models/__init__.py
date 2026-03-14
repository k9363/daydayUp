"""
数据库模型初始化
"""
from extensions import db
from models.reviewtask import ReviewTask
from models.reviewresult import ReviewResult
from models.stockdaily import StockDaily
from models.stockbasic import StockBasic
from models.kline import (
    StockSector,
    StockSectorRelation,
    StockDailyKLine,
    StockWeeklyKLine,
    StockMonthlyKLine,
    StockMinuteKLine,
    DataSyncTask
)
from models.delivery import StockDelivery
from models.tag import StockTag, StockTagRelation
from models.factor import FactorDefine
from models.expression import ScoreExpression
from models.dailynote import DailyNote
from models.cycle import Cycle, CycleSubPeriod, CycleTradeDay


def init_db(app):
    """初始化数据库"""
    with app.app_context():
        db.create_all()
