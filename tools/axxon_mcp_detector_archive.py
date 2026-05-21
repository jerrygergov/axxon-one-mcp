#!/usr/bin/env python3
"""Read-only detector and archive policy tools for the Axxon One MCP server.

Task 2 scaffolds connection and redaction. Later Phase 5E tasks add catalog,
schema, detector config, metadata, and archive policy behavior incrementally.
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


def _nested_sensitive_identity_field(name: Any) -> bool:
    return str(name) in ("id", "property_id", "propertyId", "path")


def _redact_sensitive_properties(value: Any, sensitive_context: bool) -> Any:
    if isinstance(value, dict):
        sensitive_node = sensitive_context or _sensitive_property_node(value)
        return {
            key: "<redacted>"
            if _sensitive_key(key)
            or (sensitive_node and _property_value_field(key))
            or (sensitive_context and _nested_sensitive_identity_field(key))
            else _redact_sensitive_properties(item, sensitive_node)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive_properties(item, sensitive_context) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_properties(item, sensitive_context) for item in value)
    return value


def redact_sensitive_properties(value: Any) -> Any:
    return _redact_sensitive_properties(value, False)


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


def _selected_detector_kinds_from_descriptor(descriptor: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    for field in ("detector_kind", "detectorKind"):
        value = descriptor.get(field)
        if isinstance(value, str) and value:
            kinds.add(value)
    for node in _iter_dict_nodes(descriptor):
        if _property_identity(node) != "detector":
            continue
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
    sensitive_node = _sensitive_property_node(descriptor)
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
    choices = [] if sensitive_node else _enum_choices(redacted)
    if choices:
        out["enum"] = [choice["value"] for choice in choices]
        out["enum_choices"] = choices
    if not sensitive_node and isinstance(redacted.get("range_constraint"), dict):
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


def _visual_element_path(visual: dict[str, Any], parent_uid: str = "") -> str:
    path = visual.get("path")
    if isinstance(path, str) and path:
        return path
    uid = visual.get("uid")
    if isinstance(uid, str) and uid:
        prefix = f"{parent_uid}/" if parent_uid else ""
        return uid[len(prefix) :] if prefix and uid.startswith(prefix) else uid
    name = visual.get("name")
    return str(name) if name else ""


def _visual_element_summaries(descriptor: dict[str, Any], parent_uid: str = "") -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for visual in _iter_visual_elements(descriptor):
        shape_properties = [
            item
            for item in _flatten_property_schema(visual.get("properties")).values()
            if item.get("value_kind") in VISUAL_SHAPE_VALUE_FIELDS
            and not item.get("readonly", False)
            and not item.get("internal", False)
        ]
        if not shape_properties:
            continue
        shape_fields = sorted({str(item["value_kind"]) for item in shape_properties if item.get("value_kind")})
        summaries.append(
            {
                "uid": visual.get("uid", ""),
                "type": visual.get("type", ""),
                "name": visual.get("name", ""),
                "path": _visual_element_path(visual, parent_uid),
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


def _detector_unit_type_from_uid(detector_uid: str) -> str:
    for unit_type in DETECTOR_UNIT_TYPES:
        if f"/{unit_type}." in detector_uid or detector_uid.startswith(f"{unit_type}."):
            return unit_type
    return ""


def _detector_unit_type(descriptor: dict[str, Any], detector_uid: str = "") -> str:
    for field in ("type", "unit_type", "unitType"):
        value = descriptor.get(field)
        if isinstance(value, str) and value in DETECTOR_UNIT_TYPES:
            return value
    return _detector_unit_type_from_uid(detector_uid or str(descriptor.get("uid", "")))


def _unit_uid(descriptor: dict[str, Any]) -> str:
    for field in ("uid", "unit_uid", "unitUid"):
        value = descriptor.get(field)
        if isinstance(value, str) and value:
            return value
    return ""


def _candidate_unit_types_for_uid(detector_uid: str) -> list[str]:
    parsed = _detector_unit_type_from_uid(detector_uid)
    if not parsed:
        return list(DETECTOR_UNIT_TYPES)
    return [parsed] + [unit_type for unit_type in DETECTOR_UNIT_TYPES if unit_type != parsed]


def _client_real_unit_by_uid(client: Any, detector_uid: str) -> dict[str, Any] | None:
    try:
        getattr(client, "authenticate_grpc")
        import_module = getattr(client, "import_module")
        common_stubs = getattr(client, "common_stubs")
        message_to_dict = getattr(client, "message_to_dict")
    except AttributeError:
        return None

    try:
        _authenticate_grpc_once(client)
        pb_config = import_module("axxonsoft.bl.config.ConfigurationService_pb2")
        config_stub = common_stubs()["config"]
        request = pb_config.ListUnitsRequest(unit_uids=[detector_uid])
        response = config_stub.ListUnits(request, timeout=getattr(client.config, "timeout", None))
        for unit in message_to_dict(response).get("units", []):
            if not isinstance(unit, dict):
                continue
            unit_uid = _unit_uid(unit)
            if not unit_uid or unit_uid == detector_uid:
                return unit
        return None
    except (AttributeError, KeyError, TypeError):
        return None


def _client_unit_by_uid(client: Any, detector_uid: str) -> tuple[dict[str, Any] | None, str]:
    method = getattr(client, "list_units", None)
    if callable(method):
        for unit_type in _candidate_unit_types_for_uid(detector_uid):
            for unit in _as_items(_call_source(method, unit_type=unit_type)):
                if _unit_uid(unit) == detector_uid:
                    return unit, "list_units"

    unit = _client_real_unit_by_uid(client, detector_uid)
    if unit is not None:
        return unit, "configuration_service.ListUnits"
    return None, ""


def _selected_detector_kind(descriptor: dict[str, Any]) -> str:
    for field in ("detector_kind", "detectorKind"):
        value = descriptor.get(field)
        if isinstance(value, str) and value:
            return value
    for node in _iter_dict_nodes(descriptor):
        if _property_identity(node) != "detector":
            continue
        for field in PROPERTY_VALUE_FIELDS:
            value = node.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def _iter_property_nodes(properties: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(properties, list):
        return nodes
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        prop_id = _property_id(prop)
        if not prop_id:
            continue
        path = f"{prefix}.{prop_id}" if prefix else prop_id
        nodes.append((path, prop))
        nodes.extend(_iter_property_nodes(prop.get("properties"), path))
    return nodes


def _property_value_summary(redacted: dict[str, Any]) -> tuple[str, Any]:
    value_kind = _descriptor_value_kind(redacted)
    if value_kind in SCHEMA_VALUE_FIELDS and value_kind in redacted:
        return value_kind, redacted[value_kind]
    for field in SCHEMA_VALUE_FIELDS:
        if field in redacted:
            return field, redacted[field]
    return value_kind, None


def _writable_parameter_summaries(descriptor: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path, prop in _iter_property_nodes(descriptor.get("properties")):
        redacted = redact_sensitive_properties(prop)
        value_kind, value = _property_value_summary(redacted)
        if not value_kind or redacted.get("readonly", False) or redacted.get("internal", False):
            continue
        summary: dict[str, Any] = {
            "id": _property_id(redacted),
            "path": path,
            "value_kind": value_kind,
            "readonly": bool(redacted.get("readonly", False)),
            "internal": bool(redacted.get("internal", False)),
            "value": value,
        }
        for field in ("name", "type", "category"):
            if field in redacted:
                summary[field] = redacted[field]
        summaries.append(summary)
    return summaries


def _metadata_schema_field(
    name: str,
    field_type: str,
    *,
    repeated: bool = False,
    oneof: str | None = None,
    enum: list[str] | None = None,
) -> dict[str, Any]:
    field: dict[str, Any] = {"name": name, "type": field_type, "repeated": repeated}
    if oneof:
        field["oneof"] = oneof
    if enum:
        field["enum"] = enum
    return field


def _fallback_metadata_schemas() -> dict[str, dict[str, Any]]:
    object_state = [
        "OBJECT_STATE_UNSPECIFIED",
        "OBJECT_STATE_APPEARED",
        "OBJECT_STATE_NORMAL",
        "OBJECT_STATE_DISAPPEARED",
    ]
    object_type = [
        "OBJECT_TYPE_UNSPECIFIED",
        "OBJECT_TYPE_HUMAN",
        "OBJECT_TYPE_GROUP_OF_HUMANS",
        "OBJECT_TYPE_VEHICLE",
        "OBJECT_TYPE_FACE",
        "OBJECT_TYPE_ANIMAL",
        "OBJECT_TYPE_ROBOT_DOG",
        "OBJECT_TYPE_CHILD",
        "OBJECT_TYPE_CAT",
    ]
    return {
        "PullMetadataResponse": {
            "kind": "message",
            "fields": [
                _metadata_schema_field("sample", "MetadataSample", oneof="data"),
                _metadata_schema_field("heartbeat", "HeartBeat", oneof="data"),
                _metadata_schema_field("config_update", "StreamConfig", oneof="data"),
            ],
        },
        "MetadataSample": {
            "kind": "message",
            "fields": [
                _metadata_schema_field("timestamp", "string"),
                _metadata_schema_field("tracklets", "Tracklets", oneof="data"),
                _metadata_schema_field("global_tracklets", "GlobalTracklets", oneof="data"),
            ],
        },
        "Tracklets": {
            "kind": "message",
            "fields": [_metadata_schema_field("tracklets", "Tracklet", repeated=True)],
        },
        "Tracklet": {
            "kind": "message",
            "fields": [
                _metadata_schema_field("id", "int32"),
                _metadata_schema_field("state", "ObjectState", enum=object_state),
                _metadata_schema_field("rectangle", "Rectangle"),
                _metadata_schema_field("logical_center", "Point"),
                _metadata_schema_field("color", "HsvColor"),
                _metadata_schema_field("type", "ObjectType", enum=object_type),
                _metadata_schema_field(
                    "behavior",
                    "ObjectBehavior",
                    enum=[
                        "OBJECT_BEHAVIOR_UNSPECIFIED",
                        "MOVING_OBJECT",
                        "ABANDONED_OBJECT",
                        "ABANDONED_TAKEN_OBJECT",
                        "ABANDONED_GIVEN_OBJECT",
                    ],
                ),
                _metadata_schema_field("temperature", "Temperature"),
            ],
        },
        "GlobalTracklets": {
            "kind": "message",
            "fields": [_metadata_schema_field("tracklets", "GlobalTracklet", repeated=True)],
        },
        "GlobalTracklet": {
            "kind": "message",
            "fields": [
                _metadata_schema_field("guid", "string"),
                _metadata_schema_field("profile", "Profile"),
                _metadata_schema_field(
                    "state",
                    "GlobalTrackState",
                    enum=[
                        "GT_STATE_UNSPECIFIED",
                        "GT_STATE_APPEARED",
                        "GT_STATE_NORMAL",
                        "GT_STATE_RECOGNIZED",
                        "GT_STATE_DISAPPEARED",
                        "GT_STATE_TERMINATED",
                        "GT_STATE_UNKNOWN",
                    ],
                ),
                _metadata_schema_field("type", "ObjectType", enum=object_type),
                _metadata_schema_field("on_map_positions", "MapPoint", repeated=True),
                _metadata_schema_field("velocities", "MapPoint", repeated=True),
                _metadata_schema_field("on_camera_positions", "CameraFrameArea", repeated=True),
            ],
        },
        "StreamConfig": {
            "kind": "message",
            "fields": [_metadata_schema_field("max_channel_idle_ms", "int32")],
        },
    }


def _protobuf_scalar_type(field_type: Any) -> str:
    return {
        1: "double",
        2: "float",
        3: "int64",
        4: "uint64",
        5: "int32",
        6: "fixed64",
        7: "fixed32",
        8: "bool",
        9: "string",
        12: "bytes",
        13: "uint32",
        15: "sfixed32",
        16: "sfixed64",
        17: "sint32",
        18: "sint64",
    }.get(field_type, str(field_type))


def _descriptor_field_schema(field: Any) -> dict[str, Any]:
    message_type = getattr(field, "message_type", None)
    enum_type = getattr(field, "enum_type", None)
    field_type = getattr(message_type, "name", "") if message_type is not None else ""
    if not field_type and enum_type is not None:
        field_type = getattr(enum_type, "name", "")
    if not field_type:
        field_type = _protobuf_scalar_type(getattr(field, "type", ""))

    repeated_label = getattr(field, "LABEL_REPEATED", 3)
    item: dict[str, Any] = {
        "name": getattr(field, "name", ""),
        "type": field_type,
        "repeated": getattr(field, "label", None) == repeated_label,
    }
    oneof = getattr(field, "containing_oneof", None)
    if oneof is not None and getattr(oneof, "name", ""):
        item["oneof"] = oneof.name
    if enum_type is not None:
        item["enum"] = [value.name for value in getattr(enum_type, "values", [])]
    return item


def _metadata_schemas_from_descriptor(meta_pb2: Any) -> dict[str, dict[str, Any]]:
    names = (
        "PullMetadataResponse",
        "MetadataSample",
        "Tracklets",
        "GlobalTracklets",
        "Tracklet",
        "GlobalTracklet",
        "StreamConfig",
    )
    schemas: dict[str, dict[str, Any]] = {}
    for name in names:
        message = getattr(meta_pb2, name, None)
        descriptor = getattr(message, "DESCRIPTOR", None)
        if descriptor is None:
            continue
        schemas[name] = {
            "kind": "message",
            "fields": [_descriptor_field_schema(field) for field in getattr(descriptor, "fields", [])],
        }
    return schemas


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_strings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_flatten_strings(item))
    return out


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _metadata_endpoint_strings_from_source(value: Any) -> list[str]:
    if (
        isinstance(value, dict)
        and isinstance(value.get("items"), list)
        and all(isinstance(item, str) for item in value["items"])
    ):
        values = [str(item) for item in value["items"] if isinstance(item, str)]
    else:
        values = _flatten_strings(value)
    return _unique_strings(
        [
            item
            for item in values
            if "SourceEndpoint.vmda" in item or "SourceEndpoint.metadata" in item
        ]
    )


def _client_metadata_endpoint_examples(client: Any) -> list[dict[str, Any]]:
    candidates: list[tuple[str, Any]] = []
    for method_name in ("metadata_endpoints", "find_metadata_endpoints"):
        method = getattr(client, method_name, None)
        if callable(method):
            try:
                candidates.append((method_name, _call_source(method)))
            except (AttributeError, TypeError):
                pass
    load_inventory = getattr(client, "load_inventory", None)
    if callable(load_inventory):
        try:
            candidates.append(("load_inventory", load_inventory()))
        except (AttributeError, TypeError):
            pass

    examples: list[dict[str, Any]] = []
    for source, value in candidates:
        for endpoint in _metadata_endpoint_strings_from_source(value):
            examples.append({"source": source, "access_point": endpoint})
    return examples


def _metadata_evidence_examples() -> list[dict[str, Any]]:
    return [
        {
            "source": "evidence:demo-metadata-tracklets-2026-05-02",
            "access_point": "hosts/Server/AVDetector.1/SourceEndpoint.vmda",
            "sample_kind": "MetadataSample.tracklets",
            "observed": {
                "samples": 3,
                "config_updates": 1,
                "heartbeats": 0,
                "tracklet_counts": [21, 21, 21],
            },
        }
    ]


def _dedupe_endpoint_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in examples:
        endpoint = item.get("access_point")
        if not isinstance(endpoint, str) or not endpoint or endpoint in seen:
            continue
        seen.add(endpoint)
        out.append(item)
    return out


def _normalize_metadata_sample_bounds(timeout_s: Any, limit: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = {"timeout_s": timeout_s, "limit": limit}
    try:
        normalized_timeout = float(METADATA_SAMPLE_TIMEOUT_DEFAULT if timeout_s is None else timeout_s)
    except (TypeError, ValueError):
        normalized_timeout = METADATA_SAMPLE_TIMEOUT_DEFAULT
    try:
        normalized_limit = int(METADATA_SAMPLE_LIMIT_DEFAULT if limit is None else limit)
    except (TypeError, ValueError):
        normalized_limit = METADATA_SAMPLE_LIMIT_DEFAULT
    applied = {
        "timeout_s": max(1.0, min(normalized_timeout, METADATA_SAMPLE_TIMEOUT_CAP)),
        "limit": max(1, min(normalized_limit, METADATA_SAMPLE_LIMIT_CAP)),
    }
    return requested, applied


def _sanitize_metadata_frame(client: Any, value: Any) -> Any:
    sanitize = getattr(client, "sanitize", None)
    if callable(sanitize):
        return sanitize(value)
    return redact_sensitive_properties(value)


def _fixture_needed_detector_tool(tool: str, detector_uid: str, message: str) -> dict[str, Any]:
    return {
        "status": "fixture-needed",
        "tool": tool,
        "detector_uid": detector_uid,
        "message": message,
    }


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
            if detector_kind not in _selected_detector_kinds_from_descriptor(descriptor):
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

    def detector_config_get(self, detector_uid: str) -> dict[str, Any]:
        client = self.ensure_client()
        descriptor, config_source = _client_unit_by_uid(client, detector_uid)
        if descriptor is None:
            return _fixture_needed_detector_tool(
                "detector_config_get",
                detector_uid,
                f"Could not resolve detector {detector_uid!r}; provide a live ListUnits fixture.",
            )

        unit_type = _detector_unit_type(descriptor, detector_uid)
        if unit_type not in DETECTOR_UNIT_TYPES:
            return _fixture_needed_detector_tool(
                "detector_config_get",
                detector_uid,
                f"Resolved unit {detector_uid!r} is not a supported detector type.",
            )

        detector_kind = _selected_detector_kind(descriptor)
        return {
            "status": "ok",
            "tool": "detector_config_get",
            "detector_uid": detector_uid,
            "unit_type": unit_type,
            "detector_kind": detector_kind,
            "source_type": _source_type(unit_type, descriptor),
            "config": redact_sensitive_properties(descriptor),
            "writable_parameters": _writable_parameter_summaries(descriptor),
            "visual_elements": _visual_element_summaries(descriptor, detector_uid),
            "snapshot_metadata": {
                "detector_uid": detector_uid,
                "unit_type": unit_type,
                "detector_kind": detector_kind,
                "config_source": config_source,
                "rollback_key": f"detector_config:{detector_uid}",
            },
        }

    def detector_visual_elements(self, detector_uid: str) -> dict[str, Any]:
        config = self.detector_config_get(detector_uid)
        if config.get("status") != "ok":
            return _fixture_needed_detector_tool(
                "detector_visual_elements",
                detector_uid,
                str(config.get("message", f"Could not resolve detector {detector_uid!r}.")),
            )

        visual_elements = config["visual_elements"]
        return {
            "status": "ok",
            "tool": "detector_visual_elements",
            "detector_uid": detector_uid,
            "unit_type": config["unit_type"],
            "detector_kind": config["detector_kind"],
            "source_type": config["source_type"],
            "count": len(visual_elements),
            "visual_elements": visual_elements,
            "snapshot_metadata": config["snapshot_metadata"],
        }

    def metadata_schema_catalog(self) -> dict[str, Any]:
        client = self.ensure_client()
        schema_source = ["fallback"]
        schemas = _fallback_metadata_schemas()
        try:
            meta_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
            descriptor_schemas = _metadata_schemas_from_descriptor(meta_pb2)
            if descriptor_schemas:
                schemas = {**schemas, **descriptor_schemas}
                schema_source = ["proto-descriptor", "fallback"]
        except (AttributeError, TypeError, ImportError):
            pass

        endpoint_examples = _dedupe_endpoint_examples(
            _client_metadata_endpoint_examples(client) + _metadata_evidence_examples()
        )
        return {
            "status": "ok",
            "tool": "metadata_schema_catalog",
            "schema_source": schema_source,
            "schemas": schemas,
            "endpoint_examples": redact_sensitive_properties(endpoint_examples),
            "notes": [
                "Use metadata_sample_bounded with a vmda or metadata SourceEndpoint access point.",
                "Evidence examples are summarized and exclude raw metadata payloads and credentials.",
            ],
        }

    def metadata_sample_bounded(
        self,
        access_point: str,
        timeout_s: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        requested, applied = _normalize_metadata_sample_bounds(timeout_s, limit)
        timeout = applied["timeout_s"]
        frame_limit = applied["limit"]
        frames: list[dict[str, Any]] = []
        client = self.ensure_client()

        try:
            _authenticate_grpc_once(client)
            meta_pb2 = client.import_module("axxonsoft.bl.metadata.MetadataService_pb2")
            media_pb2 = client.import_module("axxonsoft.bl.media.Media_pb2")
            stub = client.stub_from_proto("axxonsoft/bl/metadata/MetadataService.proto", "MetadataService")
            endpoint = media_pb2.EndpointRef(access_point=access_point)
            request = meta_pb2.PullMetadataRequest(count=frame_limit, endpoint=endpoint)

            import time as _time

            deadline = _time.monotonic() + timeout
            iterator = stub.PullMetadata(iter([request]), timeout=timeout)
            for response in iterator:
                if _time.monotonic() > deadline:
                    break
                frame = client.message_to_dict(response)
                sanitized = _sanitize_metadata_frame(client, frame)
                if isinstance(sanitized, dict):
                    frames.append(sanitized)
                else:
                    frames.append({"value": sanitized})
                if len(frames) >= frame_limit:
                    break
        except Exception as exc:  # noqa: BLE001 - transport/setup failures are returned to MCP callers.
            return {
                "status": "error",
                "tool": "metadata_sample_bounded",
                "access_point": access_point,
                "requested": requested,
                "applied": applied,
                "message": str(exc)[:240],
                "count": len(frames),
                "frames": frames[:frame_limit],
            }

        return {
            "status": "ok",
            "tool": "metadata_sample_bounded",
            "access_point": access_point,
            "requested": requested,
            "applied": applied,
            "count": len(frames),
            "frames": frames[:frame_limit],
        }
