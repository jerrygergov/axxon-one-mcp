#!/usr/bin/env python3
"""Approval-gated bookmark lifecycle workflow for Axxon One MCP (Phase 5G)."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import os
from pathlib import Path
from typing import Any, Callable
import uuid

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import redact_admin_secrets, _body

BOOKMARK_MUTATION_APPROVE_ENV = "AXXON_BOOKMARK_MUTATION_APPROVE"

BOOKMARK_MUTATION_WORKFLOWS: dict[str, dict[str, str]] = {
    "bookmark_lifecycle": {
        "risk": "bookmark-mutation",
        "summary": "Create a temporary codex bookmark, verify it, and delete it on rollback.",
    },
}

_REQUIRED_FIXTURE_OBJECTS = ("camera_access_point", "range")


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory() -> AxxonApiClient:
    return AxxonApiClient(default_config_factory())


def _approval_from_env() -> bool:
    return os.environ.get(BOOKMARK_MUTATION_APPROVE_ENV) == "1"


def _confirmation_token(workflow: str) -> str:
    return f"CONFIRM-bookmark-{workflow}"


def _rollback_confirmation_token(workflow: str) -> str:
    return f"CONFIRM-bookmark-{workflow}-rollback"


def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _codex_message(params: dict[str, Any]) -> str:
    raw = str(params.get("message") or "").strip()
    suffix = uuid.uuid4().hex[:12]
    if not raw:
        return f"codex temporary bookmark {suffix}, remove after smoke"
    return raw


def _message_allowed(params: dict[str, Any]) -> bool:
    raw = str(params.get("message") or "").strip()
    return not raw or raw.startswith("codex")


@dataclass
class AxxonBookmarkMutationRegistry:
    """In-memory plan/apply/verify/rollback scaffold for the bookmark lifecycle."""

    client_factory: Callable[[], Any] = default_client_factory
    enabled: bool | None = None
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit: list[dict[str, Any]] = field(default_factory=list)
    client: Any | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def _audit(self, action: str, payload: dict[str, Any]) -> None:
        self.audit.append(
            {
                "ts": dt.datetime.now(dt.UTC).isoformat(),
                "action": action,
                **redact_admin_secrets(payload),
            }
        )

    def ensure_client(self) -> Any:
        if self.client is None:
            self.client = self.client_factory()
        return self.client

    def list_workflows(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "approval_env": BOOKMARK_MUTATION_APPROVE_ENV,
            "enabled": bool(self.enabled),
            "workflows": [
                {"name": name, **metadata}
                for name, metadata in sorted(BOOKMARK_MUTATION_WORKFLOWS.items())
            ],
        }

    def plan(self, workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if workflow not in BOOKMARK_MUTATION_WORKFLOWS:
            result = {"status": "gap", "workflow": workflow, "message": f"{workflow} is not in Phase 5G scope."}
            self._audit("plan_gap", result)
            return result
        raw_params = dict(params or {})
        if not _message_allowed(raw_params):
            result = {
                "status": "rejected",
                "workflow": workflow,
                "reason": "non-codex-message-target",
                "message": "5G only writes generated or explicitly codex-* bookmark messages.",
            }
            self._audit("plan_rejected", result)
            return result
        clean_params = redact_admin_secrets(raw_params)
        plan_id = f"bookmark-{workflow}-{uuid.uuid4()}"
        plan = {
            "status": "planned",
            "plan_id": plan_id,
            "workflow": workflow,
            "risk": BOOKMARK_MUTATION_WORKFLOWS[workflow]["risk"],
            "summary": BOOKMARK_MUTATION_WORKFLOWS[workflow]["summary"],
            "params": clean_params,
            "confirmation_token": _confirmation_token(workflow),
            "rollback_confirmation_token": _rollback_confirmation_token(workflow),
            "enabled": bool(self.enabled),
            "applied": False,
            "rolled_back": False,
            "_state": {
                "camera_access_point": str(raw_params.get("camera_access_point") or ""),
                "range": raw_params.get("range") or {},
                "message": _codex_message(raw_params),
            },
        }
        plan["expected"] = {"message": plan["_state"]["message"]}
        self.plans[plan_id] = plan
        self._audit("plan", _public_plan(plan))
        return _public_plan(plan)

    def _plan_or_gap(self, plan_id: str) -> dict[str, Any]:
        plan = self.plans.get(plan_id)
        if plan is None:
            return {"status": "gap", "plan_id": plan_id, "message": "Unknown bookmark mutation plan id."}
        return plan

    def _missing_fixture(self, state: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        if not state.get("camera_access_point"):
            missing.append("camera_access_point")
        rng = state.get("range") or {}
        if not (isinstance(rng, dict) and rng.get("begin_time") and rng.get("end_time")):
            missing.append("range")
        return missing

    def apply(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("apply_gap", plan)
            return plan
        if not self.enabled:
            result = {
                "status": "rejected",
                "plan_id": plan_id,
                "message": f"Set {BOOKMARK_MUTATION_APPROVE_ENV}=1 before applying bookmark mutations.",
            }
            self._audit("apply_rejected", result)
            return result
        if confirmation != plan["confirmation_token"]:
            result = {"status": "rejected", "plan_id": plan_id, "reason": "confirmation-token-mismatch"}
            self._audit("apply_rejected", result)
            return result
        state = dict(plan.get("_state") or {})
        missing = self._missing_fixture(state)
        if missing:
            result = {
                "status": "fixture-needed",
                "plan_id": plan_id,
                "workflow": plan["workflow"],
                "required": list(_REQUIRED_FIXTURE_OBJECTS),
                "missing": missing,
                "message": "Provide a camera access point and an archive range fixture before applying.",
            }
            self._audit("apply_fixture_needed", result)
            return result
        client = self.ensure_client()
        bookmark = {
            "message": state["message"],
            "camera_descriptions": [{"camera_ap": state["camera_access_point"]}],
            "range": state["range"],
        }
        response = _body(client.bookmark_create(bookmark))
        bookmark_id = str(response.get("id") or "")
        plan["_state"]["bookmark_id"] = bookmark_id
        plan["applied"] = True
        result = {
            "status": "applied" if bookmark_id else "warn",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "bookmark_id": bookmark_id,
            "message": state["message"],
        }
        self._audit("apply", result)
        return result

    def verify(self, plan_id: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("verify_gap", plan)
            return plan
        state = dict(plan.get("_state") or {})
        bookmark_id = str(state.get("bookmark_id") or "")
        if not bookmark_id:
            result = {
                "status": "fixture-needed",
                "plan_id": plan_id,
                "workflow": plan["workflow"],
                "required": list(_REQUIRED_FIXTURE_OBJECTS),
                "message": "No bookmark was created; apply the lifecycle first.",
            }
            self._audit("verify_fixture_needed", result)
            return result
        item = _body(self.ensure_client().bookmark_get(bookmark_id))
        bookmark_present = str(item.get("id") or "") == bookmark_id
        result = {
            "status": "verified" if bookmark_present else "warn",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "bookmark_present": bookmark_present,
        }
        self._audit("verify", result)
        return result

    def rollback(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("rollback_gap", plan)
            return plan
        if not self.enabled:
            result = {
                "status": "rejected",
                "plan_id": plan_id,
                "message": f"Set {BOOKMARK_MUTATION_APPROVE_ENV}=1 before rolling back bookmark mutations.",
            }
            self._audit("rollback_rejected", result)
            return result
        if confirmation != plan["rollback_confirmation_token"]:
            result = {"status": "rejected", "plan_id": plan_id, "reason": "confirmation-token-mismatch"}
            self._audit("rollback_rejected", result)
            return result
        state = dict(plan.get("_state") or {})
        bookmark_id = str(state.get("bookmark_id") or "")
        if not bookmark_id:
            result = {
                "status": "rolled-back",
                "plan_id": plan_id,
                "workflow": plan["workflow"],
                "bookmark_removed": True,
                "message": "No bookmark was created; nothing to remove.",
            }
            plan["rolled_back"] = True
            self._audit("rollback", result)
            return result
        client = self.ensure_client()
        client.bookmark_delete(bookmark_id)
        item = _body(client.bookmark_get(bookmark_id))
        bookmark_removed = str(item.get("id") or "") != bookmark_id
        plan["rolled_back"] = True
        result = {
            "status": "rolled-back" if bookmark_removed else "warn",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "bookmark_removed": bookmark_removed,
        }
        self._audit("rollback", result)
        return result

    def audit_log(self) -> dict[str, Any]:
        return {"entries": list(self.audit)}
