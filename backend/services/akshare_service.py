"""
BaoStock 数据服务 - 使用官方 API 接口
"""
import json
import time
import random
import logging
import warnings
import requests
import urllib3

# 导入压缩库
try:
    import brotli
except ImportError:
    brotli = None

try:
    import gzip
except ImportError:
    gzip = None

# 导入 baostock
try:
    import baostock as bs
except ImportError:
    bs = None

logger = logging.getLogger(__name__)

# ==================== 压缩响应处理 ====================

def _decompress_response_content(content):
    """解压响应内容 (支持 gzip 和 brotli)"""
    if not content or len(content) == 0:
        return content
    
    # 检查是否是压缩数据
    if len(content) >= 2:
        first_byte = content[0] if isinstance(content[0], int) else ord(content[0])
        second_byte = content[1] if isinstance(content[1], int) else ord(content[1])
        
        # gzip: 0x1f 0x8b
        if first_byte == 0x1f and second_byte == 0x8b:
            if gzip:
                try:
                    return gzip.decompress(content)
                except Exception as e:
                    logger.debug(f"gzip 解压失败: {e}")
        
        # brotli: 0x1f 0x9e
        elif first_byte == 0x1f and second_byte == 0x9e:
            if brotli:
                try:
                    return brotli.decompress(content)
                except Exception as e:
                    logger.debug(f"brotli 解压失败: {e}")
    
    return content


class DecompressHTTPAdapter(requests.adapters.HTTPAdapter):
    """自定义 HTTPAdapter - 自动解压 gzip/brotli 压缩的响应"""
    
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        """发送请求并自动解压响应"""
        # 调用原始的 send 方法
        response = super().send(request, stream, timeout, verify, cert, proxies)
        
        # 检查是否需要解压
        if response.status_code == 200:
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            
            # 解压 gzip
            if 'gzip' in content_encoding:
                decompressed = _decompress_response_content(response.content)
                if decompressed != response.content:
                    logger.debug(f"[DecompressAdapter] gzip 解压: {len(response.content)} -> {len(decompressed)}")
                    response._content = decompressed
            
            # 解压 brotli
            elif 'br' in content_encoding:
                decompressed = _decompress_response_content(response.content)
                if decompressed != response.content:
                    logger.debug(f"[DecompressAdapter] brotli 解压: {len(response.content)} -> {len(decompressed)}")
                    response._content = decompressed
            
            # 或者检查 magic bytes
            elif response.content and len(response.content) >= 2:
                first_byte = response.content[0] if isinstance(response.content[0], int) else ord(response.content[0])
                second_byte = response.content[1] if isinstance(response.content[1], int) else ord(response.content[1])
                
                if first_byte == 0x1f and second_byte == 0x9e:  # brotli
                    decompressed = _decompress_response_content(response.content)
                    if decompressed != response.content:
                        logger.debug(f"[DecompressAdapter] brotli 解压(magic): {len(response.content)} -> {len(decompressed)}")
                        response._content = decompressed
                elif first_byte == 0x1f and second_byte == 0x8b:  # gzip
                    decompressed = _decompress_response_content(response.content)
                    if decompressed != response.content:
                        logger.debug(f"[DecompressAdapter] gzip 解压(magic): {len(response.content)} -> {len(decompressed)}")
                        response._content = decompressed
            
            # 打印解压后的数据预览（如果是 JSON 响应）
            try:
                content_str = response.text.strip()
                if content_str.startswith('{') or content_str.startswith('['):
                    # 尝试解析 JSON
                    try:
                        data = json.loads(content_str)
                        logger.info(f"[DecompressAdapter] ✅ 解压成功，JSON 解析成功!")
                        logger.info(f"[DecompressAdapter] 数据类型: {type(data).__name__}")
                        
                        # 如果是 dict，打印关键字段
                        if isinstance(data, dict):
                            logger.info(f"[DecompressAdapter] JSON 键: {list(data.keys())}")
                            # 打印 data 字段的内容预览
                            if 'data' in data:
                                data_inner = data['data']
                                if isinstance(data_inner, dict) and 'total' in data_inner:
                                    logger.info(f"[DecompressAdapter] 数据总数: {data_inner.get('total')} 条")
                                elif isinstance(data_inner, list):
                                    logger.info(f"[DecompressAdapter] 数据列表: {len(data_inner)} 条")
                                    if len(data_inner) > 0:
                                        logger.info(f"[DecompressAdapter] 第一条数据预览: {data_inner[0]}")
                        # 如果是 list
                        elif isinstance(data, list):
                            logger.info(f"[DecompressAdapter] 数组长度: {len(data)}")
                            if len(data) > 0:
                                logger.info(f"[DecompressAdapter] 第一个元素预览: {data[0]}")
                        
                        # 打印原始 JSON 字符串预览
                        preview = content_str[:800]
                        logger.info(f"[DecompressAdapter] 原始JSON预览:\n{preview}...")
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"[DecompressAdapter] JSON 解析失败: {e}")
                        preview = content_str[:500]
                        logger.debug(f"[DecompressAdapter] 原始内容预览:\n{preview}...")
            except Exception as e:
                logger.debug(f"[DecompressAdapter] 打印数据失败: {e}")
        
        return response

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

# ==================== 指纹伪装配置 ====================

# 常见的屏幕分辨率
SCREEN_RESOLUTIONS = [
    "1920x1080",
    "1366x768",
    "1536x864",
    "1440x900",
    "1280x720",
]

# 常见时区偏移
TIMEZONE_OFFSETS = [
    "UTC-8",
    "UTC-7",
    "UTC",
    "UTC+8",    # 中国标准时间
]

# Chrome Client Hints 对应的品牌版本
CHROME_VERSIONS = [
    "120.0.0.0",
    "119.0.0.0",
    "118.0.0.0",
    "121.0.0.0",
]

