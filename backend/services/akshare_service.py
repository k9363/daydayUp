"""
东方财富 API 数据服务 - AKShare 原始 API + Monkey Patch 反爬
"""
import json
import time
import random
import logging
import warnings
import requests
import urllib3
# 抑制 SSL 警告
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

logger = logging.getLogger(__name__)

# ==================== Monkey Patch 反爬机制 (patch requests) ====================

# 随机 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 原始请求方法
_original_request = requests.Session.request
_original_get = requests.get

# 请求间隔
_last_request_time = 0
_request_interval = 5  # 5秒间隔

def _get_random_headers():
    """生成随机浏览器 headers"""
    ua = random.choice(USER_AGENTS)
    return {
        'User-Agent': ua,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://datacenter.eastmoney.com/',
        'Origin': 'https://datacenter.eastmoney.com',
    }

def _patched_request(self, method, url, **kwargs):
    """带反爬机制的 requests.Session.request"""
    global _last_request_time
    
    # 计算延时
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < _request_interval:
        wait_time = _request_interval - elapsed
        # 添加随机抖动
        wait_time += random.uniform(1, 3)
        logger.debug(f"请求延时: {wait_time:.1f} 秒 (requests)")
        time.sleep(wait_time)
    
    _last_request_time = time.time()
    
    # 添加随机 headers
    headers = kwargs.get('headers', {})
    headers.update(_get_random_headers())
    kwargs['headers'] = headers
    
    return _original_request(self, method, url, **kwargs)

def _patched_get(url, **kwargs):
    """带反爬机制的 requests.get"""
    global _last_request_time
    
    # 计算延时
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < _request_interval:
        wait_time = _request_interval - elapsed
        # 添加随机抖动
        wait_time += random.uniform(1, 3)
        logger.debug(f"请求延时: {wait_time:.1f} 秒 (requests.get)")
        time.sleep(wait_time)
    
    _last_request_time = time.time()
    
    # 添加随机 headers
    headers = kwargs.get('headers', {})
    headers.update(_get_random_headers())
    kwargs['headers'] = headers
    
    return _original_get(url, **kwargs)

def enable_anti_scraping():
    """启用反爬机制 (patch requests)"""
    global _last_request_time
    _last_request_time = 0
    requests.Session.request = _patched_request
    requests.get = _patched_get
    logger.info("已启用反爬机制 (Monkey Patch - requests)")

def disable_anti_scraping():
    """禁用反爬机制"""
    requests.Session.request = _original_request
    requests.get = _original_get
    if '_original_urllib3_urlopen' in dir():
        urllib3.connectionpool.HTTPConnectionPool.urlopen = _original_urllib3_urlopen
    logger.info("已禁用反爬机制")

# ==================== Patch urllib3 (akshare uses it directly) ====================

_original_urllib3_urlopen = None
_original_urllib3_connect = None

def _patched_urllib3_urlopen(self, method, url, body=None, headers=None, **kwargs):
    """带反爬的 urllib3 urlopen"""
    global _last_request_time
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < _request_interval:
        wait_time = _request_interval - elapsed
        wait_time += random.uniform(1, 3)
        logger.debug(f"请求延时: {wait_time:.1f} 秒 (urllib3)")
        time.sleep(wait_time)
    _last_request_time = time.time()
    # 添加 headers
    pool_headers = getattr(self, 'headers', {})
    if headers:
        pool_headers = {**pool_headers, **headers}
    if 'User-Agent' not in pool_headers:
        pool_headers.update(_get_random_headers())
    return _original_urllib3_urlopen(self, method, url, body, pool_headers, **kwargs)

def _init_urllib3_patch():
    """初始化 urllib3 patch (延迟执行)"""
    global _original_urllib3_urlopen, _original_urllib3_connect
    if _original_urllib3_urlopen is None:
        _original_urllib3_urlopen = urllib3.connectionpool.HTTPConnectionPool.urlopen
        _original_urllib3_connect = urllib3.connectionpool.HTTPConnectionPool._make_request
        urllib3.connectionpool.HTTPConnectionPool.urlopen = _patched_urllib3_urlopen
        logger.info("已添加 urllib3 patch")

# ==================== 数据获取服务 ====================

