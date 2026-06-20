#!/usr/bin/env python3
"""Gated notifier action tools for Axxon One MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary


NOTIFIER_ACTIONS_APPROVE_ENV = "AXXON_NOTIFIER_ACTIONS_APPROVE"
NOTIFIER_ACTIONS_CONFIRMATION = "CONFIRM-notifier-actions"
NOTIFICATION_PROTO = "axxonsoft/bl/events/Notification.proto"
NOTIFICATION_PB2 = "axxonsoft.bl.events.Notification_pb2"
EMAIL_PROTO = "axxonsoft/bl/notifications/EMailNotifier.proto"
EMAIL_PB2 = "axxonsoft.bl.notifications.EMailNotifier_pb2"

NOTIFIER_ACTIONS_TOOL_NAMES = (
    "notifier_actions_connect_axxon_profile",
    "push_diagnostic_events",
    "send_email",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(NOTIFIER_ACTIONS_APPROVE_ENV) == "1"


def _message_from_dict(message_cls: Any, payload: dict[str, Any]) -> Any:
    try:
        from google.protobuf import json_format

        message = message_cls()
        json_format.ParseDict(payload, message)
        return message
    except Exception:
        return message_cls(**payload)


@dataclass
class AxxonMcpNotifierActions:
    """Approval-gated PushDiagnosticEvents and SendEMail tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def notifier_actions_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "write",
            "approval_env": NOTIFIER_ACTIONS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.notifier_actions_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.notifier_actions_connect_axxon_profile("env")
        return self.client

    def _write_gate(self, action: str, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {NOTIFIER_ACTIONS_APPROVE_ENV}=1 to enable {action}.", "approval_env": NOTIFIER_ACTIONS_APPROVE_ENV}
        if confirmation != NOTIFIER_ACTIONS_CONFIRMATION:
            return {"status": "gap", "message": f"{action} requires confirmation={NOTIFIER_ACTIONS_CONFIRMATION}"}
        return None

    def _notification_stub_and_pb2(self, notifier: str) -> tuple[Any, Any, str]:
        normalized = notifier.lower().strip()
        if normalized not in {"domain", "node"}:
            raise ValueError("notifier must be 'domain' or 'node'")
        service = "DomainNotifier" if normalized == "domain" else "NodeNotifier"
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(NOTIFICATION_PROTO, service), client.import_module(NOTIFICATION_PB2), normalized

    def _email_stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(EMAIL_PROTO, "EMailNotifier"), client.import_module(EMAIL_PB2)

    def push_diagnostic_events(
        self,
        notifier: str = "domain",
        alerts: list[dict[str, Any]] | None = None,
        actions: list[dict[str, Any]] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Push diagnostic alert/action events through DomainNotifier or NodeNotifier."""
        gated = self._write_gate("push_diagnostic_events", confirmation)
        if gated is not None:
            return {"tool": "push_diagnostic_events", **gated}
        try:
            stub, pb2, normalized = self._notification_stub_and_pb2(notifier)
        except ValueError as exc:
            return {"status": "gap", "tool": "push_diagnostic_events", "message": str(exc)}
        alert_payload = list(alerts or [])
        action_payload = list(actions or [])
        request = _message_from_dict(
            pb2.PushDiagnosticEventsRequest,
            {"alerts": alert_payload, "actions": action_payload},
        )
        stub.PushDiagnosticEvents(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "pushed",
            "tool": "push_diagnostic_events",
            "notifier": normalized,
            "alert_count": len(alert_payload),
            "action_count": len(action_payload),
        }

    def send_email(
        self,
        access_point: str = "",
        subject: str = "",
        message: str = "",
        recipients: list[str] | None = None,
        attachments: list[str] | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        """Send an email through EMailNotifier. The body is not echoed in the result."""
        gated = self._write_gate("send_email", confirmation)
        if gated is not None:
            return {"tool": "send_email", **gated}
        recipient_list = [item for item in (recipients or []) if item]
        attachment_list = [item for item in (attachments or []) if item]
        if not access_point or not recipient_list:
            return {"status": "error", "tool": "send_email", "message": "access_point and at least one recipient are required."}
        stub, pb2 = self._email_stub_and_pb2()
        request = _message_from_dict(
            pb2.SendEMailRequest,
            {
                "access_point": access_point,
                "subject": subject,
                "message": message,
                "recipients": recipient_list,
                "attachments": attachment_list,
            },
        )
        response = stub.SendEMail(request, timeout=self.ensure_client().config.timeout)
        return {
            "status": "sent",
            "tool": "send_email",
            "guid": getattr(response, "guid", ""),
            "access_point": access_point,
            "subject_length": len(subject or ""),
            "message_length": len(message or ""),
            "recipient_count": len(recipient_list),
            "attachment_count": len(attachment_list),
        }
