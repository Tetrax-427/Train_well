from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pose_tracker.application.calibration import (
    Calibration,
    calibrate,
    changed_settings,
    ordered_sections,
    render_effective,
    render_template,
    summarize,
)
from pose_tracker.config import AppConfig
from pose_tracker.errors import CalibrationError
from pose_tracker.infrastructure.calibration_file import read_calibration_file


def main(argv: Sequence[str] | None = None) -> int:
    base = AppConfig()
    parser = argparse.ArgumentParser(
        prog="python -m pose_tracker.calibrate",
        description="Create, check and inspect calibration.toml, the file holding your exercise limits.",
    )
    parser.add_argument(
        "--file", type=Path, default=base.calibration_file, help="calibration file (default: %(default)s)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="write a file listing every setting, commented out")
    init.add_argument("--force", action="store_true", help="overwrite an existing file")
    commands.add_parser("check", help="validate the file and list what it changes")
    show = commands.add_parser("show", help="print the settings the app will use")
    show.add_argument("section", nargs="?", choices=ordered_sections(base), help="only this section")
    args = parser.parse_args(argv)

    if args.command == "init":
        return _init(base, args.file, args.force)
    try:
        calibration = calibrate(base, read_calibration_file(args.file), args.file)
    except CalibrationError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.command == "check":
        return _check(base, calibration, args.file)
    print(render_effective(base, calibration, args.section))
    return 0


def _init(base: AppConfig, path: Path, force: bool) -> int:
    if path.exists() and not force:
        print(
            f"{path} already exists. Use --force to overwrite it (this discards your calibration).",
            file=sys.stderr,
        )
        return 1
    try:
        path.write_text(render_template(base), encoding="utf-8")
    except OSError as exc:
        print(f"Cannot write {path}: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {path}. Uncomment and edit the settings you want to change.")
    return 0


def _check(base: AppConfig, calibration: Calibration, path: Path) -> int:
    if not path.exists():
        print(f"{path} does not exist, so the defaults are in use. Run 'init' to create it.")
        return 0
    print(f"{path}: OK. {summarize(base, calibration)}.")
    for section, setting, default, value in changed_settings(base, calibration.config):
        print(f"  [{section}] {setting}: {default} -> {value}")
    for section, rule_ids in calibration.disabled_rules.items():
        print(f"  [{section}] switched off: {', '.join(rule_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())