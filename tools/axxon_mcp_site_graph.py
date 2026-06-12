#!/usr/bin/env python3
"""Unified read-only site graph for Axxon One MCP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


SITE_GRAPH_TOOL_NAMES = (
    "site_graph_connect_axxon_profile",
    "build_site_graph",
)

LIST_LIMIT_CAP = 1000

_SENSITIVE_KEY_TOKENS = (
    "password",
    "passwd",
    "pwd",
    "authorization",
    "bearer",
    "token",
    "cookie",
    "sessionid",
    "sessiontoken",
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
    "credential",
    "privatekey",
    "certificate",
)
_PUBLIC_PRESENT_KEYS = {"passwordpresent", "keypresent", "serialpresent", "capresent"}
_EXACT_SENSITIVE_KEYS = {"ca", "cert", "certificate", "privatekey"}
_BEARER_RE = re.compile(r"\bBearer\s+[^,\s;}\]]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<key>password|passwd|pwd|authorization|bearer|token|cookie|session[_-]?id|"
    r"session[_-]?token|tfa|otp|secret|license[_-]?key|serial[_-]?number|fingerprint|"
    r"hardware[_-]?fingerprint|machine[_-]?id|host[_-]?id|hwid|credential|ca)"
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
        "ca_present": bool(str(getattr(config, "ca", ""))),
        "timeout": getattr(config, "timeout", None),
    }


def _normalized_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _sensitive_path(path: str) -> bool:
    normalized = _normalized_key(path)
    if normalized in _PUBLIC_PRESENT_KEYS:
        return False
    parts = [_normalized_key(part) for part in path.split(".")]
    if any(part in _EXACT_SENSITIVE_KEYS for part in parts):
        return True
    return any(token in normalized for token in _SENSITIVE_KEY_TOKENS)


def redact_text(value: Any, limit: int = 240) -> str:
    text = str(value)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", text)
    return text[:limit]


def redact_site_graph(value: Any, path: str = "") -> Any:
    if isinstance(value, bytes):
        return {"redacted": "raw-bytes", "byte_count": len(value)}
    if isinstance(value, bytearray):
        return {"redacted": "raw-bytes", "byte_count": len(value)}
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if _sensitive_path(child_path) and not isinstance(item, (dict, list, tuple, bytes, bytearray)):
                out[key] = "<redacted>" if item else item
            else:
                out[key] = redact_site_graph(item, child_path)
        return out
    if isinstance(value, list):
        return [redact_site_graph(item, path) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_site_graph(item, path) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def _body(response: Any) -> dict[str, Any]:
    if isinstance(response, dict) and isinstance(response.get("body"), dict):
        return response["body"]
    if isinstance(response, dict):
        return response
    return {}


def _items(response: Any, *keys: str) -> list[dict[str, Any]]:
    data = _body(response)
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _stable_id(data: dict[str, Any], *keys: str) -> str:
    value = _first_present(data, *keys, "access_point", "accessPoint", "uid", "id", "name")
    return str(value or "")


def _display_name(data: dict[str, Any]) -> str:
    return str(_first_present(data, "display_name", "displayName", "name", "label") or "")


def _flatten_dicts(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        for item in value.values():
            out.extend(_flatten_dicts(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_dicts(item))
    return out


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_strings(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_strings(item))
    return out


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _host_from_access_point(access_point: str) -> str:
    parts = access_point.split("/")
    if len(parts) >= 2 and parts[0] == "hosts":
        return parts[1]
    return ""


def _summarize_object(item: dict[str, Any], kind: str) -> dict[str, Any]:
    redacted = redact_site_graph(item)
    out = {
        "id": _stable_id(redacted),
        "kind": kind,
        "access_point": _first_present(redacted, "access_point", "accessPoint"),
        "uid": _first_present(redacted, "uid", "id"),
        "display_name": _display_name(redacted),
        "type": redacted.get("type"),
        "enabled": redacted.get("enabled"),
        "source_access_point": _first_present(redacted, "source_access_point", "sourceAccessPoint"),
        "archive_access_point": _first_present(redacted, "archive_access_point", "archiveAccessPoint"),
        "camera_access_point": _first_present(redacted, "camera_access_point", "cameraAccessPoint"),
        "event_supplier": _first_present(redacted, "event_supplier", "eventSupplier"),
        "metadata_endpoint": _first_present(redacted, "metadata_endpoint", "metadataEndpoint"),
    }
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def _normalize_layout(raw: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_site_graph(raw)
    meta = redacted.get("meta") if isinstance(redacted.get("meta"), dict) else {}
    body = redacted.get("body") if isinstance(redacted.get("body"), dict) else {}
    layout_id = str(meta.get("layout_id") or body.get("id") or meta.get("id") or "")
    cells = body.get("cells") if isinstance(body.get("cells"), dict) else {}
    references = _dedupe_strings([value for value in _flatten_strings(cells) if value.startswith("hosts/")])
    return {
        "layout_id": layout_id,
        "id": layout_id,
        "display_name": body.get("display_name") or meta.get("name") or "",
        "etag": meta.get("etag", ""),
        "map_id": body.get("map_id", ""),
        "references": references,
    }


def _normalize_map(raw: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_site_graph(raw)
    meta = redacted.get("meta") if isinstance(redacted.get("meta"), dict) else {}
    map_id = str(meta.get("id") or redacted.get("map_id") or redacted.get("id") or "")
    return {
        "map_id": map_id,
        "id": map_id,
        "name": meta.get("name") or redacted.get("name") or "",
        "type": meta.get("type") or redacted.get("type") or "",
        "etag": meta.get("etag") or redacted.get("etag") or "",
        "image_etag": meta.get("image_etag") or "",
    }


def _normalize_marker(raw: dict[str, Any], map_id: str) -> dict[str, Any]:
    redacted = redact_site_graph(raw)
    access_point = str(redacted.get("access_point") or redacted.get("ap") or redacted.get("component_name") or "")
    marker_id = str(redacted.get("id") or redacted.get("marker_id") or access_point)
    return {
        "marker_id": marker_id,
        "id": marker_id,
        "map_id": map_id,
        "access_point": access_point,
        "position": redacted.get("position") or {},
        "marker_type": redacted.get("marker_type") or redacted.get("type") or "",
    }


class _GraphBuilder:
    def __init__(self, client: Any, limit: int) -> None:
        self.client = client
        self.limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        self.collections: dict[str, Any] = {}
        self.nodes_by_id: dict[str, dict[str, Any]] = {}
        self.edges_seen: set[tuple[str, str, str]] = set()
        self.edges: list[dict[str, str]] = []
        self.gaps: list[dict[str, Any]] = []
        self.source_sections: dict[str, dict[str, Any]] = {}

    def build(
        self,
        include_layouts: bool,
        include_maps: bool,
        include_permissions: bool,
        include_health: bool,
    ) -> dict[str, Any]:
        inventory = self._collect("inventory", self.client.load_inventory if hasattr(self.client, "load_inventory") else None) or {}
        self._build_inventory(inventory if isinstance(inventory, dict) else {})
        if include_layouts:
            self._build_layouts()
        else:
            self.source_sections["layouts"] = {"status": "skipped"}
            self.collections["layouts"] = []
        if include_maps:
            self._build_maps()
        else:
            self.source_sections["maps"] = {"status": "skipped"}
            self.collections["maps"] = []
            self.collections["markers"] = []
        if include_permissions:
            self._build_permissions()
        else:
            self.source_sections["permissions"] = {"status": "skipped"}
            self.collections["permissions"] = {"roles": [], "users": [], "role_permissions": []}
        if include_health:
            self._build_health()
        else:
            self.source_sections["health"] = {"status": "skipped"}
            self.collections["health"] = {}

        status = "warn" if self.gaps else "ok"
        summary = self._summary()
        return redact_site_graph(
            {
                "status": status,
                "tool": "build_site_graph",
                "summary": summary,
                "collections": self.collections,
                "nodes": list(self.nodes_by_id.values())[: self.limit],
                "edges": self.edges[: self.limit],
                "gaps": self.gaps,
                "source_sections": self.source_sections,
            }
        )

    def _collect(self, section: str, func: Callable[[], Any] | None) -> Any:
        if func is None:
            self._gap(section, "method unavailable")
            return None
        try:
            value = redact_site_graph(func())
        except Exception as exc:  # noqa: BLE001 - optional live sections must degrade to gaps.
            self._gap(section, redact_text(exc), exc.__class__.__name__)
            return None
        self.source_sections[section] = {"status": "ok"}
        return value

    def _gap(self, section: str, message: str, error_type: str = "") -> None:
        item = {
            "section": section,
            "status": "fixture-needed",
            "message": redact_text(message),
        }
        if error_type:
            item["error_type"] = error_type
        self.source_sections[section] = {key: item[key] for key in item if key != "section"}
        self.gaps.append(item)

    def _add_node(self, node_id: str, kind: str, label: str = "", data: dict[str, Any] | None = None) -> None:
        if not node_id or node_id in self.nodes_by_id:
            return
        node = {"id": node_id, "kind": kind}
        if label:
            node["label"] = label
        if data:
            node["data"] = data
        self.nodes_by_id[node_id] = redact_site_graph(node)

    def _add_edge(self, source: str, target: str, edge_type: str) -> None:
        if not source or not target:
            return
        key = (source, target, edge_type)
        if key in self.edges_seen:
            return
        self.edges_seen.add(key)
        self.edges.append({"source": source, "target": target, "type": edge_type})

    def _build_inventory(self, inventory: dict[str, Any]) -> None:
        cameras = [_summarize_object(item, "camera") for item in inventory.get("cameras", []) if isinstance(item, dict)]
        archives = [_summarize_object(item, "archive") for item in inventory.get("archives", []) if isinstance(item, dict)]
        dicts = _flatten_dicts(inventory.get("host_unit", {})) + _flatten_dicts(inventory.get("components", []))
        detectors = self._detectors(dicts, "AVDetector", "detector")
        appdata = self._detectors(dicts, "AppDataDetector", "appdata_detector")

        strings = _flatten_strings(inventory)
        access_points = _dedupe_strings(
            [value for value in strings if value.startswith("hosts/")]
            + [str(item.get("access_point")) for item in cameras + archives if item.get("access_point")]
        )
        event_suppliers = _dedupe_strings([value for value in strings if "EventSupplier" in value])
        metadata_endpoints = _dedupe_strings(
            [value for value in strings if re.search(r"SourceEndpoint\.(vmda|metadata)", value)]
        )

        self.collections["cameras"] = cameras[: self.limit]
        self.collections["archives"] = archives[: self.limit]
        self.collections["detectors"] = detectors[: self.limit]
        self.collections["appdata_detectors"] = appdata[: self.limit]
        self.collections["access_points"] = access_points[: self.limit]
        self.collections["event_suppliers"] = event_suppliers[: self.limit]
        self.collections["metadata_endpoints"] = metadata_endpoints[: self.limit]
        self.collections["raw_payloads"] = self._raw_payload_summaries(inventory)

        for node in inventory.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_name") or node.get("name") or node.get("display_name") or "")
            self._add_node(node_id, "host", _display_name(node) or node_id, redact_site_graph(node))

        for item in cameras:
            camera_id = str(item.get("access_point") or item.get("id") or "")
            self._add_node(camera_id, "camera", str(item.get("display_name", "")), item)
            self._host_edge(camera_id)
            self._add_edge(camera_id, str(item.get("source_access_point", "")), "camera_uses_source")
            self._add_edge(camera_id, str(item.get("archive_access_point", "")), "camera_records_to_archive")
        for item in archives:
            archive_id = str(item.get("access_point") or item.get("id") or "")
            self._add_node(archive_id, "archive", str(item.get("display_name", "")), item)
            self._host_edge(archive_id)
        for item in detectors + appdata:
            detector_id = str(item.get("uid") or item.get("access_point") or item.get("id") or "")
            kind = str(item.get("kind") or "detector")
            self._add_node(detector_id, kind, str(item.get("display_name", "")), item)
            self._host_edge(detector_id)
            camera_ap = str(item.get("camera_access_point") or "")
            self._add_edge(camera_ap, detector_id, "camera_has_detector")
            self._add_edge(detector_id, str(item.get("event_supplier") or ""), "detector_emits_event")
            self._add_edge(detector_id, str(item.get("metadata_endpoint") or ""), "detector_has_metadata")
        for access_point in access_points:
            self._add_node(access_point, "access_point", access_point.rsplit("/", 1)[-1])
            self._host_edge(access_point)
        for access_point in event_suppliers:
            self._add_node(access_point, "event_supplier", access_point.rsplit("/", 1)[-1])
        for access_point in metadata_endpoints:
            self._add_node(access_point, "metadata_endpoint", access_point.rsplit("/", 1)[-1])

    def _detectors(self, items: list[dict[str, Any]], detector_type: str, kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            identity = _stable_id(item)
            haystack = f"{identity} {item.get('type', '')} {_display_name(item)}"
            item_type = str(item.get("type") or "")
            if item_type != detector_type and f"/{detector_type}." not in identity:
                continue
            if "SourceEndpoint." in identity or "EventSupplier" in identity:
                continue
            summary = _summarize_object(item, kind)
            summary["kind"] = kind
            summary_id = str(summary.get("uid") or summary.get("access_point") or summary.get("id") or "")
            if not summary_id or summary_id in seen:
                continue
            seen.add(summary_id)
            out.append(summary)
        return out

    def _raw_payload_summaries(self, inventory: dict[str, Any]) -> dict[str, Any]:
        payloads = {}
        for key, value in inventory.items():
            if isinstance(value, (bytes, bytearray)):
                payloads[key] = redact_site_graph(value, key)
            elif isinstance(value, dict) and value.get("redacted") == "raw-bytes" and "byte_count" in value:
                payloads[key] = value
        return payloads

    def _host_edge(self, access_point: str) -> None:
        host = _host_from_access_point(access_point)
        if host:
            self._add_node(host, "host", host)
            self._add_edge(host, access_point, "host_contains")

    def _build_layouts(self) -> None:
        func = (lambda: self.client.list_layouts(view="VIEW_MODE_ONLY_META")) if hasattr(self.client, "list_layouts") else None
        response = self._collect("layouts", func)
        layouts = [_normalize_layout(item) for item in _items(response, "items")]
        self.collections["layouts"] = layouts[: self.limit]
        for layout in layouts:
            layout_id = str(layout.get("layout_id") or "")
            self._add_node(layout_id, "layout", str(layout.get("display_name", "")), layout)
            self._add_edge(layout_id, str(layout.get("map_id") or ""), "layout_uses_map")
            for ref in layout.get("references", []):
                self._add_edge(layout_id, ref, "layout_references")

    def _build_maps(self) -> None:
        func = (lambda: self.client.list_maps()) if hasattr(self.client, "list_maps") else None
        response = self._collect("maps", func)
        maps = [_normalize_map(item) for item in _items(response, "items")]
        self.collections["maps"] = maps[: self.limit]
        markers: list[dict[str, Any]] = []
        marker_seen: set[str] = set()
        for site_map in maps:
            map_id = str(site_map.get("map_id") or "")
            self._add_node(map_id, "map", str(site_map.get("name", "")), site_map)
            marker_func = (lambda map_id=map_id: self.client.get_markers(map_id)) if hasattr(self.client, "get_markers") else None
            marker_response = self._collect(f"markers:{map_id}", marker_func)
            for marker in self._markers_from_response(marker_response, map_id):
                marker_id = str(marker.get("marker_id") or "")
                if marker_id in marker_seen:
                    continue
                marker_seen.add(marker_id)
                markers.append(marker)
                self._add_node(marker_id, "marker", marker_id, marker)
                self._add_edge(map_id, marker_id, "map_contains_marker")
                self._add_edge(marker_id, str(marker.get("access_point") or ""), "marker_points_to")
        self.collections["markers"] = markers[: self.limit]

    def _markers_from_response(self, response: Any, map_id: str) -> list[dict[str, Any]]:
        body = _body(response)
        raw = body.get("markers", []) if isinstance(body, dict) else []
        if isinstance(raw, dict):
            values = []
            for access_point, marker in raw.items():
                values.append({"id": access_point, "access_point": access_point, **(marker if isinstance(marker, dict) else {})})
        else:
            values = [item for item in raw if isinstance(item, dict)]
        return [_normalize_marker(marker, map_id) for marker in values]

    def _build_permissions(self) -> None:
        inventory = self._security_inventory()
        roles = list((inventory.get("roles") or {}).get("items") or [])
        users = list((inventory.get("users") or {}).get("items") or [])
        role_permissions: list[dict[str, Any]] = []
        for role in roles[: self.limit]:
            role_id = str(role.get("role_id") or role.get("id") or "")
            self._add_node(role_id, "role", str(role.get("name", "")), role)
            if hasattr(self.client, "role_permissions"):
                permission = self._collect(f"role_permissions:{role_id}", lambda role_id=role_id: self.client.role_permissions(role_id))
                if isinstance(permission, dict):
                    role_permissions.append(permission)
                    for item in ((permission.get("objects") or {}).get("items") or []):
                        self._add_edge(role_id, str(item.get("id") or item.get("access_point") or ""), "role_grants_object")
        for user in users[: self.limit]:
            user_id = str(user.get("user_id") or user.get("id") or "")
            self._add_node(user_id, "user", str(user.get("login") or user.get("name") or ""), user)
            for role_id in user.get("role_ids", []):
                self._add_edge(user_id, str(role_id), "user_has_role")
        self.collections["permissions"] = {
            "roles": redact_site_graph(roles[: self.limit]),
            "users": redact_site_graph(users[: self.limit]),
            "role_permissions": redact_site_graph(role_permissions[: self.limit]),
        }

    def _security_inventory(self) -> dict[str, Any]:
        if hasattr(self.client, "security_inventory"):
            data = self._collect("permissions", self.client.security_inventory)
            return data if isinstance(data, dict) else {}
        if not hasattr(self.client, "security_list_roles"):
            self._gap("permissions", "method unavailable")
            return {}
        roles_response = self._collect("permissions", lambda: self.client.security_list_roles(page_size=100))
        users_response = self._collect("users", lambda: self.client.security_list_users(page_size=100)) if hasattr(self.client, "security_list_users") else {}
        return {
            "status": "ok",
            "roles": {"items": _items(roles_response, "roles"), "count": len(_items(roles_response, "roles"))},
            "users": {"items": _items(users_response, "users"), "count": len(_items(users_response, "users"))},
        }

    def _build_health(self) -> None:
        health = self._collect("health", self.client.system_health if hasattr(self.client, "system_health") else self._health_fallback)
        health = health if isinstance(health, dict) else {}
        self.collections["health"] = health
        self._add_node("site_health", "health", "Site health", {})
        for key, value in health.items():
            if key in ("status", "tool"):
                continue
            node_id = f"health:{key}"
            self._add_node(node_id, "health_section", key, value if isinstance(value, dict) else {"value": value})
            self._add_edge("site_health", node_id, "health_reports")

    def _health_fallback(self) -> dict[str, Any]:
        health: dict[str, Any] = {"status": "ok", "tool": "system_health"}
        if hasattr(self.client, "license_get_domain_key_info"):
            health["license"] = _body(self.client.license_get_domain_key_info())
        if hasattr(self.client, "time_get_time_zone"):
            health["time"] = _body(self.client.time_get_time_zone())
        if len(health) <= 2:
            raise RuntimeError("method unavailable")
        return health

    def _summary(self) -> dict[str, Any]:
        permissions = self.collections.get("permissions") if isinstance(self.collections.get("permissions"), dict) else {}
        health = self.collections.get("health") if isinstance(self.collections.get("health"), dict) else {}
        health_sections = [key for key in health if key not in ("status", "tool")]
        return {
            "cameras": len(self.collections.get("cameras", [])),
            "archives": len(self.collections.get("archives", [])),
            "detectors": len(self.collections.get("detectors", [])),
            "appdata_detectors": len(self.collections.get("appdata_detectors", [])),
            "layouts": len(self.collections.get("layouts", [])),
            "maps": len(self.collections.get("maps", [])),
            "markers": len(self.collections.get("markers", [])),
            "access_points": len(self.collections.get("access_points", [])),
            "event_suppliers": len(self.collections.get("event_suppliers", [])),
            "metadata_endpoints": len(self.collections.get("metadata_endpoints", [])),
            "permissions_roles": len(permissions.get("roles", [])),
            "permissions_users": len(permissions.get("users", [])),
            "health_sections": len(health_sections),
            "gaps": len(self.gaps),
            "node_count": len(self.nodes_by_id),
            "edge_count": len(self.edges),
            "applied_limit": self.limit,
        }


def build_site_graph(
    client: Any,
    include_layouts: bool = True,
    include_maps: bool = True,
    include_permissions: bool = True,
    include_health: bool = True,
    limit: int = 500,
) -> dict[str, Any]:
    return _GraphBuilder(client, limit).build(include_layouts, include_maps, include_permissions, include_health)


@dataclass
class AxxonMcpSiteGraph:
    """Read-only unified graph over inventory, views, permissions, health, and event sources."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def site_graph_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
            "mode": "read-only",
        }

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.site_graph_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.site_graph_connect_axxon_profile("env")
        return self.client

    def build_site_graph(
        self,
        include_layouts: bool = True,
        include_maps: bool = True,
        include_permissions: bool = True,
        include_health: bool = True,
        limit: int = 500,
    ) -> dict[str, Any]:
        return build_site_graph(
            self.ensure_client(),
            include_layouts=include_layouts,
            include_maps=include_maps,
            include_permissions=include_permissions,
            include_health=include_health,
            limit=limit,
        )