# 平台信息
PLATFORMS = [
    "Windows NT 10.0; Win64; x64",
    "Macintosh; Intel Mac OS X 10_15_7",
    "X11; Linux x86_64",
]

def _get_random_fingerprint():
    """生成完整的浏览器指纹 headers"""
    ua = random.choice(USER_AGENTS)
    screen = random.choice(SCREEN_RESOLUTIONS)
    timezone = random.choice(TIMEZONE_OFFSETS)
    chrome_ver = random.choice(CHROME_VERSIONS)
    platform = random.choice(PLATFORMS)
    
    # 根据 UA 推断平台
    if "Windows" in ua:
        platform = "Windows"
        sec_ch_ua = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    elif "Macintosh" in ua:
        platform = "macOS"
        sec_ch_ua = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    else:
        platform = "Linux"
        sec_ch_ua = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    
    return {
        # 基础 Headers
        'User-Agent': ua,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://datacenter.eastmoney.com/',
        'Origin': 'https://datacenter.eastmoney.com',
        
        # 🔐 Chrome User Agent Client Hints (指纹伪装关键)
        'Sec-Ch-Ua': sec_ch_ua,
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': f'"{platform}"',
        'Sec-Ch-Ua-Platform-Version': f'"{random.choice(["10.0", "14.0", "15.0", "16.0"])}"',
        'Sec-Ch-Ua-Model': '""',
        'Sec-Ch-Ua-Full-Version': f'"{chrome_ver}"',
        'Sec-Ch-Ua-Full-Version-List': sec_ch_ua,
        
        # 🔐 Fetch Metadata (防止被识别为爬虫)
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        
        # 🔐 其他指纹伪装
        'DNT': '1',  # Do Not Track
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        
        # 非标准但有指纹价值的 Headers
        'X-Requested-With': 'XMLHttpRequest',
        'X-DevTools-Emulate-Network-Conditions-Client-Id': str(random.randint(1000000000000, 9999999999999)),
    }

# 存储上一个请求的 fingerprint，用于模拟浏览器行为
_last_fingerprint = {}

# ==================== 反爬机制配置 ====================

# 原始请求方法
_original_request = requests.Session.request
_original_get = requests.get

# 请求间隔 - 增加间隔避免触发反爬
_last_request_time = 0
_request_interval = 8  # 8秒间隔 - 东方财富限制较严格

def _get_random_headers():
    """生成随机浏览器 headers - 使用完整的指纹伪装"""
    return _get_random_fingerprint()

def _patched_request(self, method, url, **kwargs):
    """带反爬机制的 requests.Session.request"""
    global _last_request_time
    
    # 计算延时 - 增加随机性避免被识别为爬虫
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < _request_interval:
        wait_time = _request_interval - elapsed
        # 添加随机抖动 (2-4秒)
        wait_time += random.uniform(2, 4)
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
        wait_time += random.uniform(1, 2)
        logger.debug(f"请求延时: {wait_time:.1f} 秒 (requests.get)")
        time.sleep(wait_time)
    
    _last_request_time = time.time()
    
    # 添加随机 headers
    headers = kwargs.get('headers', {})
    headers.update(_get_random_headers())
    kwargs['headers'] = headers
    
    return _original_get(url, **kwargs)

def enable_anti_scraping():
    """启用反爬机制 (安装自定义 HTTPAdapter + urllib3 patch)"""
    global _last_request_time
    _last_request_time = 0
    
    # 安装自定义 HTTPAdapter（自动解压响应）
    requests.Session().mount('http://', DecompressHTTPAdapter())
    requests.Session().mount('https://', DecompressHTTPAdapter())
    
    # 安装到全局的 adapters
    requests.adapters.HTTPAdapter = DecompressHTTPAdapter
    
    # 保留请求延迟和 headers 伪装
    requests.Session.request = _patched_request
    requests.get = _patched_get
    
    # 初始化 urllib3 patch（解压 gzip/brotli）
    _init_urllib3_patch()
    
    logger.info("已启用反爬机制 (DecompressHTTPAdapter + urllib3 patch + 请求延迟)")
    
    logger.info("已启用反爬机制 (DecompressHTTPAdapter + 请求延迟)")

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

# 用于存储原始 response 类
_original_response = None

