from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pose_factory import squat_pose

from pose_tracker.application.history_presenter import HistoryPresenter
from pose_tracker.domain.history import (
    SessionSummary,
    StoredRep,
    StoredSession,
    StoredViolation,
)
from pose_tracker.domain.pose import LandmarkId, Pose

STARTED = datetime(2026, 10, 15, 15, 30, 12)
ENDED = datetime(2026, 10, 15, 15, 31, 2)


def violation(
    measured: float = 118.4, limit: float = 100.0, snapshot: Path | None = None
) -> StoredViolation:
    return StoredViolation(
        "squat_depth", "Go deeper", "Because depth.", measured, limit, 1500,
        squat_pose(120), snapshot,
    )


def make_session(
    session_id: int = 1, ended: datetime | None = ENDED, flawed: StoredViolation | None = None
) -> StoredSession:
    flawed = flawed or violation()
    reps = (
        StoredRep(1, datetime(2026, 10, 15, 15, 30, 15), 2400, {}, ()),
        StoredRep(2, datetime(2026, 10, 15, 15, 30, 20), 2100, {}, (flawed,)),
    )
    summary = SessionSummary(session_id, "squat", "Squat", STARTED, ended, 2, 1)
    return StoredSession(summary, reps)


class FakeReader:
    def __init__(self, *sessions: StoredSession) -> None:
        self.sessions = {s.summary.session_id: s for s in sessions}
        self.deleted: list[int] = []

    def list_sessions(self, exercise_key: str | None = None) -> list[SessionSummary]:
        return [
            s.summary for s in self.sessions.values()
            if exercise_key is None or s.summary.exercise_key == exercise_key
        ]

    def get_session(self, session_id: int) -> StoredSession | None:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: int) -> None:
        self.deleted.append(session_id)
        self.sessions.pop(session_id, None)

class FakeReferences:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float]] = []

    def has_reference(self, rule_id: str) -> bool:
        return rule_id == "squat_depth"

    def corrected_pose(
        self, rule_id: str, pose: Pose, limit: float, aspect_ratio: float
    ) -> Pose | None:
        self.calls.append((rule_id, limit, aspect_ratio))
        return pose


def make_presenter(
    reader: FakeReader, references: FakeReferences | None = None
) -> HistoryPresenter:
    return HistoryPresenter(
        reader, {"squat": "Squat", "push_up": "Push-up"}, references or FakeReferences()
    )


def test_filter_options_start_with_all_exercises() -> None:
    options = make_presenter(FakeReader()).filter_options()
    assert options == ((None, "All exercises"), ("squat", "Squat"), ("push_up", "Push-up"))


def test_session_rows_describe_each_session() -> None:
    [row] = make_presenter(FakeReader(make_session())).sessions()
    assert row.session_id == 1
    assert row.title == "Squat"
    assert row.subtitle == "15 Oct 2026, 15:30 · 2 reps · 1 clean"


def test_sessions_can_be_filtered_by_exercise() -> None:
    presenter = make_presenter(FakeReader(make_session()))
    assert len(presenter.sessions("squat")) == 1
    assert presenter.sessions("push_up") == ()


def test_detail_has_stats_and_one_card_per_violation() -> None:
    detail = make_presenter(FakeReader(make_session())).load(1)
    assert detail is not None
    assert detail.title == "Squat" and detail.when_text == "15 Oct 2026, 15:30"
    assert detail.stats_text == "2 reps · 1 clean · 1 with issues · 50% clean · 50 s"

    [card] = detail.mistakes
    assert card.title == "Go deeper"
    assert card.meta == "Rep 2 · 15:30:20"
    assert card.measurement == "Measured 118.4, needed 100.0 or less"
    assert card.explanation == "Because depth."
    assert card.highlights == (
        LandmarkId.LEFT_HIP, LandmarkId.LEFT_KNEE, LandmarkId.LEFT_ANKLE,
    )


def test_detail_lists_every_rep() -> None:
    detail = make_presenter(FakeReader(make_session())).load(1)
    assert detail is not None
    clean, flawed = detail.reps
    assert (clean.result_text, clean.is_clean, clean.duration_text) == ("Clean", True, "2.4s")
    assert (flawed.result_text, flawed.is_clean) == ("Go deeper", False)


def test_unfinished_session_has_no_duration() -> None:
    detail = make_presenter(FakeReader(make_session(ended=None))).load(1)
    assert detail is not None
    assert detail.stats_text.endswith("50% clean")


def test_requirement_direction_follows_the_numbers() -> None:
    below = make_session(flawed=violation(measured=140.0, limit=165.0))
    detail = make_presenter(FakeReader(below)).load(1)
    assert detail is not None
    assert detail.mistakes[0].measurement == "Measured 140.0, needed 165.0 or more"


def test_small_values_keep_three_decimals() -> None:
    session = make_session(flawed=violation(measured=0.021, limit=0.015))
    detail = make_presenter(FakeReader(session)).load(1)
    assert detail is not None
    assert detail.mistakes[0].measurement == "Measured 0.021, needed 0.015 or less"


def test_pose_without_enough_landmarks_has_no_highlights() -> None:
    flawed = StoredViolation("squat_depth", "m", "e", 118.4, 100.0, 0, Pose(()), None)
    detail = make_presenter(FakeReader(make_session(flawed=flawed))).load(1)
    assert detail is not None
    assert detail.mistakes[0].highlights == ()


def test_unknown_session_and_delete() -> None:
    reader = FakeReader(make_session())
    presenter = make_presenter(reader)
    assert presenter.load(99) is None
    presenter.delete(1)
    assert reader.deleted == [1]

def test_cards_for_correctable_rules_carry_a_ghost_factory() -> None:
    references = FakeReferences()
    detail = make_presenter(FakeReader(make_session()), references).load(1)
    assert detail is not None
    ghost = detail.mistakes[0].ghost
    assert ghost is not None
    assert ghost(1.5) == squat_pose(120)  # the fake hands back the stored pose
    assert references.calls == [("squat_depth", 100.0, 1.5)]


def test_cards_for_other_rules_have_no_ghost() -> None:
    flawed = StoredViolation("control", "m", "e", 0.03, 0.015, 0, squat_pose(120), None)
    detail = make_presenter(FakeReader(make_session(flawed=flawed))).load(1)
    assert detail is not None
    assert detail.mistakes[0].ghost is None