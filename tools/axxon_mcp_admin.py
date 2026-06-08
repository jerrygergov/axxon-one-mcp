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
    "update_event_subscription",
    "collect_config_backup",
    "schedule_descriptor_get",
)

BACKUP_TYPES = ("LOCAL", "SHARED", "LICENSE", "TICKETS")
BACKUP_CHUNK_KB_CAP = 1024
NOTIFIER_TIMEOUT_CAP_S = 30.0
NOTIFIER_LIMIT_CAP = 100
SCHEDULE_UNIT_TYPE_CANDIDATES = ("DeviceIpint", "MultimediaStorage", "AVDetector", "AppDataDetector")
PROPERTY_ID_FIELDS = ("id", "property_id", "propertyId", "path", "name")
PROPERTY_VALUE_FIELDS = (
    "value",
    "value_string",
    "value_bool",
    "value_int32",
    "value_int64",
    "value_uint32",
    "value_uint64",
    "value_float",
    "value_double",
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
            if _is_sensitive_key(key) and item and not isinstance(item, (dict, list, tuple)):
                out[key] = "<redacted>"
            else:
                out[key] = redact_admin_secrets(item)
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


def _items(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _constraint_count(data: dict[str, Any]) -> int:
    constraints = data.get("constraints")
    if isinstance(constraints, dict):
        nested = constraints.get("constraints")
        return len(nested) if isinstance(nested, list) else len(constraints)
    return len(constraints) if isinstance(constraints, list) else 0


def _license_domain_summary(data: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(data)
    return {
        "status": redacted.get("status") or redacted.get("ls_status") or redacted.get("state") or "",
        "type": redacted.get("type", ""),
        "is_license_expiring": bool(redacted.get("is_license_expiring", False)),
        "key_present": bool(data.get("license_key") or data.get("key")),
    }


def _host_info_summary(data: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(data)
    return {
        "os_name": redacted.get("osname") or redacted.get("os_name") or "",
        "host_name": redacted.get("host_name") or redacted.get("name") or redacted.get("node_name") or "",
        "hardware_fingerprint_present": bool(
            data.get("hwinfo") or data.get("hardware_fingerprint") or data.get("fingerprint")
        ),
        "serial_present": bool(data.get("serial_number") or data.get("serialNumber")),
    }


def _section_unavailable(exc: Exception) -> dict[str, Any]:
    return {
        "status": "fixture-needed",
        "error_type": exc.__class__.__name__,
        "message": redact_admin_text(exc),
    }


def _zone_summary(zone: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_admin_secrets(zone)
    return {
        "id": redacted.get("id") or redacted.get("time_zone_id") or redacted.get("name") or "",
        "display_name": redacted.get("display_name") or redacted.get("displayName") or redacted.get("name") or "",
    }


def _unit_type_from_uid(uid: str) -> str:
    leaf = str(uid).rstrip("/").split("/")[-1]
    return leaf.split(".", 1)[0] if "." in leaf else ""


def _unit_uid(value: dict[str, Any]) -> str:
    for field in ("uid", "unit_uid", "unitUid", "id"):
        item = value.get(field)
        if isinstance(item, str) and item:
            return item
    return ""


def _property_id(value: dict[str, Any]) -> str:
    for field in PROPERTY_ID_FIELDS:
        item = value.get(field)
        if isinstance(item, str) and item:
            return item
    return ""


def _iter_property_nodes(properties: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(properties, list):
        return nodes
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        prop_id = _property_id(prop)
        path = f"{prefix}.{prop_id}" if prefix and prop_id else prop_id or prefix
        if path:
            nodes.append((path, prop))
        nodes.extend(_iter_property_nodes(prop.get("properties"), path))
    return nodes


def _property_value(prop: dict[str, Any]) -> tuple[str, Any]:
    redacted = redact_admin_secrets(prop)
    for field in PROPERTY_VALUE_FIELDS:
        if field in redacted:
            return field, redacted[field]
    return "", None


def _schedule_like(path: str) -> bool:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in path)
    return any(token in text for token in ("schedule", "calendar", "weekly", "daily"))


def _schedule_property_summary(path: str, prop: dict[str, Any], source: str) -> dict[str, Any] | None:
    value_kind, value = _property_value(prop)
    if not value_kind:
        return None
    redacted = redact_admin_secrets(prop)
    out: dict[str, Any] = {
        "id": _property_id(redacted),
        "path": path,
        "value_kind": value_kind,
        "value": value,
        "readonly": bool(redacted.get("readonly", False)),
        "source": source,
    }
    for field in ("name", "type", "category"):
        if field in redacted:
            out[field] = redacted[field]
    return out


def _schedule_properties(descriptor: dict[str, Any], source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path, prop in _iter_property_nodes(descriptor.get("properties")):
        if not _schedule_like(path):
            continue
        summary = _schedule_property_summary(path, prop, source)
        if summary is not None:
            items.append(summary)
    return items


def _fixture_needed_schedule(uid: str, message: str) -> dict[str, Any]:
    return {
        "status": "fixture-needed",
        "tool": "schedule_descriptor_get",
        "target": uid,
        "schedule_properties": [],
        "confidence": "none",
        "message": message,
        "missing": [
            "list_units wrapper or ConfigurationService.ListUnits descriptor",
            "descriptor fields containing schedule, calendar, weekly, or daily properties",
        ],
    }


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

    def license_status(
        self,
        include_host_info: bool = True,
        include_node_restrictions: bool = True,
        node_names: list[str] | None = None,
        limit: int = 32,
    ) -> dict[str, Any]:
        client = self.ensure_client()
        applied_limit = min(max(int(limit), 1), 128)
        global_restrictions = redact_admin_secrets(_body(client.license_get_global_restrictions()))
        domain_info = _body(client.license_get_domain_key_info())
        key_info = _body(client.license_key_info())
        result: dict[str, Any] = {
            "status": "ok",
            "tool": "license_status",
            "global_restrictions": {"constraint_count": _constraint_count(global_restrictions)},
            "domain": _license_domain_summary(domain_info),
            "key_info": _license_domain_summary(key_info),
            "launch": {
                "AVDetector": redact_admin_secrets(_body(client.license_is_possible_to_launch("AVDetector", quantity=1)))
            },
            "applied_limit": applied_limit,
        }
        if include_host_info:
            try:
                result["host_info"] = _host_info_summary(_body(client.license_get_host_info()))
            except Exception as exc:  # noqa: BLE001 - optional live license host data may be absent.
                result["status"] = "warn"
                result["host_info"] = _section_unavailable(exc)
        if include_node_restrictions:
            requested_nodes = list(node_names or [])
            if not requested_nodes:
                requested_nodes = [client.node_name() if hasattr(client, "node_name") else getattr(client.config, "tls_cn", "")]
            requested_nodes = [name for name in requested_nodes if name][:applied_limit]
            try:
                node_data = redact_admin_secrets(_body(client.license_get_node_restrictions(requested_nodes)))
                restriction_items = _items(node_data, "items", "node_restrictions", "restrictions")
                result["node_restrictions"] = {
                    "count": len(restriction_items),
                    "nodes": requested_nodes,
                    "items": restriction_items,
                }
            except Exception as exc:  # noqa: BLE001 - optional live node restrictions may be absent.
                result["status"] = "warn"
                result["node_restrictions"] = _section_unavailable(exc)
        return redact_admin_secrets(result)

    def time_status(self, include_available: bool = True) -> dict[str, Any]:
        client = self.ensure_client()
        current = redact_admin_secrets(_body(client.time_get_time_zone()))
        ntp = redact_admin_secrets(_body(client.time_get_ntp()))
        current_zone = current.get("time_zone") if isinstance(current.get("time_zone"), dict) else current
        result: dict[str, Any] = {
            "status": "ok",
            "tool": "time_status",
            "current_zone": _zone_summary(current_zone),
            "ntp": ntp,
        }
        if include_available:
            zones_body = redact_admin_secrets(_body(client.time_list_time_zones()))
            zones = _items(zones_body, "time_zones", "zones", "items")
            zone_ids = [str(_zone_summary(zone).get("id")) for zone in zones if _zone_summary(zone).get("id")]
            batch = redact_admin_secrets(_body(client.time_batch_get_zones(zone_ids[:32]))) if zone_ids else {}
            result["available_zones"] = {
                "count": len(zones),
                "items": [_zone_summary(zone) for zone in zones[:32]],
                "batch_count": len(_items(batch, "time_zones", "zones", "items")),
            }
        return result

    def _health_section(self, name: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return builder()
        except Exception as exc:
            return {
                "status": "fixture-needed",
                "section": name,
                "message": redact_admin_text(exc),
            }

    def system_health(
        self,
        include_security: bool = True,
        include_license: bool = True,
        include_time: bool = True,
        include_archive: bool = True,
    ) -> dict[str, Any]:
        self.ensure_client()
        result: dict[str, Any] = {"status": "ok", "tool": "system_health"}
        if include_security:
            def security_builder() -> dict[str, Any]:
                inventory = self.security_inventory()
                policy = self.security_policy_summary()
                return {
                    "status": "ok",
                    "roles_count": inventory.get("roles", {}).get("count", 0),
                    "users_count": inventory.get("users", {}).get("count", 0),
                    "ldap_status": policy.get("ldap", {}).get("status", ""),
                }

            result["security"] = self._health_section("security", security_builder)
        if include_license:
            result["license"] = self._health_section("license", lambda: self.license_status())
        if include_time:
            result["time"] = self._health_section("time", lambda: self.time_status())
        if include_archive:
            result["archive"] = {
                "status": "fixture-needed",
                "message": "Archive storage aggregation is added with the live smoke fixture.",
            }
        result["session"] = {
            "connected": self.client is not None,
            "profile_name": self.profile_name,
            "mode": ADMIN_MODE,
        }
        return redact_admin_secrets(result)

    def _notifier_subscribe(
        self,
        *,
        notifier: str,
        tool: str,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        timeout = max(1.0, min(float(timeout_s), NOTIFIER_TIMEOUT_CAP_S))
        applied_limit = max(1, min(int(limit), NOTIFIER_LIMIT_CAP))
        client = self.ensure_client()
        result = client.pull_notifier_events_bounded(
            notifier=notifier,
            subjects=list(subjects or []),
            event_types=list(event_types or []),
            timeout_s=timeout,
            limit=applied_limit,
            detailed=detailed,
        )
        out = {
            "tool": tool,
            "subjects": list(subjects or []),
            "event_types": list(event_types or []),
            **redact_admin_secrets(result),
        }
        out["caps"] = {"timeout_s": timeout, "limit": applied_limit}
        return out

    def domain_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        return self._notifier_subscribe(
            notifier="domain",
            tool="domain_event_subscribe",
            subjects=subjects,
            event_types=event_types,
            timeout_s=timeout_s,
            limit=limit,
            detailed=detailed,
        )

    def node_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ) -> dict[str, Any]:
        return self._notifier_subscribe(
            notifier="node",
            tool="node_event_subscribe",
            subjects=subjects,
            event_types=event_types,
            timeout_s=timeout_s,
            limit=limit,
            detailed=detailed,
        )

    def update_event_subscription(
        self,
        notifier: str = "domain",
        event_types: list[str] | None = None,
        new_event_types: list[str] | None = None,
        subjects: list[str] | None = None,
        new_subjects: list[str] | None = None,
        timeout_s: float = 5.0,
    ) -> dict[str, Any]:
        if notifier not in ("domain", "node"):
            return {"status": "gap", "tool": "update_event_subscription", "message": "notifier must be 'domain' or 'node'"}
        timeout = max(1.0, min(float(timeout_s), NOTIFIER_TIMEOUT_CAP_S))
        client = self.ensure_client()
        result = client.update_subscription_bounded(
            notifier=notifier,
            event_types=list(event_types or []),
            new_event_types=list(new_event_types or []),
            subjects=list(subjects or []),
            new_subjects=list(new_subjects or []),
            timeout_s=timeout,
        )
        out = {"tool": "update_event_subscription", **redact_admin_secrets(result)}
        out["caps"] = {"timeout_s": timeout}
        return out

    def collect_config_backup(
        self,
        node: str = "",
        backup_types: list[str] | None = None,
        chunk_size_kb: int = 64,
    ) -> dict[str, Any]:
        names = list(backup_types or ["LOCAL"])
        unknown = [name for name in names if name not in BACKUP_TYPES]
        if not node or unknown:
            return {
                "status": "gap",
                "tool": "collect_config_backup",
                "message": "node required and backup_types must be in " + ", ".join(BACKUP_TYPES),
            }
        chunk = max(1, min(int(chunk_size_kb), BACKUP_CHUNK_KB_CAP))
        client = self.ensure_client()
        result = client.collect_backup_grpc(node=node, backup_types=names, chunk_size_kb=chunk)
        return {
            "status": "ok",
            "tool": "collect_config_backup",
            "node": result["node"],
            "backup_types": result["backup_types"],
            "total_size_bytes": result["total_size_bytes"],
            "chunk_count": result["chunk_count"],
            "byte_count": result["byte_count"],
            "caps": {"chunk_size_kb": chunk},
        }

    def _schedule_descriptor(self, uid: str) -> tuple[dict[str, Any] | None, str]:
        client = self.ensure_client()
        list_units = getattr(client, "list_units", None)
        if not callable(list_units):
            return None, ""
        parsed = _unit_type_from_uid(uid)
        unit_types = [parsed] if parsed else []
        unit_types.extend(unit_type for unit_type in SCHEDULE_UNIT_TYPE_CANDIDATES if unit_type not in unit_types)
        found: dict[str, Any] | None = None
        source = ""
        for unit_type in unit_types:
            for unit in _items({"items": list_units(unit_type)}, "items"):
                if _unit_uid(unit) == uid:
                    found = unit
                    source = "list_units"
            if found is not None:
                break
        return found, source

    def schedule_descriptor_get(self, uid: str) -> dict[str, Any]:
        if not str(uid or "").strip():
            return _fixture_needed_schedule(uid, "schedule_descriptor_get requires a concrete unit UID.")
        descriptor, source = self._schedule_descriptor(uid)
        if descriptor is None:
            return _fixture_needed_schedule(
                uid,
                "Could not resolve descriptor with schedule-like fields; provide an isolated config fixture.",
            )
        schedule_properties = _schedule_properties(descriptor, source)
        if not schedule_properties:
            return _fixture_needed_schedule(
                uid,
                "Resolved descriptor did not expose schedule, calendar, weekly, or daily fields.",
            )
        return {
            "status": "ok",
            "tool": "schedule_descriptor_get",
            "target": uid,
            "schedule_properties": schedule_properties,
            "confidence": "descriptor",
            "descriptor_source": source,
            "descriptor": redact_admin_secrets(
                {
                    "uid": descriptor.get("uid", ""),
                    "type": descriptor.get("type", ""),
                    "display_name": descriptor.get("display_name", descriptor.get("name", "")),
                }
            ),
            "notes": [
                "Read-only descriptor discovery only.",
                "Schedule authoring is deferred until descriptor-backed fixtures are available.",
            ],
        }