def _patched_urllib3_urlopen(self, method, url, body=None, headers=None, **kwargs):
    """带反爬的 urllib3 urlopen - 支持 gzip/brotli 解压"""
    global _last_request_time
    current_time = time.time()
    elapsed = current_time - _last_request_time
    if elapsed < _request_interval:
        wait_time = _request_interval - elapsed
        # 添加随机抖动 (2-4秒)
        wait_time += random.uniform(2, 4)
        logger.debug(f"请求延时: {wait_time:.1f} 秒 (urllib3)")
        time.sleep(wait_time)
    _last_request_time = time.time()
    
    # 添加 headers
    pool_headers = getattr(self, 'headers', {})
    if headers:
        pool_headers = {**pool_headers, **headers}
    if 'User-Agent' not in pool_headers:
        pool_headers.update(_get_random_headers())
    
    response = _original_urllib3_urlopen(self, method, url, body, pool_headers, **kwargs)
    
    # 处理压缩响应 (gzip/brotli)
    try:
        # 首先尝试读取原始数据
        data = response.data
        response_headers = dict(response.headers)
        content_encoding = response_headers.get('Content-Encoding', '').lower()
        
        # 如果数据为空，尝试直接读取响应
        if data is None or len(data) == 0:
            logger.debug("[urllib3] data为空，尝试读取响应...")
            try:
                # 尝试从 HTTPResponse 对象读取数据
                if hasattr(response, 'read'):
                    data = response.read()
                    logger.debug(f"[urllib3] 从 response.read() 获取到 {len(data) if data else 0} 字节")
            except Exception as e:
                logger.debug(f"[urllib3] response.read() 失败: {e}")
                data = None
        
        if data and len(data) > 0:
            # 检查压缩类型
            is_gzip = False
            is_brotli = False
            first_byte = data[0] if isinstance(data[0], int) else ord(data[0])
            second_byte = data[1] if isinstance(data[1], int) else ord(data[1])
            is_gzip = (first_byte == 0x1f and second_byte == 0x8b)
            is_brotli = (first_byte == 0x1f and second_byte == 0x9e)
            
            logger.debug(f"[urllib3] data长度: {len(data)}, Content-Encoding: {content_encoding}, is_gzip={is_gzip}, is_brotli={is_brotli}")
            
            decompressed_data = None
            
            # 解压 gzip
            if content_encoding == 'gzip' or is_gzip:
                logger.info("检测到 gzip 压缩，自动解压...")
                import gzip
                try:
                    decompressed_data = gzip.decompress(data)
                    logger.info(f"gzip 解压后数据长度: {len(decompressed_data)}")
                except Exception as e:
                    logger.warning(f"gzip 解压失败: {e}")
            
            # 解压 brotli
            elif content_encoding in ('br', 'brotli') or is_brotli:
                logger.info("检测到 brotli 压缩，自动解压...")
                try:
                    import brotli
                    decompressed_data = brotli.decompress(data)
                    logger.info(f"brotli 解压后数据长度: {len(decompressed_data)}")
                except Exception as e:
                    logger.warning(f"brotli 解压失败: {e}")
            
            # 如果解压成功，更新响应对象
            if decompressed_data is not None:
                # 更新 urllib3 response 的 __dict__
                response.__dict__['_data'] = decompressed_data
                response.__dict__['_HTTPResponse__data'] = decompressed_data
                response.__dict__['_body'] = decompressed_data
                
                # 记录响应内容预览
                try:
                    data_str = decompressed_data[:200].decode('utf-8', errors='ignore')
                    logger.debug(f"解压后响应内容预览: {data_str[:500]}")
                except:
                    pass
                
                # 【关键修复】直接更新 requests.Response._content
                # 获取当前活跃的 connection，查找 requests.Response
                try:
                    # 方式: 从 HTTPConnectionPool 的 connections 列表中查找
                    if hasattr(response, '_pool') and hasattr(response._pool, '_pool'):
                        pool = response._pool
                        if hasattr(pool, '_connections') and hasattr(pool._connections, 'values'):
                            for conn in pool._connections.values():
                                if hasattr(conn, '_response') and conn._response is not None:
                                    resp = conn._response
                                    # 直接设置 _content
                                    if hasattr(resp, '_content'):
                                        resp._content = decompressed_data
                                        logger.debug(f"[urllib3] 已更新 requests.Response._content: {len(decompressed_data)} 字节")
                                    # 也保存到 __dict__
                                    resp.__dict__['_content'] = decompressed_data
                                    resp.__dict__['_decompressed'] = decompressed_data
                                    logger.debug(f"[urllib3] 已更新 requests.Response.__dict__")
                                    break
                except Exception as e:
                    logger.debug(f"[urllib3] 更新 requests.Response 失败: {e}")
    except Exception as e:
        logger.warning(f"处理响应数据失败: {e}")
        import traceback
        logger.debug(f"详细错误: {traceback.format_exc()}")
    
    return response

_original_data_getter = None  # 用于 urllib3 HTTPResponse.data 的原始 getter
_original_get_json = None
_original_response_class = None
_original_response_content = None

