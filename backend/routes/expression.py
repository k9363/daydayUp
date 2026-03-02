"""
表达式管理API
"""
import logging
from flask import Blueprint, request, jsonify
from extensions import db
from models.expression import ScoreExpression

logger = logging.getLogger(__name__)

expression_bp = Blueprint('expression', __name__, url_prefix='/api/expression')


@expression_bp.route('/list', methods=['GET'])
def get_expressions():
    """获取表达式列表"""
    scope = request.args.get('scope')  # stock/sector/market
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    query = ScoreExpression.query
    
    if scope:
        query = query.filter_by(scope=scope)
    if active_only:
        query = query.filter_by(is_active=True)
    
    expressions = query.order_by(ScoreExpression.scope, ScoreExpression.expression_name).all()
    
    return jsonify({
        'code': 200,
        'data': [e.to_dict() for e in expressions]
    })


@expression_bp.route('/<int:expr_id>', methods=['GET'])
def get_expression(expr_id):
    """获取单个表达式详情"""
    expr = ScoreExpression.query.get(expr_id)
    if not expr:
        return jsonify({'code': 404, 'message': '表达式不存在'})
    
    return jsonify({
        'code': 200,
        'data': expr.to_dict()
    })


@expression_bp.route('', methods=['POST'])
def create_expression():
    """创建表达式"""
    data = request.get_json()
    
    # 验证必填字段
    if not data.get('expression_name'):
        return jsonify({'code': 400, 'message': '表达式名称不能为空'})
    if not data.get('expression'):
        return jsonify({'code': 400, 'message': '表达式不能为空'})
    if not data.get('scope'):
        return jsonify({'code': 400, 'message': '作用域不能为空'})
    
    # 如果设为默认，取消其他默认
    if data.get('is_default'):
        ScoreExpression.query.filter_by(
            scope=data['scope'],
            is_default=True
        ).update({'is_default': False})
    
    expr = ScoreExpression(
        expression_name=data['expression_name'],
        scope=data['scope'],
        factors=data.get('factors', []),
        expression=data['expression'],
        top_n=data.get('top_n'),
        description=data.get('description'),
        is_default=data.get('is_default', False),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(expr)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': expr.to_dict(),
        'message': '表达式创建成功'
    })


@expression_bp.route('/<int:expr_id>', methods=['PUT'])
def update_expression(expr_id):
    """更新表达式"""
    expr = ScoreExpression.query.get(expr_id)
    if not expr:
        return jsonify({'code': 404, 'message': '表达式不存在'})
    
    data = request.get_json()
    
    # 如果设为默认，取消其他默认
    if data.get('is_default') and not expr.is_default:
        ScoreExpression.query.filter_by(
            scope=expr.scope,
            is_default=True
        ).update({'is_default': False})
    
    # 更新字段
    if 'expression_name' in data:
        expr.expression_name = data['expression_name']
    if 'scope' in data:
        expr.scope = data['scope']
    if 'factors' in data:
        expr.factors = data['factors']
    if 'expression' in data:
        expr.expression = data['expression']
    if 'top_n' in data:
        expr.top_n = data['top_n']
    if 'description' in data:
        expr.description = data['description']
    if 'is_default' in data:
        expr.is_default = data['is_default']
    if 'is_active' in data:
        expr.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': expr.to_dict(),
        'message': '表达式更新成功'
    })


@expression_bp.route('/<int:expr_id>', methods=['DELETE'])
def delete_expression(expr_id):
    """删除表达式"""
    expr = ScoreExpression.query.get(expr_id)
    if not expr:
        return jsonify({'code': 404, 'message': '表达式不存在'})
    
    # 软删除
    expr.is_active = False
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '表达式删除成功'
    })


@expression_bp.route('/test', methods=['POST'])
def test_expression():
    """测试表达式"""
    data = request.get_json()
    
    expression = data.get('expression')
    factors = data.get('factors', {})  # 因子值字典
    
    if not expression:
        return jsonify({'code': 400, 'message': '表达式不能为空'})
    
    try:
        # 动态导入，避免顶层依赖
        import simpleeval
        simpleeval.simple_eval(expression, names=factors)
        
        return jsonify({
            'code': 200,
            'message': '表达式语法正确',
            'data': {'valid': True}
        })
    except Exception as e:
        return jsonify({
            'code': 400,
            'message': f'表达式语法错误: {str(e)}',
            'data': {'valid': False, 'error': str(e)}
        })


@expression_bp.route('/calculate', methods=['POST'])
def calculate_expression():
    """计算表达式得分"""
    data = request.get_json()
    
    expression = data.get('expression')
    factors = data.get('factors', {})  # 因子值字典
    
    if not expression:
        return jsonify({'code': 400, 'message': '表达式不能为空'})
    
    try:
        import simpleeval
        result = simpleeval.simple_eval(expression, names=factors)
        
        return jsonify({
            'code': 200,
            'data': {
                'result': result,
                'factors': factors
            }
        })
    except Exception as e:
        return jsonify({
            'code': 400,
            'message': f'计算错误: {str(e)}',
            'data': {'error': str(e)}
        })


@expression_bp.route('/default/<scope>', methods=['GET'])
def get_default_expression(scope):
    """获取指定作用域的默认表达式"""
    expr = ScoreExpression.query.filter_by(
        scope=scope,
        is_default=True,
        is_active=True
    ).first()
    
    if not expr:
        return jsonify({
            'code': 404,
            'message': '未找到默认表达式'
        })
    
    return jsonify({
        'code': 200,
        'data': expr.to_dict()
    })
