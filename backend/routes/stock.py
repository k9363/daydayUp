"""
股票数据API路由
"""
from flask import Blueprint, request, jsonify
from services.baostock_service import BaostockService
from extensions import db
from models.stockdaily import StockDaily
from datetime import datetime, timedelta
import json
import pandas as pd

stock_bp = Blueprint('stock', __name__)


@stock_bp.route('/list', methods=['GET'])
def stock_list():
    """获取股票列表"""
    try:
        date = request.args.get('date')
        
        service = BaostockService()
        stocks = service.get_stock_list(date)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': stocks
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/info/<stock_code>', methods=['GET'])
def stock_info(stock_code):
    """获取股票基本信息"""
    try:
        service = BaostockService()
        info = service.get_stock_info(stock_code)
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': info
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/history', methods=['GET'])
def stock_history():
    """获取股票历史数据"""
    try:
        symbol = request.args.get('symbol')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        frequency = request.args.get('frequency', 'daily')
        adjust_type = request.args.get('adjustType', 'qfq')
        
        if not symbol:
            return jsonify({'code': 400, 'message': '请输入股票代码'}), 400
        
        if not start_date:
            # 默认获取最近30天数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        service = BaostockService()
        df = service.get_stock_zh_a_hist(symbol, start_date, end_date, frequency, adjust_type)
        
        # 转换为字典列表
        data = df.to_dict('records') if not df.empty else []
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': data
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/daily_basic', methods=['GET'])
def stock_daily_basic():
    """获取股票每日基本面数据"""
    try:
        symbol = request.args.get('symbol')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        if not symbol:
            return jsonify({'code': 400, 'message': '请输入股票代码'}), 400
        
        if not start_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        service = BaostockService()
        df = service.get_daily_basic(symbol, start_date, end_date)
        
        data = df.to_dict('records') if not df.empty else []
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': data
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/industry', methods=['GET'])
def stock_industry():
    """获取行业分类"""
    try:
        service = BaostockService()
        industries = service.get_industry_classify()
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': industries
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/import', methods=['POST'])
def import_stock_data():
    """导入股票历史数据"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'code': 400, 'message': '请求数据不能为空'}), 400
        
        stock_code = data.get('stockCode')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        
        if not stock_code:
            return jsonify({'code': 400, 'message': '请输入股票代码'}), 400
        
        # 默认时间范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 获取股票数据
        service = BaostockService()
        df = service.get_stock_zh_a_hist(stock_code, start_date, end_date)
        
        if df.empty:
            return jsonify({'code': 404, 'message': '未获取到股票数据'}), 404
        
        # 保存数据到数据库
        stock_name = stock_code
        for _, row in df.iterrows():
            if pd.notna(row.get('name')):
                stock_name = row['name']
                break
            
            record = StockDaily(
                stock_code=stock_code,
                stock_name=stock_name,
                trade_date=row.get('date', ''),
                open_price=row.get('open') or None,
                high_price=row.get('high') or None,
                low_price=row.get('low') or None,
                close_price=row.get('close') or None,
                pre_close_price=row.get('preclose') or None,
                volume=row.get('volume') or None,
                turnover=row.get('amount') or None,
                change_percent=row.get('pctChg') or None,
            )
            db.session.add(record)
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '导入成功',
            'data': {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'row_count': len(df),
                'start_date': start_date,
                'end_date': end_date
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': str(e)}), 500


@stock_bp.route('/realtime', methods=['GET'])
def stock_realtime():
    """获取实时行情"""
    try:
        symbols = request.args.getlist('symbols')
        
        if not symbols:
            return jsonify({'code': 400, 'message': '请输入股票代码'}), 400
        
        service = BaostockService()
        df = service.get_realtime_quotes(symbols)
        
        data = df.to_dict('records') if not df.empty else []
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': data
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500
