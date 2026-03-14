from flask import Blueprint, request, jsonify
from extensions import db
from models.cycle import Cycle, CycleSubPeriod, CycleTradeDay

cycle_bp = Blueprint('cycle', __name__)


@cycle_bp.route('', methods=['GET'])
def get_cycles():
    """获取所有周期列表"""
    cycles = Cycle.query.order_by(Cycle.start_date.desc()).all()
    return jsonify({'code': 200, 'data': [c.to_dict() for c in cycles]})


@cycle_bp.route('/<int:cycle_id>', methods=['GET'])
def get_cycle(cycle_id):
    """获取单个周期详情"""
    cycle = Cycle.query.get(cycle_id)
    if not cycle:
        return jsonify({'code': 404, 'message': '周期不存在'}), 404
    return jsonify({'code': 200, 'data': cycle.to_dict()})


@cycle_bp.route('', methods=['POST'])
def create_cycle():
    """创建周期"""
    data = request.get_json()
    if not data or not data.get('title') or not data.get('start_date'):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400

    cycle = Cycle(
        title=data['title'],
        features=data.get('features', ''),
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        status=data.get('status', 'active')
    )
    db.session.add(cycle)
    db.session.commit()
    return jsonify({'code': 200, 'data': cycle.to_dict()})


@cycle_bp.route('/<int:cycle_id>', methods=['PUT'])
def update_cycle(cycle_id):
    """更新周期"""
    cycle = Cycle.query.get(cycle_id)
    if not cycle:
        return jsonify({'code': 404, 'message': '周期不存在'}), 404

    data = request.get_json()
    if data.get('title'):
        cycle.title = data['title']
    if 'features' in data:
        cycle.features = data['features']
    if 'start_date' in data:
        cycle.start_date = data['start_date']
    if 'end_date' in data:
        cycle.end_date = data['end_date']
    if 'status' in data:
        cycle.status = data['status']

    db.session.commit()
    return jsonify({'code': 200, 'data': cycle.to_dict()})


@cycle_bp.route('/<int:cycle_id>', methods=['DELETE'])
def delete_cycle(cycle_id):
    """删除周期"""
    cycle = Cycle.query.get(cycle_id)
    if not cycle:
        return jsonify({'code': 404, 'message': '周期不存在'}), 404

    db.session.delete(cycle)
    db.session.commit()
    return jsonify({'code': 200, 'message': '删除成功'})


# ===== 小周期管理 =====

@cycle_bp.route('/<int:cycle_id>/sub-periods', methods=['GET'])
def get_sub_periods(cycle_id):
    """获取周期下的所有小周期"""
    sub_periods = CycleSubPeriod.query.filter_by(cycle_id=cycle_id).order_by(CycleSubPeriod.order_num).all()
    return jsonify({'code': 200, 'data': [sp.to_dict() for sp in sub_periods]})


@cycle_bp.route('/<int:cycle_id>/sub-periods', methods=['POST'])
def create_sub_period(cycle_id):
    """创建小周期"""
    cycle = Cycle.query.get(cycle_id)
    if not cycle:
        return jsonify({'code': 404, 'message': '周期不存在'}), 404

    data = request.get_json()
    if not data or not data.get('period_type') or not data.get('start_date'):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400

    # 获取最大排序号
    max_order = db.session.query(db.func.max(CycleSubPeriod.order_num)).filter_by(cycle_id=cycle_id).scalar() or 0

    sub_period = CycleSubPeriod(
        cycle_id=cycle_id,
        period_type=data['period_type'],
        name=data.get('name', data['period_type']),
        start_date=data['start_date'],
        end_date=data.get('end_date'),
        order_num=data.get('order_num', max_order + 1)
    )
    db.session.add(sub_period)
    db.session.commit()
    return jsonify({'code': 200, 'data': sub_period.to_dict()})


@cycle_bp.route('/sub-periods/<int:sub_period_id>', methods=['PUT'])
def update_sub_period(sub_period_id):
    """更新小周期"""
    sub_period = CycleSubPeriod.query.get(sub_period_id)
    if not sub_period:
        return jsonify({'code': 404, 'message': '小周期不存在'}), 404

    data = request.get_json()
    if data.get('period_type'):
        sub_period.period_type = data['period_type']
    if 'name' in data:
        sub_period.name = data['name']
    if 'start_date' in data:
        sub_period.start_date = data['start_date']
    if 'end_date' in data:
        sub_period.end_date = data['end_date']
    if 'order_num' in data:
        sub_period.order_num = data['order_num']

    db.session.commit()
    return jsonify({'code': 200, 'data': sub_period.to_dict()})


@cycle_bp.route('/sub-periods/<int:sub_period_id>', methods=['DELETE'])
def delete_sub_period(sub_period_id):
    """删除小周期"""
    sub_period = CycleSubPeriod.query.get(sub_period_id)
    if not sub_period:
        return jsonify({'code': 404, 'message': '小周期不存在'}), 404

    db.session.delete(sub_period)
    db.session.commit()
    return jsonify({'code': 200, 'message': '删除成功'})


# ===== 交易日关联 =====

