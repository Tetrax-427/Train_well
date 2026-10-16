from __future__ import annotations

from pathlib import Path

import pytest

from pose_tracker.infrastructure.filesystem_snapshot_store import FileSnapshotStore


def test_save_and_resolve_round_trip(tmp_path: Path) -> None:
    store = FileSnapshotStore(tmp_path)
    key = store.save(3, "rep1_squat_depth", b"jpeg-bytes")
    assert key == "3/rep1_squat_depth.jpg"
    assert store.resolve(key).read_bytes() == b"jpeg-bytes"


def test_delete_session_removes_its_images_and_tolerates_missing_ones(tmp_path: Path) -> None:
    store = FileSnapshotStore(tmp_path)
    store.save(3, "a", b"x")
    store.delete_session(3)
    store.delete_session(3)
    assert not (tmp_path / "3").exists()


@pytest.mark.parametrize("name", ["../evil", "a/b", "", "a b"])
def test_unsafe_names_are_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        FileSnapshotStore(tmp_path).save(1, name, b"x")


def test_keys_cannot_escape_the_store(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        FileSnapshotStore(tmp_path / "store").resolve("../outside.jpg")