import importlib.util
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ticket_demo_test_package", ROOT / "__init__.py",
                                            submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
server_spec = importlib.util.spec_from_file_location("ticket_mock_server", ROOT / "mock_server.py")
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)


@contextmanager
def running(server):
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.fixture
def api():
    with running(server_module.make_server(0, "test-token")) as url:
        yield url


def query(url, ticket="TASK-101", token="test-token", **kwargs):
    return plugin.get_ticket(ticket, base_url=url, token=token, **kwargs)


def test_real_http_query(api):
    result = query(api)
    assert result["ok"] is True
    assert result["ticket"]["id"] == "TASK-101"
    assert result["ticket"]["status"] == "处理中"
    assert result["ticket"]["assignee"] == "小林"


@pytest.mark.parametrize("ticket,token,code", [
    ("TASK-999", "test-token", "not_found"),
    ("TASK-101", "wrong-token", "unauthorized"),
    ("TASK-101", "", "missing_credentials"),
    ("../secret", "test-token", "invalid_input"),
])
def test_failure_reasons(api, ticket, token, code):
    result = query(api, ticket, token)
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert "wrong-token" not in json.dumps(result)


@pytest.mark.parametrize("payload", [b"not-json", b'{"id":"TASK-101"}'])
def test_invalid_upstream_response(payload):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(payload)

    with running(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as url:
        assert query(url)["error"]["code"] == "invalid_response"


def test_http_timeout():
    release = threading.Event()
    entered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            entered.set()
            release.wait(timeout=5)
            self.close_connection = True

    with running(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as url:
        try:
            result = query(url, timeout=0.2)
            assert entered.is_set()
            assert result["error"]["code"] == "timeout"
        finally:
            release.set()


def test_plugin_handler_to_http(api, monkeypatch):
    from agent import secret_scope
    monkeypatch.setattr(secret_scope, "get_secret", lambda name: "test-token")

    class Context:
        def get_config(self, key, default=None):
            return {"base_url": api}.get(key, default)

        def register_tool(self, **kwargs):
            self.handler = kwargs["handler"]

        def register_skill(self, name, path):
            pass

    ctx = Context()
    plugin.register(ctx)
    result = json.loads(ctx.handler({"ticket_id": "TASK-102"}))
    assert result["ticket"]["title"] == "补充插件测试"
    assert result["ticket"]["status"] == "待处理"
