from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from .models import Capability


class HumanApproval(BaseModel):
    """Human-in-the-loop approval record for side-effecting actions.

    This is intentionally explicit. A bare `confirmed=true` is not enough for
    publishing, sending, deleting, updating, purchasing, or other write actions.
    The caller must include who approved the action and what they reviewed.
    """

    approved: bool = False
    approved_by: str = Field(default="", min_length=1)
    action_summary: str = Field(default="", min_length=1)
    reviewed_params_sha256: str | None = None


def params_sha256(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_side_effecting(capability: Capability) -> bool:
    return capability.type == "write" or capability.requires_confirmation


def require_human_approval(
    *,
    site_id: str,
    capability_id: str,
    capability: Capability,
    params: dict[str, Any],
    confirmed: bool,
    human_approval: dict[str, Any] | HumanApproval | None,
) -> HumanApproval | None:
    if not is_side_effecting(capability):
        return None
    if not confirmed:
        raise PermissionError(f"capability '{capability_id}' requires confirmation")
    if human_approval is None:
        digest = params_sha256(params)
        raise PermissionError(
            "human approval required before write action; include "
            f"human_approval with approved=true, approved_by, action_summary, "
            f"reviewed_params_sha256={digest}"
        )

    approval = human_approval if isinstance(human_approval, HumanApproval) else HumanApproval.model_validate(human_approval)
    if approval.approved is not True:
        raise PermissionError("human approval must set approved=true")
    if approval.reviewed_params_sha256 and approval.reviewed_params_sha256 != params_sha256(params):
        raise PermissionError(
            f"human approval params hash mismatch for {site_id}/{capability_id}; "
            "review the final params again"
        )
    return approval
