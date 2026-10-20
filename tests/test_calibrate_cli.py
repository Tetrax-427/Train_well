from __future__ import annotations

from pathlib import Path

import pytest

from pose_tracker.calibrate import main


def test_init_writes_a_template_and_never_overwrites_without_force(tmp_path: Path) -> None:
    path = tmp_path / "calibration.toml"
    assert main(["--file", str(path), "init"]) == 0
    assert "[squat]" in path.read_text(encoding="utf-8")

    path.write_text("# mine\n", encoding="utf-8")
    assert main(["--file", str(path), "init"]) == 1
    assert path.read_text(encoding="utf-8") == "# mine\n"

    assert main(["--file", str(path), "init", "--force"]) == 0
    assert "[squat]" in path.read_text(encoding="utf-8")


def test_check_lists_what_the_file_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "calibration.toml"
    path.write_text('[squat]\ntarget_knee_angle = 120.0\ndisabled_rules = ["torso_lean"]\n')
    assert main(["--file", str(path), "check"]) == 0
    out = capsys.readouterr().out
    assert "1 setting(s) changed, 1 check(s) switched off" in out
    assert "[squat] target_knee_angle: 100.0 -> 120.0" in out
    assert "[squat] switched off: torso_lean" in out


def test_check_reports_problems_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "calibration.toml"
    path.write_text("[squat]\nnope = 1\n")
    assert main(["--file", str(path), "check"]) == 1
    assert "unknown setting" in capsys.readouterr().err


def test_a_missing_file_is_fine(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--file", str(tmp_path / "calibration.toml"), "check"]) == 0
    assert "does not exist" in capsys.readouterr().out


def test_show_marks_calibrated_values_and_can_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "calibration.toml"
    path.write_text("[squat]\ntarget_knee_angle = 120.0\n")
    assert main(["--file", str(path), "show", "squat"]) == 0
    out = capsys.readouterr().out
    assert "[squat]" in out and "<- calibrated" in out and "[deadlift]" not in out