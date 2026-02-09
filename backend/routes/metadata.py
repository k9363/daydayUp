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

logger = logging.getLogger(__name__)

metadata_bp = Blueprint('metadata', __name__, url_prefix='/api/metadata')


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
    """获取板块列表"""
    try:
        sector_type = request.args.get('type')
        
        query = StockSector.query
        if sector_type:
            query = query.filter(StockSector.sector_type == sector_type)
        
        sectors = query.order_by(StockSector.stock_count.desc()).all()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': [s.to_dict() for s in sectors]
        })
        
    except Exception as e:
        logger.exception("获取板块列表失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


@metadata_bp.route('/sectors/<sector_code>/stocks', methods=['GET'])
def get_sector_stocks(sector_code):
    """获取板块下的股票列表"""
    try:
        sector = StockSector.query.filter(
            StockSector.sector_code == sector_code
        ).first()
        
        if not sector:
            return jsonify({'code': 404, 'message': '板块不存在'}), 404
        
        relations = db.session.query(StockSectorRelation).filter(
            StockSectorRelation.sector_id == sector.id
        ).all()
        
        stocks = []
        for relation in relations:
            stock = StockBasic.query.filter(
                StockBasic.stock_code == relation.stock_code
            ).first()
            if stock:
                stocks.append({
                    'stock': stock.to_dict(),
                    'is_main': relation.is_main,
                    'weight': relation.weight
                })
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {
                'sector': sector.to_dict(),
                'stocks': stocks
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


def register_metadata_blueprint(app):
    """注册元数据蓝图"""
    app.register_blueprint(metadata_bp)

