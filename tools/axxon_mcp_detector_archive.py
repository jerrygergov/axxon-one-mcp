#!/usr/bin/env python3
"""Read-only detector and archive policy tools for the Axxon One MCP server.

Task 2 scaffolds connection and redaction only. Catalog, schema, detector
config, metadata, and archive policy behavior are added in later Phase 5E tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


DETECTOR_LIST_LIMIT_CAP = 200
METADATA_SAMPLE_TIMEOUT_DEFAULT = 5.0
METADATA_SAMPLE_TIMEOUT_CAP = 30.0
METADATA_SAMPLE_LIMIT_DEFAULT = 20
METADATA_SAMPLE_LIMIT_CAP = 200
SENSITIVE_PROPERTY_TOKENS = ("password", "token", "secret", "certificate", "private_key", "serial", "license")
DETECTOR_UNIT_TYPES = ("AVDetector", "AppDataDetector")
KNOWN_DETECTOR_KINDS = {
    "AVDetector": ("MotionDetection", "SceneDescription", "NeuroTracker"),
    "AppDataDetector": ("MoveInZone", "OneLineCrossing", "LongInZone", "LostObject", "AbandonedObject"),
}
DETECTOR_SOURCE_TYPES = {
    "AVDetector": "Video",
    "AppDataDetector": "TargetList",
}
DETECTOR_REQUIRED_FIXTURES = {
    "AVDetector": ("video_source_ap",),
    "AppDataDetector": ("video_source_ap", "vmda_source_ap"),
}
DETECTOR_PROVENANCE_ORDER = ("known-catalog", "live-unit", "factory", "template")
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
    "value_bytes",
    "string_list_value",
)
VISUAL_SHAPE_VALUE_FIELDS = ("value_simple_polygon", "value_rectangle", "value_polyline")
SCHEMA_VALUE_FIELDS = PROPERTY_VALUE_FIELDS + VISUAL_SHAPE_VALUE_FIELDS


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


def _sensitive_key(name: Any) -> bool:
    simplified = "".join(ch for ch in str(name).lower() if ch.isalnum())
    return any(token.replace("_", "") in simplified for token in SENSITIVE_PROPERTY_TOKENS)


def _sensitive_property_node(value: dict[Any, Any]) -> bool:
    return any(_sensitive_key(value.get(field, "")) for field in PROPERTY_ID_FIELDS)


def _property_value_field(name: Any) -> bool:
    return str(name) in PROPERTY_VALUE_FIELDS


def redact_sensitive_properties(value: Any) -> Any:
    if isinstance(value, dict):
        sensitive_node = _sensitive_property_node(value)
        return {
            key: "<redacted>"
            if _sensitive_key(key) or (sensitive_node and _property_value_field(key))
            else redact_sensitive_properties(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_properties(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_properties(item) for item in value)
    return value


def _as_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    if isinstance(value.get("body"), dict):
        nested = _as_items(value["body"])
        if nested:
            return nested
    for key in ("units", "items", "templates", "factories"):
        if isinstance(value.get(key), list):
            return [item for item in value[key] if isinstance(item, dict)]
    return [value]


def _property_identity(value: dict[str, Any]) -> str:
    for field in PROPERTY_ID_FIELDS:
        if value.get(field):
            return str(value[field]).split(".")[-1].split("/")[-1].lower()
    return ""


def _iter_dict_nodes(value: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(value, dict):
        nodes.append(value)
        for item in value.values():
            nodes.extend(_iter_dict_nodes(item))
    elif isinstance(value, list):
        for item in value:
            nodes.extend(_iter_dict_nodes(item))
    return nodes


def _enum_item_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for field in ("value_string", "value", "name", "id"):
        item = value.get(field)
        if isinstance(item, str) and item:
            return item
    return ""


def _detector_kinds_from_descriptor(descriptor: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    for node in _iter_dict_nodes(descriptor):
        if _property_identity(node) != "detector":
            continue
        enum_items = node.get("enum_constraint", {}).get("items", [])
        if isinstance(enum_items, list):
            for item in enum_items:
                detector_kind = _enum_item_value(item)
                if detector_kind:
                    kinds.add(detector_kind)
        for field in PROPERTY_VALUE_FIELDS:
            value = node.get(field)
            if isinstance(value, str) and value:
                kinds.add(value)
    return kinds


def _descriptor_value_kind(descriptor: dict[str, Any]) -> str:
    value_kind = descriptor.get("value_kind")
    if isinstance(value_kind, str) and value_kind:
        return value_kind
    for field in SCHEMA_VALUE_FIELDS:
        if field in descriptor:
            return field
    return ""


def _property_id(value: dict[str, Any]) -> str:
    for field in PROPERTY_ID_FIELDS:
        item = value.get(field)
        if isinstance(item, str) and item:
            return item.split(".")[-1].split("/")[-1]
    return ""


def _enum_choices(descriptor: dict[str, Any]) -> list[dict[str, Any]]:
    items = descriptor.get("enum_constraint", {}).get("items", [])
    if not isinstance(items, list):
        return []
    choices: list[dict[str, Any]] = []
    for item in items:
        value = _enum_item_value(item)
        if not value:
            continue
        choice: dict[str, Any] = {"value": value}
        if isinstance(item, dict):
            for field in ("id", "name", "display_name", "displayName"):
                if item.get(field):
                    choice[field] = item[field]
        choices.append(choice)
    return choices


def _schema_property_descriptor(descriptor: dict[str, Any], path: str) -> dict[str, Any]:
    redacted = redact_sensitive_properties(descriptor)
    out: dict[str, Any] = {
        "id": _property_id(redacted),
        "path": path,
        "value_kind": _descriptor_value_kind(redacted),
        "readonly": bool(redacted.get("readonly", False)),
        "internal": bool(redacted.get("internal", False)),
    }
    for field in ("name", "type", "category", "required"):
        if field in redacted:
            out[field] = redacted[field]
    choices = _enum_choices(redacted)
    if choices:
        out["enum"] = [choice["value"] for choice in choices]
        out["enum_choices"] = choices
    if isinstance(redacted.get("range_constraint"), dict):
        out["range"] = dict(redacted["range_constraint"])
    return out


def _flatten_property_schema(properties: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    flattened: dict[str, dict[str, Any]] = {}
    if not isinstance(properties, list):
        return flattened
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        prop_id = _property_id(prop)
        if not prop_id:
            continue
        path = f"{prefix}.{prop_id}" if prefix else prop_id
        flattened[path] = _schema_property_descriptor(prop, path)
        flattened.update(_flatten_property_schema(prop.get("properties"), path))
    return flattened


def _is_visual_element(value: dict[str, Any]) -> bool:
    for field in ("type", "name", "unit_type", "unitType"):
        item = value.get(field)
        if isinstance(item, str) and "visualelement" in "".join(ch for ch in item.lower() if ch.isalnum()):
            return True
    return False


def _iter_visual_elements(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _is_visual_element(value):
            found.append(value)
        for item in value.values():
            found.extend(_iter_visual_elements(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_iter_visual_elements(item))
    return found


def _visual_element_summaries(descriptor: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for visual in _iter_visual_elements(descriptor):
        shape_properties = [
            item
            for item in _flatten_property_schema(visual.get("properties")).values()
            if item.get("value_kind") in VISUAL_SHAPE_VALUE_FIELDS
        ]
        if not shape_properties:
            continue
        shape_fields = sorted({str(item["value_kind"]) for item in shape_properties if item.get("value_kind")})
        summaries.append(
            {
                "uid": visual.get("uid", ""),
                "type": visual.get("type", ""),
                "name": visual.get("name", ""),
                "shape_fields": shape_fields,
                "properties": shape_properties,
            }
        )
    return summaries


def _source_type(unit_type: str, descriptor: dict[str, Any] | None = None) -> str:
    descriptor = descriptor or {}
    for field in ("source_type", "sourceType"):
        value = descriptor.get(field)
        if isinstance(value, str) and value:
            return value
    return DETECTOR_SOURCE_TYPES.get(unit_type, "")


def _catalog_fixtures(unit_type: str) -> dict[str, list[str]]:
    required = list(DETECTOR_REQUIRED_FIXTURES.get(unit_type, ()))
    return {"required": required, "missing": list(required)}


def _sort_provenance(values: set[str]) -> list[str]:
    ordered = [item for item in DETECTOR_PROVENANCE_ORDER if item in values]
    ordered.extend(sorted(values.difference(ordered)))
    return ordered


def _call_source(method: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return method(*args, **kwargs)
    except TypeError:
        if kwargs:
            try:
                return method(*args)
            except TypeError:
                return method()
        return method()


def _live_unit_uid_from_access_point(access_point: str, unit_type: str) -> str:
    if f"/{unit_type}." not in access_point:
        return ""
    return access_point.split("/EventSupplier")[0].split("/SourceEndpoint")[0]


def _authenticate_grpc_once(client: Any) -> None:
    if getattr(client, "_detector_archive_grpc_authenticated", False):
        return
    client.authenticate_grpc()
    setattr(client, "_detector_archive_grpc_authenticated", True)


def _client_real_units_by_type(client: Any) -> dict[str, list[dict[str, Any]]]:
    cached = getattr(client, "_detector_archive_live_units_cache", None)
    if isinstance(cached, dict):
        return cached

    empty: dict[str, list[dict[str, Any]]] = {unit_type: [] for unit_type in DETECTOR_UNIT_TYPES}
    try:
        getattr(client, "authenticate_grpc")
        import_module = getattr(client, "import_module")
        common_stubs = getattr(client, "common_stubs")
        message_to_dict = getattr(client, "message_to_dict")
    except AttributeError:
        return empty

    try:
        _authenticate_grpc_once(client)
        pb_domain = import_module("axxonsoft.bl.domain.Domain_pb2")
        pb_config = import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        stubs = common_stubs()
        domain = stubs["domain"]
        config_stub = stubs["config"]

        candidates: dict[str, list[str]] = {unit_type: [] for unit_type in DETECTOR_UNIT_TYPES}
        request = pb_domain.ListComponentsRequest(page_size=500)
        for page in domain.ListComponents(request, timeout=getattr(client.config, "timeout", None)):
            for component in message_to_dict(page).get("items", []):
                access_point = component.get("access_point", "")
                for unit_type in DETECTOR_UNIT_TYPES:
                    if len(candidates[unit_type]) >= 50:
                        continue
                    uid = _live_unit_uid_from_access_point(access_point, unit_type)
                    if uid and uid not in candidates[unit_type]:
                        candidates[unit_type].append(uid)

        units_by_type = {unit_type: [] for unit_type in DETECTOR_UNIT_TYPES}
        for unit_type, unit_uids in candidates.items():
            for uid in unit_uids[:10]:
                request = pb_config.ListUnitsRequest(unit_uids=[uid])
                response = config_stub.ListUnits(request, timeout=getattr(client.config, "timeout", None))
                for unit in message_to_dict(response).get("units", []):
                    if isinstance(unit, dict):
                        units_by_type[unit_type].append(unit)
        setattr(client, "_detector_archive_live_units_cache", units_by_type)
        return units_by_type
    except (AttributeError, KeyError, TypeError):
        return empty


def _client_units(client: Any, unit_type: str) -> list[dict[str, Any]]:
    method = getattr(client, "list_units", None)
    if callable(method):
        return _as_items(_call_source(method, unit_type=unit_type))
    return _client_real_units_by_type(client).get(unit_type, [])


def _client_templates(client: Any) -> list[dict[str, Any]]:
    for name in ("detector_archive_templates", "list_templates", "device_templates"):
        source = getattr(client, name, None)
        if callable(source):
            return _as_items(_call_source(source))
        if source is not None:
            return _as_items(source)
    return _client_real_templates(client)


def _client_real_templates(client: Any) -> list[dict[str, Any]]:
    try:
        getattr(client, "authenticate_grpc")
        import_module = getattr(client, "import_module")
        common_stubs = getattr(client, "common_stubs")
        message_to_dict = getattr(client, "message_to_dict")
    except AttributeError:
        return []

    try:
        _authenticate_grpc_once(client)
        pb_config = import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        config_stub = common_stubs()["config"]
        view = getattr(pb_config, "VIEW_MODE_FULL", "VIEW_MODE_FULL")
        request = pb_config.ListTemplatesRequest(view=view)
        response = config_stub.ListTemplates(request, timeout=getattr(client.config, "timeout", None))
        templates = []
        for item in message_to_dict(response).get("items", []):
            if not isinstance(item, dict):
                continue
            unit = item.get("body", {}).get("unit")
            if isinstance(unit, dict):
                templates.append(unit)
            else:
                templates.append(item)
        return templates
    except (AttributeError, KeyError, TypeError):
        return []


def _client_factories(client: Any) -> list[dict[str, Any]]:
    method = getattr(client, "batch_get_factories", None)
    if not callable(method):
        return []
    parent_uid = _factory_parent_uid(client)
    request = [
        {"unit_type": unit_type, "parent_uid": parent_uid, "ignore_possible_limits": True}
        for unit_type in DETECTOR_UNIT_TYPES
    ]
    return _as_items(method(request))


def _factory_parent_uid(client: Any) -> str:
    inventory = getattr(client, "inventory", None)
    if isinstance(inventory, dict):
        for field in ("host_uid", "uid"):
            value = inventory.get(field)
            if isinstance(value, str) and value.startswith("hosts/"):
                return value
        hosts = inventory.get("hosts")
        if isinstance(hosts, list):
            for host in hosts:
                if isinstance(host, dict):
                    value = host.get("uid")
                    if isinstance(value, str) and value.startswith("hosts/"):
                        return value
    tls_cn = getattr(getattr(client, "config", None), "tls_cn", "")
    return f"hosts/{tls_cn}" if tls_cn else ""


def _fixture_needed_schema(unit_type: str, detector_kind: str, message: str) -> dict[str, Any]:
    return {
        "status": "fixture-needed",
        "tool": "detector_parameter_schema",
        "unit_type": unit_type,
        "detector_kind": detector_kind,
        "message": message,
        "fixtures": _catalog_fixtures(unit_type),
    }


def _schema_source_candidates(client: Any, unit_type: str) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for unit in _client_units(client, unit_type):
        actual_unit_type = unit.get("type") or unit_type
        if actual_unit_type == unit_type:
            candidates.append(("live-unit", unit))
    for template in _client_templates(client):
        actual_unit_type = template.get("type") or template.get("unit_type") or template.get("unitType")
        if actual_unit_type == unit_type:
            candidates.append(("template", template))
    for factory_item in _client_factories(client):
        factory = factory_item.get("factory") if isinstance(factory_item.get("factory"), dict) else factory_item
        actual_unit_type = factory.get("type") or factory.get("unit_type") or factory.get("unitType")
        if actual_unit_type == unit_type:
            candidates.append(("factory", factory))
    return candidates


@dataclass
class AxxonMcpDetectorArchive:
    """Read-only detector and archive policy tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def detector_archive_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
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
        return self.detector_archive_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.detector_archive_connect_axxon_profile("env")
        return self.client

    def detector_kind_catalog(self, include_live: bool = True) -> dict[str, Any]:
        catalog: dict[str, dict[str, dict[str, Any]]] = {unit_type: {} for unit_type in DETECTOR_UNIT_TYPES}

        def add_kind(unit_type: str, detector_kind: str, provenance: str, descriptor: dict[str, Any] | None = None) -> None:
            if unit_type not in catalog or not detector_kind:
                return
            existing = catalog[unit_type].setdefault(
                detector_kind,
                {
                    "unit_type": unit_type,
                    "detector_kind": detector_kind,
                    "source_type": _source_type(unit_type, descriptor),
                    "provenance": set(),
                    "fixtures": _catalog_fixtures(unit_type),
                },
            )
            if not existing.get("source_type"):
                existing["source_type"] = _source_type(unit_type, descriptor)
            existing["provenance"].add(provenance)

        for unit_type, detector_kinds in KNOWN_DETECTOR_KINDS.items():
            for detector_kind in detector_kinds:
                add_kind(unit_type, detector_kind, "known-catalog")

        if include_live:
            client = self.ensure_client()
            for unit_type in DETECTOR_UNIT_TYPES:
                for unit in _client_units(client, unit_type):
                    actual_unit_type = unit.get("type") or unit_type
                    if actual_unit_type != unit_type:
                        continue
                    for detector_kind in _detector_kinds_from_descriptor(unit):
                        add_kind(unit_type, detector_kind, "live-unit", unit)

            for template in _client_templates(client):
                unit_type = template.get("type") or template.get("unit_type") or template.get("unitType")
                if unit_type not in DETECTOR_UNIT_TYPES:
                    continue
                for detector_kind in _detector_kinds_from_descriptor(template):
                    add_kind(unit_type, detector_kind, "template", template)

            for factory_item in _client_factories(client):
                factory = factory_item.get("factory") if isinstance(factory_item.get("factory"), dict) else factory_item
                unit_type = factory.get("type") or factory.get("unit_type") or factory.get("unitType")
                if unit_type not in DETECTOR_UNIT_TYPES:
                    continue
                for detector_kind in _detector_kinds_from_descriptor(factory):
                    add_kind(unit_type, detector_kind, "factory", factory)

        by_unit_type: dict[str, list[dict[str, Any]]] = {}
        for unit_type, entries in catalog.items():
            by_unit_type[unit_type] = []
            for detector_kind in sorted(entries):
                entry = dict(entries[detector_kind])
                entry["provenance"] = _sort_provenance(entry["provenance"])
                by_unit_type[unit_type].append(entry)

        return {
            "status": "ok",
            "tool": "detector_kind_catalog",
            "include_live": bool(include_live),
            "by_unit_type": by_unit_type,
            "count": sum(len(items) for items in by_unit_type.values()),
        }

    def detector_parameter_schema(self, unit_type: str, detector_kind: str) -> dict[str, Any]:
        if unit_type not in DETECTOR_UNIT_TYPES:
            return _fixture_needed_schema(
                unit_type,
                detector_kind,
                f"Unknown detector unit type {unit_type!r}; provide a fixture for detector_parameter_schema.",
            )

        client = self.ensure_client()
        for provenance, descriptor in _schema_source_candidates(client, unit_type):
            if detector_kind not in _detector_kinds_from_descriptor(descriptor):
                continue
            return {
                "status": "ok",
                "tool": "detector_parameter_schema",
                "unit_type": unit_type,
                "detector_kind": detector_kind,
                "source_type": _source_type(unit_type, descriptor),
                "schema": {
                    "type": "object",
                    "properties": _flatten_property_schema(descriptor.get("properties")),
                },
                "visual_elements": _visual_element_summaries(descriptor),
                "provenance": [provenance],
                "fixtures": _catalog_fixtures(unit_type),
            }

        return _fixture_needed_schema(
            unit_type,
            detector_kind,
            f"Could not resolve detector kind {detector_kind!r} for {unit_type}; provide live/template/factory fixtures.",
        )
