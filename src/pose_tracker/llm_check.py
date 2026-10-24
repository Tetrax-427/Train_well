from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlparse

from pose_tracker.application.chat.llm_settings import parse_llm_settings
from pose_tracker.config import AppConfig, LlmSettings
from pose_tracker.domain.chat import ChatMessage, ToolSpec
from pose_tracker.errors import LlmConfigError
from pose_tracker.infrastructure.http_json import OPENER
from pose_tracker.infrastructure.llm_settings_file import read_llm_settings_file
from pose_tracker.infrastructure.openai_compatible_client import OpenAiCompatibleClient

_TIME_TOOL = ToolSpec("get_time", "Returns the current time.", {"type": "object", "properties": {}})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m pose_tracker.llm_check",
        description="Test the connection to the model server, one step at a time.",
    )
    parser.add_argument("--file", type=Path, default=AppConfig().llm_file)
    args = parser.parse_args(argv)

    found = "found" if args.file.exists() else "NOT FOUND, so the defaults are used"
    print(f"Settings file: {args.file.resolve()} ({found})")
    try:
        settings = parse_llm_settings(read_llm_settings_file(args.file), args.file)
    except LlmConfigError as exc:
        print(exc)
        return 1
    key = "set" if settings.api_key else "not set"
    print(
        f"base_url={settings.base_url}  model={settings.model}  "
        f"timeout={settings.timeout_s:g}s  api_key={key}\n"
    )

    url = urlparse(settings.base_url)
    host = url.hostname or ""
    port = url.port or (443 if url.scheme == "https" else 80)
    client = OpenAiCompatibleClient(settings)

    required: list[tuple[str, Callable[[], str]]] = [
        (f"resolve {host}", lambda: _resolve(host, port)),
        (f"connect to {host}:{port}", lambda: _connect(host, port)),
    ]
    for label, action in required:
        if not _step(label, action):
            return _failed()
    _step("list models (optional)", lambda: _list_models(settings))
    for label, action in (
        ("simple question", lambda: _simple(client)),
        ("question with tools", lambda: _with_tools(client)),
    ):
        if not _step(label, action):
            return _failed()
    print("\nEverything works. The Chat tab should answer.")
    return 0


def _step(label: str, action: Callable[[], str]) -> bool:
    started = time.perf_counter()
    try:
        detail = action()
    except Exception as exc:  # a diagnostic: report any failure instead of crashing
        print(f"FAIL  {label} ({time.perf_counter() - started:.1f}s): {exc}")
        return False
    print(f"OK    {label} ({time.perf_counter() - started:.1f}s): {detail}")
    return True


def _failed() -> int:
    print(
        "\nStopped at the first failing step. Check that the server runs, listens on "
        "0.0.0.0 (not only localhost), and that the host, port and /v1 in llm.toml are right."
    )
    return 1


def _resolve(host: str, port: int) -> str:
    found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return ", ".join(sorted({str(item[4][0]) for item in found}))


def _connect(host: str, port: int) -> str:
    with socket.create_connection((host, port), timeout=5):
        return "port is open"


def _list_models(settings: LlmSettings) -> str:
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    request = urllib.request.Request(settings.base_url.rstrip("/") + "/models", headers=headers)
    with OPENER.open(request, timeout=min(settings.timeout_s, 15)) as response:
        data = json.load(response)
    ids = [str(m.get("id")) for m in data.get("data", []) if isinstance(m, dict)]
    warning = "" if settings.model in ids else f"  WARNING: '{settings.model}' is not in this list"
    return f"{len(ids)} model(s): {', '.join(ids[:5])}{warning}"


def _simple(client: OpenAiCompatibleClient) -> str:
    reply = client.complete([ChatMessage.user("Reply with the single word: ready")], [])
    return f"replied {reply.content[:60]!r}"


def _with_tools(client: OpenAiCompatibleClient) -> str:
    reply = client.complete(
        [ChatMessage.user("What time is it? Use the get_time tool.")], [_TIME_TOOL]
    )
    if reply.tool_calls:
        return f"the model called {reply.tool_calls[0].name}"
    return "the server accepted tools, but the model answered without calling one"


if __name__ == "__main__":
    raise SystemExit(main())