def _patched_response_json(self, **kwargs):
    """处理 gzip/brotli 压缩的 Response.json() - 直接从 urllib3 response 获取解压数据"""
    logger.debug(f"[json patch] r.json() 被调用")
    
    import json as json_module
    
    # 方法1: 直接从底层 urllib3 response 获取解压后的数据
    _raw = getattr(self, 'raw', None)
    if _raw is not None:
        # 方式1a: 从 __dict__ 获取 _decompressed
        decompressed_data = _raw.__dict__.get('_decompressed')
        if decompressed_data:
            logger.debug(f"[json patch] 从 raw.__dict__['_decompressed'] 获取到 {len(decompressed_data)} 字节")
            
            # 检查是否是压缩数据（如果是，需要再次解压）
            if len(decompressed_data) >= 2:
                first_byte = decompressed_data[0] if isinstance(decompressed_data[0], int) else ord(decompressed_data[0])
                second_byte = decompressed_data[1] if isinstance(decompressed_data[1], int) else ord(decompressed_data[1])
                is_gzip = (first_byte == 0x1f and second_byte == 0x8b)
                is_brotli = (first_byte == 0x1f and second_byte == 0x9e)
                
                if is_gzip or is_brotli:
                    # 数据还是压缩的，需要再次解压
                    compression = "brotli" if is_brotli else "gzip"
                    logger.debug(f"[json patch] 检测到 {compression} 压缩，再次解压...")
                    try:
                        if is_gzip:
                            import gzip
                            final_data = gzip.decompress(decompressed_data)
                        else:
                            import brotli
                            final_data = brotli.decompress(decompressed_data)
                        logger.debug(f"[json patch] 再次解压成功: {len(decompressed_data)} -> {len(final_data)}")
                        return json_module.loads(final_data)
                    except Exception as e:
                        logger.warning(f"[json patch] 再次解压失败: {e}")
            
            # 数据已是解压后的 JSON，直接解析
            try:
                result = json_module.loads(decompressed_data)
                logger.debug(f"[json patch] JSON 解析成功")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"[json patch] raw.__dict__['_decompressed'] JSON 解析失败: {e}")
        
        # 方式1b: 从 _raw._body 获取
        _body = getattr(_raw, '_body', None)
        if _body and isinstance(_body, bytes):
            try:
                body_str = _body.decode('utf-8', errors='ignore')
                if body_str.strip().startswith('{'):
                    logger.debug(f"[json patch] 从 raw._body 获取到解压后的 JSON")
                    return json_module.loads(_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    
    # 方法2: 检查 _content 是否已经是解压后的 JSON
    _content = getattr(self, '_content', None)
    if _content and isinstance(_content, bytes):
        try:
            content_str = _content.decode('utf-8', errors='ignore')
            if content_str.strip().startswith('{'):
                logger.debug(f"[json patch] _content 已是解压后的 JSON，直接解析")
                return json_module.loads(_content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        
        # 尝试解压 _content
        try:
            first_byte = _content[0] if isinstance(_content[0], int) else ord(_content[0])
            second_byte = _content[1] if isinstance(_content[1], int) else ord(_content[1])
            
            # gzip
            if first_byte == 0x1f and second_byte == 0x8b:
                import gzip
                decompressed = gzip.decompress(_content)
                logger.debug(f"[json patch] gzip 解压成功: {len(_content)} -> {len(decompressed)}")
                return json_module.loads(decompressed)
            
            # brotli
            elif first_byte == 0x1f and second_byte == 0x9e:
                import brotli
                decompressed = brotli.decompress(_content)
                logger.debug(f"[json patch] brotli 解压成功: {len(_content)} -> {len(decompressed)}")
                return json_module.loads(decompressed)
        except Exception as e:
            logger.warning(f"[json patch] _content 解压失败: {e}")
    
    # 方法3: 调用原始方法（如果数据已正确解压）
    try:
        return _original_get_json(self, **kwargs)
    except json.JSONDecodeError as e:
        logger.warning(f"[json patch] 原始 json() 失败: {e}")
def _patched_response_json(self, **kwargs):
    """处理 gzip/brotli 压缩的 Response.json() - 直接从 urllib3 response 获取已解压的数据"""
    import json as json_module
    
    logger.debug(f"[json patch] r.json() 被调用")
    
    # 直接从底层 urllib3 response 获取已解压的数据
    _raw = getattr(self, 'raw', None)
    if _raw is not None:
        logger.debug(f"[json patch] _raw 类型: {type(_raw)}")
        
        # 从 __dict__ 获取已解压的数据
        raw_dict = getattr(_raw, '__dict__', {})
        
        # 优先从 _body 获取（_patched_urllib3_urlopen 保存的数据）
        data = raw_dict.get('_body') or raw_dict.get('_data')
        
        if data:
            logger.debug(f"[json patch] 从 _raw.__dict__ 获取到数据: {len(data)} 字节")
            
            # 检查是否需要解压
            if len(data) >= 2:
                first_byte = data[0] if isinstance(data[0], int) else ord(data[0])
                second_byte = data[1] if isinstance(data[1], int) else ord(data[1])
                is_gzip = (first_byte == 0x1f and second_byte == 0x8b)
                is_brotli = (first_byte == 0x1f and second_byte == 0x9e)
                
                if is_gzip or is_brotli:
                    compression = "brotli" if is_brotli else "gzip"
                    logger.debug(f"[json patch] 检测到 {compression}，尝试解压...")
                    try:
                        if is_gzip:
                            import gzip
                            decompressed = gzip.decompress(data)
                        else:
                            import brotli
                            decompressed = brotli.decompress(data)
                        logger.debug(f"[json patch] {compression} 解压成功: {len(data)} -> {len(decompressed)}")
                        return json_module.loads(decompressed)
                    except Exception as e:
                        logger.warning(f"[json patch] {compression} 解压失败: {e}")
            
            # 数据已是解压后的 JSON，直接解析
            try:
                logger.debug(f"[json patch] 直接解析 JSON")
                return json_module.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(f"[json patch] JSON 解析失败: {e}")
    
    # 兜底：调用原始方法
    try:
        return _original_get_json(self, **kwargs)
    except json.JSONDecodeError as e:
        logger.warning(f"[json patch] 原始 json() 失败: {e}")
        raise

def _ensure_decompressed_content(response):
    """确保 response.content 是解压后的数据"""
    # 直接访问 _content（绕过 property）
    content = getattr(response, '_content', None)
    
    # 如果 _content 已经有解压后的数据，跳过
    if content is not None and len(content if isinstance(content, bytes) else b'') > 0:
        # 检查是否已经是解压后的数据（不是压缩格式）
        if len(content) >= 2:
            first_byte = content[0] if isinstance(content[0], int) else ord(content[0])
            second_byte = content[1] if isinstance(content[1], int) else ord(content[1])
            # 如果不是 gzip 或 brotli 格式，说明已经解压
            if not ((first_byte == 0x1f and second_byte == 0x8b) or (first_byte == 0x1f and second_byte == 0x9e)):
                return
        # 有数据且已解压，跳过
        return
    
    # _content 为空，尝试从底层 response 获取解压后的数据
    # 尝试多种方式获取解压后的数据
    decompressed_data = None
    
    # 方式1: 检查 _response (urllib3 response)
    _response = getattr(response, '_response', None)
    if _response is not None:
        # 尝试获取 _decompressed 属性
        decompressed_data = getattr(_response, '_decompressed', None)
        if decompressed_data is None:
            # 尝试从 __dict__ 获取
            decompressed_data = _response.__dict__.get('_decompressed')
    
    # 方式2: 如果有 _content 但为空，直接从 __dict__ 获取解压数据
    if decompressed_data is None:
        decompressed_data = response.__dict__.get('_decompressed')
    
    # 方式3: 检查原始 _body 是否已经是解压后的数据
    if decompressed_data is None:
        _body = getattr(response, '_body', None)
        if _body is not None and len(_body if isinstance(_body, bytes) else b'') > 0:
            # 检查是否是解压后的数据
            try:
                _body_str = _body.decode('utf-8', errors='ignore')
                if _body_str.startswith('{'):
                    decompressed_data = _body
            except Exception:
                pass
    
    # 更新 _content
    if decompressed_data is not None:
        response._content = decompressed_data
        logger.debug(f"[content patch] 已更新 response._content: {len(decompressed_data)} 字节")
        
        # 打印完整解压后的数据
        try:
            data_str = decompressed_data.decode('utf-8', errors='ignore')
            logger.info(f"[content patch] 解压后完整数据预览: {data_str[:500]}...")
            logger.info(f"[content patch] 解压后数据总长度: {len(decompressed_data)} 字节")
        except Exception as e:
            logger.debug(f"[content patch] 无法解码数据: {e}")

def _init_urllib3_patch():
    """初始化 urllib3 patch (延迟执行) - 支持 gzip/brotli 解压"""
    global _original_urllib3_urlopen, _original_urllib3_connect, _original_get_json, _original_response_class, _original_response_content, _original_data_getter
    import urllib3
    import urllib3.response
    import requests.models
    import requests
    
    if _original_urllib3_urlopen is None:
        _original_urllib3_urlopen = urllib3.connectionpool.HTTPConnectionPool.urlopen
        _original_urllib3_connect = urllib3.connectionpool.HTTPConnectionPool._make_request
        urllib3.connectionpool.HTTPConnectionPool.urlopen = _patched_urllib3_urlopen
        
        # 先保存原始 data getter（必须在定义 _decompressing_data 之前）
        _original_data_getter = urllib3.response.HTTPResponse.data
        
        @property
        def _decompressing_data(self):
            """直接读取 __dict__ 中的原始数据，避免递归调用"""
            logger.debug(f"[HTTPResponse.data] 被调用")
            
            # 首先检查是否已经有解压后的数据
            if '_decompressed' in self.__dict__ and self.__dict__.get('_decompressed'):
                logger.debug(f"[HTTPResponse.data] 返回已解压数据: {len(self.__dict__['_decompressed'])} 字节")
                return self.__dict__['_decompressed']
            
            # 直接从 __dict__ 读取原始压缩数据
            raw_data = self.__dict__.get('_body')
            logger.debug(f"[HTTPResponse.data] _body: {type(raw_data)}")
            
            # 如果 _body 为 None，尝试从 _fp 读取原始数据
            if raw_data is None or len(raw_data if raw_data else b'') == 0:
                _fp = self.__dict__.get('_fp')
                if _fp is not None:
                    logger.debug(f"[HTTPResponse.data] _body 为空，检查 _fp: {type(_fp)}")
                    # 检查是否是 http.client.HTTPResponse（标准库）
                    if _fp.__class__.__module__ == 'http.client' and _fp.__class__.__name__ == 'HTTPResponse':
                        try:
                            # 首先尝试从 _buffer 读取（这是存储压缩数据的地方）
                            if hasattr(_fp, '_buffer') and _fp._buffer:
                                raw_data = _fp._buffer
                                logger.debug(f"[HTTPResponse.data] 从 _fp._buffer 读取: {len(raw_data)} 字节")
                            # 如果 _buffer 为空，尝试 read() 方法
                            elif hasattr(_fp, 'readable') and _fp.readable():
                                raw_data = _fp.read()
                                logger.debug(f"[HTTPResponse.data] 从 _fp.read() 读取: {len(raw_data)} 字节")
                        except Exception as e:
                            logger.debug(f"[HTTPResponse.data] 读取 _fp 失败: {e}")
            
            if raw_data is None:
                logger.debug(f"[HTTPResponse.data] raw_data is None, returning None")
                return None
            
            if not isinstance(raw_data, (bytes, bytearray)):
                logger.debug(f"[HTTPResponse.data] raw_data 不是 bytes: {type(raw_data)}")
                return None
            
            if len(raw_data) == 0:
                logger.debug(f"[HTTPResponse.data] raw_data 为空 (0 字节), 返回 None")
                return None
            
            logger.debug(f"[HTTPResponse.data] 原始数据: {len(raw_data)} 字节")
            
            # 【关键调试】打印前4个字节用于判断压缩格式
            if len(raw_data) >= 4:
                hex_preview = ' '.join(f'{b:02x}' for b in raw_data[:4])
                logger.debug(f"[HTTPResponse.data] 前4字节 hex: {hex_preview}")
            
            # 检查是否需要解压
            decompressed_data = raw_data  # 默认不解压
            
            if len(raw_data) >= 2:
                first_byte = raw_data[0] if isinstance(raw_data[0], int) else ord(raw_data[0])
                second_byte = raw_data[1] if isinstance(raw_data[1], int) else ord(raw_data[1])
                
                is_gzip = (first_byte == 0x1f and second_byte == 0x8b)
                is_brotli = (first_byte == 0x1f and second_byte == 0x9e)
                logger.debug(f"[HTTPResponse.data] is_gzip={is_gzip}, is_brotli={is_brotli}")
                
                # gzip: 0x1f 0x8b
                if is_gzip:
                    try:
                        import gzip
                        decompressed_data = gzip.decompress(raw_data)
                        logger.debug(f"[HTTPResponse.data] gzip 解压: {len(raw_data)} -> {len(decompressed_data)}")
                    except Exception as e:
                        logger.warning(f"[HTTPResponse.data] gzip 解压失败: {e}")
                        return raw_data  # 解压失败返回原始数据
                
                # brotli: 0x1f 0x9e
                elif is_brotli:
                    try:
                        import brotli
                        decompressed_data = brotli.decompress(raw_data)
                        logger.debug(f"[HTTPResponse.data] brotli 解压: {len(raw_data)} -> {len(decompressed_data)}")
                    except Exception as e:
                        logger.warning(f"[HTTPResponse.data] brotli 解压失败: {e}")
                        return raw_data  # 解压失败返回原始数据
            
            # 保存解压后的数据
            self.__dict__['_decompressed'] = decompressed_data
            self.__dict__['_data'] = decompressed_data
            self.__dict__['_body'] = decompressed_data
            
            # 验证保存的数据
            saved = self.__dict__.get('_decompressed')
            logger.debug(f"[HTTPResponse.data] 验证保存: 长度={len(saved) if saved else 'N/A'}")
            
            # 打印完整解压后的数据
            try:
                data_str = decompressed_data.decode('utf-8', errors='ignore')
                logger.info(f"[HTTPResponse.data] 解压后完整数据预览: {data_str[:200]}...")
                logger.info(f"[HTTPResponse.data] 解压后数据总长度: {len(decompressed_data)} 字节")
            except Exception as e:
                logger.debug(f"[HTTPResponse.data] 无法解码解压后的数据: {e}")
            
            logger.debug(f"[HTTPResponse.data] 已保存解压数据到 __dict__，长度: {len(decompressed_data)}")
            return decompressed_data
        
        urllib3.response.HTTPResponse.data = _decompressing_data
        logger.info("已添加 urllib3.response.HTTPResponse.data patch (gzip/brotli 解压)")
        
        # Patch requests.Response.content - 在读取时自动解压
        import requests.models
        import requests
        
        if _original_response_content is None and hasattr(requests.models.Response, 'content'):
            _original_response_content = property(requests.models.Response.content.fget, requests.models.Response.content.fset)
            
            @property
            def _patched_content(self):
                # 调用原始 getter
                content = _original_response_content.fget(self)
                # 解压 gzip/brotli
                _ensure_decompressed_content(self)
                # 再次调用原始 getter（现在 content 已经被解压了）
                return _original_response_content.fget(self)
            
            requests.models.Response.content = _patched_content
            requests.Response.content = _patched_content
            logger.info("已添加 requests.Response.content patch (gzip/brotli 解压)")
        
        # Patch json() 方法
        if _original_get_json is None:
            _original_get_json = requests.models.Response.json
            requests.models.Response.json = _patched_response_json
            
            # 更新 Response 类
            if _original_response_class is None and hasattr(requests, 'Response'):
                _original_response_class = requests.Response
                
                class PatchedResponse(_original_response_class):
                    @property
                    def content(self):
                        # 调用原始 getter
                        content = _original_response_content.fget(self) if _original_response_content else super().content
                        # 解压
                        _ensure_decompressed_content(self)
                        # 返回解压后的
                        return _original_response_content.fget(self) if _original_response_content else super().content
                
                requests.Response = PatchedResponse
                logger.info("已添加 requests.Response 类 patch (gzip/brotli 处理)")
        
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
                name = str(row.get('板块名称', row.get('同花顺行业', row.get('行业名称', '')))).strip()
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
                # 尝试多种可能的列名
                name = str(row.get('概念名称') or row.get('concept_name') or row.get('板块名称') or row.get('name') or '').strip()
                if name and name not in ['nan', 'None', '']:
                    concepts.append({
                        'concept': name,
                        'code': row.get('概念代码', row.get('concept_code', row.get('板块代码', ''))),
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
        """获取全部A股列表 - 使用 BaoStock 官方接口"""
        if bs is None:
            logger.error("BaoStock 库未安装，请运行: pip install baostock")
            return self._get_stock_basics_fallback()
        
        logger.info(f"正在获取股票列表 (BaoStock 官方接口)...")
        
        all_stocks = []
        success_count = 0
        
        try:
            # 登录 BaoStock
            lg = bs.login()
            
            if lg.error_code != '0':
                logger.error(f"BaoStock 登录失败: {lg.error_code} - {lg.error_msg}")
                bs.logout()
                return self._get_stock_basics_fallback()
            
            logger.info(f"BaoStock 登录成功")
            
            # 使用 query_stock_basic 获取所有 A 股基础信息
            # 不传 code 参数则获取所有股票
            logger.info(f"开始查询股票基本信息...")
            rs = bs.query_stock_basic()
            
            logger.info(f"BaoStock query_stock_basic 返回: error_code={rs.error_code}, error_msg={rs.error_msg}")
            logger.info(f"BaoStock response 类型: {type(rs)}")
            
            # 调试：查看返回属性
            logger.info(f"BaoStock fields: {rs.fields}")
            logger.info(f"BaoStock data 类型: {type(rs.data)}, 长度: {len(rs.data) if rs.data else 0}")
            
            # 统计总行数
            row_count = 0
            if rs.data:
                row_count = len(rs.data)
            logger.info(f"BaoStock 数据总行数: {row_count}")
            
            # 遍历数据
            page_count = 0
            total_count = 0
            
            # 调试：打印前3条数据的详细信息
            debug_count = 0
            for i, row in enumerate(rs.data, 1):
                # 调试前3条数据
                if debug_count < 3:
                    logger.info(f"BaoStock 调试[{debug_count+1}]: type={type(row)}, row={row}")
                    debug_count += 1
                
                page_count += 1
                stock_data = row
                
                # BaoStock data 格式检查
                if not stock_data:
                    continue
                
                # 调试：打印每条数据的详细信息（限制前10条）
                if page_count <= 10:
                    logger.info(f"BaoStock 调试[{page_count}]: stock_data={stock_data}, type={type(stock_data)}, len={len(stock_data) if hasattr(stock_data, '__len__') else 'N/A'}")
                
                # 如果 stock_data 是字符串，尝试解析
                if isinstance(stock_data, str):
                    logger.info(f"BaoStock stock_data 是字符串: {stock_data[:100]}...")
                    continue
                
                # 解析字段 - BaoStock fields: ['code', 'code_name', 'ipoDate', 'outDate', 'type', 'status']
                # 注意：没有 'market' 字段，需要从 'type' 字段判断
                if len(stock_data) >= 2:
                    code_with_prefix = str(stock_data[0]).strip() if stock_data[0] else ''
                    name = str(stock_data[1]).strip() if stock_data[1] else ''  # code_name
                    ipo_date = str(stock_data[2]).strip() if len(stock_data) > 2 and stock_data[2] else ''  # ipoDate
                    out_date = str(stock_data[3]).strip() if len(stock_data) > 3 and stock_data[3] else ''  # outDate
                    stock_type = str(stock_data[4]).strip() if len(stock_data) > 4 and stock_data[4] else ''  # type
                    status = str(stock_data[5]).strip() if len(stock_data) > 5 and stock_data[5] else ''  # status
                else:
                    code_with_prefix = ''
                    name = ''
                    ipo_date = ''
                    out_date = ''
                    stock_type = ''
                    status = ''
                
                # 提取纯数字代码 (去除市场前缀，如 sh.600000 -> 600000)
                if '.' in code_with_prefix:
                    code = code_with_prefix.split('.')[-1]
                else:
                    code = code_with_prefix
                
                # 判断市场类型 (从 type 字段: 1=主板, 2=指数, 3=创业板, 4=科创板, 5=B股, 6=基金, 7=债券, 8=港股)
                # 只保留 A 股: 沪市 'sh' (sz.000001) 和深市 'sz' (sz.000001)
                # BaoStock 的市场前缀已经包含在 code 中: sh.xxx 或 sz.xxx
                market_prefix = ''
                if code_with_prefix.startswith('sh.'):
                    market_prefix = 'sh'
                elif code_with_prefix.startswith('sz.'):
                    market_prefix = 'sz'
                
                # 调试前几条数据
                if page_count <= 3:
                    logger.info(f"BaoStock 解析结果[{page_count}]: code_with_prefix={code_with_prefix}, code={code}, market={market_prefix}, type={stock_type}, name={name}")
                
                # 解析字段类型映射 (BaoStock type字段)
                # 1=股票, 2=指数, 3=其它, 4=可转债, 5=ETF
                stock_type_map = {
                    '1': 'stock',    # 股票
                    '2': 'index',    # 指数
                    '3': 'other',    # 其它
                    '4': 'bond',     # 可转债
                    '5': 'etf',      # ETF
                }
                
                # 从 type 字段获取类型
                type_code = stock_type_map.get(stock_type, 'other')
                
                # 构建复合 market 字段: {type}_{market}
                # 例如: stock_sh (沪市股票), index_sz (深市指数), etf_sh (沪市ETF)
                market = f"{type_code}_{market_prefix}" if market_prefix else type_code
                
                # 过滤有效的代码 (6位数字)
                is_valid = bool(code and len(code) == 6 and code.isdigit() and market_prefix in ['sh', 'sz'])
                
                if is_valid:
                    all_stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,  # 格式: stock_sh, index_sz, etf_sh 等
                        'type': type_code,  # 原始类型: stock, index, etf
                    })
                    total_count += 1
                
                # 每 1000 条保存一次
                if total_count > 0 and total_count % 1000 == 0:
                    saved = self._save_stocks_to_db(all_stocks)
                    logger.info(f"📊 BaoStock: 已保存 {total_count} 只股票...")
            
            # 登出
            bs.logout()
            logger.info(f"BaoStock 登出成功")
            
            # 最终保存
            if all_stocks:
                saved = self._save_stocks_to_db(all_stocks)
                logger.info(f"✅ BaoStock 数据获取完成: 共 {len(all_stocks)} 只股票")
            
            return all_stocks
            
        except Exception as e:
            logger.error(f"BaoStock 数据获取失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            # 尝试备用方案
            return self._get_stock_basics_fallback()
    
    def _get_stock_basics_fallback(self):
        """备用方案：使用东方财富 API"""
        logger.info(f"使用备用方案获取股票列表...")
        
        import akshare as ak
        
        try:
            df = ak.stock_zh_a_spot_em()
            
            if df is None or len(df) == 0:
                logger.warning("备用方案返回空数据")
                return []
            
            logger.info(f"✅ 备用方案 API 调用成功，获取 {len(df)} 条数据")
            
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('代码', row.get('code', ''))).strip()
                name = str(row.get('名称', row.get('name', ''))).strip()
                
                if '.' in code:
                    code = code.split('.')[0]
                
                if code and len(code) == 6 and code.isdigit():
                    stocks.append({
                        'code': code,
                        'name': name,
                    })
            
            # 保存到数据库
            if stocks:
                self._save_stocks_to_db(stocks)
                logger.info(f"✅ 备用方案: 保存 {len(stocks)} 只股票")
            
            return stocks
            
        except Exception as e:
            logger.error(f"备用方案也失败: {e}")
            return []

    def _save_stocks_to_db(self, stocks):
        """保存股票列表到数据库"""
        from models.stockbasic import StockBasic
        from app import db
        
        if not stocks:
            return 0
        
        saved_count = 0
        updated_count = 0
        
        try:
            for stock in stocks:
                code = stock['code']  # 纯数字代码
                name = stock['name']
                market = stock.get('market', '')  # 复合市场: stock_sh, index_sz, etf_sh 等
                stock_type = stock.get('type', 'stock')  # 原始类型: stock, index, etf
                
                # 构建完整的股票代码 (如 sh.600000)
                if 'sh' in market:
                    full_code = f'sh.{code}'
                    exchange = 'sh'
                elif 'sz' in market:
                    full_code = f'sz.{code}'
                    exchange = 'sz'
                else:
                    # 尝试根据代码前缀判断
                    if code.startswith('6'):
                        full_code = f'sh.{code}'
                        exchange = 'sh'
                    elif code.startswith(('0', '3')):
                        full_code = f'sz.{code}'
                        exchange = 'sz'
                    else:
                        full_code = code
                        exchange = ''
                
                # 查找是否已存在
                existing = StockBasic.query.filter_by(stock_code=full_code).first()
                
                if existing:
                    # 更新
                    existing.stock_name = name
                    existing.market = market
                    existing.stock_type = stock_type
                    existing.exchange = exchange
                    existing.update_time = db.func.now()
                    updated_count += 1
                else:
                    # 插入
                    new_stock = StockBasic(
                        stock_code=full_code,
                        stock_name=name,
                        exchange=exchange,
                        market=market,
                        stock_type=stock_type,
                        create_time=db.func.now(),
                        update_time=db.func.now()
                    )
                    db.session.add(new_stock)
                    saved_count += 1
            
            db.session.commit()
            logger.info(f"💾 数据库保存: 新增 {saved_count} 只，更新 {updated_count} 只")
            
        except Exception as e:
            logger.warning(f"保存股票数据失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            db.session.rollback()
            
        return saved_count

    def supplement_stock_individual_info(self, stock_codes=None):
        """
        通过AKShare获取并补充股票详细信息（东方财富个股信息）
        
        Args:
            stock_codes: 股票代码列表，如 ['sh.600000', 'sz.000001']，默认None表示全部
        
        Returns:
            dict: 处理结果
        """
        from models.stockbasic import StockBasic
        from app import db
        import time
        import random
        
        try:
            # 确保启用反爬机制
            self._ensure_connected()
            
            import akshare as ak
            
            # 如果没有指定股票代码，则获取所有股票
            if stock_codes is None:
                stocks = StockBasic.query.all()
                stock_codes = [s.stock_code for s in stocks]
            
            if not stock_codes:
                return {'success': 0, 'failed': 0, 'message': '没有股票需要补充信息'}
            
            logger.info(f"📊 开始补充 {len(stock_codes)} 只股票的详细信息")
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for i, stock_code in enumerate(stock_codes):
                try:
                    # 转换代码格式: sh.600000 -> 600000
                    symbol = stock_code.split('.')[-1]
                    
                    logger.info(f"📥 获取股票信息 [{i+1}/{len(stock_codes)}]: {stock_code}")
                    
                    # 调用东方财富个股信息接口
                    df = ak.stock_individual_info_em(symbol=symbol)
                    
                    if df is None or df.empty:
                        logger.warning(f"⚠️ 未获取到 {stock_code} 的信息")
                        failed_count += 1
                        continue
                    
                    # 调试：打印原始返回数据
                    logger.info(f"🔍 {stock_code} 原始返回数据类型: {type(df)}")
                    logger.info(f"🔍 {stock_code} DataFrame列名: {list(df.columns)}")
                    logger.info(f"🔍 {stock_code} DataFrame内容:\n{df.to_string()}")
                    # logger.info(f"🔍 {stock_code} DataFrame前3行:\n{df.head(3)}")
                    
                    # 解析数据 - AKShare新版本使用 'item' 和 'value' 列名
                    info_dict = {}
                    for _, row in df.iterrows():
                        field = row.get('item', '')
                        value = row.get('value', '')
                        if field and value is not None and str(value).strip():
                            info_dict[field] = value
                    
                    # 更新数据库
                    stock = StockBasic.query.filter_by(stock_code=stock_code).first()
                    if not stock:
                        logger.warning(f"⚠️ 数据库中找不到股票: {stock_code}")
                        failed_count += 1
                        continue
                    
                    logger.info(f"✅ 找到股票: {stock_code} - {stock.stock_name}")
                    
                    # 更新可用的字段 - AKShare返回的字段名是中文简体
                        update_fields = {
                            'company_name': info_dict.get('公司名称'),
                        'industry': info_dict.get('所属行业') or info_dict.get('行业'),
                        'area': info_dict.get('所在地区') or info_dict.get('地区'),
                        'total_shares': self._parse_number(info_dict.get('总股本(股)')) or self._parse_number(info_dict.get('总股本')),
                        'circulate_shares': self._parse_number(info_dict.get('流通股本(股)')) or self._parse_number(info_dict.get('流通股本')),
                        'total_market_value': self._parse_number(info_dict.get('总市值')),
                        'circulate_market_value': self._parse_number(info_dict.get('流通市值')),
                            'list_date': info_dict.get('上市日期'),
                            'is_hs': 1 if info_dict.get('沪深港通') == '是' else 0,
                        }
                        
                        # 调试：打印将要更新的字段
                        updateable = {k: v for k, v in update_fields.items() if v is not None}
                        logger.info(f"📝 {stock_code} 准备更新的字段: {updateable}")
                        
                        for field, value in update_fields.items():
                            if value is not None:
                                setattr(stock, field, value)
                        
                    from datetime import datetime
                    stock.update_time = datetime.now()
                    
                    success_count += 1
                    
                    # 随机延时，避免请求过快
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    logger.error(f"❌ 处理 {stock_code} 失败: {e}")
                    failed_count += 1
                    errors.append({'stock_code': stock_code, 'error': str(e)})
                    time.sleep(2)  # 失败后延长等待时间
            
            db.session.commit()
            
            result = {
                'success': success_count,
                'failed': failed_count,
                'total': len(stock_codes),
                'message': f'成功 {success_count} 只，失败 {failed_count} 只'
            }
            
            if errors:
                result['errors'] = errors[:10]  # 只保留前10个错误
            
            logger.info(f"✅ 股票详细信息补充完成: {result}")
            return result
            
        except ImportError as e:
            logger.error(f"AKShare 模块不可用: {e}")
            return {'success': 0, 'failed': 0, 'message': f'AKShare 模块不可用: {str(e)}'}
        except Exception as e:
            logger.exception("补充股票详细信息失败")
            return {'success': 0, 'failed': 0, 'message': str(e)}

    def _parse_number(self, value):
        """解析数值字符串为浮点数"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            # 移除可能的单位（万、亿等）
            value = str(value).strip()
            multipliers = {'万': 10000, '亿': 100000000, '千': 1000}
            for unit, mult in multipliers.items():
                if unit in value:
                    return float(value.replace(unit, '')) * mult
            return float(value)
        except (ValueError, TypeError):
            return None

# ==================== 单例服务 ====================
_service = None

def get_service():
    """获取东方财富服务单例"""
    global _service
    if _service is None:
        _service = EastMoneyService()
    return _service

# 兼容旧名称
get_eastmoney_service = get_service
