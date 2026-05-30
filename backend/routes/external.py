"""
外部系统集成路由（TradingAgents-CN 等推送分析结果到此）。
"""
import logging
from flask import Blueprint, jsonify, request

from extensions import db
from models.external_analysis import ExternalAnalysis
from utils.api_response import ApiResponse

logger = logging.getLogger(__name__)

external_bp = Blueprint('external', __name__)


@external_bp.route('/analysis', methods=['POST'])
def upsert_external_analysis():
    """接收外部系统（TA-CN 等）推送的分析结果。

    Body (JSON):
        source              required, 如 "ta-cn"
        external_id         required, 来源系统的任务/分析 ID
        stock_code          required
        stock_name          optional
        trade_date          optional, YYYY-MM-DD
        decision            optional, buy/sell/hold/neutral
        confidence          optional, 0-1
        target_price        optional
        summary             optional, 200 字以内
        raw_report          optional, JSON
        report_url          optional
        related_review_task_id optional

    幂等：按 (source, external_id) 唯一约束 upsert。
    """
    try:
        payload = request.get_json(silent=True) or {}
        source = (payload.get('source') or '').strip()
        external_id = (payload.get('external_id') or '').strip()
        stock_code = (payload.get('stock_code') or '').strip()
        if not source or not external_id or not stock_code:
            return jsonify({'code': 400, 'message': 'source / external_id / stock_code 都必填'}), 400

        # 查重
        existing = ExternalAnalysis.query.filter_by(source=source, external_id=external_id).first()
        if existing:
            obj = existing
            action = 'updated'
        else:
            obj = ExternalAnalysis(source=source, external_id=external_id, stock_code=stock_code)
            db.session.add(obj)
            action = 'created'

        obj.stock_code = stock_code
        obj.stock_name = payload.get('stock_name') or obj.stock_name
        obj.trade_date = payload.get('trade_date') or obj.trade_date
        obj.decision = payload.get('decision') or obj.decision
        obj.confidence = payload.get('confidence') if payload.get('confidence') is not None else obj.confidence
        obj.target_price = payload.get('target_price') if payload.get('target_price') is not None else obj.target_price
        obj.summary = payload.get('summary') or obj.summary
        obj.raw_report = payload.get('raw_report') if payload.get('raw_report') is not None else obj.raw_report
        obj.report_url = payload.get('report_url') or obj.report_url
        obj.related_review_task_id = payload.get('related_review_task_id') or obj.related_review_task_id

        db.session.commit()
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {'id': obj.id, 'action': action}
        })
    except Exception as e:
        db.session.rollback()
        logger.exception(f"upsert_external_analysis failed: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@external_bp.route('/analysis', methods=['GET'])
def list_external_analysis():
    """按股票代码 / 来源 / 日期查询外部分析。

    Query:
        stock_code  optional
        source      optional
        trade_date  optional (YYYY-MM-DD)
        days        optional, 配合无 trade_date 时取最近 N 天
        limit       optional, 默认 50
    """
    try:
        from datetime import datetime, timedelta
        stock_code = request.args.get('stock_code')
        source = request.args.get('source')
        trade_date = request.args.get('trade_date')
        days = request.args.get('days', type=int)
        limit = request.args.get('limit', default=50, type=int)

        # 2026-05-24: 列表只 select 小字段，避免 raw_report (大 JSON) 进入 ORDER BY 临时表导致
        # MySQL "Out of sort memory" 错误。raw_report 仅在 GET /<id> 详情接口里返回。
        cols = [
            ExternalAnalysis.id, ExternalAnalysis.source, ExternalAnalysis.external_id,
            ExternalAnalysis.stock_code, ExternalAnalysis.stock_name,
            ExternalAnalysis.trade_date, ExternalAnalysis.decision,
            ExternalAnalysis.confidence, ExternalAnalysis.target_price,
            ExternalAnalysis.summary, ExternalAnalysis.report_url,
            ExternalAnalysis.related_review_task_id,
            ExternalAnalysis.create_time, ExternalAnalysis.update_time,
        ]
        q = db.session.query(*cols)
        if stock_code:
            q = q.filter(ExternalAnalysis.stock_code == stock_code)
        if source:
            q = q.filter(ExternalAnalysis.source == source)
        if trade_date:
            q = q.filter(ExternalAnalysis.trade_date == trade_date)
        elif days:
            since = datetime.now() - timedelta(days=days)
            q = q.filter(ExternalAnalysis.create_time >= since)

        rows = q.order_by(ExternalAnalysis.create_time.desc()).limit(limit).all()
        return jsonify({'code': 200, 'data': [
            {
                'id': r.id,
                'source': r.source,
                'external_id': r.external_id,
                'stock_code': r.stock_code,
                'stock_name': r.stock_name,
                'trade_date': r.trade_date,  # String(10) "YYYY-MM-DD"
                'decision': r.decision,
                'confidence': float(r.confidence) if r.confidence is not None else None,
                'target_price': float(r.target_price) if r.target_price is not None else None,
                'summary': r.summary,
                'report_url': r.report_url,
                'related_review_task_id': r.related_review_task_id,
                'create_time': r.create_time.isoformat() if r.create_time else None,
                'update_time': r.update_time.isoformat() if r.update_time else None,
            } for r in rows
        ]})
    except Exception as e:
        logger.exception(f"list_external_analysis failed: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@external_bp.route('/analysis/<int:analysis_id>', methods=['GET'])
def get_external_analysis(analysis_id):
    try:
        obj = ExternalAnalysis.query.get(analysis_id)
        if not obj:
            return jsonify({'code': 404, 'message': 'not found'}), 404
        return jsonify({'code': 200, 'data': obj.to_dict()})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@external_bp.route('/analysis/<int:analysis_id>', methods=['DELETE'])
def delete_external_analysis(analysis_id):
    """删除指定 ID 的外部分析记录（含交割单复盘历史）。"""
    try:
        obj = ExternalAnalysis.query.get(analysis_id)
        if not obj:
            return jsonify({'code': 404, 'message': 'not found'}), 404
        db.session.delete(obj)
        db.session.commit()
        return jsonify({'code': 200, 'message': 'deleted', 'data': {'id': analysis_id}})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"删除 external_analysis {analysis_id} 失败")
        return jsonify({'code': 500, 'message': str(e)}), 500


def register_external_blueprint(app):
    app.register_blueprint(external_bp, url_prefix='/api/external')
