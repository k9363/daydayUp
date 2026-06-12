"""
baostock 进程级串行化锁 + 安全登录。

根因：baostock 是模块级全局单例（一个 socket 长连接），非线程安全。daydayUp 里
启动线程、复盘同步线程（run_sync_task）、APScheduler 定时线程会并发调 bs.login()/
bs.query_*，并发操作同一 socket 导致协议层串话 → "网络接收错误"，登录/查询频繁失败。

方案：所有 baostock 登录统一走 safe_bs_login()，用进程级 RLock 串行化 + 失败重试，
消除并发 login 冲突。baostock 现仅作 tushare 的兜底，串行化带来的性能损失可忽略。
"""
import concurrent.futures
import threading
import logging
import time

logger = logging.getLogger(__name__)

# 进程级共享锁：所有用到 baostock 的线程（启动/同步/定时）共用，串行化对全局会话的操作
BAOSTOCK_LOCK = threading.RLock()

# bs.login() 超时：baostock 是全局单 socket 单例,某次查询服务端不响应会让 socket 卡在 recv,
# 此时重连 bs.login() 在同一坏 socket 上会【无限阻塞】→ 整个同步死锁(2026-06-12 复盘卡死根因:
# 查询有30s超时、但登录没有,超时后重连卡死、连 MAX_CONSECUTIVE_TIMEOUTS 熔断都没机会触发)。
# 给登录套线程级超时,让重连失败可被上层熔断,而非永久挂死。
_LOGIN_TIMEOUT_SEC = 15


def _bs_login_with_timeout(timeout=_LOGIN_TIMEOUT_SEC):
    import baostock as bs
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(bs.login).result(timeout=timeout)
    finally:
        ex.shutdown(wait=False)  # 卡住的 login 线程后台泄漏,随 daydayup-backend 重启清空


def safe_bs_login(max_retry=3):
    """串行化 + 重试的 baostock 登录(登录套超时)。成功返回 login 结果对象；重试耗尽抛异常。"""
    with BAOSTOCK_LOCK:
        last_err = None
        for attempt in range(1, max_retry + 1):
            try:
                lg = _bs_login_with_timeout()
            except concurrent.futures.TimeoutError:
                last_err = f"login 超时(>{_LOGIN_TIMEOUT_SEC}s,全局 socket 疑似卡死)"
                logger.warning(f"⚠️ baostock 登录超时（{attempt}/{max_retry}）: {last_err}")
                if attempt < max_retry:
                    time.sleep(2 * attempt)
                continue
            if lg.error_code == '0':
                if attempt > 1:
                    logger.info(f"✅ baostock 登录成功（第 {attempt} 次尝试）")
                return lg
            last_err = lg.error_msg
            logger.warning(f"⚠️ baostock 登录失败（{attempt}/{max_retry}）: {last_err}")
            if attempt < max_retry:
                time.sleep(2 * attempt)
        raise Exception(f"Baostock登录失败: {last_err}")
