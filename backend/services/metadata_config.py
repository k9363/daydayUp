"""
元数据补充配置
提供元数据补充的统一配置和开关控制
"""

# 元数据补充配置
METADATA_SUPPLEMENT_CONFIG = {
    # 是否在数据同步时自动补充元数据
    'auto_supplement_on_sync': True,

    # 是否在复盘时自动补充元数据
    'auto_supplement_on_review': True,

    # 是否更新已存在的股票信息
    'update_existing_stocks': False,

    # 是否补充板块信息
    'supplement_sectors': True,

    # 是否补充股票-板块关联
    'supplement_relations': True,

    # 是否补充股票基本信息
    'supplement_stock_basic': True,

    # 板块类型配置
    'sector_types': ['industry', 'area'],  # 支持 industry(行业), concept(概念), area(地区)

    # 批量处理大小
    'batch_size': 100,

    # 请求间隔（秒），避免API限流
    'request_interval': 0.5,
}


def get_metadata_config(key):
    """
    获取配置值

    Args:
        key: 配置键名

    Returns:
        配置值，如果键不存在则返回None
    """
    return METADATA_SUPPLEMENT_CONFIG.get(key)


def set_metadata_config(key, value):
    """
    设置配置值

    Args:
        key: 配置键名
        value: 配置值
    """
    if key in METADATA_SUPPLEMENT_CONFIG:
        METADATA_SUPPLEMENT_CONFIG[key] = value


def is_auto_supplement_enabled(context='sync'):
    """
    检查指定场景下是否自动补充元数据

    Args:
        context: 场景，'sync' 或 'review'

    Returns:
        bool: 是否启用自动补充
    """
    if context == 'sync':
        return METADATA_SUPPLEMENT_CONFIG.get('auto_supplement_on_sync', True)
    elif context == 'review':
        return METADATA_SUPPLEMENT_CONFIG.get('auto_supplement_on_review', True)
    return True

