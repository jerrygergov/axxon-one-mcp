#!/usr/bin/env python3
"""NL-to-plan translator and recipe assembler for the Axxon One MCP server.

Three read-only tools that translate English intent strings into verified operator
workflow plans, then expose rich previews. Recipe execution continues to use the
existing ``apply_operator_plan`` tool.

- ``assemble_recipe``: deterministic keyword/rule table maps an intent string + context
  dict into ordered workflow steps.
- ``validate_recipe``: dry-runs each step via ``operator.plan`` (no apply/rollback).
- ``explain_recipe``: pure formatting; zero network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

# Wall-clock estimate per risk class — static, not fetched.
_TIME_ESTIMATES: dict[str, str] = {
    "mutation": "~5-30 seconds per step",
    "archive_maintenance": "~1-10 minutes per step",
    "read": "~1-5 seconds per step",
    "noop": "~1 second per step",
}
_DEFAULT_TIME_ESTIMATE = "~5-30 seconds per step"

# Rollback note per risk class — static.
_ROLLBACK_NOTES: dict[str, str] = {
    "mutation": "rollback removes created objects if caller explicitly invokes rollback",
    "archive_maintenance": "rollback cancels or is a no-op depending on operation",
    "read": "no rollback needed (read-only)",
    "noop": "no rollback needed",
}
_DEFAULT_ROLLBACK_NOTE = "rollback available via rollback_operator_plan"

# ---------------------------------------------------------------------------
# Intent rule table — deterministic keyword/pattern matching.
#
# Each rule is a dict:
#   keywords   : set[str] — ALL must appear in the lowercased intent string
#   excludes   : set[str] — if ANY appears, this rule is skipped
#   workflows  : list of (workflow_name, param_extractor_fn)
#   priority   : int — higher wins when multiple rules match (default 0)
#
# param_extractor_fn(context: dict) -> dict maps the context dict into the
# params dict that assemble_recipe passes to the step.
# ---------------------------------------------------------------------------

def _ctx(keys: list[str], rename: dict[str, str] | None = None) -> Callable[[dict], dict]:
    """Return a function that extracts the given keys from context, applying optional renames."""
    rename = rename or {}
    def _extract(ctx: dict) -> dict:
        out: dict[str, Any] = {}
        for k in keys:
            if k in ctx:
                out[rename.get(k, k)] = ctx[k]
        return out
    return _extract


def _camera_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("display_name", "name", "ip", "login", "password", "vendor", "model", "display_id"):
        if k in ctx:
            out[k] = ctx[k]
    return out


def _av_detector_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("display_name", "name", "video_source_ap", "detector"):
        if k in ctx:
            out[k] = ctx[k]
    # allow camera_uid as hint for display_name if not already set
    if "display_name" not in out and "name" not in out and "camera_uid" in ctx:
        out["display_name"] = f"av-detector-{ctx['camera_uid']}"
    return out


def _appdata_detector_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("display_name", "name", "video_source_ap", "vmda_source_ap", "detector"):
        if k in ctx:
            out[k] = ctx[k]
    if "display_name" not in out and "name" not in out and "camera_uid" in ctx:
        out["display_name"] = f"appdata-detector-{ctx['camera_uid']}"
    return out


def _archive_policy_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("uid", "archive_uid", "properties", "descriptor", "archive_descriptor"):
        if k in ctx:
            out[k] = ctx[k]
    # days hint: build a minimal properties list using a known descriptor-safe id
    if "days" in ctx and "properties" not in out:
        out["properties"] = [{"id": "archiveMaximumDuration", "value_string": str(ctx["days"]) + "d"}]
    if "descriptor" not in out and "archive_descriptor" not in out:
        # provide a stub descriptor so the builder doesn't immediately reject
        out["descriptor"] = {"archiveMaximumDuration": True}
    return out


def _macro_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("name", "display_name", "enabled", "conditions", "actions", "guid"):
        if k in ctx:
            out[k] = ctx[k]
    if "name" not in out and "display_name" not in out and "camera_uid" in ctx:
        out["name"] = f"export-sched-{ctx['camera_uid']}"
    return out


def _layout_create_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("name", "display_name", "layout_id", "cells", "rows", "cols"):
        if k in ctx:
            out[k] = ctx[k]
    return out


def _layout_update_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("layout_id", "etag", "body"):
        if k in ctx:
            out[k] = ctx[k]
    if "video_source_ap" in ctx and "body" not in out:
        ap = ctx["video_source_ap"]
        out["body"] = {"cells": {"0": {"items": [{"access_point": ap}]}}}
    return out


def _map_create_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("name", "map_id", "type", "zoom", "markers", "image_data_b64"):
        if k in ctx:
            out[k] = ctx[k]
    return out


def _update_markers_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("map_id", "markers"):
        if k in ctx:
            out[k] = ctx[k]
    if "access_point" in ctx and "markers" not in out:
        out["markers"] = [{"access_point": ctx["access_point"], "x": 0.5, "y": 0.5}]
    return out


def _external_event_params(ctx: dict) -> dict:
    out: dict[str, Any] = {}
    for k in ("access_point", "event_type"):
        if k in ctx:
            out[k] = ctx[k]
    return out


# Each rule: (keywords_all, excludes_any, workflows_list, priority)
# workflows_list is a list of (workflow_name, param_fn, why_template)
# Higher priority wins. Rules are matched against the full lowercased intent string.
_INTENT_RULES: list[tuple[frozenset, frozenset, list[tuple[str, Callable, str]], int]] = [
    # --- Multi-step combination rules (priority >= 10) --------------------------------
    # Camera + AV detector: "add a camera with av detector" — requires "with" to distinguish
    # from "add av detector to camera" (which is a single-step detector-add).
    (
        frozenset({"camera", "with", "av detector"}),
        frozenset({"appdata", "app data"}),
        [
            ("create_camera", _camera_params, "create IP/virtual camera"),
            ("create_av_detector_full", _av_detector_params, "attach AV detector to camera"),
        ],
        20,
    ),
    # Camera + AppData detector: "add camera with appdata detector"
    (
        frozenset({"camera", "with", "appdata"}),
        frozenset(),
        [
            ("create_camera", _camera_params, "create IP/virtual camera"),
            ("create_appdata_detector_full", _appdata_detector_params, "attach AppData detector to camera"),
        ],
        20,
    ),
    # Camera + archive policy: "add camera with 7-day archive"
    (
        frozenset({"camera", "with", "archive"}),
        frozenset({"detector", "layout", "map"}),
        [
            ("create_camera", _camera_params, "create IP/virtual camera"),
            ("archive_policy_update", _archive_policy_params, "set archive retention policy"),
        ],
        20,
    ),
    # --- Single-concept rules (priority < 10) -----------------------------------------
    # I-2: AV detector — higher priority than plain camera so "add av detector to camera" wins
    (
        frozenset({"av detector"}),
        frozenset({"appdata", "app data"}),
        [("create_av_detector_full", _av_detector_params, "attach AV detector to camera")],
        8,
    ),
    # I-3: AppData detector — higher priority than plain camera
    (
        frozenset({"appdata"}),
        frozenset(),
        [("create_appdata_detector_full", _appdata_detector_params, "attach AppData detector to camera")],
        8,
    ),
    # I-4: Archive policy — higher priority than plain camera
    (
        frozenset({"archive"}),
        frozenset({"format", "reindex", "cancel reindex"}),
        [("archive_policy_update", _archive_policy_params, "set archive retention policy")],
        8,
    ),
    # I-5: Macro — higher priority than plain camera
    (
        frozenset({"macro"}),
        frozenset(),
        [("create_macro", _macro_params, "create automation macro")],
        8,
    ),
    # I-7: Add camera to existing layout — "add camera to existing layout"
    (
        frozenset({"camera", "existing layout"}),
        frozenset(),
        [("update_layout", _layout_update_params, "update existing layout with camera")],
        15,
    ),
    # I-7 alt: "add camera to layout" (without the word "existing")
    (
        frozenset({"camera", "to", "layout"}),
        frozenset({"create layout", "create a layout", "new layout", "with"}),
        [("update_layout", _layout_update_params, "update existing layout with camera")],
        12,
    ),
    # I-6: Create layout — "create layout named X"
    (
        frozenset({"layout"}),
        frozenset({"add camera to", "update layout"}),
        [("create_layout", _layout_create_params, "create named view layout")],
        5,
    ),
    # I-9: Place marker on map — higher priority than map create
    (
        frozenset({"marker"}),
        frozenset(),
        [("update_markers", _update_markers_params, "place camera marker on map")],
        8,
    ),
    # I-8: Create map
    (
        frozenset({"map"}),
        frozenset({"marker", "update map", "update markers"}),
        [("create_map", _map_create_params, "create named site map")],
        5,
    ),
    # I-10: Inject external event / alarm
    (
        frozenset({"event"}),
        frozenset(),
        [("external_event_inject", _external_event_params, "inject external alarm or sensor event")],
        5,
    ),
    # I-1: Add camera (plain) — lowest priority so single-concept rules beat it
    (
        frozenset({"camera"}),
        frozenset({"detector", "layout"}),
        [("create_camera", _camera_params, "create IP/virtual camera")],
        0,
    ),
]

# Unsupported intent patterns — keyword sets that indicate no workflow exists.
_UNSUPPORTED_PATTERNS: list[tuple[frozenset, str]] = [
    (frozenset({"ptz"}), "PTZ control has no operator workflow; use the camera's native SDK"),
    (frozenset({"preset"}), "PTZ presets have no operator workflow"),
    (frozenset({"role"}), "user/role management has no operator workflow in this version"),
    (frozenset({"permission"}), "permission management has no operator workflow in this version"),
    (frozenset({"user account"}), "user account management has no operator workflow"),
    (frozenset({"password"}), "password management has no operator workflow"),
    (frozenset({"create user"}), "user creation has no operator workflow"),
    (frozenset({"assign"}), "assignment operations have no operator workflow"),
    (frozenset({"grant access"}), "access-grant operations have no operator workflow"),
]


def _keywords_match(keywords: frozenset, text: str) -> bool:
    return all(kw in text for kw in keywords)


def _match_intent(intent_text: str) -> list[tuple[str, Callable, str]] | None:
    """Return the best-matching workflow list for an intent, or None if no rule matches."""
    lowered = intent_text.lower()
    best_priority = -1
    best_workflows = None
    for (keywords, excludes, workflows, priority) in _INTENT_RULES:
        if not _keywords_match(keywords, lowered):
            continue
        if any(ex in lowered for ex in excludes):
            continue
        if priority > best_priority:
            best_priority = priority
            best_workflows = workflows
    return best_workflows


def _is_unsupported(intent_text: str) -> str | None:
    """Return a reason string if the intent maps to a known unsupported concept, else None."""
    lowered = intent_text.lower()
    for (keywords, reason) in _UNSUPPORTED_PATTERNS:
        if _keywords_match(keywords, lowered):
            return reason
    return None


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AxxonMcpTranslator:
    """NL-to-plan translator and recipe assembler.

    Args:
        operator_factory: Callable that returns an OperatorRegistry (or compatible stub).
            Called lazily on first validate_recipe call so unit tests inject stubs.
    """

    operator_factory: Callable[[], Any]
    _operator: Any | None = field(default=None, init=False, repr=False)

    def _ensure_operator(self) -> Any:
        if self._operator is None:
            self._operator = self.operator_factory()
        return self._operator

    # ------------------------------------------------------------------
    # assemble_recipe
    # ------------------------------------------------------------------

    def assemble_recipe(self, intent_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Translate an English intent string into an ordered list of workflow steps.

        Args:
            intent_text: Free-text description of what the operator wants to accomplish.
            context: Optional structured context supplying fixture values such as camera_uid,
                video_source_ap, layout_id, etc.

        Returns:
            dict with a ``steps`` key containing a list of workflow step dicts, OR a dict
            with ``status == "unsupported_intent"`` when the intent has no matching workflow.
        """
        context = dict(context or {})
        known = sorted(self._ensure_operator().known_workflows())

        unsupported_reason = _is_unsupported(intent_text)
        if unsupported_reason:
            return {
                "status": "unsupported_intent",
                "intent_text": intent_text,
                "reason": unsupported_reason,
                "known_workflows": known,
            }

        matched = _match_intent(intent_text)
        if matched is None:
            return {
                "status": "unsupported_intent",
                "intent_text": intent_text,
                "reason": "no matching operator workflow found for this intent",
                "known_workflows": known,
            }

        steps = [
            {"workflow": wf, "params": param_fn(context), "why": why}
            for (wf, param_fn, why) in matched
        ]
        return {"intent_text": intent_text, "steps": steps}

    # ------------------------------------------------------------------
    # validate_recipe
    # ------------------------------------------------------------------

    def validate_recipe(self, recipe: list[dict[str, Any]]) -> dict[str, Any]:
        """Dry-run each step via operator.plan and aggregate the results.

        Args:
            recipe: List of step dicts, each with ``workflow``, ``params``, and ``why`` keys.

        Returns:
            Aggregated validation result with ``valid``, ``steps``, ``risk_classes``,
            ``required_approvals``, and ``gaps`` keys.
        """
        operator = self._ensure_operator()
        step_results: list[dict[str, Any]] = []
        risk_classes: list[str] = []
        required_approvals: list[str] = []
        gaps: list[str] = []

        for step in recipe:
            workflow = step.get("workflow", "")
            params = dict(step.get("params") or {})
            plan = operator.plan(workflow, params)
            status = plan.get("status", "planned")
            if status == "gap":
                gaps.append(workflow)
                step_result: dict[str, Any] = {
                    "workflow": workflow,
                    "status": "gap",
                    "plan_id": None,
                    "risk": None,
                    "confirmation_token": None,
                    "rollback_confirmation_token": None,
                    "required_env_gates": [],
                    "message": plan.get("message"),
                }
            else:
                risk = plan.get("risk")
                if risk and risk not in risk_classes:
                    risk_classes.append(risk)
                env_gates: list[str] = []
                if plan.get("archive_maintenance"):
                    env_val = plan.get("maintenance_approval_env", "AXXON_ARCHIVE_MAINTENANCE_APPROVE")
                    env_gates.append(env_val)
                    if env_val not in required_approvals:
                        required_approvals.append(env_val)
                step_result = {
                    "workflow": workflow,
                    "status": "planned",
                    "plan_id": plan.get("plan_id"),
                    "risk": risk,
                    "confirmation_token": plan.get("confirmation_token"),
                    "rollback_confirmation_token": plan.get("rollback_confirmation_token"),
                    "required_env_gates": env_gates,
                    "message": None,
                }
            step_results.append(step_result)

        return {
            "valid": len(gaps) == 0,
            "steps": step_results,
            "risk_classes": risk_classes,
            "required_approvals": required_approvals,
            "gaps": gaps,
        }

    # ------------------------------------------------------------------
    # explain_recipe
    # ------------------------------------------------------------------

    def explain_recipe(self, recipe: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        """Render a human-readable explanation of a recipe with no network I/O.

        Args:
            recipe: Either the raw ``assemble_recipe`` output (dict with ``steps`` key),
                the ``validate_recipe`` output (dict with ``valid`` and ``steps`` keys),
                or a plain list of step dicts.

        Returns:
            Dict with a ``text`` key containing the formatted explanation.
        """
        # Normalize input: accept raw steps list, assemble output dict, or validate output dict.
        if isinstance(recipe, dict):
            steps = recipe.get("steps", [])
        else:
            steps = list(recipe)

        lines: list[str] = ["Recipe explanation:", ""]
        confirmations: list[str] = []
        env_gates_seen: list[str] = []

        for idx, step in enumerate(steps, start=1):
            workflow = step.get("workflow", "unknown")
            # why from raw step or from enriched validate output
            why = step.get("why", step.get("intent", ""))
            # risk from raw step (not present) or from validate_recipe enriched step
            risk = step.get("risk") or "mutation"
            status = step.get("status", "unknown")
            time_est = _TIME_ESTIMATES.get(risk, _DEFAULT_TIME_ESTIMATE)
            rollback_note = _ROLLBACK_NOTES.get(risk, _DEFAULT_ROLLBACK_NOTE)
            confirmation_token = step.get("confirmation_token")
            env_gates = step.get("required_env_gates") or []

            lines.append(f"Step {idx}: {workflow}")
            if why:
                lines.append(f"  Intent: {why}")
            lines.append(f"  Risk: {risk}")
            lines.append(f"  Estimated time: {time_est}")
            lines.append(f"  Rollback: {rollback_note}")
            if status == "gap":
                lines.append(f"  Status: GAP — {step.get('message', 'missing required params')}")
            elif status == "planned":
                lines.append(f"  Status: planned (plan_id={step.get('plan_id')})")
            if confirmation_token:
                confirmations.append(confirmation_token)
            for gate in env_gates:
                if gate not in env_gates_seen:
                    env_gates_seen.append(gate)
            lines.append("")

        # Footer
        lines.append("Summary:")
        if confirmations:
            lines.append(f"  Required confirmations: {', '.join(confirmations)}")
        else:
            lines.append("  No confirmation tokens yet (run validate_recipe first)")
        if env_gates_seen:
            lines.append(f"  Required env gates: {', '.join(env_gates_seen)}")
        else:
            lines.append("  No additional env gates required")

        return {"text": "\n".join(lines)}


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_translator_tools(server: Any, translator: AxxonMcpTranslator) -> None:
    """Register the three translator tools on a FastMCP server instance.

    Args:
        server: FastMCP server instance.
        translator: Configured AxxonMcpTranslator.
    """
    @server.tool(name="assemble_recipe")
    def assemble_recipe(intent_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Translate a natural-language intent into an ordered list of operator workflow steps."""
        return translator.assemble_recipe(intent_text, context or {})

    @server.tool(name="validate_recipe")
    def validate_recipe(recipe: list[dict[str, Any]]) -> dict[str, Any]:
        """Dry-run each step in a recipe via operator.plan and return aggregated validation results."""
        return translator.validate_recipe(recipe)

    @server.tool(name="explain_recipe")
    def explain_recipe(recipe: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        """Return a human-readable explanation of a recipe including risk, rollback, and time estimates."""
        return translator.explain_recipe(recipe)
