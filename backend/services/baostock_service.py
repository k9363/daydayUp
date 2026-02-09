"""
Baostock股票数据服务
"""
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps
import time
import logging

from extensions import db
from models.stockdaily import StockDaily


logger = logging.getLogger(__name__)


class BaostockService:
    """Baostock股票数据服务类"""
    
    def __init__(self):
        self.lg = None
    
    def login(self):
        """登录Baostock"""
        if self.lg is None or not self.lg.error_code == '0':
            self.lg = bs.login()
            if self.lg.error_code != '0':
                raise Exception(f"Baostock登录失败: {self.lg.error_msg}")
        return self.lg
    
    def logout(self):
        """登出Baostock"""
        if self.lg:
            bs.logout()
            self.lg = None
    
    def __enter__(self):
        """上下文管理器入口"""
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.logout()
    
    def get_stock_list(self, date=None):
        """
        获取股票列表

        Args:
            date: 日期，默认最新

        Returns:
            list: 股票列表
        """
        # 注意：登录/注销由调用者管理，避免频繁登录/注销导致被限流

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 获取全部A股数据（带重试）
        max_retries = 3
        for retry in range(max_retries):
            try:
                rs = bs.query_all_stock(day=date)

                data_list = []
                while (rs.error_code == '0') and rs.next():
                    data_list.append(rs.get_row_data())

                logger.info(f"get_stock_list({date}): 获取到 {len(data_list)} 条原始数据")
                if data_list:
                    logger.debug(f"第一条数据字段数: {len(data_list[0])}, 内容: {data_list[0]}")
                return data_list

            except Exception as e:
                logger.warning(f"获取股票列表异常: {e}")
                if retry < max_retries - 1:
                    logger.info(f"第 {retry + 1} 次尝试失败，等待 3 秒后重试...")
                    import time
                    time.sleep(3)
        
        return []
    
    def get_history_data(self, code, start_date, end_date, frequency='d', adjust_type='2'):
        """
        获取历史行情数据
        
        Args:
            code: 股票代码，如 'sh.600000'
            start_date: 开始日期，YYYY-MM-DD
            end_date: 结束日期，YYYY-MM-DD
            frequency: 数据类型，d=日k线，w=周k线，m=月k线
            adjust_type: 复权类型，1=后复权，2=前复权，3=不复权
        
        Returns:
            pandas.DataFrame: 历史数据
        """
        self.login()
        
        try:
            rs = bs.query_history_k_data_plus(
                code=code,
                start_date=start_date,
                end_date=end_date,
                fields="date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,psTTM",
                frequency=frequency,
                adjustflag=adjust_type
            )
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            # 创建DataFrame
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换数值列
            numeric_columns = ['open', 'high', 'low', 'close', 'preclose', 'volume', 
                             'amount', 'turn', 'pctChg', 'peTTM', 'psTTM']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        finally:
            self.logout()
    
    def get_daily_basic(self, code, start_date, end_date):
        """
        获取每日基本面数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            pandas.DataFrame: 每日基本面数据
        """
        self.login()
        
        try:
            rs = bs.query_daily_basic(
                code=code,
                start_date=start_date,
                end_date=end_date,
                fields="date,code,close,turn,volume,amount,pe,pb"
            )
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换数值列
            numeric_columns = ['close', 'turn', 'volume', 'amount', 'pe', 'pb']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        finally:
            self.logout()
    
    def get_stock_info(self, code):
        """
        获取股票基本信息
        
        Args:
            code: 股票代码
        
        Returns:
            dict: 股票信息
        """
        self.login()
        
        try:
            rs = bs.query_stock_info(code)
            
            info = {}
            while (rs.error_code == '0') and rs.next():
                info = dict(zip(rs.fields, rs.get_row_data()))
                break
            
            return info
            
        finally:
            self.logout()
    
    def get_stock_basic_batch(self, logged_in=False):
        """
        批量获取全部股票基本信息（使用query_stock_basic API）

        Args:
            logged_in: 是否已登录

        Returns:
            list: 股票基本信息列表，每个元素为字典
        """
        data_list = []
        
        try:
            if not logged_in:
                self.login()

            rs = bs.query_stock_basic()

            if rs.error_code == '0':
                while rs.next():
                    data_list.append(dict(zip(rs.fields, rs.get_row_data())))
                
                logger.info(f"通过query_stock_basic API获取到 {len(data_list)} 条股票基本信息")
            else:
                logger.warning(f"query_stock_basic API返回错误: {rs.error_msg}")

        except Exception as e:
            logger.error(f"批量获取股票基本信息失败: {e}")
        finally:
            if not logged_in:
                try:
                    self.logout()
                except:
                    pass

        return data_list
    
    def get_industry_classify(self):
        """获取行业分类"""
        # 注意：登录/注销由调用者管理，避免频繁登录/注销导致被限流

        rs = bs.query_stock_industry()

        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(dict(zip(rs.fields, rs.get_row_data())))

        return data_list
    
    def get_trade_calendar(self, start_date, end_date, logged_in=False):
        """
        获取交易日历

        Args:
            start_date: 开始日期
            end_date: 结束日期
            logged_in: 是否已登录

        Returns:
            list: 交易日历
        """
        need_logout = False
        if not logged_in:
            self.login()
            need_logout = True

        try:
            # Baostock 版本不同，方法名可能不同
            if hasattr(bs, 'query_trade_calendar'):
                rs = bs.query_trade_calendar(start_date=start_date, end_date=end_date)
            elif hasattr(bs, 'trade_cal'):
                rs = bs.trade_cal(start_date=start_date, end_date=end_date)
            else:
                logger.warning("Baostock 不支持交易日历 API")
                return []

            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(dict(zip(rs.fields, rs.get_row_data())))

            return data_list

        except Exception as e:
            logger.warning(f"获取交易日历失败: {e}")
            return []

        finally:
            if need_logout:
                try:
                    self.logout()
                except:
                    pass

    def check_is_trading_day(self, date, logged_in=False):
        """
        检查指定日期是否为交易日

        Args:
            date: 日期 (YYYY-MM-DD)
            logged_in: 是否已登录（避免重复登录）

        Returns:
            bool: 是否为交易日
        """
        need_logout = False
        if not logged_in:
            self.login()
            need_logout = True

        try:
            # 尝试使用交易日历 API
            if hasattr(bs, 'query_trade_calendar') or hasattr(bs, 'trade_cal'):
                try:
                    if hasattr(bs, 'query_trade_calendar'):
                        rs = bs.query_trade_calendar(start_date=date, end_date=date)
                    else:
                        rs = bs.trade_cal(start_date=date, end_date=date)
                    
                    data_list = []
                    while (rs.error_code == '0') and rs.next():
                        data_list.append(dict(zip(rs.fields, rs.get_row_data())))
                    
                    logger.info(f"交易日历 API 返回: {data_list}")
                    if data_list:
                        calendar_entry = data_list[0]
                        logger.info(f"日历条目字段: {calendar_entry}")
                        # 尝试多种可能的字段名
                        is_trading = (calendar_entry.get('is_trading_day') == '1' or 
                                     calendar_entry.get('isTradingDay') == '1')
                        if is_trading:
                            return True
                except Exception as e:
                    logger.warning(f"交易日历 API 调用失败: {e}")

            # 备用方法：检查股票数据是否有返回
            logger.info(f"使用备用方法检查 {date} 是否为交易日...")
            max_retries = 3
            for retry in range(max_retries):
                try:
                    rs = bs.query_all_stock(day=date)
                    data_list = []
                    while (rs.error_code == '0') and rs.next():
                        data_list.append(rs.get_row_data())
                    logger.info(f"query_all_stock 返回 {len(data_list)} 条数据")
                    return len(data_list) > 0
                except Exception as e:
                    logger.warning(f"查询股票列表异常: {e}")
                    if retry < max_retries - 1:
                        import time
                        time.sleep(2)
            return False

        finally:
            if need_logout:
                try:
                    self.logout()
                except:
                    pass

    def get_latest_trading_day(self, target_date):
        """
        检查指定日期是否为交易日，如果不是则抛出错误

        Args:
            target_date: 目标日期 (YYYY-MM-DD)

        Returns:
            str: 交易日日期

        Raises:
            ValueError: 如果日期不是交易日
        """
        # 检查目标日期是否为交易日
        is_trading = self.check_is_trading_day(target_date)
        if is_trading:
            return target_date

        # 如果不是交易日，抛出错误
        raise ValueError(f"指定日期 {target_date} 不是交易日，请选择A股交易日期（周一至周五，节假日除外）")
    
    def get_stock_zh_a_hist(self, symbol, start_date, end_date, frequency='daily', adjust_type='2'):
        """
        获取A股历史数据（简化接口）
        
        Args:
            symbol: 股票代码，如 '600000'
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率，daily-日线，weekly-周线，monthly-月线
            adjust_type: 复权类型，1-不复权，2-前复权，3-后复权
        
        Returns:
            pandas.DataFrame: 历史数据
        """
        self.login()
        
        try:
            # 转换代码格式
            if symbol.startswith('sh') or symbol.startswith('sz'):
                bs_code = symbol
            else:
                bs_code = f'sh.{symbol}' if symbol.startswith('6') else f'sz.{symbol}'
            
            # 转换复权参数：qfq->2, hfq->3
            if adjust_type == 'qfq':
                adjust_flag = '2'  # 前复权
            elif adjust_type == 'hfq':
                adjust_flag = '3'  # 后复权
            else:
                adjust_flag = str(adjust_type)  # 默认或直接使用数字
            
            rs = bs.query_history_k_data_plus(
                code=bs_code,
                start_date=start_date,
                end_date=end_date,
                fields="date,code,open,high,low,close,volume,amount,pctChg",
                frequency=frequency,
                adjustflag=adjust_flag
            )
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换数值列
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pctChg']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        finally:
            self.logout()
    
    def get_realtime_quotes(self, symbols):
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            pandas.DataFrame: 实时行情
        """
        self.login()
        
        try:
            # 转换代码格式
            bs_codes = []
            for symbol in symbols:
                if symbol.startswith('sh') or symbol.startswith('sz'):
                    bs_codes.append(symbol)
                else:
                    bs_code = f'sh.{symbol}' if symbol.startswith('6') else f'sz.{symbol}'
                    bs_codes.append(bs_code)
            
            rs = bs.query_trade_notes(bs_codes)
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            return df
            
        finally:
            self.logout()
    
    def get_daily_market_data(self, date):
        """
        获取指定日期全部A股日线数据
        
        Args:
            date: 交易日期 (YYYY-MM-DD)
        
        Returns:
            pandas.DataFrame: 日线数据
        """
        self.login()
        
        try:
            # 获取全部A股日线数据
            rs = bs.query_history_k_data_plus(
                code="sh.000001",  # 先获取上证指数
                start_date=date,
                end_date=date,
                fields="date,code,open,high,low,close,volume,amount,pctChg,turn,peTTM,pb",
                frequency='d',
                adjustflag='2'
            )
            
            # 实际上 baostock 的 query_history_k_data_plus 不支持一次获取全部股票
            # 需要先获取股票列表，再逐个获取
            return None
            
        finally:
            self.logout()
    
    def get_a_stock_daily_data(self, date, batch_size=100):
        """
        获取指定日期全部A股日线数据（逐只获取）

        Args:
            date: 交易日期 (YYYY-MM-DD)
            batch_size: 每批查询的股票数量（实际是组合格式）

        Returns:
            pandas.DataFrame: 日线数据
        """
        import baostock as bs

        self.login()

        try:
            # 1. 先获取全部股票列表
            stock_list = self.get_stock_list(date=date)

            if not stock_list:
                return pd.DataFrame()

            # 2. 提取股票代码
            stock_codes = [stock[0] for stock in stock_list if stock and len(stock) > 0 and len(stock[0]) == 9]

            print(f"获取 {len(stock_codes)} 只股票的日线数据...")

            all_data = []

            # 3. 逐只获取日线数据
            for i, code in enumerate(stock_codes):
                rs = bs.query_history_k_data_plus(
                    code=code,
                    start_date=date,
                    end_date=date,
                    fields="date,code,name,open,high,low,close,preclose,volume,amount,pctChg,turn,peTTM,pb",
                    frequency='d',
                    adjustflag='2'
                )

                while (rs.error_code == '0') and rs.next():
                    all_data.append(rs.get_row_data())

                # 每100只打印进度
                if (i + 1) % 100 == 0:
                    print(f"  已处理 {i + 1}/{len(stock_codes)} 只股票...")

                # 避免请求过快
                time.sleep(0.1)

            print(f"  获取完成，共 {len(all_data)} 条数据")

            if not all_data:
                return pd.DataFrame()

            # 4. 创建DataFrame
            df = pd.DataFrame(all_data, columns=rs.fields)

            # 5. 转换数值列
            numeric_columns = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'pctChg', 'turn', 'peTTM', 'pb']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        finally:
            self.logout()
    
    def get_stock_industry(self, stock_codes):
        """
        获取指定股票的所属行业

        Args:
            stock_codes: 股票代码列表

        Returns:
            dict: 股票代码 -> 行业名称
        """
        self.login()

        try:
            industry_map = {}
            rs = bs.query_stock_industry()

            while (rs.error_code == '0') and rs.next():
                row = dict(zip(rs.fields, rs.get_row_data()))
                if row['code'] in stock_codes:
                    industry_map[row['code']] = row.get('industry', '未知')

            return industry_map

        finally:
            self.logout()

    def get_stock_industry_batch(self, stock_codes):
        """
        批量获取股票行业分类（带缓存版本）

        Args:
            stock_codes: 股票代码列表

        Returns:
            dict: 股票代码 -> {'industry': 行业, 'area': 地区, 'sector': 板块}
        """
        industry_map = {}
        all_industries = self.get_industry_classify()

        if all_industries:
            code_set = set(stock_codes)
            for item in all_industries:
                if item.get('code') in code_set:
                    industry_map[item['code']] = {
                        'industry': item.get('industry', '未知'),
                        'area': item.get('area', '未知'),
                        'sector': self._get_sector_from_code(item['code'])
                    }

        # 补充没有行业信息的股票
        for code in stock_codes:
            if code not in industry_map:
                industry_map[code] = {
                    'industry': '未知',
                    'area': '未知',
                    'sector': self._get_sector_from_code(code)
                }

        return industry_map

    def fetch_and_save_daily_data(self, date, db_session, max_retries=3):
        """
        获取指定日期的A股日线数据（先查库，没有则API获取并落库）

        Args:
            date: 交易日期 (YYYY-MM-DD)
            db_session: 数据库会话
            max_retries: 最大重试次数

        Returns:
            list: 日线数据字典列表

        Raises:
            ValueError: 如果指定日期不是交易日
        """
        from models.stockdaily import StockDaily

        # 0. 检查指定日期是否为交易日
        # 先登录检查，检查完不登出，继续使用
        self.login()
        try:
            is_trading = self.check_is_trading_day(date, logged_in=True)
        except Exception as e:
            self.logout()
            raise

        if not is_trading:
            self.logout()  # 确保登出
            raise ValueError(f"指定日期 {date} 不是交易日，请选择A股交易日期（周一至周五，节假日除外）")

        # 1. 先查库：检查是否已有该日期的数据
        existing_data = db_session.query(StockDaily).filter(
            StockDaily.trade_date == date
        ).all()

        if existing_data:
            print(f"数据库中已存在 {date} 的股票数据，共 {len(existing_data)} 条")
            # 数据已存在时也尝试补充元数据（确保元数据完整）
            try:
                from services.metadata_service import get_metadata_service
                from services.metadata_config import is_auto_supplement_enabled

                logger.info(f"数据已存在，检查是否需要补充元数据...")
                if is_auto_supplement_enabled('sync'):
                    metadata_service = get_metadata_service()
                    stock_codes = [record.stock_code for record in existing_data]
                    
                    result = metadata_service.supplement_metadata(
                        stock_codes=stock_codes,
                        db_session=db_session,
                        context='sync'
                    )
                    logger.info(f"元数据补充完成: {result}")
                else:
                    logger.info("数据同步时自动补充元数据已禁用")

            except Exception as e:
                logger.error(f"补充元数据失败: {e}")
                # 元数据补充失败不应影响主流程

            return [record.to_dict() for record in existing_data]

        # 2. 数据库没有，从API获取
        print(f"数据库中未找到 {date} 的股票数据，开始从Baostock获取...")

        # 已登录，直接使用
        try:
            # 2.1 获取股票列表
            stock_list = self.get_stock_list(date=date)
            if not stock_list:
                print("未获取到股票列表")
                return []

            # 过滤掉非A股股票的板块数据（如指数、基金等）
            # query_all_stock 返回字段可能因版本而异：
            # - 新版: code, name, market, board, industry, status
            # - 旧版: code, status, name
            stock_codes = []
            stock_name_map = {}
            stock_type_map = {}  # 股票代码 -> 类型映射
            for stock in stock_list:
                if not stock or len(stock) < 2:
                    continue
                code = stock[0]  # 证券代码
                
                # 根据字段数量判断版本并正确解析
                if len(stock) >= 6:
                    # 新版格式: code, name, market, board, industry, status
                    name = stock[1]  # 证券名称
                    market = stock[2] if len(stock) > 2 else ''
                    board = stock[3].strip() if stock[3] else ''  # 板块类型
                    industry = stock[4] if len(stock) > 4 else ''
                    status = stock[5].strip() if len(stock) > 5 and stock[5] else ''  # 状态
                elif len(stock) == 3:
                    # 旧版格式: code, status, name
                    status = stock[1].strip() if stock[1] else ''
                    name = stock[2] if len(stock) > 2 and stock[2] else ''
                    market = ''
                    board = ''
                    industry = ''
                else:
                    # 兜底处理
                    name = stock[1] if len(stock) > 1 and stock[1] else ''
                    status = ''
                    market = ''
                    board = ''
                    industry = ''
                
                # 通过代码前缀判断股票类型
                stock_type = self._get_type_from_code(code)
                
                # 过滤条件：
                # 1. 代码必须是 6 位数字（如 sh.600000 -> 6 位）
                # 2. 排除指数（board='指数'）、基金（board='基金'）等
                # 3. 状态为正常或上市状态（非退市、暂停等）
                if (len(code) >= 8 and code[2:8].replace('.', '').isdigit() and 
                    board not in ['指数', '基金', '债券', '期货', '期权', '港股', 'B股'] and
                    status not in ['退市', '暂停上市', '终止上市', '0']):
                    stock_codes.append(code)
                    stock_name_map[code] = name
                    stock_type_map[code] = stock_type

            print(f"获取到 {len(stock_codes)} 只A股股票")

            # 2.2 获取行业信息
            industry_info = self.get_stock_industry_batch(stock_codes)

            # 2.3 逐只获取日线数据（带重试机制和限流）
            batch_data = []  # 每批数据，用于批量落库
            batch_size = 100  # 每100条落库一次
            request_interval = 0.5  # 请求间隔 0.5 秒，Baostock免费版限制较严格
            batch_pause = 2  # 每批后暂停2秒，避免被限流
            max_retries = 5  # 增加重试次数

            success_count = 0
            fail_count = 0
            total_saved = 0

            for i, code in enumerate(stock_codes):
                retry_count = 0
                retry_delay = 2  # 初始重试延迟2秒

                while retry_count < max_retries:
                    try:
                        # 逐只查询 - 注意：name字段不在query_history_k_data_plus API支持范围内
                        rs = bs.query_history_k_data_plus(
                            code=code,
                            start_date=date,
                            end_date=date,
                            fields="date,code,open,high,low,close,preclose,volume,amount,pctChg,turn,peTTM,psTTM",
                            frequency='d',
                            adjustflag='2'
                        )

                        if rs.error_code == '0':
                            while rs.next():
                                row = dict(zip(rs.fields, rs.get_row_data()))
                                batch_data.append(row)
                            success_count += 1
                        else:
                            # API返回错误码，重试
                            fail_count += 1
                            error_msg = rs.error_msg if hasattr(rs, 'error_msg') else 'Unknown error'
                            if retry_count == 0:
                                print(f"    API错误: {code} - {rs.error_code}: {error_msg}")

                        break  # 成功，跳出重试循环

                    except Exception as e:
                        error_str = str(e)
                        # 检查是否是网络错误
                        if 'Bad file descriptor' in error_str or 'Connection' in error_str:
                            fail_count += 1
                            print(f"    网络异常，等待 {retry_delay} 秒后重试 ({retry_count + 1}/{max_retries})")
                            if retry_count < max_retries - 1:
                                time.sleep(retry_delay)
                                retry_delay *= 2  # 指数退避，最大等待32秒
                                retry_count += 1
                                continue
                        # 其他错误直接跳过
                        print(f"    跳过股票 {code}: {error_str}")
                        break

                # 避免请求过快
                time.sleep(request_interval)

                # 每批数据落库（每100条或最后一批）
                if len(batch_data) >= batch_size:
                    saved_count = self._save_batch_data(db_session, batch_data, stock_name_map, stock_type_map, industry_info, date)
                    total_saved += saved_count
                    batch_data = []  # 清空批次数据
                    print(f"  已保存 {i + 1}/{len(stock_codes)} 只股票 (累计保存: {total_saved})")
                    # 每批后暂停一下，避免被限流
                    time.sleep(batch_pause)

            # 保存最后一批数据
            if batch_data:
                saved_count = self._save_batch_data(db_session, batch_data, stock_name_map, stock_type_map, industry_info, date)
                total_saved += saved_count

            print(f"  共获取 {success_count} 只股票，成功保存 {total_saved} 条数据")

            # 补充元数据：板块信息和股票-板块关联
            if total_saved > 0:
                try:
                    from services.metadata_service import get_metadata_service
                    from services.metadata_config import is_auto_supplement_enabled

                    # 检查是否启用自动补充
                    if is_auto_supplement_enabled('sync'):
                        metadata_service = get_metadata_service()

                        # 使用统一的综合补充方法
                        result = metadata_service.supplement_metadata(
                            stock_codes=stock_codes,
                            db_session=db_session,
                            context='sync'
                        )
                        logger.info(f"元数据补充完成: {result}")
                    else:
                        logger.info("数据同步时自动补充元数据已禁用")

                except Exception as e:
                    logger.error(f"补充元数据失败: {e}")
                    # 元数据补充失败不应影响主流程

            return total_saved  # 返回保存的记录数

        finally:
            # 确保登出
            self.logout()

    def _get_type_from_code(self, code):
        """
        根据股票代码判断股票类型

        Args:
            code: 股票代码，如 'sh.600000'

        Returns:
            str: 股票类型
        """
        if not code:
            return '未知'
        # 科创板: 68 开头 (sh.68xxx)
        if code.startswith('sh.68'):
            return '科创板'
        # 上海主板: 60 开头 (sh.60xxx)
        elif code.startswith('sh.60'):
            return '上海主板'
        # 深圳主板: 00 开头 (sz.00xxx)
        elif code.startswith('sz.00'):
            return '深圳主板'
        # 创业板: 30 开头 (sz.30xxx)
        elif code.startswith('sz.30'):
            return '创业板'
        elif code.startswith('sz'):
            return '深圳其他'
        return '未知'

    def _get_sector_from_code(self, code):
        """
        根据股票代码判断板块

        Args:
            code: 股票代码，如 'sh.600000'

        Returns:
            str: 板块名称
        """
        if not code:
            return '未知'
        # 科创板: 68 开头 (sh.68xxx)
        if code.startswith('sh.68'):
            return '科创板'
        # 上海主板: 60 开头 (sh.60xxx)
        elif code.startswith('sh.60'):
            return '上海主板'
        # 深圳主板: 00 开头 (sz.00xxx)
        elif code.startswith('sz.00'):
            return '深圳主板'
        # 创业板: 30 开头 (sz.30xxx)
        elif code.startswith('sz.60'):
            return '科创板'
        elif code.startswith('sz'):
            return '深圳其他'
        return '未知'

    def _save_batch_data(self, db_session, batch_data, stock_name_map, stock_type_map, industry_info, trade_date):
        """
        批量保存股票数据到数据库

        Args:
            db_session: 数据库会话
            batch_data: 批次数据列表
            stock_name_map: 股票代码到名称的映射
            stock_type_map: 股票代码到类型的映射
            industry_info: 行业信息映射
            trade_date: 交易日期

        Returns:
            int: 保存的记录数
        """
        from models.stockbasic import StockBasic

        # 预加载所有股票名称（从StockBasic表）
        stock_basics = db_session.query(StockBasic.stock_code, StockBasic.stock_name).all()
        db_stock_name_map = {sb.stock_code: sb.stock_name for sb in stock_basics}
        logger.info(f"从StockBasic表加载了 {len(db_stock_name_map)} 只股票的名称")

        saved_count = 0
        for row in batch_data:
            # 跳过没有数据的记录
            if not row.get('code') or row.get('close') == '':
                continue

            # 获取行业信息
            code = row['code']
            info = industry_info.get(code, {})

            # 股票名称：优先使用API返回的name字段 -> StockBasic表 -> 空
            stock_name = row.get('name') or stock_name_map.get(code, '') or db_stock_name_map.get(code, '')
            
            if not stock_name:
                logger.warning(f"警告: 股票 {code} 没有找到名称")
            else:
                logger.info(f"股票名称: code={code}, name={stock_name}")

            # 股票类型：从映射获取
            stock_type = stock_type_map.get(code, '未知')

            # 成交额转换：Baostock返回单位是千元，转换为元
            amount = row.get('amount', 0)
            if amount is not None:
                amount = float(amount) * 1000  # 千元转元

            record = StockDaily(
                stock_code=code,
                stock_name=stock_name,
                trade_date=trade_date,
                open_price=row.get('open', 0) or None,
                high_price=row.get('high', 0) or None,
                low_price=row.get('low', 0) or None,
                close_price=row.get('close', 0) or None,
                pre_close_price=row.get('preclose', 0) or None,
                volume=row.get('volume', 0) or None,
                turnover=amount,
                turnover_rate=row.get('turn', 0) or None,
                change_percent=row.get('pctChg', 0) or None,
                industry=info.get('industry', '未知'),
                market=stock_type
            )
            db_session.add(record)
            saved_count += 1

        db_session.commit()
        return saved_count


def get_baostock_service():
    """获取Baostock服务实例"""
    return BaostockService()

