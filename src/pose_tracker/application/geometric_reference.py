from __future__ import annotations

from pose_tracker.domain.pose import Pose
from pose_tracker.domain.pose_correction import corrected_pose, has_corrected_pose


class GeometricReferenceProvider:
    """Reference poses computed from the rule's limit and the person's own body."""

    def has_reference(self, rule_id: str) -> bool:
        return has_corrected_pose(rule_id)

    def corrected_pose(
        self, rule_id: str, pose: Pose, limit: float, aspect_ratio: float
    ) -> Pose | None:
        return corrected_pose(rule_id, pose, limit, aspect_ratio)