"""API boundary: validation, authentication, HTTP, and stable error results."""
import json
import math
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


def error(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_ticket(ticket_id, *, base_url, token, timeout=3.0):
    if not isinstance(ticket_id, str) or not re.fullmatch(r"TASK-[1-9][0-9]*", ticket_id):
        return error("invalid_input", "工单编号格式应为 TASK-123。")
    try:
        url = urlsplit(base_url)
        valid = (url.scheme == "http" and url.hostname == "127.0.0.1"
                 and not url.username and not url.password
                 and not url.query and not url.fragment and url.path in ("", "/")
                 and url.port is not None)
        seconds = float(timeout)
        if not valid or not math.isfinite(seconds) or not 0 < seconds <= 30:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        return error("invalid_config", "地址必须是 http://127.0.0.1:端口，超时须在 0 到 30 秒之间。")
    if not isinstance(token, str) or not token.strip():
        return error("missing_credentials", "请配置 LOCAL_TICKET_API_KEY。")
    if "\r" in token or "\n" in token:
        return error("invalid_credentials", "令牌不能包含换行。")
    request = Request(
        base_url.rstrip("/") + "/api/tickets/" + ticket_id,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    # This teaching service is loopback-only; never forward credentials on redirects.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=seconds) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                return error("invalid_response", "服务响应超过允许大小。")
            body = json.loads(raw)
    except HTTPError as exc:
        if exc.code in (401, 403):
            return error("unauthorized", "鉴权失败，请检查模拟服务与插件的令牌是否一致。")
        if exc.code == 404:
            return error("not_found", f"工单 {ticket_id} 不存在。")
        return error("http_error", f"服务返回 HTTP {exc.code}。")
    except (TimeoutError, socket.timeout):
        return error("timeout", "查询超时，请检查服务状态后重试。")
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return error("timeout", "查询超时，请检查服务状态后重试。")
        return error("unavailable", "无法连接本地工单服务，请先启动服务。")
    except (ValueError, UnicodeError):
        return error("invalid_response", "服务未返回有效 JSON。")
    fields = ("id", "title", "status", "assignee", "description")
    if (not isinstance(body, dict)
            or any(not isinstance(body.get(key), str) for key in fields)
            or body["id"] != ticket_id):
        return error("invalid_response", "工单响应字段缺失、类型错误或编号不匹配。")
    return {"ok": True, "ticket": {key: body[key] for key in fields}}
