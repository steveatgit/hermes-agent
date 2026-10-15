"""Run a local read-only ticket API with the Python standard library."""
import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TICKETS = {
    "TASK-101": {"id": "TASK-101", "title": "开发环境安装失败", "status": "处理中",
                 "assignee": "小林", "description": "缺少 YAML 依赖，正在核对 Python 解释器。"},
    "TASK-102": {"id": "TASK-102", "title": "补充插件测试", "status": "待处理",
                 "assignee": "小陈", "description": "补充鉴权失败、超时及不存在工单的测试。"},
}


def make_server(port=8765, token="local-demo-token"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            supplied = self.headers.get("Authorization", "").encode()
            expected = ("Bearer " + token).encode()
            if not hmac.compare_digest(supplied, expected):
                status, body = 401, {"error": "unauthorized"}
            else:
                ticket = TICKETS.get(self.path.removeprefix("/api/tickets/"))
                if self.path.startswith("/api/tickets/") and ticket:
                    status, body = 200, ticket
                else:
                    status, body = 404, {"error": "not_found"}
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port, os.environ.get("LOCAL_TICKET_API_KEY", "local-demo-token"))
    print(f"模拟工单 API: http://127.0.0.1:{server.server_port} (Ctrl+C 停止)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
