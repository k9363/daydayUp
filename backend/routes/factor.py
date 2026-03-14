"""
因子管理API
"""
import logging
from flask import Blueprint, request, jsonify
from extensions import db
from models.factor import FactorDefine

logger = logging.getLogger(__name__)

# 在应用工厂中通过 url_prefix='/api/factor' 统一配置前缀
factor_bp = Blueprint('factor', __name__)


@factor_bp.route('/list', methods=['GET'])
def get_factors():
    """获取因子列表"""
    scope = request.args.get('scope')  # stock/sector/market
    source = request.args.get('source')
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    query = FactorDefine.query
    
    if scope:
        query = query.filter_by(factor_scope=scope)
    if source:
        query = query.filter_by(source=source)
    if active_only:
        query = query.filter_by(is_active=True)
    
    factors = query.order_by(FactorDefine.factor_scope, FactorDefine.factor_code).all()
    
    return jsonify({
        'code': 200,
        'data': [f.to_dict() for f in factors]
    })


@factor_bp.route('/<int:factor_id>', methods=['GET'])
def get_factor(factor_id):
    """获取单个因子详情"""
    factor = FactorDefine.query.get(factor_id)
    if not factor:
        return jsonify({'code': 404, 'message': '因子不存在'})
    
    return jsonify({
        'code': 200,
        'data': factor.to_dict()
    })


@factor_bp.route('', methods=['POST'])
def create_factor():
    """创建因子"""
    data = request.get_json()
    
    # 验证必填字段
    if not data.get('factor_code'):
        return jsonify({'code': 400, 'message': '因子代码不能为空'})
    if not data.get('factor_name'):
        return jsonify({'code': 400, 'message': '因子名称不能为空'})
    if not data.get('factor_scope'):
        return jsonify({'code': 400, 'message': '因子作用域不能为空'})
    
    # 检查因子代码是否已存在
    existing = FactorDefine.query.filter_by(factor_code=data['factor_code']).first()
    if existing:
        return jsonify({'code': 400, 'message': '因子代码已存在'})
    
    factor = FactorDefine(
        factor_code=data['factor_code'],
        factor_name=data['factor_name'],
        factor_scope=data['factor_scope'],
        source=data.get('source'),
        calculation_method=data.get('calculation_method'),
        field_name=data.get('field_name'),
        days_range=data.get('days_range'),
        days_offset=data.get('days_offset'),
        aggregation=data.get('aggregation'),
        index_code=data.get('index_code'),
        expression=data.get('expression'),
        description=data.get('description'),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(factor)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': factor.to_dict(),
        'message': '因子创建成功'
    })


@factor_bp.route('/<int:factor_id>', methods=['PUT'])
def update_factor(factor_id):
    """更新因子"""
    factor = FactorDefine.query.get(factor_id)
    if not factor:
        return jsonify({'code': 404, 'message': '因子不存在'})
    
    data = request.get_json()
    
    # 如果修改因子代码，检查是否冲突
    if data.get('factor_code') and data['factor_code'] != factor.factor_code:
        existing = FactorDefine.query.filter_by(factor_code=data['factor_code']).first()
        if existing:
            return jsonify({'code': 400, 'message': '因子代码已存在'})
        factor.factor_code = data['factor_code']
    
    # 更新其他字段
    if 'factor_name' in data:
        factor.factor_name = data['factor_name']
    if 'factor_scope' in data:
        factor.factor_scope = data['factor_scope']
    if 'source' in data:
        factor.source = data['source']
    if 'calculation_method' in data:
        factor.calculation_method = data['calculation_method']
    if 'field_name' in data:
        factor.field_name = data['field_name']
    if 'days_range' in data:
        factor.days_range = data['days_range']
    if 'aggregation' in data:
        factor.aggregation = data['aggregation']
    if 'index_code' in data:
        factor.index_code = data['index_code']
    if 'expression' in data:
        factor.expression = data['expression']
    if 'description' in data:
        factor.description = data['description']
    if 'is_active' in data:
        factor.is_active = data['is_active']
    if 'days_offset' in data:
        factor.days_offset = data['days_offset']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': factor.to_dict(),
        'message': '因子更新成功'
    })


@factor_bp.route('/<int:factor_id>', methods=['DELETE'])
def delete_factor(factor_id):
    """删除因子"""
    factor = FactorDefine.query.get(factor_id)
    if not factor:
        return jsonify({'code': 404, 'message': '因子不存在'})
    
    # 软删除
    factor.is_active = False
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '因子删除成功'
    })


@factor_bp.route('/batch', methods=['POST'])
def batch_create_factors():
    """批量创建因子"""
    data = request.get_json()
    factors_data = data.get('factors', [])
    
    if not factors_data:
        return jsonify({'code': 400, 'message': '因子列表不能为空'})
    
    created = []
    errors = []
    
    for item in factors_data:
        # 检查必填字段
        if not item.get('factor_code') or not item.get('factor_name'):
            errors.append({'factor': item.get('factor_code'), 'error': '缺少必填字段'})
            continue
        
        # 检查是否已存在
        existing = FactorDefine.query.filter_by(factor_code=item['factor_code']).first()
        if existing:
            errors.append({'factor': item['factor_code'], 'error': '因子代码已存在'})
            continue
        
        factor = FactorDefine(
            factor_code=item['factor_code'],
            factor_name=item['factor_name'],
            factor_scope=item.get('factor_scope', 'stock'),
            source=item.get('source'),
            calculation_method=item.get('calculation_method'),
            field_name=item.get('field_name'),
            days_range=item.get('days_range'),
            aggregation=item.get('aggregation'),
            index_code=item.get('index_code'),
            expression=item.get('expression'),
            description=item.get('description'),
            is_active=item.get('is_active', True)
        )
        db.session.add(factor)
        created.append(item['factor_code'])
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'成功创建 {len(created)} 个因子',
        'data': {
            'created': created,
            'errors': errors
        }
    })


@factor_bp.route('/options', methods=['GET'])
def get_factor_options():
    """获取因子下拉选项（用于表达式配置）"""
    scope = request.args.get('scope')  # stock/sector/market
    
    query = FactorDefine.query.filter_by(is_active=True)
    if scope:
        query = query.filter_by(factor_scope=scope)
    
    factors = query.order_by(FactorDefine.factor_scope, FactorDefine.factor_code).all()
    
    # 按作用域分组
    result = {
        'stock': [],
        'sector': [],
        'market': []
    }
    
    for f in factors:
        result[f.factor_scope].append({
            'factor_code': f.factor_code,
            'factor_name': f.factor_name,
            'source': f.source,
            'field_name': f.field_name
        })
    
    return jsonify({
        'code': 200,
        'data': result
    })
