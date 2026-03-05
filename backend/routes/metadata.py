"""
元数据管理API路由
提供元数据的查询和补充功能
"""
import logging
from flask import Blueprint, request, jsonify
from services.metadata_service import get_metadata_service
from extensions import db
from models.stockbasic import StockBasic
from models.kline import StockSector, StockSectorRelation
from models.delivery import StockDelivery
import csv
import re
import io

logger = logging.getLogger(__name__)

# 在应用工厂中通过 url_prefix='/api/metadata' 统一配置前缀
metadata_bp = Blueprint('metadata', __name__)


@metadata_bp.route('/summary', methods=['GET'])
def get_summary():
    """获取元数据统计摘要"""
    try:
        service = get_metadata_service()
        summary = service.get_metadata_summary()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': summary
        })
        
    except Exception as e:
        logger.exception("获取元数据摘要失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/supplement', methods=['POST'])
def supplement_metadata():
    """
    综合元数据补充
    
    请求参数（可选）:
        - stock_codes: 股票代码列表
    """
    try:
        data = request.get_json() or {}
        stock_codes = data.get('stock_codes')
        
        service = get_metadata_service()
        result = service.supplement_metadata(stock_codes=stock_codes)
        
        return jsonify({
            'code': 200,
            'message': '元数据补充完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("元数据补充失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors/supplement', methods=['POST'])
def supplement_sectors():
    """
    补充板块信息
    
    请求参数:
        - sector_type: 板块类型 (industry/area/concept)，可选，默认全部
    """
    try:
        data = request.get_json() or {}
        sector_type = data.get('sector_type')
        
        service = get_metadata_service()
        result = service.supplement_sectors(sector_type=sector_type)
        
        return jsonify({
            'code': 200,
            'message': '板块信息补充完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("板块信息补充失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock-supplement', methods=['POST'])
def supplement_stock_basic():
    """
    补充股票基本信息（单只或指定股票）
    
    请求参数:
        - stock_codes: 股票代码列表
    """
    try:
        data = request.get_json()
        if not data or not data.get('stock_codes'):
            return jsonify({'code': 400, 'message': '请提供股票代码列表'}), 400
        
        stock_codes = data.get('stock_codes')
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        
        service = get_metadata_service()
        result = service.supplement_stock_basic(stock_codes)
        
        return jsonify({
            'code': 200,
            'message': '股票信息补充完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("股票信息补充失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock-supplement-all', methods=['POST'])
def supplement_all_stock_basic():
    """
    通过query_stock_basic API批量补充全部股票基本信息
    
    请求参数:
        - update_existing: 是否更新已存在的股票信息，默认true
    """
    try:
        data = request.get_json() or {}
        update_existing = data.get('update_existing', True)
        
        service = get_metadata_service()
        result = service.supplement_all_stock_basic(update_existing=update_existing)
        
        return jsonify({
            'code': 200,
            'message': '全部股票信息补充完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("批量补充股票信息失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/relations/supplement', methods=['POST'])
def supplement_relations():
    """
    补充股票-板块关联
    
    请求参数:
        - stock_codes: 股票代码列表（可选，不传则补充所有股票）
    """
    try:
        data = request.get_json() or {}
        stock_codes = data.get('stock_codes')
        
        # 如果没有提供股票代码，则获取所有股票
        if not stock_codes:
            from models.kline import StockBasic
            db = current_app.extensions.get('sqlalchemy')
            if db:
                all_stocks = db.session.query(StockBasic.stock_code).all()
                stock_codes = [s[0] for s in all_stocks]
        
        if not stock_codes:
            return jsonify({'code': 400, 'message': '没有可关联的股票'}), 400
        
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        
        service = get_metadata_service()
        result = service.supplement_stock_sector_relations(stock_codes)
        
        return jsonify({
            'code': 200,
            'message': '关联关系补充完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("关联关系补充失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock/sync', methods=['POST'])
def sync_stock_with_sectors():
    """
    同步单只股票的板块信息
    
    请求参数:
        - stock_code: 股票代码
    """
    try:
        data = request.get_json()
        if not data or not data.get('stock_code'):
            return jsonify({'code': 400, 'message': '请提供股票代码'}), 400
        
        stock_code = data.get('stock_code')
        
        service = get_metadata_service()
        success = service.sync_stock_with_sectors(stock_code)
        
        if success:
            return jsonify({
                'code': 200,
                'message': f'股票 {stock_code} 板块信息同步成功',
                'data': {'stock_code': stock_code}
            })
        else:
            return jsonify({
                'code': 404,
                'message': f'股票 {stock_code} 未找到板块信息',
                'data': {'stock_code': stock_code}
            })
        
    except Exception as e:
        logger.exception("同步股票板块信息失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock/<stock_code>', methods=['GET'])
def get_stock_info(stock_code):
    """获取股票基本信息和所属板块"""
    try:
        service = get_metadata_service()
        
        # 获取股票基本信息
        stock_basic = service.get_stock_basic(stock_code)
        
        # 获取所属板块
        sectors = service.get_stock_sectors(stock_code)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'stock_basic': stock_basic.to_dict() if stock_basic else None,
                'sectors': sectors
            }
        })
        
    except Exception as e:
        logger.exception("获取股票信息失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock/list', methods=['GET'])
def list_stocks():
    """获取股票列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 20, type=int)
        industry = request.args.get('industry')
        market = request.args.get('market')
        
        query = StockBasic.query
        
        if industry:
            query = query.filter(StockBasic.industry == industry)
        if market:
            query = query.filter(StockBasic.market == market)
        
        total = query.count()
        stocks = query.order_by(StockBasic.stock_code).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'total': total,
                'page': page,
                'pageSize': page_size,
                'list': [s.to_dict() for s in stocks]
            }
        })
        
    except Exception as e:
        logger.exception("获取股票列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors', methods=['GET'])
def list_sectors():
    """获取板块列表（支持搜索和分页）"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        sector_type = request.args.get('type')
        keyword = request.args.get('keyword', '').strip()
        
        query = StockSector.query
        if sector_type:
            query = query.filter(StockSector.sector_type == sector_type)
        if keyword:
            query = query.filter(StockSector.sector_name.like(f'%{keyword}%'))
        
        # 获取总数
        total = query.count()
        
        # 分页获取
        sectors = query.order_by(StockSector.stock_count.desc()).paginate(page=page, per_page=page_size, error_out=False)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': [s.to_dict() for s in sectors.items],
            'total': total,
            'page': page,
            'page_size': page_size
        })
        
    except Exception as e:
        logger.exception("获取板块列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors/<sector_code>/stocks', methods=['GET'])
def get_sector_stocks(sector_code):
    """获取板块下的股票列表（优化：使用JOIN查询，同时获取每只股票的所有板块）"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        keyword = request.args.get('keyword', '').strip()
        
        sector = StockSector.query.filter(
            StockSector.sector_code == sector_code
        ).first()
        
        if not sector:
            return jsonify({'code': 404, 'message': '板块不存在'}), 404
        
        # 使用LEFT JOIN查询：获取所有关联的股票，包括stock_basic中不存在的
        query = db.session.query(
            StockSectorRelation.stock_code,
            StockBasic
        ).outerjoin(
            StockBasic, StockSectorRelation.stock_code == StockBasic.stock_code
        ).filter(
            StockSectorRelation.sector_id == sector.id
        )

        if keyword:
            query = query.filter(
                db.or_(
                    StockSectorRelation.stock_code.like(f'%{keyword}%'),
                    StockBasic.stock_name.like(f'%{keyword}%')
                )
            )

        # 获取总数
        total = query.count()

        # 分页获取
        stocks_result = query.order_by(StockSectorRelation.stock_code).paginate(page=page, per_page=page_size, error_out=False)

        # 获取这些股票的板块信息
        stock_codes = [s[0] for s in stocks_result.items if s[0]]
        all_relations = db.session.query(StockSectorRelation, StockSector).join(
            StockSector, StockSectorRelation.sector_id == StockSector.id
        ).filter(
            StockSectorRelation.stock_code.in_(stock_codes)
        ).all()
        
        # 构建 stock_code -> [sectors] 映射
        stock_sectors_map = {}
        for rel, sec in all_relations:
            if rel.stock_code not in stock_sectors_map:
                stock_sectors_map[rel.stock_code] = []
            stock_sectors_map[rel.stock_code].append({
                'sector_code': sec.sector_code,
                'sector_name': sec.sector_name,
                'sector_type': sec.sector_type
            })

        # 构建返回数据
        stocks_data = []
        for s in stocks_result.items:
            rel_stock_code, basic = s
            # 处理stock_basic中不存在的股票
            stock_dict = {
                'id': basic.id if basic else None,
                'stock_code': rel_stock_code,
                'stock_name': basic.stock_name if basic and basic.stock_name else f'未知({rel_stock_code})',
                'exchange': basic.exchange if basic else None,
                'market': basic.market if basic else None,
                'company_name': basic.company_name if basic else None,
                'industry': basic.industry if basic else None,
                'area': basic.area if basic else None,
                'list_date': basic.list_date.strftime('%Y-%m-%d') if basic and basic.list_date else None,
                'delist_date': basic.delist_date.strftime('%Y-%m-%d') if basic and basic.delist_date else None,
                'is_hs': basic.is_hs if basic else 0,
                'total_shares': float(basic.total_shares) if basic and basic.total_shares else None,
                'circulate_shares': float(basic.circulate_shares) if basic and basic.circulate_shares else None,
                'total_market_value': float(basic.total_market_value) if basic and basic.total_market_value else None,
                'circulate_market_value': float(basic.circulate_market_value) if basic and basic.circulate_market_value else None,
                'remarks': basic.remarks if basic else None,
                'create_time': basic.create_time.strftime('%Y-%m-%d %H:%M:%S') if basic and basic.create_time else None,
                'update_time': basic.update_time.strftime('%Y-%m-%d %H:%M:%S') if basic and basic.update_time else None,
                'sectors': stock_sectors_map.get(rel_stock_code, [])
            }
            stocks_data.append(stock_dict)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'sector': sector.to_dict(),
                'stocks': stocks_data,
                'total': total,
                'page': page,
                'page_size': page_size
            }
        })
        
    except Exception as e:
        logger.exception("获取板块股票列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/config', methods=['GET', 'PUT'])
def metadata_config():
    """
    获取或更新元数据补充配置
    """
    try:
        from services.metadata_config import (
            get_metadata_config,
            set_metadata_config,
            METADATA_SUPPLEMENT_CONFIG
        )

        if request.method == 'GET':
            # 返回当前配置
            return jsonify({
                'code': 200,
                'message': '操作成功',
                'data': METADATA_SUPPLEMENT_CONFIG
            })

        elif request.method == 'PUT':
            # 更新配置
            data = request.get_json()
            if not data:
                return jsonify({'code': 400, 'message': '请求数据不能为空'}), 400

            # 只允许更新特定的配置项
            allowed_keys = set(METADATA_SUPPLEMENT_CONFIG.keys())
            for key in data.keys():
                if key in allowed_keys:
                    set_metadata_config(key, data[key])

            return jsonify({
                'code': 200,
                'message': '配置更新成功',
                'data': METADATA_SUPPLEMENT_CONFIG
            })

    except Exception as e:
        logger.exception("配置操作失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


# ==================== AKShare 板块初始化接口 ====================


@metadata_bp.route('/init/industry-from-akshare', methods=['POST'])
def init_industry_from_akshare():
    """
    使用AKShare初始化行业板块和成分股
    
    Returns:
        JSON: 初始化结果
    """
    try:
        service = get_metadata_service()
        result = service.supplement_industry_sectors_from_akshare()
        
        return jsonify({
            'code': 200,
            'message': '行业板块初始化完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("行业板块初始化失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/init/concept-from-akshare', methods=['POST'])
def init_concept_from_akshare():
    """
    使用AKShare初始化概念板块和成分股
    
    Returns:
        JSON: 初始化结果
    """
    try:
        service = get_metadata_service()
        result = service.supplement_concept_sectors_from_akshare()
        
        return jsonify({
            'code': 200,
            'message': '概念板块初始化完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("概念板块初始化失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/init/all-from-akshare', methods=['POST'])
def init_all_from_akshare():
    """
    使用AKShare初始化所有板块元数据（行业板块 + 概念板块）
    
    Returns:
        JSON: 初始化结果
    """
    try:
        service = get_metadata_service()
        result = service.init_all_metadata_from_akshare()
        
        return jsonify({
            'code': 200,
            'message': '所有板块元数据初始化完成',
            'data': result
        })
        
    except ImportError as e:
        logger.error(f"AKShare 未安装: {e}")
        return jsonify({'code': 500, 'message': f'AKShare 未安装: {str(e)}'}), 500
    except Exception as e:
        logger.exception("板块元数据初始化失败")
        return jsonify({'code': 500, 'message': f'初始化失败: {type(e).__name__}: {str(e)}'}), 500


@metadata_bp.route('/akshare/test', methods=['GET'])
def test_akshare():
    """
    测试AKShare连接（轻量级测试，不调用外部API）
    
    Returns:
        JSON: 测试结果
    """
    try:
        from services.akshare_service import get_eastmoney_service
        aks = get_eastmoney_service()
        
        # 只检查 AKShare 模块是否可用，不调用东方财富 API
        try:
            ak = aks._get_akshare()
            logger.info("AKShare 模块检查成功")
        except ImportError as e:
            raise ImportError(str(e))
        
        return jsonify({
            'code': 200,
            'message': 'AKShare 模块已安装，连接正常',
            'data': {
                'industry_count': 0,
                'concept_count': 0,
                'sample_industries': [],
                'sample_concepts': [],
                'note': '此为轻量级测试，未调用东方财富API'
            }
        })
        
    except ImportError as e:
        logger.error(f"AKShare 未安装: {e}")
        return jsonify({'code': 500, 'message': f'AKShare 未安装: {str(e)}'}), 500
    except Exception as e:
        logger.exception("AKShare 连接测试失败")
        return jsonify({'code': 500, 'message': f'连接失败: {type(e).__name__}: {str(e)}'}), 500


@metadata_bp.route('/akshare/direct-test', methods=['GET'])
def akshare_direct_test():
    """
    直接测试东方财富API（绕过AKShare内部解析）
    
    Returns:
        JSON: 测试结果和原始响应
    """
    try:
        from services.akshare_service import get_eastmoney_service
        aks = get_eastmoney_service()
        result = aks.test_direct_api()
        
        return jsonify({
            'code': 200 if result.get('success') else 500,
            'message': '测试完成',
            'data': result
        })
        
    except Exception as e:
        logger.exception("直接API测试失败")
        return jsonify({'code': 500, 'message': f'测试失败: {str(e)}'}), 500


# ==================== 股票元数据初始化接口 ====================


@metadata_bp.route('/init/stock-from-akshare', methods=['POST'])
def init_stock_from_akshare():
    """
    使用AKShare初始化股票基本信息

    请求参数:
        - update_existing: 是否更新已存在的股票信息，默认true

    Returns:
        JSON: 初始化结果
    """
    try:
        from services.metadata_service import supplement_stock_basic_from_akshare

        data = request.get_json() or {}
        update_existing = data.get('update_existing', True)

        result = supplement_stock_basic_from_akshare(update_existing=update_existing)

        return jsonify({
            'code': 200,
            'message': '股票基本信息初始化完成',
            'data': result
        })

    except ImportError as e:
        logger.exception("AKShare 未安装")
        return jsonify({'code': 500, 'message': f'AKShare 未安装: {str(e)}'}), 500
    except Exception as e:
        logger.exception("股票基本信息初始化失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/init/full-from-akshare', methods=['POST'])
def init_full_from_akshare():
    """
    使用AKShare初始化所有元数据（股票 + 行业板块 + 概念板块）

    请求参数:
        - update_existing: 是否更新已存在的信息，默认true

    Returns:
        JSON: 初始化结果
    """
    try:
        from services.metadata_service import init_all_metadata_from_akshare_full

        data = request.get_json() or {}
        update_existing = data.get('update_existing', True)

        result = init_all_metadata_from_akshare_full(update_existing=update_existing)

        return jsonify({
            'code': 200,
            'message': '全部元数据初始化完成',
            'data': result
        })

    except ImportError as e:
        logger.exception("AKShare 未安装")
        return jsonify({'code': 500, 'message': f'AKShare 未安装: {str(e)}'}), 500
    except Exception as e:
        logger.exception("全部元数据初始化失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stocks', methods=['GET'])
def get_stocks_with_sectors():
    """获取股票列表（包含所属板块信息）- 优化版
    
    Query Parameters:
        type: 股票类型过滤 (stock-股票, index-指数, etf-ETF, 空=全部)
        search: 搜索关键词（代码或名称）
    """
    from flask import request
    
    try:
        # 获取类型过滤参数和搜索参数
        stock_type = request.args.get('type', '')
        search = request.args.get('search', '').strip()
        
        # 构建基础查询
        query = StockBasic.query
        
        # 按类型过滤 - 使用 stock_type 字段
        if stock_type:
            if stock_type == 'stock':
                # 股票：包含 stock, ct (创业板), cs (科创板)
                query = query.filter(
                    (StockBasic.stock_type == 'stock') | 
                    (StockBasic.stock_type == 'ct') |
                    (StockBasic.stock_type == 'cs')
                )
            elif stock_type == 'bond':
                # 可转债
                query = query.filter(StockBasic.stock_type == 'bond')
            else:
                query = query.filter(StockBasic.stock_type == stock_type)
            logger.info(f"[stocks] 类型过滤: {stock_type}")
        
        # 按搜索关键词过滤
        if search:
            query = query.filter(
                (StockBasic.stock_code.like(f'%{search}%')) | 
                (StockBasic.stock_name.like(f'%{search}%'))
            )
            logger.info(f"[stocks] 搜索过滤: {search}")
        
        # 一次性获取所有股票
        stocks = query.order_by(StockBasic.stock_code).all()

        # 一次性获取所有关联关系
        relations = db.session.query(StockSectorRelation).all()

        # 一次性获取所有板块
        sectors = db.session.query(StockSector).all()

        logger.info(f"[stocks] 股票总数: {len(stocks)}, 关联关系总数: {len(relations)}, 板块总数: {len(sectors)}")

        # 构建 sector_id -> sector_info 映射
        sector_map = {s.id: {
            'sector_code': s.sector_code,
            'sector_name': s.sector_name,
            'sector_type': s.sector_type
        } for s in sectors}

        # 构建 stock_code -> [sectors] 映射
        stock_sectors_map = {}
        for rel in relations:
            if rel.stock_code not in stock_sectors_map:
                stock_sectors_map[rel.stock_code] = []
            if rel.sector_id in sector_map:
                stock_sectors_map[rel.stock_code].append(sector_map[rel.sector_id])

        logger.info(f"[stocks] 有板块关联的股票数: {len(stock_sectors_map)}")

        # 构建结果
        result = []
        for stock in stocks:
            result.append({
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'market': stock.market,
                'exchange': stock.exchange,
                'company_name': stock.company_name,
                'industry': stock.industry,
                'area': stock.area,
                'list_date': stock.list_date,
                'is_hs': stock.is_hs,
                'total_shares': float(stock.total_shares) if stock.total_shares else None,
                'circulate_shares': float(stock.circulate_shares) if stock.circulate_shares else None,
                'total_market_value': float(stock.total_market_value) if stock.total_market_value else None,
                'circulate_market_value': float(stock.circulate_market_value) if stock.circulate_market_value else None,
                'update_time': stock.update_time.isoformat() if stock.update_time else None,
                'sectors': stock_sectors_map.get(stock.stock_code, [])
            })

        # 调试：打印前3条数据
        if result:
            logger.info(f"[stocks] 返回数据预览: {result[0]}")
            if len(result) > 1 and result[1].get('sectors'):
                logger.info(f"[stocks] 第二条有sectors: {result[1]}")

        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': result
        })

    except Exception as e:
        logger.exception("获取股票列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors/all', methods=['GET'])
def get_all_sectors():
    """获取所有板块列表（用于下拉选择）"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 100, type=int)
        sector_type = request.args.get('type')
        
        # 构建查询
        query = db.session.query(StockSector)
        
        if sector_type:
            query = query.filter(StockSector.sector_type == sector_type)
        
        # 获取总数
        total = query.count()
        
        # 分页获取
        sectors = query.order_by(StockSector.sector_name).paginate(page=page, per_page=page_size, error_out=False)
        
        result = [{
            'id': s.id,
            'sector_code': s.sector_code,
            'sector_name': s.sector_name,
            'sector_type': s.sector_type,
            'stock_count': s.stock_count or 0
        } for s in sectors.items]
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': result,
            'total': total,
            'page': page,
            'page_size': page_size
        })
        
    except Exception as e:
        logger.exception("获取板块列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock-sector', methods=['POST'])
def add_stock_to_sector():
    """将股票添加到板块"""
    try:
        data = request.get_json()
        
        stock_code = data.get('stock_code')
        sector_id = data.get('sector_id')
        
        if not stock_code or not sector_id:
            return jsonify({'code': 400, 'message': '股票代码和板块ID不能为空'}), 400
        
        # 检查是否已存在关联
        existing = db.session.query(StockSectorRelation).filter(
            StockSectorRelation.stock_code == stock_code,
            StockSectorRelation.sector_id == sector_id
        ).first()
        
        if existing:
            return jsonify({'code': 400, 'message': '该股票已在当前板块中'}), 400
        
        # 添加关联
        relation = StockSectorRelation(
            stock_code=stock_code,
            sector_id=sector_id
        )
        db.session.add(relation)
        db.session.commit()
        
        # 更新板块成分股数量
        service = get_metadata_service()
        service._update_sector_stock_count(sector_id)
        
        return jsonify({
            'code': 200,
            'message': '添加成功'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("添加股票到板块失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/stock-sector', methods=['DELETE'])
def remove_stock_from_sector():
    """将股票从板块移除"""
    try:
        data = request.get_json()
        
        stock_code = data.get('stock_code')
        sector_id = data.get('sector_id')
        
        if not stock_code or not sector_id:
            return jsonify({'code': 400, 'message': '股票代码和板块ID不能为空'}), 400
        
        # 删除关联
        result = db.session.query(StockSectorRelation).filter(
            StockSectorRelation.stock_code == stock_code,
            StockSectorRelation.sector_id == sector_id
        ).delete()
        
        db.session.commit()
        
        if result == 0:
            return jsonify({'code': 404, 'message': '未找到该关联关系'}), 404
        
        # 更新板块成分股数量
        service = get_metadata_service()
        service._update_sector_stock_count(sector_id)
        
        return jsonify({
            'code': 200,
            'message': '移除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("从板块移除股票失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors', methods=['POST'])
def create_sector():
    """创建新板块"""
    try:
        data = request.get_json()
        
        sector_name = data.get('sector_name')
        sector_type = data.get('sector_type', 'industry')
        sector_code = data.get('sector_code')  # 允许手动指定板块代码
        
        if not sector_name:
            return jsonify({'code': 400, 'message': '板块名称不能为空'}), 400
        
        # 如果没有指定板块代码，则自动生成
        if not sector_code:
            import uuid
            sector_code = f"{sector_type[:3].upper()}{str(uuid.uuid4())[:8].upper()}"
        
        # 检查板块名称是否已存在
        existing = db.session.query(StockSector).filter(
            StockSector.sector_name == sector_name
        ).first()
        
        if existing:
            return jsonify({'code': 400, 'message': '板块名称已存在'}), 400
        
        # 检查板块代码是否已存在
        existing_code = db.session.query(StockSector).filter(
            StockSector.sector_code == sector_code
        ).first()
        
        if existing_code:
            return jsonify({'code': 400, 'message': '板块代码已存在'}), 400
        
        # 创建板块
        sector = StockSector(
            sector_code=sector_code,
            sector_name=sector_name,
            sector_type=sector_type,
            description=data.get('description', '')
        )
        db.session.add(sector)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '板块创建成功',
            'data': {
                'id': sector.id,
                'sector_code': sector_code,
                'sector_name': sector_name,
                'sector_type': sector_type
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("创建板块失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


def register_metadata_blueprint(app):
    """注册元数据蓝图（用于非工厂模式）"""
    app.register_blueprint(metadata_bp, url_prefix='/api/metadata')


# ==================== 个股信息补充接口 ====================


@metadata_bp.route('/stock/supplement-info', methods=['POST'])
def supplement_stock_info():
    """
    通过AKShare获取并补充股票详细信息（东方财富个股信息）
    
    请求参数:
        - stock_codes: 股票代码列表（可选，默认全部）
    """
    try:
        from services.akshare_service import get_eastmoney_service
        
        data = request.get_json() or {}
        stock_codes = data.get('stock_codes')
        
        aks = get_eastmoney_service()
        result = aks.supplement_stock_individual_info(stock_codes)
        
        return jsonify({
            'code': 200,
            'message': '股票详细信息补充完成',
            'data': result
        })
        
    except ImportError as e:
        logger.error(f"AKShare 未安装: {e}")
        return jsonify({'code': 500, 'message': f'AKShare 未安装: {str(e)}'}), 500
    except Exception as e:
        logger.exception("股票详细信息补充失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


# ==================== 交割单导入接口 ====================

def parse_excel(file):
    """解析Excel文件（.xls或.xlsx），失败时尝试CSV解析"""
    import io
    
    # 读取文件内容
    content = file.read()
    filename = file.filename.lower()
    
    # 根据文件扩展名选择引擎
    if filename.endswith('.xlsx'):
        engine = 'openpyxl'
    elif filename.endswith('.xls'):
        engine = 'xlrd'
    else:
        engine = None
    
    try:
        import pandas as pd
        # 使用pandas读取Excel，指定引擎
        df = pd.read_excel(io.BytesIO(content), header=None, engine=engine)
        # 转换为列表格式
        rows = df.values.tolist()
        # 将所有值转换为字符串
        rows = [[str(cell) if pd.notna(cell) else '' for cell in row] for row in rows]
        return rows
    except Exception as e:
        # 如果Excel解析失败，尝试作为CSV/TXT解析
        try:
            # 尝试GBK解码
            try:
                text = content.decode('gbk')
            except UnicodeDecodeError:
                text = content.decode('utf-8', errors='replace')
            
            # 解析CSV/TXT
            import csv
            reader = csv.reader(io.StringIO(text), delimiter='\t')
            rows = list(reader)
            return rows
        except Exception as csv_error:
            raise ImportError(f"Excel解析失败: {str(e)}，CSV解析也失败: {str(csv_error)}")


def has_letters(text):
    """检查文本是否包含字母（排除ETF等常见基金后缀）"""
    if not text:
        return False
    # 排除常见基金后缀
    exclude_suffixes = ['ETF', 'LOF', 'FOF', 'QDII', 'ETF联接', 'etf', 'lof', 'fof', 'qdii']
    text_upper = str(text).upper()
    for suffix in exclude_suffixes:
        if text_upper.endswith(suffix):
            return False
    return bool(re.search(r'[a-zA-Z]', str(text)))


def parse_number(value):
    """解析数字"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_int(value):
    """解析整数"""
    if value is None or value == '':
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


@metadata_bp.route('/delivery/import', methods=['POST'])
def import_delivery():
    """导入股票交割单数据"""
    try:
        if 'file' not in request.files:
            return jsonify({'code': 400, 'message': '请上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'code': 400, 'message': '文件名不能为空'}), 400
        
        filename = file.filename.lower()
        
        # 根据文件扩展名选择解析方式
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            # 解析Excel文件
            rows = parse_excel(file)
        elif filename.endswith('.csv') or filename.endswith('.txt'):
            # 解析CSV/TXT文件
            content = file.read()
            try:
                text = content.decode('gbk')
            except UnicodeDecodeError:
                text = content.decode('utf-8', errors='replace')
            reader = csv.reader(io.StringIO(text), delimiter='\t')
            rows = list(reader)
        else:
            return jsonify({'code': 400, 'message': '不支持的文件格式，请上传 .xls, .xlsx, .csv 或 .txt 文件'}), 400
        
        if len(rows) < 2:
            return jsonify({'code': 400, 'message': '文件内容为空或格式不正确'}), 400
        
        imported_count = 0
        skipped_letters = 0
        skipped_apply_allotment = 0
        skipped_duplicate = 0
        error_count = 0
        
        # Skip header
        for row in rows[1:]:
            if not row or len(row) < 21:
                continue
            
            try:
                # 提取字段
                trade_date = row[0].strip()
                trade_time = row[1].strip()
                security_code = row[2].strip()
                security_name = row[3].strip()
                operation = row[4].strip()
                
                # 过滤条件1: 证券名称包含字母
                if has_letters(security_name):
                    skipped_letters += 1
                    continue
                
                # 过滤条件2: 证券名称以R开头（如R-001、Ｒ-001等）
                if security_name and (security_name.startswith('R') or security_name.startswith('r') or security_name.startswith('Ｒ')):
                    skipped_letters += 1
                    continue
                
                # 过滤条件3: 操作是"申请配号"、"申购配号"或"指定交易"
                if operation in ['申请配号', '申购配号', '指定交易']:
                    skipped_apply_allotment += 1
                    continue
                
                deal_no = row[6].strip() if len(row) > 6 else None
                
                # 过滤条件4: 成交编号为空时不导入（避免唯一键冲突）
                if not deal_no or deal_no == '':
                    skipped_duplicate += 1
                    continue
                
                # 检查是否已存在
                if deal_no:
                    existing = StockDelivery.query.filter_by(deal_no=deal_no).first()
                    if existing:
                        skipped_duplicate += 1
                        continue
                
                # 创建记录
                delivery = StockDelivery(
                    trade_date=trade_date,
                    trade_time=trade_time if trade_time else None,
                    security_code=security_code,
                    security_name=security_name if security_name else None,
                    operation=operation if operation else None,
                    quantity=parse_int(row[5]),
                    deal_no=deal_no,
                    price=parse_number(row[7]),
                    amount=parse_number(row[8]),
                    balance=parse_number(row[9]),
                    stock_balance=parse_int(row[10]),
                    occur_amount=parse_number(row[11]),
                    commission=parse_number(row[12]),
                    stamp_duty=parse_number(row[13]),
                    other_fee=parse_number(row[14]),
                    fund_balance=parse_number(row[15]),
                    current_amount=parse_number(row[16]),
                    contract_no=row[17].strip() if len(row) > 17 else None,
                    other_expense=parse_number(row[18]) if len(row) > 18 else None,
                    transfer_fee=parse_number(row[19]) if len(row) > 19 else None,
                    market=row[20].strip() if len(row) > 20 else None,
                )
                
                db.session.add(delivery)
                imported_count += 1
                
                # 批量提交
                if imported_count % 100 == 0:
                    db.session.commit()
                    
            except Exception as e:
                error_count += 1
                logger.error(f"导入错误: {e}, row: {row[:3]}")
                continue
        
        # 最后提交
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '导入完成',
            'data': {
                'imported': imported_count,
                'skipped_letters': skipped_letters,
                'skipped_apply_allotment': skipped_apply_allotment,
                'skipped_duplicate': skipped_duplicate,
                'error': error_count,
                'total': imported_count + skipped_letters + skipped_apply_allotment + skipped_duplicate + error_count
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("交割单导入失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/list', methods=['GET'])
def get_delivery_list():
    """获取交割单列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        
        query = StockDelivery.query.order_by(StockDelivery.trade_date.desc(), StockDelivery.trade_time.desc())
        
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'items': [d.to_dict() for d in items],
                'total': total,
                'page': page,
                'page_size': page_size
            }
        })
        
    except Exception as e:
        logger.exception("获取交割单列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/stats', methods=['GET'])
def get_delivery_stats():
    """获取交割单统计信息"""
    try:
        total = StockDelivery.query.count()
        
        # 统计操作类型
        operations = db.session.query(
            StockDelivery.operation,
            db.func.count(StockDelivery.id)
        ).group_by(StockDelivery.operation).all()
        
        operation_stats = [{'operation': op, 'count': count} for op, count in operations]
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'total': total,
                'operations': operation_stats
            }
        })
        
    except Exception as e:
        logger.exception("获取交割单统计失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/by-stock/<stock_code>', methods=['GET'])
def get_delivery_by_stock(stock_code):
    """根据股票代码获取交割单列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        operation = request.args.get('operation')  # 可选：过滤操作类型
        start_date = request.args.get('start_date')  # 开始日期
        end_date = request.args.get('end_date')  # 结束日期
        
        query = StockDelivery.query.filter(
            StockDelivery.security_code == stock_code
        )
        
        if operation:
            query = query.filter(StockDelivery.operation == operation)
        
        if start_date:
            query = query.filter(StockDelivery.trade_date >= start_date)
        
        if end_date:
            query = query.filter(StockDelivery.trade_date <= end_date)
        
        query = query.order_by(StockDelivery.trade_date.desc(), StockDelivery.trade_time.desc())
        
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'items': [d.to_dict() for d in items],
                'total': total,
                'page': page,
                'page_size': page_size,
                'stock_code': stock_code
            }
        })
        
    except Exception as e:
        logger.exception("获取交割单列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/stocks', methods=['GET'])
def get_delivery_stocks():
    """获取交割单中涉及的股票列表（去重）"""
    try:
        # 获取筛选参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 基础查询
        query = db.session.query(
            StockDelivery.security_code,
            StockDelivery.security_name,
            db.func.count(StockDelivery.id).label('trade_count'),
            db.func.sum(StockDelivery.amount).label('total_amount'),
            db.func.max(StockDelivery.trade_date).label('latest_date')
        )
        
        # 时间筛选
        if start_date:
            query = query.filter(StockDelivery.trade_date >= start_date)
        if end_date:
            query = query.filter(StockDelivery.trade_date <= end_date)
        
        # 分组和排序
        stocks = query.group_by(
            StockDelivery.security_code,
            StockDelivery.security_name
        ).order_by(
            db.func.max(StockDelivery.trade_date).desc()  # 按最近交易时间排序
        ).all()
        
        # 计算每只股票的获利（卖出 - 买入）
        result = []
        for s in stocks:
            # 获取该股票的买入总金额
            buy_query = db.session.query(
                db.func.sum(StockDelivery.amount)
            ).filter(
                StockDelivery.security_code == s.security_code,
                StockDelivery.operation == '证券买入'
            )
            if start_date:
                buy_query = buy_query.filter(StockDelivery.trade_date >= start_date)
            if end_date:
                buy_query = buy_query.filter(StockDelivery.trade_date <= end_date)
            buy_stats = buy_query.scalar() or 0
            
            # 获取该股票的卖出总金额
            sell_query = db.session.query(
                db.func.sum(StockDelivery.amount)
            ).filter(
                StockDelivery.security_code == s.security_code,
                StockDelivery.operation == '证券卖出'
            )
            if start_date:
                sell_query = sell_query.filter(StockDelivery.trade_date >= start_date)
            if end_date:
                sell_query = sell_query.filter(StockDelivery.trade_date <= end_date)
            sell_stats = sell_query.scalar() or 0
            
            profit = float(sell_stats) - float(buy_stats)
            
            result.append({
                'security_code': s.security_code,
                'security_name': s.security_name,
                'trade_count': s.trade_count,
                'total_amount': float(s.total_amount) if s.total_amount else 0,
                'profit': profit,
                'latest_date': s.latest_date
            })
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': result
        })
        
    except Exception as e:
        logger.exception("获取股票列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/summary/<stock_code>', methods=['GET'])
def get_delivery_summary_by_stock(stock_code):
    """获取指定股票代码的交割单统计汇总"""
    try:
        # 统计该股票的总交易次数、买入次数、卖出次数、总成交金额等
        stats = db.session.query(
            StockDelivery.operation,
            db.func.count(StockDelivery.id).label('count'),
            db.func.sum(StockDelivery.quantity).label('total_quantity'),
            db.func.sum(StockDelivery.amount).label('total_amount')
        ).filter(
            StockDelivery.security_code == stock_code
        ).group_by(StockDelivery.operation).all()
        
        operation_stats = {}
        for op, count, quantity, amount in stats:
            operation_stats[op] = {
                'count': count,
                'total_quantity': quantity if quantity else 0,
                'total_amount': float(amount) if amount else 0
            }
        
        # 计算总交易次数和总成交金额
        total_trades = sum(s['count'] for s in operation_stats.values())
        total_amount = sum(s['total_amount'] for s in operation_stats.values())
        
        # 获取最新和最早的交易日
        latest = StockDelivery.query.filter(
            StockDelivery.security_code == stock_code
        ).order_by(StockDelivery.trade_date.desc()).first()
        
        earliest = StockDelivery.query.filter(
            StockDelivery.security_code == stock_code
        ).order_by(StockDelivery.trade_date.asc()).first()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'stock_code': stock_code,
                'stock_name': latest.security_name if latest else None,
                'total_trades': total_trades,
                'total_amount': total_amount,
                'operations': operation_stats,
                'date_range': {
                    'earliest': earliest.trade_date if earliest else None,
                    'latest': latest.trade_date if latest else None
                }
            }
        })
        
    except Exception as e:
        logger.exception("获取交割单汇总失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/delivery/<int:delivery_id>/review-note', methods=['PUT'])
def update_delivery_review_note(delivery_id):
    """更新交割单的复盘记录"""
    try:
        data = request.get_json()
        review_note = data.get('review_note', '')
        
        delivery = StockDelivery.query.get(delivery_id)
        if not delivery:
            return jsonify({'code': 404, 'message': '交割单不存在'}), 404
        
        delivery.review_note = review_note
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '更新成功',
            'data': {'review_note': review_note}
        })
        
    except Exception as e:
        db.session.rollback()
        logger.exception("更新复盘记录失败")
        return jsonify({'code': 500, 'message': str(e)}), 500