@cycle_bp.route('/trade-days', methods=['GET'])
def get_trade_days():
    """获取所有交易日与小周期的关联"""
    trade_days = CycleTradeDay.query.order_by(CycleTradeDay.trade_date.desc()).all()
    result = []
    for td in trade_days:
        item = td.to_dict()
        if td.sub_period:
            item['sub_period_name'] = td.sub_period.name
            item['period_type'] = td.sub_period.period_type
            item['cycle_id'] = td.sub_period.cycle_id
            item['cycle_title'] = td.sub_period.cycle.title if td.sub_period.cycle else None
        result.append(item)
    return jsonify({'code': 200, 'data': result})


@cycle_bp.route('/trade-days/bind', methods=['POST'])
def bind_trade_day():
    """绑定交易日到小周期"""
    data = request.get_json()
    if not data or not data.get('sub_period_id') or not data.get('trade_date'):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400

    sub_period = CycleSubPeriod.query.get(data['sub_period_id'])
    if not sub_period:
        return jsonify({'code': 404, 'message': '小周期不存在'}), 404

    # 检查是否已存在
    existing = CycleTradeDay.query.filter_by(trade_date=data['trade_date']).first()
    if existing:
        existing.sub_period_id = data['sub_period_id']
    else:
        trade_day = CycleTradeDay(
            sub_period_id=data['sub_period_id'],
            trade_date=data['trade_date']
        )
        db.session.add(trade_day)

    db.session.commit()
    return jsonify({'code': 200, 'message': '绑定成功'})


@cycle_bp.route('/trade-days/<string:trade_date>', methods=['DELETE'])
def unbind_trade_day(trade_date):
    """解绑交易日的关联"""
    trade_day = CycleTradeDay.query.filter_by(trade_date=trade_date).first()
    if not trade_day:
        return jsonify({'code': 404, 'message': '交易日不存在'}), 404

    db.session.delete(trade_day)
    db.session.commit()
    return jsonify({'code': 200, 'message': '解绑成功'})


@cycle_bp.route('/trade-days/batch', methods=['POST'])
def batch_bind_trade_days():
    """批量绑定交易日到小周期"""
    data = request.get_json()
    if not data or not data.get('sub_period_id') or not data.get('trade_dates'):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400

    sub_period = CycleSubPeriod.query.get(data['sub_period_id'])
    if not sub_period:
        return jsonify({'code': 404, 'message': '小周期不存在'}), 404

    trade_dates = data['trade_dates']
    for trade_date in trade_dates:
        existing = CycleTradeDay.query.filter_by(trade_date=trade_date).first()
        if existing:
            existing.sub_period_id = data['sub_period_id']
        else:
            trade_day = CycleTradeDay(
                sub_period_id=data['sub_period_id'],
                trade_date=trade_date
            )
            db.session.add(trade_day)

    db.session.commit()
    return jsonify({'code': 200, 'message': f'成功绑定 {len(trade_dates)} 个交易日'})


@cycle_bp.route('/by-date/<string:trade_date>', methods=['GET'])
def get_cycle_by_date(trade_date):
    """根据交易日获取所属周期信息（按小周期时间范围自动匹配）"""
    # 优先匹配已设定 end_date 的封闭小周期
    sub_period = CycleSubPeriod.query.filter(
        CycleSubPeriod.start_date <= trade_date,
        CycleSubPeriod.end_date >= trade_date
    ).order_by(CycleSubPeriod.start_date.desc()).first()

    # 未命中封闭区间，则归属到进行中（无 end_date）的小周期
    if not sub_period:
        sub_period = CycleSubPeriod.query.filter(
            CycleSubPeriod.end_date == None,
            CycleSubPeriod.start_date <= trade_date
        ).order_by(CycleSubPeriod.start_date.desc()).first()

    if not sub_period:
        return jsonify({'code': 404, 'message': '该交易日未在任何小周期时间范围内'}), 404

    cycle = sub_period.cycle

    return jsonify({
        'code': 200,
        'data': {
            'trade_date': trade_date,
            'cycle': cycle.to_dict() if cycle else None,
            'sub_period': sub_period.to_dict()
        }
    })


@cycle_bp.route('/latest', methods=['GET'])
def get_latest_cycle():
    """获取当前进行中（无 end_date）的小周期信息"""
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')

    # 直接取进行中（无 end_date）且已开始的小周期
    sub_period = CycleSubPeriod.query.filter(
        CycleSubPeriod.end_date == None,
        CycleSubPeriod.start_date <= today
    ).order_by(CycleSubPeriod.start_date.desc()).first()

    if not sub_period:
        # 兜底：取 start_date 最近的小周期
        sub_period = CycleSubPeriod.query.order_by(CycleSubPeriod.start_date.desc()).first()

    if not sub_period:
        return jsonify({'code': 404, 'message': '暂无周期数据'}), 404

    cycle = sub_period.cycle

    return jsonify({
        'code': 200,
        'data': {
            'trade_date': today,
            'cycle': cycle.to_dict() if cycle else None,
            'sub_period': sub_period.to_dict()
        }
    })
