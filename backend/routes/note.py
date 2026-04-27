"""
炒股笔记路由
"""
import logging
import re
from flask import Blueprint, request
from utils.api_response import ApiResponse
from models.stocknote import StockNote
from extensions import db
from sqlalchemy import or_

note_bp = Blueprint('note', __name__)
logger = logging.getLogger(__name__)


def extract_title_from_html(html_content):
    """从 HTML 内容中提取纯文本前50字符作为标题"""
    if not html_content:
        return None
    # 移除 HTML 标签获取纯文本
    text = re.sub(r'<[^>]+>', '', html_content)
    text = text.strip()
    if not text:
        return None
    return text[:50] + ('...' if len(text) > 50 else '')


# ==================== 炒股笔记 CRUD ====================

@note_bp.route('/notes', methods=['GET'])
def list_notes():
    """分页获取笔记列表，支持搜索"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        search = request.args.get('search', '', type=str).strip()
        stock_code = request.args.get('stock_code', '', type=str).strip()
        tag = request.args.get('tag', '', type=str).strip()

        query = StockNote.query

        if stock_code:
            query = query.filter(StockNote.stock_code == stock_code)

        if tag:
            query = query.filter(StockNote.tags.contains(tag))

        if search:
            # 搜索标题、内容、股票名称
            pattern = f'%{search}%'
            query = query.filter(
                or_(
                    StockNote.title.ilike(pattern),
                    StockNote.content.ilike(pattern),
                    StockNote.stock_name.ilike(pattern),
                    StockNote.tags.ilike(pattern)
                )
            )

        # 置顶优先，然后按更新时间倒序
        query = query.order_by(StockNote.is_pinned.desc(), StockNote.update_time.desc())

        total = query.count()
        notes = query.offset((page - 1) * page_size).limit(page_size).all()

        return ApiResponse.success({
            'list': [n.to_dict() for n in notes],
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': (total + page_size - 1) // page_size if total > 0 else 0
        })
    except Exception as e:
        logger.exception("获取笔记列表失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """获取单条笔记"""
    try:
        note = StockNote.query.get(note_id)
        if not note:
            return ApiResponse.not_found('笔记不存在')
        return ApiResponse.success(note.to_dict())
    except Exception as e:
        logger.exception("获取笔记失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes', methods=['POST'])
def create_note():
    """创建笔记"""
    try:
        data = request.get_json()
        if not data:
            return ApiResponse.bad_request('请求数据不能为空')

        content = data.get('content', '').strip()
        if not content:
            return ApiResponse.bad_request('笔记内容不能为空')

        stock_code = data.get('stockCode') or data.get('stock_code', '')
        stock_name = data.get('stockName') or data.get('stock_name', '')
        tags = data.get('tags', '')
        is_pinned = data.get('isPinned', data.get('is_pinned', False))
        title = data.get('title', '') or extract_title_from_html(content)

        note = StockNote(
            stock_code=stock_code or None,
            stock_name=stock_name or None,
            content=content,
            title=title,
            tags=tags or None,
            is_pinned=bool(is_pinned),
        )
        db.session.add(note)
        db.session.commit()
        return ApiResponse.success(note.to_dict(), message='笔记创建成功')
    except Exception as e:
        db.session.rollback()
        logger.exception("创建笔记失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """更新笔记"""
    try:
        note = StockNote.query.get(note_id)
        if not note:
            return ApiResponse.not_found('笔记不存在')

        data = request.get_json()
        if not data:
            return ApiResponse.bad_request('请求数据不能为空')

        if 'content' in data:
            content = data['content'].strip()
            if not content:
                return ApiResponse.bad_request('笔记内容不能为空')
            note.content = content
            # 如果没有手动指定标题，且内容变了，自动重新提取
            if not data.get('title'):
                note.title = extract_title_from_html(content)

        if 'title' in data:
            note.title = data['title'].strip() or None

        if 'stockCode' in data or 'stock_code' in data:
            note.stock_code = data.get('stockCode') or data.get('stock_code') or None

        if 'stockName' in data or 'stock_name' in data:
            note.stock_name = data.get('stockName') or data.get('stock_name') or None

        if 'tags' in data:
            note.tags = data['tags'] or None

        if 'isPinned' in data or 'is_pinned' in data:
            note.is_pinned = bool(data.get('isPinned', data.get('is_pinned')))

        db.session.commit()
        return ApiResponse.success(note.to_dict(), message='笔记更新成功')
    except Exception as e:
        db.session.rollback()
        logger.exception("更新笔记失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """删除笔记"""
    try:
        note = StockNote.query.get(note_id)
        if not note:
            return ApiResponse.not_found('笔记不存在')

        db.session.delete(note)
        db.session.commit()
        return ApiResponse.success(message='笔记删除成功')
    except Exception as e:
        db.session.rollback()
        logger.exception("删除笔记失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes/<int:note_id>/pin', methods=['PUT'])
def toggle_pin(note_id):
    """切换置顶状态"""
    try:
        note = StockNote.query.get(note_id)
        if not note:
            return ApiResponse.not_found('笔记不存在')

        note.is_pinned = not note.is_pinned
        db.session.commit()
        return ApiResponse.success(note.to_dict(), message='置顶状态已更新')
    except Exception as e:
        db.session.rollback()
        logger.exception("切换置顶状态失败")
        return ApiResponse.server_error(str(e))


@note_bp.route('/notes/tags', methods=['GET'])
def list_tags():
    """获取所有已使用的标签（去重）"""
    try:
        # 从 tags 字段中提取所有标签
        notes = StockNote.query.filter(StockNote.tags.isnot(None)).all()
        tag_set = set()
        for note in notes:
            for tag in note.tags.split(','):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)
        return ApiResponse.success(sorted(tag_set))
    except Exception as e:
        logger.exception("获取标签列表失败")
        return ApiResponse.server_error(str(e))
