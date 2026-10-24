from __future__ import annotations

import socket
from pathlib import Path

import pytest

from pose_tracker.llm_check import main


def test_an_unreachable_server_stops_at_the_connection_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    path = tmp_path / "llm.toml"
    path.write_text(f'base_url = "http://127.0.0.1:{port}/v1"\n')

    assert main(["--file", str(path)]) == 1
    out = capsys.readouterr().out
    assert "OK    resolve 127.0.0.1" in out
    assert "FAIL  connect to 127.0.0.1" in out
    assert "simple question" not in out  # stops at the first broken step


def test_an_invalid_settings_file_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "llm.toml"
    path.write_text('modle = "x"\n')
    assert main(["--file", str(path)]) == 1
    assert "Did you mean 'model'" in capsys.readouterr().out