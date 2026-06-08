#!/usr/bin/env python3
"""DomainSettingsService data-storage tools for Axxon One MCP (Phase 17).

Read and update the data-storage settings (system-logs + VMDA/metadata retention
and cleanup). The update is approval-gated (`AXXON_SETTINGS_APPROVE=1`) plus a
per-call confirmation token, mirroring the audit-injector idiom. It is always
field-masked (never a blind overwrite) and manages the etag for optimistic
concurrency internally, so callers pass only the seconds they want to change.
Direct gRPC against `DomainSettingsService`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from google.protobuf.duration_pb2 import Duration
from google.protobuf.field_mask_pb2 import FieldMask

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

SETTINGS_APPROVE_ENV = "AXXON_SETTINGS_APPROVE"
SETTINGS_CONFIRMATION = "CONFIRM-settings-update"
SETTINGS_PROTO = "axxonsoft/bl/settings/DomainSettingsService.proto"
SETTINGS_PB2 = "axxonsoft.bl.settings.DomainSettingsService_pb2"
DATA_PB2 = "axxonsoft.bl.settings.DataStorageSettings_pb2"
BOOKMARK_PB2 = "axxonsoft.bl.settings.BookmarkSettings_pb2"
GDPR_PB2 = "axxonsoft.bl.settings.GDPRSettings_pb2"

# update arg -> (proto field path for the mask, nested setter)
UPDATE_FIELDS = {
    "system_logs_retention_s": "system_logs_settings.retention_period",
    "system_logs_cleanup_s": "system_logs_settings.cleanup_period",
    "vmda_retention_s": "vmda_storage_settings.retention_period",
}

# GDPR privacy_mask_type friendly name -> enum name
GDPR_MASK_TYPES = {"unspecified": "PRIVACY_MASK_TYPE_UNSPECIFIED", "mosaic": "MOSAIC", "black": "BLACK"}

SETTINGS_TOOL_NAMES = (
    "settings_connect_axxon_profile",
    "get_data_storage_settings",
    "update_data_storage_settings",
    "get_bookmark_settings",
    "update_bookmark_settings",
    "get_gdpr_settings",
    "update_gdpr_settings",
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def _approval_from_env() -> bool:
    return os.environ.get(SETTINGS_APPROVE_ENV) == "1"


@dataclass
class AxxonMcpSettings:
    """Phase 17 DomainSettingsService data-storage tools (read + gated update)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def settings_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read+update",
            "approval_env": SETTINGS_APPROVE_ENV,
            "enabled": bool(self.enabled),
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.settings_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.settings_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(SETTINGS_PROTO, "DomainSettingsService"), client.import_module(SETTINGS_PB2)

    def get_data_storage_settings(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        cur = stub.GetDataStorageSettings(pb2.GetDataStorageSettingsRequest(), timeout=self.ensure_client().config.timeout)
        return {
            "status": "ok",
            "system_logs": {
                "retention_period_s": cur.system_logs_settings.retention_period.seconds,
                "cleanup_period_s": cur.system_logs_settings.cleanup_period.seconds,
            },
            "vmda": {"retention_period_s": cur.vmda_storage_settings.retention_period.seconds},
            "etag": cur.etag,
        }

    def update_data_storage_settings(
        self,
        system_logs_retention_s: int | None = None,
        system_logs_cleanup_s: int | None = None,
        vmda_retention_s: int | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {SETTINGS_APPROVE_ENV}=1 to enable settings updates.", "approval_env": SETTINGS_APPROVE_ENV}
        if confirmation != SETTINGS_CONFIRMATION:
            return {"status": "gap", "message": f"settings updates require confirmation={SETTINGS_CONFIRMATION}"}
        provided = {
            "system_logs_retention_s": system_logs_retention_s,
            "system_logs_cleanup_s": system_logs_cleanup_s,
            "vmda_retention_s": vmda_retention_s,
        }
        provided = {k: v for k, v in provided.items() if v is not None}
        if not provided:
            return {"status": "error", "message": "provide at least one of " + ", ".join(UPDATE_FIELDS)}

        stub, pb2 = self._stub_and_pb2()
        data = self.ensure_client().import_module(DATA_PB2)
        current = stub.GetDataStorageSettings(pb2.GetDataStorageSettingsRequest(), timeout=self.ensure_client().config.timeout)

        settings = data.DataStorageSettings(etag=current.etag)
        if "system_logs_retention_s" in provided:
            settings.system_logs_settings.retention_period.seconds = int(provided["system_logs_retention_s"])
        if "system_logs_cleanup_s" in provided:
            settings.system_logs_settings.cleanup_period.seconds = int(provided["system_logs_cleanup_s"])
        if "vmda_retention_s" in provided:
            settings.vmda_storage_settings.retention_period.seconds = int(provided["vmda_retention_s"])

        mask = FieldMask(paths=[UPDATE_FIELDS[k] for k in provided])
        resp = stub.UpdateDataStorageSettings(
            pb2.UpdateDataStorageSettingsRequest(data_storage_settings=settings, update_mask=mask),
            timeout=self.ensure_client().config.timeout,
        )
        return {
            "status": "applied",
            "updated_fields": list(provided),
            "system_logs": {
                "retention_period_s": resp.system_logs_settings.retention_period.seconds,
                "cleanup_period_s": resp.system_logs_settings.cleanup_period.seconds,
            },
            "vmda": {"retention_period_s": resp.vmda_storage_settings.retention_period.seconds},
            "etag": resp.etag,
        }

    def _update_gate(self, confirmation: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {"status": "disabled", "message": f"Set {SETTINGS_APPROVE_ENV}=1 to enable settings updates.", "approval_env": SETTINGS_APPROVE_ENV}
        if confirmation != SETTINGS_CONFIRMATION:
            return {"status": "gap", "message": f"settings updates require confirmation={SETTINGS_CONFIRMATION}"}
        return None

    def get_bookmark_settings(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        resp = stub.GetBookmarkSettings(pb2.GetBookmarkSettingsRequest(), timeout=self.ensure_client().config.timeout)
        s = resp.settings
        return {
            "status": "ok",
            "mandatory_protection": s.mandatory_protection,
            "bookmark_max_duration_s": s.bookmark_max_duration.seconds,
            "retention_period_s": s.retention_period.seconds,
            "etag": resp.etag,
        }

    def update_bookmark_settings(
        self,
        mandatory_protection: bool | None = None,
        bookmark_max_duration_s: int | None = None,
        retention_period_s: int | None = None,
        confirmation: str = "",
    ) -> dict[str, Any]:
        gated = self._update_gate(confirmation)
        if gated is not None:
            return gated
        stub, pb2 = self._stub_and_pb2()
        book = self.ensure_client().import_module(BOOKMARK_PB2)
        settings = book.BookmarkSettings()
        paths: list[str] = []
        if mandatory_protection is not None:
            settings.mandatory_protection = bool(mandatory_protection)
            paths.append("mandatory_protection")
        if bookmark_max_duration_s is not None:
            settings.bookmark_max_duration.seconds = int(bookmark_max_duration_s)
            paths.append("bookmark_max_duration")
        if retention_period_s is not None:
            settings.retention_period.seconds = int(retention_period_s)
            paths.append("retention_period")
        if not paths:
            return {"status": "error", "message": "provide at least one of mandatory_protection, bookmark_max_duration_s, retention_period_s"}
        current = stub.GetBookmarkSettings(pb2.GetBookmarkSettingsRequest(), timeout=self.ensure_client().config.timeout)
        resp = stub.UpdateBookmarkSettings(
            pb2.UpdateBookmarkSettingsRequest(settings=settings, mask=FieldMask(paths=paths), etag=current.etag),
            timeout=self.ensure_client().config.timeout,
        )
        return {"status": "applied", "updated_fields": paths, "etag": resp.etag}

    def get_gdpr_settings(self) -> dict[str, Any]:
        stub, pb2 = self._stub_and_pb2()
        gdpr = self.ensure_client().import_module(GDPR_PB2)
        resp = stub.GetGDPRSettings(pb2.GetGDPRSettingsRequest(), timeout=self.ensure_client().config.timeout)
        # map the enum value back to a friendly name via the GDPRSettings enum attrs
        value_to_friendly = {getattr(gdpr.GDPRSettings, enum): friendly for friendly, enum in GDPR_MASK_TYPES.items()}
        friendly = value_to_friendly.get(resp.settings.privacy_mask_type, str(resp.settings.privacy_mask_type))
        return {"status": "ok", "privacy_mask_type": friendly, "etag": resp.etag}

    def update_gdpr_settings(self, privacy_mask_type: str = "", confirmation: str = "") -> dict[str, Any]:
        gated = self._update_gate(confirmation)
        if gated is not None:
            return gated
        enum_name = GDPR_MASK_TYPES.get(str(privacy_mask_type).lower())
        if enum_name is None:
            return {"status": "error", "message": f"privacy_mask_type must be one of {list(GDPR_MASK_TYPES)}, got {privacy_mask_type!r}"}
        stub, pb2 = self._stub_and_pb2()
        gdpr = self.ensure_client().import_module(GDPR_PB2)
        settings = gdpr.GDPRSettings(privacy_mask_type=getattr(gdpr.GDPRSettings, enum_name))
        current = stub.GetGDPRSettings(pb2.GetGDPRSettingsRequest(), timeout=self.ensure_client().config.timeout)
        resp = stub.UpdateGDPRSettings(
            pb2.UpdateGDPRSettingsRequest(settings=settings, mask=FieldMask(paths=["privacy_mask_type"]), etag=current.etag),
            timeout=self.ensure_client().config.timeout,
        )
        return {"status": "applied", "privacy_mask_type": str(privacy_mask_type).lower(), "etag": resp.etag}
