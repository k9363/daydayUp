"""
标签管理API
"""
import logging
from flask import Blueprint, request, jsonify
from extensions import db
from models.tag import StockTag, StockTagRelation

logger = logging.getLogger(__name__)

# 在应用工厂中通过 url_prefix='/api/tag' 统一配置前缀
tag_bp = Blueprint('tag', __name__)


@tag_bp.route('/list', methods=['GET'])
def get_tags():
    """获取所有标签列表"""
    tags = StockTag.query.order_by(StockTag.create_time.desc()).all()
    return jsonify({
        'code': 200,
        'data': [tag.to_dict() for tag in tags]
    })


@tag_bp.route('/add', methods=['POST'])
def add_tag():
    """新增标签"""
    data = request.get_json()
    name = data.get('name', '').strip()
    color = data.get('color', '#409EFF')
    
    if not name:
        return jsonify({'code': 400, 'message': '标签名称不能为空'})
    
    # 检查是否已存在
    existing = StockTag.query.filter_by(name=name).first()
    if existing:
        return jsonify({'code': 400, 'message': '标签名称已存在'})
    
    tag = StockTag(name=name, color=color)
    db.session.add(tag)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': tag.to_dict(),
        'message': '标签创建成功'
    })


@tag_bp.route('/update/<int:tag_id>', methods=['PUT'])
def update_tag(tag_id):
    """更新标签"""
    data = request.get_json()
    name = data.get('name', '').strip()
    color = data.get('color')
    
    tag = StockTag.query.get(tag_id)
    if not tag:
        return jsonify({'code': 404, 'message': '标签不存在'})
    
    if name and name != tag.name:
        existing = StockTag.query.filter_by(name=name).first()
        if existing:
            return jsonify({'code': 400, 'message': '标签名称已存在'})
        tag.name = name
    
    if color:
        tag.color = color
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': tag.to_dict(),
        'message': '标签更新成功'
    })


@tag_bp.route('/delete/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """删除标签"""
    tag = StockTag.query.get(tag_id)
    if not tag:
        return jsonify({'code': 404, 'message': '标签不存在'})
    
    # 删除关联关系
    StockTagRelation.query.filter_by(tag_id=tag_id).delete()
    db.session.delete(tag)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '标签删除成功'
    })


@tag_bp.route('/stock/<stock_code>', methods=['GET'])
def get_stock_tags(stock_code):
    """获取股票的所有标签"""
    relations = StockTagRelation.query.filter_by(stock_code=stock_code).all()
    tags = []
    for rel in relations:
        tag = StockTag.query.get(rel.tag_id)
        if tag:
            tags.append(tag.to_dict())
    
    return jsonify({
        'code': 200,
        'data': tags
    })


@tag_bp.route('/stock/add', methods=['POST'])
def add_stock_tag():
    """为股票添加标签"""
    data = request.get_json()
    stock_code = data.get('stock_code')
    tag_id = data.get('tag_id')
    
    if not stock_code or not tag_id:
        return jsonify({'code': 400, 'message': '股票代码和标签ID不能为空'})
    
    # 检查是否已关联
    existing = StockTagRelation.query.filter_by(stock_code=stock_code, tag_id=tag_id).first()
    if existing:
        return jsonify({'code': 400, 'message': '该标签已关联到此股票'})
    
    relation = StockTagRelation(stock_code=stock_code, tag_id=tag_id)
    db.session.add(relation)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '标签添加成功'
    })


@tag_bp.route('/stock/remove', methods=['POST'])
def remove_stock_tag():
    """移除股票的标签"""
    data = request.get_json()
    stock_code = data.get('stock_code')
    tag_id = data.get('tag_id')
    
    if not stock_code or not tag_id:
        return jsonify({'code': 400, 'message': '股票代码和标签ID不能为空'})
    
    relation = StockTagRelation.query.filter_by(stock_code=stock_code, tag_id=tag_id).first()
    if relation:
        db.session.delete(relation)
        db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '标签移除成功'
    })


@tag_bp.route('/batch/stock/tags', methods=['POST'])
def get_batch_stock_tags():
    """批量获取股票的标签"""
    data = request.get_json()
    stock_codes = data.get('stock_codes', [])
    
    if not stock_codes:
        return jsonify({'code': 200, 'data': {}})
    
    logger.info(f"[batch_stock_tags] 股票数量: {len(stock_codes)}, 前5个: {stock_codes[:5]}")
    
    relations = StockTagRelation.query.filter(StockTagRelation.stock_code.in_(stock_codes)).all()
    logger.info(f"[batch_stock_tags] 关联记录数: {len(relations)}")
    
    # 构建结果
    result = {}
    for rel in relations:
        if rel.stock_code not in result:
            result[rel.stock_code] = []
        tag = StockTag.query.get(rel.tag_id)
        if tag:
            result[rel.stock_code].append(tag.to_dict())
    
    logger.info(f"[batch_stock_tags] 返回结果: {result}")
    
    return jsonify({
        'code': 200,
        'data': result
    })
