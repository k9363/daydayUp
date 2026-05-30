"""邮件服务：把每日复盘详情发到指定邮箱

设计：
  - SMTP 配置走 env，避免硬编码（见下方 _smtp_config）
  - 内容：复盘摘要 + Top10 个股因子 + Top 板块 + （可选）TA-CN 全市场综合分析 + 复盘页链接
  - 复盘完成后自动调用（review_service 完成路径里调 send_daily_review_email）；
    也提供路由手动重发（routes/email.py）。
  - 失败只 log warning，不影响复盘成功状态。

环境变量：
  SMTP_HOST              SMTP 服务器，如 smtp.qq.com / smtp.163.com
  SMTP_PORT              端口（465=SSL，587=STARTTLS），默认 465
  SMTP_USER              登录账号（通常即发件邮箱）
  SMTP_PASSWORD          授权码（不是登录密码，去邮箱后台申请）
  SMTP_FROM              发件人地址（默认=SMTP_USER）
  SMTP_FROM_NAME         发件人显示名，默认 "daydayUp 复盘助手"
  SMTP_USE_SSL           true/false，默认 true（与 465 对应；587 时改 false）
  EMAIL_REVIEW_RECIPIENTS 收件人列表，逗号分隔
  EMAIL_REVIEW_ENABLED   true/false，默认 true（false 时跳过自动发送）
  DAYDAYUP_PUBLIC_URL    daydayUp 对外访问 URL，用于邮件里的链接
"""
import json
import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models.reviewresult import ReviewResult
from models.reviewtask import ReviewTask

logger = logging.getLogger(__name__)


# ============== 配置 ==============

def _smtp_config() -> Dict[str, Any]:
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "465")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_addr": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", ""),
        "from_name": os.getenv("SMTP_FROM_NAME", "daydayUp 复盘助手"),
        "use_ssl": os.getenv("SMTP_USE_SSL", "true").lower() != "false",
    }


