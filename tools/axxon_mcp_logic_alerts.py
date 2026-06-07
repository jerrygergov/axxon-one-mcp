#!/usr/bin/env python3
"""LogicService node-scoped batch alert tools for Axxon One MCP (Phase 35).

Read active alerts across nodes (BatchGetActiveAlerts / BatchFilterActiveAlerts) and
run node+filter-scoped review actions (BatchBeginAlertsReview / ...Continue /
...Cancel / ...Complete / BatchEscalateAlerts). The five review writes are
approval-gated (`AXXON_LOGIC_ALERTS_APPROVE=1`) plus a per-call confirmation token,
mirroring the audit-injector idiom. Direct gRPC against `LogicService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

LOGIC_ALERTS_APPROVE_ENV = "AXXON_LOGIC_ALERTS_APPROVE"
LOGIC_ALERTS_CONFIRMATION = "CONFIRM-batch-alerts"
LOGIC_PROTO = "axxonsoft/bl/logic/LogicService.proto"
LOGIC_PB2 = "axxonsoft.bl.logic.LogicService_pb2"

LOGIC_ALERTS_TOOL_NAMES = (
    "logic_alerts_connect_axxon_profile",
    "batch_get_active_alerts",
    "batch_filter_active_alerts",
    "batch_begin_alerts_review",
    "batch_continue_alerts_review",
    "batch_cancel_alerts_review",
    "batch_complete_alerts_review",
    "batch_escalate_alerts",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(LOGIC_ALERTS_APPROVE_ENV) == "1"


def _alert_filter(pb2: Any, groups: list[str] | None, parents: list[str] | None) -> Any:
    flt = pb2.AlertFilter(groups=list(groups or []))
    for ap in parents or []:
        flt.parents.append(pb2.AlertParent(access_point=ap))
    return flt


@dataclass
class AxxonMcpLogicAlerts:
    """Phase 35 LogicService batch alert tools (reads + gated batch reviews)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def logic_alerts_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+write",
            "approval_env": LOGIC_ALERTS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.logic_alerts_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.logic_alerts_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(LOGIC_PROTO, "LogicService"), client.import_module(LOGIC_PB2)

    def _write_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {LOGIC_ALERTS_APPROVE_ENV}=1 to enable batch alert reviews.", "approval_env": LOGIC_ALERTS_APPROVE_ENV}
        if confirmation != LOGIC_ALERTS_CONFIRMATION:
            return {"status": "gap", "message": f"batch alert reviews require confirmation={LOGIC_ALERTS_CONFIRMATION}"}
        return None

    def _alert_brief(self, alert: Any) -> dict[str, Any]:
        return {
            "id": getattr(alert, "id", "") or getattr(alert, "guid", ""),
            "source": getattr(alert, "source_endpoint", "") or getattr(alert, "initiator", ""),
            "node": getattr(alert, "node", ""),
        }

    def batch_get_active_alerts(self, nodes: list[str] | None = None) -> dict[str, Any]:
        ids = [n for n in (nodes or []) if n]
        if not ids:
            return {"status": "error", "tool": "batch_get_active_alerts", "message": "provide at least one node"}
        stub, pb2 = self._stub_and_pb2()
        alerts: list[dict[str, Any]] = []
        unreachable: list[str] = []
        for response in stub.BatchGetActiveAlerts(pb2.BatchGetActiveAlertsRequest(nodes=ids), timeout=self.ensure_client().config.timeout):
            alerts.extend(self._alert_brief(a) for a in response.alerts)
            unreachable.extend(response.unreachable_nodes)
        return {"status": "ok", "tool": "batch_get_active_alerts", "alert_count": len(alerts), "alerts": alerts, "unreachable_nodes": unreachable}

    def batch_filter_active_alerts(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None) -> dict[str, Any]:
        ids = [n for n in (nodes or []) if n]
        if not ids:
            return {"status": "error", "tool": "batch_filter_active_alerts", "message": "provide at least one node"}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.BatchFilterActiveAlertsRequest(nodes=ids, filter=_alert_filter(pb2, groups, parents))
        alerts: list[dict[str, Any]] = []
        unreachable: list[str] = []
        for response in stub.BatchFilterActiveAlerts(request, timeout=self.ensure_client().config.timeout):
            alerts.extend(self._alert_brief(a) for a in response.alerts)
            unreachable.extend(response.unreachable_nodes)
        return {"status": "ok", "tool": "batch_filter_active_alerts", "alert_count": len(alerts), "alerts": alerts, "unreachable_nodes": unreachable}

    def _drain_review(self, stream: Any) -> dict[str, list[str]]:
        success: list[str] = []
        failure: list[str] = []
        unreachable: list[str] = []
        for response in stream:
            success.extend(response.success)
            failure.extend(response.failure)
            unreachable.extend(response.unreachable_nodes)
        return {"success": success, "failure": failure, "unreachable_nodes": unreachable}

    def _gated_review(self, tool: str, rpc: str, request_name: str, nodes: list[str] | None, groups: list[str] | None, parents: list[str] | None, confirmation: str, **extra: Any) -> dict[str, Any]:
        gated = self._write_gate(confirmation)
        if gated is not None:
            return {"tool": tool, **gated}
        ids = [n for n in (nodes or []) if n]
        if not ids:
            return {"status": "error", "tool": tool, "message": "provide at least one node"}
        stub, pb2 = self._stub_and_pb2()
        request = getattr(pb2, request_name)(nodes=ids, filter=_alert_filter(pb2, groups, parents), **extra)
        result = self._drain_review(getattr(stub, rpc)(request, timeout=self.ensure_client().config.timeout))
        return {"status": "applied", "tool": tool, **result}

    def batch_begin_alerts_review(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        return self._gated_review("batch_begin_alerts_review", "BatchBeginAlertsReview", "BatchBeginAlertsReviewRequest", nodes, groups, parents, confirmation)

    def batch_continue_alerts_review(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        return self._gated_review("batch_continue_alerts_review", "BatchContinueAlertsRewiew", "BatchContinueAlertsRewiewRequest", nodes, groups, parents, confirmation)

    def batch_cancel_alerts_review(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, confirmation: str = "") -> dict[str, Any]:
        return self._gated_review("batch_cancel_alerts_review", "BatchCancelAlertsReview", "BatchCancelAlertsReviewRequest", nodes, groups, parents, confirmation)

    def batch_complete_alerts_review(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, severity: int = 0, confirmation: str = "") -> dict[str, Any]:
        extra = {"severity": int(severity)} if severity else {}
        return self._gated_review("batch_complete_alerts_review", "BatchCompleteAlertsReview", "BatchCompleteAlertsReviewRequest", nodes, groups, parents, confirmation, **extra)

    def batch_escalate_alerts(self, nodes: list[str] | None = None, groups: list[str] | None = None, parents: list[str] | None = None, comment: str = "", confirmation: str = "") -> dict[str, Any]:
        extra = {"comment": comment} if comment else {}
        return self._gated_review("batch_escalate_alerts", "BatchEscalateAlerts", "BatchEscalateAlertsRequest", nodes, groups, parents, confirmation, **extra)
