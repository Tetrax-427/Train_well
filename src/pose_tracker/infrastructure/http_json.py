from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from pose_tracker.errors import LlmError

# The model server is on this machine or your own network (for example over Tailscale), so
# system proxy settings must not apply: on macOS they can make a request hang or fail.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post_json(
    url: str, payload: Mapping[str, Any], headers: Mapping[str, str], timeout: float
) -> dict[str, Any]:
    """POST JSON and return the JSON reply. Every failure becomes an LlmError that says why."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with OPENER.open(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace").strip()
        raise LlmError(f"The model server answered with HTTP {exc.code}: {detail}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace").strip()
        raise LlmError(_http_message(exc.code, detail)) from exc
    except TimeoutError as exc:
        raise LlmError(_timeout(timeout)) from exc
    except (OSError, http.client.HTTPException) as exc:
        raise LlmError(f"Lost the connection to the model server: {exc}") from exc
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise LlmError("The model server sent a reply that is not JSON.") from exc
    if not isinstance(data, dict):
        raise LlmError("The model server sent an unexpected reply.")
    return data


def _timeout(seconds: float) -> str:
    return f"The model server did not answer within {seconds:g} seconds."

def _http_message(code: int, detail: str) -> str:
    try:
        error = json.loads(detail).get("error", {})
    except (ValueError, AttributeError):
        error = {}
    if isinstance(error, dict) and error.get("type") == "exceed_context_size_error":
        return (
            f"The prompt ({error.get('n_prompt_tokens')} tokens) does not fit the server's "
            f"context size ({error.get('n_ctx')} tokens). Raise the server's context size "
            "(llama.cpp: -c) and set context_tokens in llm.toml to match."
        )
    return f"The model server answered with HTTP {code}: {detail}"