def _default_recipients() -> List[str]:
    raw = os.getenv("EMAIL_REVIEW_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def is_review_email_enabled() -> bool:
    return os.getenv("EMAIL_REVIEW_ENABLED", "true").lower() != "false"


def _public_base_url() -> str:
    return os.getenv("DAYDAYUP_PUBLIC_URL", "http://192.168.31.123:20080")


# ============== 工具 ==============

def _h(text: Any) -> str:
    """HTML 转义"""
    if text is None:
        return ""
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _markdown_to_html(md: Optional[str]) -> str:
    """轻量 markdown → HTML；无 markdown 库时退回 <pre> 包裹转义文本。"""
    if not md:
        return ""
    try:
        import markdown  # 可选依赖
        return markdown.markdown(md, extensions=["tables", "fenced_code"])
    except ImportError:
        return f"<pre style=\"white-space:pre-wrap;font-family:inherit\">{_h(md)}</pre>"


def _strip_section_by_heading(md: Optional[str], *keywords: str) -> Optional[str]:
    """从 markdown 中剥离含 keyword 的章节（h1~h3 / 加粗 / "X、" 编号 都识别为章节起点）。

    遇到含任一 keyword 的章节标题行 → 从该行开始丢弃；直到下一个同/更高层级标题行恢复。
    用于在邮件展示场景里隐藏某些章节（如「持仓个股操作建议」），原始报告不变。
    """
    if not md:
        return md
    import re
    heading_patterns = [
        re.compile(r"^\s*#{1,3}\s+"),                              # markdown # / ## / ###
        re.compile(r"^\s*\*\*\s*[一二三四五六七八九十百千]+\s*[、.]"),  # **一、...** 加粗标题
        re.compile(r"^\s*[一二三四五六七八九十百千]+\s*[、.][^\d]"),    # 一、xxx 中文编号标题
    ]
    def is_heading(line: str) -> bool:
        return any(p.match(line) for p in heading_patterns)

    out, skip = [], False
    for line in md.split("\n"):
        if is_heading(line):
            hit = any(kw in line for kw in keywords)
            if hit:
                skip = True
                continue
            else:
                skip = False
        if not skip:
            out.append(line)
    return "\n".join(out)


def _safe_json_loads(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


# ============== 数据采集 ==============

def _fetch_top10_stocks(task_id: int) -> List[Dict[str, Any]]:
    """从 review_result 拉「因子分析 / 前10股票」的 JSON 明细。
    存储约定（见 review_service._save_review_results）：detail_data 是 JSON，含股票列表。"""
    try:
        rr = (ReviewResult.query
              .filter_by(task_id=task_id, dimension='因子分析', metric_name='前10股票')
              .first())
        if not rr or not rr.detail_data:
            return []
        data = _safe_json_loads(rr.detail_data)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("stocks", "items", "list", "data"):
                if isinstance(data.get(k), list):
                    return data[k]
        return []
    except Exception as e:
        logger.warning(f"取 Top10 个股失败: {e}")
        return []


def _fetch_top_sectors(task_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """从 review_result 拉板块得分（dimension 名称版本可能不同，宽匹配）。"""
    try:
        rrs = (ReviewResult.query
               .filter(ReviewResult.task_id == task_id)
               .filter(ReviewResult.dimension.in_(['板块分析', '板块得分', 'sector', 'sector_score']))
               .all())
        # 优先：单条 detail_data 含板块列表的
        for rr in rrs:
            data = _safe_json_loads(rr.detail_data)
            if isinstance(data, list) and data:
                return data[:limit]
            if isinstance(data, dict):
                for k in ("sectors", "items", "list", "data"):
                    if isinstance(data.get(k), list):
                        return data[k][:limit]
        # 退路：按 metric_value 数值排序
        sortable: List[Tuple[float, Dict[str, Any]]] = []
        for rr in rrs:
            try:
                v = float(rr.metric_value) if rr.metric_value is not None else 0.0
            except (TypeError, ValueError):
                v = 0.0
            sortable.append((v, {"sector_name": rr.metric_name, "total_score": rr.metric_value}))
        sortable.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in sortable[:limit]]
    except Exception as e:
        logger.warning(f"取板块得分失败: {e}")
        return []


def _fetch_external_market_report(trade_date: Optional[str], task_id: int) -> Optional[str]:
    """取 TA-CN 全市场综合分析全文（1W+ 字）。

    存储路径（实测确认 2026-05-28）:
      external_analysis 表, source='ta-cn-batch', 同 trade_date 匹配；
      全文在 raw_report.result.report（嵌套，不是顶层）；data_markdown 等也在 result 下。
    """
    try:
        from models.external_analysis import ExternalAnalysis
    except Exception:
        return None
    try:
        q = ExternalAnalysis.query
        # 优先按关联 review_task；其次按 trade_date + source ta-cn-batch
        ext = q.filter(ExternalAnalysis.related_review_task_id == task_id).order_by(ExternalAnalysis.id.desc()).first()
        if not ext and trade_date:
            ext = (q.filter(ExternalAnalysis.trade_date == trade_date)
                   .filter(ExternalAnalysis.source.in_(['ta-cn-batch', 'ta-cn-batch-market']))
                   .order_by(ExternalAnalysis.id.desc()).first())
        if not ext and trade_date:
            ext = (q.filter(ExternalAnalysis.trade_date == trade_date)
                   .filter(ExternalAnalysis.source.like('%batch%'))
                   .order_by(ExternalAnalysis.id.desc()).first())
        if not ext:
            return None
        raw = ext.raw_report
        if isinstance(raw, str):
            raw = _safe_json_loads(raw) or {}
        if not isinstance(raw, dict):
            return _markdown_to_html(ext.summary) if ext.summary else None

        # 邮件渲染前剥离的章节关键词（用户希望邮件里不出现持仓个股操作建议）
        STRIP_KW = ("持仓个股操作建议", "持仓操作建议", "持仓个股")
        # raw_report 实际结构: {"result": {"report": "...1.6W字...", "data_markdown": "..."}} 或扁平
        result_node = raw.get("result") if isinstance(raw.get("result"), dict) else raw
        for k in ("report", "report_md", "markdown"):
            v = result_node.get(k)
            if v and isinstance(v, str):
                return _markdown_to_html(_strip_section_by_heading(v, *STRIP_KW))
        # 顶层 fallback
        for k in ("report", "report_md", "markdown", "summary"):
            v = raw.get(k)
            if v and isinstance(v, str):
                return _markdown_to_html(_strip_section_by_heading(v, *STRIP_KW))
        if ext.summary:
            return _markdown_to_html(_strip_section_by_heading(ext.summary, *STRIP_KW))
        return None
    except Exception as e:
        logger.warning(f"取全市场分析失败（忽略，邮件仍会发）: {e}")
        return None


def _fetch_all_review_dimensions(task_id: int) -> List[Dict[str, Any]]:
    """拉本次复盘的所有 review_result 行（除 Top10/板块这两个已单独渲染的维度外），按维度归并。
    每个返回项: {dimension, items: [{metric_name, metric_value, status, suggestion, detail_text}]}。"""
    try:
        rrs = (ReviewResult.query
               .filter_by(task_id=task_id)
               .order_by(ReviewResult.dimension.asc(), ReviewResult.id.asc())
               .all())
    except Exception as e:
        logger.warning(f"取全部复盘维度失败: {e}")
        return []

    skip_pairs = {('因子分析', '前10股票')}  # 已在 Top10 个股段渲染
    skip_dims = {'板块分析', '板块得分'}      # 已在 Top10 板块段渲染

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for rr in rrs:
        dim = rr.dimension or '其它'
        mn = rr.metric_name or ''
        if (dim, mn) in skip_pairs or dim in skip_dims:
            continue
        # detail_data 优先尝试 JSON 简短摘要；过长截断
        detail = None
        if rr.detail_data:
            j = _safe_json_loads(rr.detail_data)
            if isinstance(j, (dict, list)):
                # 仅截取一个简短摘要避免邮件臃肿；用 json dumps 但限长
                s = json.dumps(j, ensure_ascii=False)
                detail = s if len(s) <= 600 else s[:600] + '…（节略）'
            elif isinstance(j, str):
                detail = j if len(j) <= 600 else j[:600] + '…'
            else:
                detail = str(rr.detail_data)[:600]
        grouped.setdefault(dim, []).append({
            'metric_name': mn,
            'metric_value': rr.metric_value,
            'status': rr.status,
            'suggestion': rr.suggestion,
            'detail_text': detail,
        })
    return [{'dimension': k, 'items': v} for k, v in grouped.items()]


# ============== HTML 渲染 ==============

def _fmt_num(v: Any, nd: int = 2) -> str:
    try:
        if v is None or v == "":
            return "-"
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return _h(v)


def _build_html(task: ReviewTask,
                top_stocks: List[Dict[str, Any]],
                sectors: List[Dict[str, Any]],
                ext_html: Optional[str],
                all_dims: Optional[List[Dict[str, Any]]] = None) -> str:
    base = _public_base_url()
    trade_date = task.trade_date or "-"
    review_url = f"{base}/review?id={task.id}" if getattr(task, 'id', None) else f"{base}/review"

    # 个股表
    if top_stocks:
        rows = []
        for i, s in enumerate(top_stocks[:10], 1):
            code = s.get("code") or s.get("stock_code") or "-"
            name = s.get("name") or s.get("stock_name") or "-"
            sector = s.get("sector") or s.get("industry") or "-"
            score = s.get("totalScore", s.get("total_score", s.get("score")))
            cp = s.get("changePercent", s.get("change_percent"))
            amt = s.get("amount", s.get("turnover_yi"))
            rows.append(
                f"<tr>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed'>{i}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed;font-family:monospace'>{_h(code)}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed'>{_h(name)}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed;color:#666;font-size:12px'>{_h(sector)}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed;text-align:right'>{_fmt_num(cp)}%</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed;text-align:right'><b>{_fmt_num(score, 3)}</b></td>"
                f"</tr>")
        stock_table = "".join(rows)
    else:
        stock_table = "<tr><td colspan='6' style='padding:12px;color:#999;text-align:center'>无 Top10 数据</td></tr>"

    # 板块表
    if sectors:
        srows = []
        for i, s in enumerate(sectors[:10], 1):
            sname = s.get("sector_name") or s.get("name") or "-"
            score = s.get("total_score") or s.get("score") or s.get("totalScore")
            srows.append(
                f"<tr>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed'>{i}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed'>{_h(sname)}</td>"
                f"<td style='padding:6px 8px;border:1px solid #e0e6ed;text-align:right'><b>{_fmt_num(score, 3)}</b></td>"
                f"</tr>")
        sector_table = "".join(srows)
    else:
        sector_table = "<tr><td colspan='3' style='padding:12px;color:#999;text-align:center'>无板块数据</td></tr>"

    # TA-CN 全市场综合分析全文（1W+ 字），放在突出位置（摘要后立刻给）
    ext_block = ""
    if ext_html:
        ext_block = (
            "<h3 style='margin-top:24px;color:#333'>🌐 全市场综合分析（TA-CN 多代理 LLM）— 全文</h3>"
            "<div style='font-size:13.5px;line-height:1.75;background:#fafbfc;padding:18px;"
            "border:1px solid #e0e6ed;border-radius:6px;overflow-x:auto'>" + ext_html + "</div>"
        )

    # 全部复盘维度（除 Top10 个股/板块已单独表格化外的全部数据）
    dims_block = ""
    if all_dims:
        dim_rows = []
        for dim_grp in all_dims:
            dim_name = dim_grp.get('dimension', '')
            items = dim_grp.get('items') or []
            if not items:
                continue
            item_rows = []
            for it in items:
                color = ('#67c23a' if it.get('status') == 'normal' else
                         '#e6a23c' if it.get('status') == 'warning' else
                         '#f56c6c' if it.get('status') == 'critical' else '#909399')
                detail = it.get('detail_text')
                detail_html = (f"<details style='margin-top:4px'><summary style='cursor:pointer;color:#909399;font-size:11px'>明细数据</summary>"
                               f"<pre style='font-size:11px;background:#f5f7fa;padding:6px;border-radius:3px;overflow:auto;white-space:pre-wrap'>{_h(detail)}</pre></details>") if detail else ''
                item_rows.append(
                    f"<tr>"
                    f"<td style='padding:6px 8px;border:1px solid #e0e6ed'>{_h(it.get('metric_name') or '-')}</td>"
                    f"<td style='padding:6px 8px;border:1px solid #e0e6ed;text-align:right'>{_h(it.get('metric_value') or '-')}</td>"
                    f"<td style='padding:6px 8px;border:1px solid #e0e6ed'><span style='display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:4px'></span>{_h(it.get('status') or '-')}</td>"
                    f"<td style='padding:6px 8px;border:1px solid #e0e6ed;color:#666;font-size:12px'>{_h(it.get('suggestion') or '')}{detail_html}</td>"
                    f"</tr>")
            dim_rows.append(
                f"<h4 style='margin:18px 0 6px;color:#1a73e8'>📂 {_h(dim_name)}</h4>"
                f"<table style='width:100%;border-collapse:collapse;font-size:12px'>"
                f"<thead style='background:#f0f4f8'><tr>"
                f"<th style='padding:6px;text-align:left;border:1px solid #e0e6ed'>指标</th>"
                f"<th style='padding:6px;text-align:right;border:1px solid #e0e6ed'>值</th>"
                f"<th style='padding:6px;text-align:left;border:1px solid #e0e6ed'>状态</th>"
                f"<th style='padding:6px;text-align:left;border:1px solid #e0e6ed'>建议 / 明细</th>"
                f"</tr></thead><tbody>" + "".join(item_rows) + "</tbody></table>"
            )
        if dim_rows:
            dims_block = (
                "<h3 style='margin-top:24px;color:#333'>📋 全部复盘维度</h3>"
                + "".join(dim_rows)
            )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;
             max-width:780px;margin:0 auto;padding:18px;color:#333;background:#fff">
  <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px;margin:0 0 12px">
    📊 daydayUp 每日复盘 · {_h(trade_date)}
  </h2>
  <p style="background:#f5f9ff;padding:12px;border-left:4px solid #1a73e8;border-radius:4px;margin:14px 0">
    <strong>复盘摘要：</strong>{_h(task.result_summary) or '<span style="color:#999">（无摘要）</span>'}
  </p>

  {ext_block}

  <h3 style="margin-top:24px;color:#333">🏆 Top 10 个股（因子总得分）</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead style="background:#f0f4f8">
      <tr>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">#</th>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">代码</th>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">名称</th>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">板块</th>
        <th style="padding:8px;text-align:right;border:1px solid #e0e6ed">涨跌幅</th>
        <th style="padding:8px;text-align:right;border:1px solid #e0e6ed">总得分</th>
      </tr>
    </thead>
    <tbody>{stock_table}</tbody>
  </table>

  <h3 style="margin-top:24px;color:#333">🏭 Top 10 板块</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead style="background:#f0f4f8">
      <tr>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">#</th>
        <th style="padding:8px;text-align:left;border:1px solid #e0e6ed">板块</th>
        <th style="padding:8px;text-align:right;border:1px solid #e0e6ed">总得分</th>
      </tr>
    </thead>
    <tbody>{sector_table}</tbody>
  </table>

  {dims_block}

  <p style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:12px;color:#999">
    完整复盘详情请访问：
    <a href="{_h(review_url)}" style="color:#1a73e8;text-decoration:none">{_h(review_url)}</a><br>
    本邮件由 daydayUp 自动发送 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  </p>
</body></html>"""


# ============== 发送 ==============

def _send_smtp(cfg: Dict[str, Any], msg: MIMEMultipart, to_list: List[str]) -> None:
    if cfg["use_ssl"]:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=20) as s:
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from_addr"], to_list, msg.as_string())
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as s:
            s.ehlo()
            try:
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            except smtplib.SMTPException:
                pass
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from_addr"], to_list, msg.as_string())


def send_daily_review_email(task_id: int,
                            recipients: Optional[List[str]] = None,
                            skip_if_disabled: bool = True) -> Dict[str, Any]:
    """发送每日复盘邮件。task_id = review_task.id；recipients 默认走 env。
    返回 {success, ...} 字典；失败不抛异常。"""
    if skip_if_disabled and not is_review_email_enabled():
        return {"success": False, "skipped": True, "reason": "EMAIL_REVIEW_ENABLED=false"}

    cfg = _smtp_config()
    if not cfg["host"] or not cfg["user"] or not cfg["password"]:
        return {"success": False, "error": "SMTP 未配置（缺 SMTP_HOST/SMTP_USER/SMTP_PASSWORD）"}

    to_list = recipients or _default_recipients()
    if not to_list:
        return {"success": False, "error": "未指定收件人（设 EMAIL_REVIEW_RECIPIENTS 或调用时传 recipients）"}

    task = db.session.get(ReviewTask, task_id)
    if not task:
        return {"success": False, "error": f"复盘任务 {task_id} 不存在"}
    if task.status != 'completed':
        return {"success": False, "error": f"复盘任务 {task_id} 状态={task.status}，非 completed，跳过发送"}

    top_stocks = _fetch_top10_stocks(task_id)
    sectors = _fetch_top_sectors(task_id)
    ext_html = _fetch_external_market_report(task.trade_date, task_id)
    all_dims = _fetch_all_review_dimensions(task_id)

    html = _build_html(task, top_stocks, sectors, ext_html, all_dims)
    subject = f"daydayUp 每日复盘 · {task.trade_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg["from_name"], cfg["from_addr"]))
    msg["To"] = ", ".join(to_list)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText("您的邮件客户端不支持 HTML 显示，请切换 HTML 模式或访问 daydayUp 复盘页面。", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        _send_smtp(cfg, msg, to_list)
        logger.info(f"📧 复盘邮件已发: task={task_id} trade_date={task.trade_date} → {to_list}")
        return {
            "success": True,
            "task_id": task_id,
            "trade_date": task.trade_date,
            "recipients": to_list,
            "subject": subject,
            "has_external_report": ext_html is not None,
            "top_stocks_count": len(top_stocks),
            "sectors_count": len(sectors),
        }
    except Exception as e:
        logger.error(f"❌ 复盘邮件发送失败 task={task_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def send_test_email(recipients: Optional[List[str]] = None) -> Dict[str, Any]:
    """发一封测试邮件，验证 SMTP 配置可用（不依赖复盘数据）。"""
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["user"] or not cfg["password"]:
        return {"success": False, "error": "SMTP 未配置"}
    to_list = recipients or _default_recipients()
    if not to_list:
        return {"success": False, "error": "未指定收件人"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "daydayUp · SMTP 测试邮件"
    msg["From"] = formataddr((cfg["from_name"], cfg["from_addr"]))
    msg["To"] = ", ".join(to_list)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText("daydayUp SMTP 测试邮件（plain）", "plain", "utf-8"))
    msg.attach(MIMEText(
        f"<p style='font-family:sans-serif'>这是一封 daydayUp 的 SMTP 测试邮件。</p>"
        f"<p style='color:#666;font-size:12px'>发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        "html", "utf-8"))
    try:
        _send_smtp(cfg, msg, to_list)
        return {"success": True, "recipients": to_list}
    except Exception as e:
        logger.error(f"测试邮件发送失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
