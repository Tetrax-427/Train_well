from __future__ import annotations

import re
import shutil
from pathlib import Path

_SAFE_NAME = re.compile(r"[A-Za-z0-9_-]+")


class FileSnapshotStore:
    """Stores JPEGs as <root>/<session_id>/<name>.jpg. Keys are root-relative paths."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, session_id: int, name: str, jpeg: bytes) -> str:
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError(f"Unsafe snapshot name: {name!r}")
        key = f"{session_id}/{name}.jpg"
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(jpeg)
        return key

    def resolve(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"Snapshot key escapes the store: {key!r}")
        return path

    def delete_session(self, session_id: int) -> None:
        shutil.rmtree(self._root / str(session_id), ignore_errors=True)