class EastMoneyService:
    """东方财富数据服务 - 使用 AKShare 原始 API"""
    
    def __init__(self):
        self._connected = False
    
    def _ensure_connected(self):
        """确保已启用反爬"""
        if not self._connected:
            enable_anti_scraping()
            self._connected = True
    
    def test_connection(self):
        """测试连接"""
        try:
            self._ensure_connected()
            logger.info("测试 AKShare 连接...")
            # 简单调用测试
            import akshare as ak
            ak.stock_zh_a_spot_em()
            logger.info("AKShare 连接成功")
            return True
        except Exception as e:
            logger.error(f"AKShare 连接失败: {e}")
            return False
    
    def get_industry_classify(self):
        """获取行业分类列表 - 使用 AKShare"""
        try:
            self._ensure_connected()
            logger.info("正在获取行业分类 (AKShare)...")
            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            
            logger.info(f"获取到 {len(df)} 条行业数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            industries = []
            for _, row in df.iterrows():
                name = str(row.get('同花顺行业', row.get('行业名称', ''))).strip()
                if name and name not in ['nan', 'None', '']:
                    industries.append({
                        'industry': name,
                        'code': '',
                    })
            
            logger.info(f"解析到 {len(industries)} 个行业分类")
            return industries
        except Exception as e:
            logger.error(f"获取行业分类失败: {e}")
            return []
    
    def get_industry_stocks(self, industry_name):
        """获取行业成分股 - 使用 AKShare"""
        try:
            self._ensure_connected()
            logger.info(f"正在获取 {industry_name} 成分股 (AKShare)...")
            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'industry': industry_name,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只成分股")
            return stocks
        except Exception as e:
            logger.error(f"获取 {industry_name} 成分股失败: {e}")
            return []
    
    def get_concept_classify(self):
        """获取概念分类列表 - 使用 AKShare"""
        try:
            self._ensure_connected()
            logger.info("正在获取概念分类 (AKShare)...")
            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_board_concept_name_em()
            
            logger.info(f"获取到 {len(df)} 条概念数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            concepts = []
            for _, row in df.iterrows():
                name = str(row.get('概念名称', row.get('concept_name', ''))).strip()
                if name and name not in ['nan', 'None', '']:
                    concepts.append({
                        'concept': name,
                        'code': '',
                    })
            
            logger.info(f"解析到 {len(concepts)} 个概念分类")
            return concepts
        except Exception as e:
            logger.error(f"获取概念分类失败: {e}")
            return []
    
    def get_concept_stocks(self, concept_name):
        """获取概念成分股 - 使用 AKShare"""
        try:
            self._ensure_connected()
            logger.info(f"正在获取 {concept_name} 成分股 (AKShare)...")
            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_board_concept_cons_em(symbol=concept_name)
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'concept': concept_name,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只成分股")
            return stocks
        except Exception as e:
            logger.error(f"获取 {concept_name} 成分股失败: {e}")
            return []
    
    def get_stock_basics(self):
        """获取全部A股列表 - 使用 AKShare"""
        try:
            self._ensure_connected()
            logger.info("正在获取股票列表 (AKShare)...")
            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                market = 'sh' if code.startswith('6') else 'sz'
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只股票")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []


# 单例服务
_service = None

def get_service():
    """获取东方财富服务单例"""
    global _service
    if _service is None:
        _service = EastMoneyService()
    return _service

# 兼容旧名称
get_eastmoney_service = get_service

            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                market = 'sh' if code.startswith('6') else 'sz'
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只股票")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []


# 单例服务
_service = None

def get_service():
    """获取东方财富服务单例"""
    global _service
    if _service is None:
        _service = EastMoneyService()
    return _service

# 兼容旧名称
get_eastmoney_service = get_service

            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                market = 'sh' if code.startswith('6') else 'sz'
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只股票")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []


# 单例服务
_service = None

def get_service():
    """获取东方财富服务单例"""
    global _service
    if _service is None:
        _service = EastMoneyService()
    return _service

# 兼容旧名称
get_eastmoney_service = get_service

            
            # 调用 AKShare 原始 API
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            logger.info(f"获取到 {len(df)} 条股票数据")
            if len(df) > 0:
                logger.debug(f"列名: {list(df.columns)}")
                logger.debug(f"前2条数据: {df.head(2).to_dict()}")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                market = 'sh' if code.startswith('6') else 'sz'
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                    })
            
            logger.info(f"解析到 {len(stocks)} 只股票")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []


# 单例服务
_service = None

def get_service():
    """获取东方财富服务单例"""
    global _service
    if _service is None:
        _service = EastMoneyService()
    return _service

# 兼容旧名称
get_eastmoney_service = get_service
