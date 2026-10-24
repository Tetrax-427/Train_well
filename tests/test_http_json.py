from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pose_tracker.errors import LlmError
from pose_tracker.infrastructure.http_json import post_json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/ok":
            status, reply = 200, {"echo": body, "auth": self.headers.get("Authorization")}
            data = json.dumps(reply).encode()
        elif self.path == "/error":
            status, data = 500, b'{"error": "boom"}'
        elif self.path == "/list":
            status, data = 200, b"[1, 2]"
        elif self.path == "/context":
            status = 400
            data = json.dumps({"error": {
                "code": 400, "message": "too big", "type": "exceed_context_size_error",
                "n_prompt_tokens": 2569, "n_ctx": 2048,
            }}).encode()
        else:
            status, data = 200, b"<html>not json</html>"
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def base_url() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_a_json_reply_comes_back_and_the_headers_are_sent(base_url: str) -> None:
    reply = post_json(f"{base_url}/ok", {"a": 1}, {"Authorization": "Bearer x"}, 5.0)
    assert reply == {"echo": {"a": 1}, "auth": "Bearer x"}


def test_an_error_status_is_reported_with_its_body(base_url: str) -> None:
    with pytest.raises(LlmError, match="HTTP 500.*boom"):
        post_json(f"{base_url}/error", {}, {}, 5.0)


def test_replies_that_are_not_a_json_object_are_rejected(base_url: str) -> None:
    with pytest.raises(LlmError, match="not JSON"):
        post_json(f"{base_url}/html", {}, {}, 5.0)
    with pytest.raises(LlmError, match="unexpected reply"):
        post_json(f"{base_url}/list", {}, {}, 5.0)


def test_an_unreachable_server_is_reported() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(LlmError, match="Cannot reach the model server"):
        post_json(f"http://127.0.0.1:{port}/v1/chat/completions", {}, {}, 5.0)

def test_a_context_overflow_explains_how_to_fix_it(base_url: str) -> None:
    with pytest.raises(LlmError, match=r"2569 tokens.*2048 tokens.*context_tokens"):
        post_json(f"{base_url}/context", {}, {}, 5.0)