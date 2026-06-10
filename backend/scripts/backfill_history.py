#!/usr/bin/env python3
"""
独立历史 K 线回填脚本（一次性 / 可断点续跑）—— 大历史数据灌库专用工具。

== 为什么用独立脚本（而非 in-app 同步任务）==
in-app 任务做长周期回填有两个硬伤：
  ① 增量过滤是「区间内有 ≥1 行即视为已齐全、跳过」——每只活跃股都已有近期数据(2025-06+)，
     于是几乎全被跳过，2007-2025 的历史一行都拉不到（正确性 bug）。
  ② 数小时的同步线程跑在 gunicorn worker 进程内，worker 回收/重新部署会中断。
本脚本：脱离 web 进程，直连 DB + 复用 DataSyncService.save_kline_data（分块800 + INSERT ON
DUPLICATE KEY UPDATE，幂等可反复跑），用**正确的 done 判断**（已有 min(trade_date) ≤ START
才算回溯到位），断点续跑，baostock 掉线自动重登。

== 用法（在 daydayup-backend 容器内）==
  # 后台跑（推荐，3-4h），日志写文件：
  docker exec -d daydayup-backend sh -c "python /app/scripts/backfill_history.py > /tmp/backfill.log 2>&1"
  # 前台跑（看实时输出）：
  docker exec daydayup-backend python /app/scripts/backfill_history.py
  # 监控：
  docker exec daydayup-backend tail -f /tmp/backfill.log
  # 或查 DB： SELECT MIN(trade_date), COUNT(*) FROM stock_daily_kline;  应见 min 降到 2007

== 参数（环境变量，均有默认）==
  BACKFILL_START=2007-01-01   起始日（覆盖 07大牛/08熊/15牛熊/18熊/19-21牛/22熊/24-26 多 regime）
  BACKFILL_END=2025-08-01     结束日（与已有数据 2025-06+ 略重叠，upsert 幂等无害）
  BACKFILL_TYPE=stock         股票类型（stock=真股票5525只；不要用 all，会混入 baostock 拉不到的 ETF）

== 限制 ==
  baostock 不支持北交所(bj.)，脚本自动跳过（如需北交所历史，另接 tushare）。
"""
import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, "/app")

START = os.getenv("BACKFILL_START", "2007-01-01")
END = os.getenv("BACKFILL_END", "2025-08-01")
STOCK_TYPE = os.getenv("BACKFILL_TYPE", "stock")
FREQ = "daily"
CKPT = os.getenv("BACKFILL_CKPT", "/app/scripts/backfill_ckpt.json")
LOG_EVERY = 20


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def main():
    from app import create_app
    from extensions import db
    from sqlalchemy import func

    app = create_app("development")
    with app.app_context():
        from services.data_sync_service import get_data_sync_service
        from models.kline import StockDailyKLine
        from models.stockbasic import StockBasic

        svc = get_data_sync_service()
        try:
            svc.ensure_login()
            log("baostock 登录成功")
        except Exception as e:
            log(f"baostock 登录失败，退出：{e}")
            sys.exit(1)

        # universe：真股票，且仅 baostock 支持的 sh./sz.（排除北交所 bj. 等）
        rows = db.session.query(StockBasic.stock_code, StockBasic.stock_name).filter(
            StockBasic.stock_type == STOCK_TYPE).all()
        name_map = {c: n for c, n in rows}
        all_codes = sorted(name_map.keys())
        codes = [c for c in all_codes if c.startswith(("sh.", "sz."))]
        skipped = len(all_codes) - len(codes)
        log(f"区间 {START} ~ {END} | 类型 {STOCK_TYPE}：共 {len(all_codes)} 只，"
            f"baostock 可拉(sh/sz) {len(codes)} 只，跳过北交所等 {skipped} 只")

        # 断点续跑：已完成代码集
        done = set()
        if os.path.exists(CKPT):
            try:
                done = set(json.load(open(CKPT)).get("done", []))
            except Exception:
                done = set()

        # 正确的 done 判断：已有 min(trade_date) ≤ START = 历史已回溯到位（不是"有≥1行"）
        have_history = set()
        try:
            mrows = db.session.query(
                StockDailyKLine.stock_code, func.min(StockDailyKLine.trade_date)
            ).filter(StockDailyKLine.stock_code.in_(codes)).group_by(
                StockDailyKLine.stock_code).all()
            have_history = {c for c, mn in mrows if mn and mn <= START}
        except Exception as e:
            log(f"⚠️ 已有历史检查失败（不影响，全量跑）：{e}")
            try:
                db.session.rollback()
            except Exception:
                pass

        todo = [c for c in codes if c not in done and c not in have_history]
        log(f"已回溯到位 {len(have_history)} 只 + 断点已完成 {len(done)} 只 → 本次待处理 {len(todo)} 只")
        if not todo:
            log("无待处理股票，全部已回溯到位。")
            return

        saved_total = 0
        fail = []
        t0 = time.time()
        for i, code in enumerate(todo, 1):
            try:
                # adjustflag 默认 '2'(前复权)，与每日复盘同步口径一致；连续复权适合顶底/新高回测
                data = svc.get_kline_data(code, START, END, FREQ)
                if data:
                    svc.save_kline_data(db.session, data, FREQ, name_map)
                    saved_total += len(data)
                done.add(code)
            except Exception as e:
                log(f"  ✗ {code} 失败：{e}")
                fail.append(code)
                try:
                    db.session.rollback()  # 防 session 中毒拖垮后续
                except Exception:
                    pass
                try:
                    svc.ensure_login()  # 失败常因 baostock 掉线，重登
                except Exception:
                    pass
                continue

            if i % LOG_EVERY == 0:
                json.dump({"done": list(done)}, open(CKPT, "w"))
                el = time.time() - t0
                eta = el / i * (len(todo) - i) / 60
                log(f"进度 {i}/{len(todo)} | 累计存 {saved_total} 行 | 用时 {el/60:.1f}min "
                    f"| ETA {eta:.0f}min | 失败 {len(fail)}")

        json.dump({"done": list(done)}, open(CKPT, "w"))
        try:
            svc.logout()
        except Exception:
            pass
        log(f"✅ 完成：处理 {len(todo)} 只，新增 ~{saved_total} 行，失败 {len(fail)} 只")
        if fail:
            log(f"失败代码(重跑本脚本会自动续传)：{fail[:30]}{'...' if len(fail) > 30 else ''}")


if __name__ == "__main__":
    main()
