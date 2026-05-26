#!/usr/bin/env python3
"""Read-only security, health, notifier, and schedule tools for Axxon One MCP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


ADMIN_MODE = "read-only"

ADMIN_TOOL_NAMES = (
    "admin_connect_axxon_profile",
    "security_inventory",
    "security_policy_summary",
    "role_permissions",
    "current_user_security",
    "license_status",
    "time_status",
    "system_health",
    "domain_event_subscribe",
    "node_event_subscribe",
    "schedule_descriptor_get",
)

_SENSITIVE_KEY_TOKENS = (
    "password",
    "passwd",
    "pwd",
    "authorization",
    "bearer",
    "token",
    "sessionid",
    "tfa",
    "otp",
    "secret",
    "license",
    "serial",
    "fingerprint",
    "hardware",
    "machineid",
    "hostid",
    "hwid",
)

_BEARER_TEXT_RE = re.compile(r"\bBearer\s+[^,\s;]+", re.IGNORECASE)
_SECRET_TEXT_KEY = (
    r"password|passwd|pwd|authorization|bearer|token|session[_-]?token|tfa[_-]?(secret|code|key)?|"
    r"otp|secret|license[_-]?key|serial[_-]?number|fingerprint|hardware[_-]?fingerprint|"
    r"machine[_-]?id|host[_-]?id|hwid"
)
_QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?P<key_quote>['\"]?)(?P<key>\b(?:{_SECRET_TEXT_KEY})\b)(?P=key_quote)"
    r"(?P<sep>\s*[:=]\s*)(?P<value_quote>['\"])(?P<value>.*?)(?P=value_quote)",
    re.IGNORECASE,
)
_UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?P<key_quote>['\"]?)(?P<key>\b(?:{_SECRET_TEXT_KEY})\b)(?P=key_quote)"
    r"(?P<sep>\s*[:=]\s*)[^,\s;}\]]+",
    re.IGNORECASE,
)


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def public_config_summary(config: Any) -> dict[str, Any]:
    return {
        "host": getattr(config, "host", ""),
        "grpc_port": getattr(config, "grpc_port", None),
        "http_port": getattr(config, "http_port", None),
        "http_url": getattr(config, "http_url", ""),
        "username": getattr(config, "username", ""),
        "password_present": bool(getattr(config, "password", "")),
        "tls_cn": getattr(config, "tls_cn", ""),
        "ca": str(getattr(config, "ca", "")),
        "timeout": getattr(config, "timeout", None),
    }


def _normalized_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    if normalized in ("pwdpolicy", "pwdpolicies", "passwordpolicy", "passwordpolicies"):
        return False
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def redact_admin_text(value: Any, limit: int = 240) -> str:
    text = str(value)
    text = _BEARER_TEXT_RE.sub("Bearer <redacted>", text)
    text = _QUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
        f"{match.group('sep')}<redacted>",
        text,
    )
    text = _UNQUOTED_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
        f"{match.group('sep')}<redacted>",
        text,
    )
    return text[:limit]


def redact_admin_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            out[key] = "<redacted>" if _is_sensitive_key(key) and item else redact_admin_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_admin_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_admin_secrets(item) for item in value)
    if isinstance(value, str):
        return redact_admin_text(value)
    return value


def _body(response: Any) -> dict[str, Any]:
    if isinstance(response, dict) and isinstance(response.get("body"), dict):
        return response["body"]
    if isinstance(response, dict):
        return response
    return {}


def _clamp_page_size(page_size: int) -> int:
    return min(max(int(page_size), 1), 1000)


def _role_summary(role: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(role)
    role_id = str(redacted.get("index") or redacted.get("role_id") or redacted.get("id") or "")
    out = {
        "role_id": role_id,
        "role_id_length": len(role_id),
        "name": redacted.get("name", ""),
    }
    if redacted.get("comment"):
        out["comment"] = redacted["comment"]
    return out


def _user_summary(user: dict[str, Any], assignments_by_user: dict[str, list[str]]) -> dict[str, Any]:
    redacted = redact_admin_secrets(user)
    user_id = str(redacted.get("index") or redacted.get("user_id") or redacted.get("id") or "")
    return {
        "user_id": user_id,
        "user_id_length": len(user_id),
        "login": redacted.get("login", ""),
        "name": redacted.get("name", ""),
        "enabled": bool(redacted.get("enabled", False)),
        "role_ids": assignments_by_user.get(user_id, []),
    }


def _ldap_summary(server: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(server)
    ldap_id = str(redacted.get("index") or redacted.get("ldap_server_id") or redacted.get("id") or "")
    return {
        "ldap_id": ldap_id,
        "ldap_id_length": len(ldap_id),
        "name": redacted.get("name") or redacted.get("display_name") or "",
        "enabled": bool(redacted.get("enabled", False)),
    }


def _permission_info_summary(item: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(item)
    out = {}
    for field in ("id", "name", "display_name", "type", "access_point"):
        if field in redacted:
            out[field] = redacted[field]
    return out or {"keys": sorted(str(key) for key in redacted.keys())}


@dataclass
class AxxonMcpAdmin:
    """Read-only Phase 5F-A admin tool scaffold."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def admin_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
                "profile_name": profile,
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": ADMIN_MODE,
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.admin_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.admin_connect_axxon_profile("env")
        return self.client

    def _collect_pages(self, method_name: str, item_key: str, page_size: int, **kwargs: Any) -> list[dict[str, Any]]:
        client = self.ensure_client()
        items: list[dict[str, Any]] = []
        page_token = ""
        applied_page_size = _clamp_page_size(page_size)
        while True:
            response = getattr(client, method_name)(page_size=applied_page_size, page_token=page_token, **kwargs)
            data = _body(response)
            items.extend(item for item in data.get(item_key, []) if isinstance(item, dict))
            page_token = str(data.get("next_page_token") or "")
            if not page_token:
                return items

    def _collect_user_pages(self, page_size: int, role_ids: list[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        client = self.ensure_client()
        users: list[dict[str, Any]] = []
        assignments: list[dict[str, Any]] = []
        page_token = ""
        applied_page_size = _clamp_page_size(page_size)
        while True:
            response = client.security_list_users(
                page_size=applied_page_size,
                page_token=page_token,
                role_ids=role_ids,
            )
            data = _body(response)
            users.extend(item for item in data.get("users", []) if isinstance(item, dict))
            assignments.extend(item for item in data.get("user_assignments", []) if isinstance(item, dict))
            page_token = str(data.get("next_page_token") or "")
            if not page_token:
                return users, assignments

    def security_inventory(
        self,
        include_users: bool = True,
        include_roles: bool = True,
        include_ldap: bool = True,
        page_size: int = 100,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "ok", "tool": "security_inventory"}
        if include_roles:
            roles = self._collect_pages("security_list_roles", "roles", page_size)
            result["roles"] = {"count": len(roles), "items": [_role_summary(role) for role in roles]}
        if include_users:
            users, assignments = self._collect_user_pages(page_size)
            assignments_by_user: dict[str, list[str]] = {}
            for assignment in assignments:
                user_id = str(assignment.get("user_id") or assignment.get("user_index") or "")
                role_id = str(assignment.get("role_id") or assignment.get("role_index") or "")
                if user_id and role_id:
                    assignments_by_user.setdefault(user_id, []).append(role_id)
            result["users"] = {
                "count": len(users),
                "enabled_count": sum(1 for user in users if user.get("enabled") is True),
                "assignment_count": len(assignments),
                "items": [_user_summary(user, assignments_by_user) for user in users],
            }
        if include_ldap:
            ldap_servers = self._collect_pages("security_list_ldap_servers", "ldap_servers", page_size)
            result["ldap_servers"] = {
                "count": len(ldap_servers),
                "items": [_ldap_summary(server) for server in ldap_servers],
            }
        return result

    def security_policy_summary(self) -> dict[str, Any]:
        client = self.ensure_client()
        policies = redact_admin_secrets(_body(client.security_get_policies()))
        ldap_servers = self._collect_pages("security_list_ldap_servers", "ldap_servers", 100)
        ldap_status = "ok" if ldap_servers else "fixture-needed"
        return {
            "status": "ok",
            "tool": "security_policy_summary",
            "password_policy_count": len(policies.get("pwd_policy", [])),
            "ip_filter_count": len(policies.get("ip_filters", [])),
            "trusted_ip_count": len(policies.get("trusted_ip_list", [])),
            "system_integrity_modes_count": len(policies.get("system_integrity_reaction_modes", [])),
            "cloud_public_key_present": bool(policies.get("cloud_public_key")),
            "ldap": {
                "status": ldap_status,
                "servers_count": len(ldap_servers),
                "message": "No LDAP servers configured." if ldap_status == "fixture-needed" else "",
            },
        }

    def role_permissions(self, role_id: str, page_size: int = 50) -> dict[str, Any]:
        client = self.ensure_client()
        global_permissions = redact_admin_secrets(_body(client.security_list_global_permissions([role_id])))
        node_name = client.node_name() if hasattr(client, "node_name") else getattr(client.config, "tls_cn", "")
        objects = self._collect_pages(
            "security_list_object_permissions_info",
            "items",
            page_size,
            role_id=role_id,
            node_name=node_name,
        )
        permissions = global_permissions.get("permissions", {})
        return {
            "status": "ok",
            "tool": "role_permissions",
            "role_id": role_id,
            "global": {
                "roles_count": len(permissions) if isinstance(permissions, dict) else 0,
                "permission_keys": sorted(str(key) for key in permissions.get(role_id, {}).keys())
                if isinstance(permissions, dict) and isinstance(permissions.get(role_id), dict)
                else [],
            },
            "objects": {
                "count": len(objects),
                "items": [_permission_info_summary(item) for item in objects],
            },
            "groups": {"status": "not-in-task-scope"},
            "macros": {"status": "not-in-task-scope"},
        }

    def current_user_security(self) -> dict[str, Any]:
        client = self.ensure_client()
        data = redact_admin_secrets(_body(client.security_get_restricted_config()))
        current_user = data.get("current_user") if isinstance(data.get("current_user"), dict) else {}
        current_roles = [role for role in data.get("current_roles", []) if isinstance(role, dict)]
        return {
            "status": "ok",
            "tool": "current_user_security",
            "current_user": _user_summary(current_user, {}),
            "current_roles": {"count": len(current_roles), "items": [_role_summary(role) for role in current_roles]},
            "all_roles_count": len(data.get("all_roles", [])),
            "all_users_count": len(data.get("all_users", [])),
            "password_policy_count": len(data.get("pwd_policy", [])),
            "system_integrity_modes_count": len(data.get("system_integrity_reaction_modes", [])),
        }
