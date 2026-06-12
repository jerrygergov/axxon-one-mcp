from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: object) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}

    def tool(self, name: str | None = None, **_kwargs: object):
        def decorator(func):
            key = name or func.__name__
            if key in self.tools:
                raise ValueError(f"duplicate tool registration: {key!r}")
            self.tools[key] = func
            return func

        return decorator

    def resource(self, uri: str, **_kwargs: object):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator


class StubDocs:
    def search_api_docs(self, query: str, *, limit: int = 10):
        return {"query": query, "limit": limit}

    def get_api_method(self, fqmn: str):
        return {"fqmn": fqmn}

    def get_http_endpoint(self, path_or_topic: str):
        return {"path_or_topic": path_or_topic}

    def get_verified_example(self, topic: str):
        return {"topic": topic}

    def explain_task_recipe(self, task: str):
        return {"task": task}

    def list_remaining_gaps(self):
        return {"gaps": []}


class StubLive:
    def connect_axxon_profile(self, profile: str = "env"):
        return {"profile": profile}

    def list_cameras(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "cameras", "filter_text": filter_text, "limit": limit}

    def list_archives(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "archives", "filter_text": filter_text, "limit": limit}

    def list_config_units(self, filter_text: str | None = None, limit: int = 100):
        return {"kind": "config_units", "filter_text": filter_text, "limit": limit}

    def list_detectors(self, camera_or_host: str | None = None, limit: int = 100):
        return {"kind": "detectors", "camera_or_host": camera_or_host, "limit": limit}

    def list_appdata_detectors(self, camera_or_host: str | None = None, limit: int = 100):
        return {"kind": "appdata_detectors", "camera_or_host": camera_or_host, "limit": limit}

    def find_event_suppliers(self, camera_or_detector: str | None = None, limit: int = 100):
        return {"kind": "event_suppliers", "camera_or_detector": camera_or_detector, "limit": limit}

    def find_metadata_endpoints(self, camera_or_detector: str | None = None, limit: int = 100):
        return {"kind": "metadata_endpoints", "camera_or_detector": camera_or_detector, "limit": limit}

    def preflight_task(self, task: str):
        return {"task": task}

    def get_archive_intervals(self, camera: str, hours: float = 1.0, max_count: int = 32, min_gap_ms: int = 1000):
        return {"camera": camera, "hours": hours, "max_count": max_count, "min_gap_ms": min_gap_ms}

    def subscribe_events_bounded(self, subjects=None, event_types=None, timeout: float = 5.0, limit: int = 25):
        return {"subjects": subjects or [], "event_types": event_types or [], "timeout": timeout, "limit": limit}


class StubOperator:
    def known_workflows(self):
        return ["temp_camera"]

    def plan(self, workflow, params):
        return {"plan_id": "plan-test", "workflow": workflow, "params": dict(params or {}), "status": "planned"}

    def apply(self, plan_id, confirmation):
        return {"status": "applied", "plan_id": plan_id, "confirmation": confirmation, "created_uids": []}

    def verify(self, plan_id):
        return {"status": "verified", "plan_id": plan_id, "still_present": []}

    def rollback(self, plan_id, confirmation):
        return {"status": "rolled_back", "plan_id": plan_id, "confirmation": confirmation}

    def audit_log(self):
        return [{"action": "plan", "plan_id": "plan-test"}]


class StubDetectorArchive:
    def detector_archive_connect_axxon_profile(self, profile: str = "env"):
        return {"profile": profile, "mode": "read-only"}

    def detector_kind_catalog(self, include_live: bool = True):
        return {"include_live": include_live}

    def detector_parameter_schema(self, unit_type: str, detector_kind: str):
        return {"unit_type": unit_type, "detector_kind": detector_kind}

    def detector_config_get(self, detector_uid: str):
        return {"detector_uid": detector_uid}

    def detector_visual_elements(self, detector_uid: str):
        return {"detector_uid": detector_uid, "elements": []}

    def metadata_schema_catalog(self):
        return {"schemas": []}

    def metadata_sample_bounded(self, access_point: str, timeout_s=None, limit=None):
        return {"access_point": access_point, "timeout_s": timeout_s, "limit": limit}

    def archive_policy_get(self, camera_or_archive: str):
        return {"camera_or_archive": camera_or_archive}

    def archive_management_status(self):
        return {"status": "ok"}

    def archive_volume_probe(self, path_or_volume_hint: str):
        return {"path_or_volume_hint": path_or_volume_hint}

    def analytics_fixture_report(self):
        return {"fixtures": []}


class StubAdmin:
    def admin_connect_axxon_profile(self, profile: str = "env"):
        return {"profile": profile, "mode": "read-only"}

    def security_inventory(self, include_users: bool = True, include_roles: bool = True, include_ldap: bool = True):
        return {"include_users": include_users, "include_roles": include_roles, "include_ldap": include_ldap}

    def security_policy_summary(self):
        return {"status": "ok", "tool": "security_policy_summary"}

    def role_permissions(self, role_id: str, page_size: int = 50):
        return {"role_id": role_id, "page_size": page_size}

    def current_user_security(self):
        return {"status": "ok", "tool": "current_user_security"}

    def license_status(
        self,
        include_host_info: bool = True,
        include_node_restrictions: bool = True,
        node_names: list[str] | None = None,
        limit: int = 32,
    ):
        return {
            "include_host_info": include_host_info,
            "include_node_restrictions": include_node_restrictions,
            "node_names": list(node_names or []),
            "limit": limit,
        }

    def time_status(self, include_available: bool = True):
        return {"include_available": include_available}

    def system_health(self):
        return {"status": "ok", "tool": "system_health"}

    def domain_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ):
        return {
            "notifier": "domain",
            "subjects": list(subjects or []),
            "event_types": list(event_types or []),
            "timeout_s": timeout_s,
            "limit": limit,
            "detailed": detailed,
        }

    def node_event_subscribe(
        self,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        timeout_s: float = 5.0,
        limit: int = 25,
        detailed: bool = False,
    ):
        return {
            "notifier": "node",
            "subjects": list(subjects or []),
            "event_types": list(event_types or []),
            "timeout_s": timeout_s,
            "limit": limit,
            "detailed": detailed,
        }

    def schedule_descriptor_get(self, uid: str):
        return {"uid": uid, "tool": "schedule_descriptor_get"}


class StubBookmarks:
    def bookmark_connect_axxon_profile(self, profile: str = "env"):
        return {"profile": profile, "mode": "read-only"}

    def bookmark_list(self, time_range: dict, limit: int = 100, page_token: str = ""):
        return {"range": time_range, "limit": limit, "page_token": page_token}

    def bookmark_get(self, bookmark_id: str):
        return {"bookmark_id": bookmark_id}


class StubAdminMutator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_workflows(self):
        self.calls.append(("list_workflows", ()))
        return {"status": "ok", "workflows": [{"name": "security_user_role_lifecycle"}]}

    def plan(self, workflow: str, params: dict | None = None):
        self.calls.append(("plan", (workflow, dict(params or {}))))
        return {"status": "planned", "workflow": workflow, "params": dict(params or {})}

    def apply(self, plan_id: str, confirmation: str):
        self.calls.append(("apply", (plan_id, confirmation)))
        return {"status": "applied", "plan_id": plan_id, "confirmation": confirmation}

    def verify(self, plan_id: str):
        self.calls.append(("verify", (plan_id,)))
        return {"status": "verified", "plan_id": plan_id}

    def rollback(self, plan_id: str, confirmation: str):
        self.calls.append(("rollback", (plan_id, confirmation)))
        return {"status": "rolled-back", "plan_id": plan_id, "confirmation": confirmation}

    def audit_log(self):
        return [{"action": name, "args": args} for name, args in self.calls]


class StubPtz:
    def ptz_connect_axxon_profile(self, profile: str = "env"):
        return {"connected": True, "profile_name": profile, "mode": "ptz-control"}

    def list_telemetry_sources(self, limit: int = 64):
        return {"status": "ok", "count": 1, "sources": ["hosts/Server/DeviceIpint.53/TelemetryControl.0"]}

    def session_available(self, access_point: str):
        return {"status": "ok", "access_point": access_point, "is_available": True}

    def acquire_session(self, access_point: str, host_name: str = "axxon-mcp"):
        return {"status": "ok", "access_point": access_point, "session_id": 1}

    def keepalive_session(self, access_point: str, session_id: int):
        return {"status": "ok", "result": True}

    def release_session(self, access_point: str, session_id: int):
        return {"status": "ok", "session_id": session_id}

    def get_position(self, access_point: str):
        return {"status": "ok", "absolute_position": {"pan": 675, "tilt": 279, "zoom": 10}}

    def move(self, access_point: str, session_id: int, pan: float, tilt: float, mode: str = "continuous"):
        return {"status": "ok", "pan": pan, "tilt": tilt, "mode": mode}

    def zoom(self, access_point: str, session_id: int, value: float, mode: str = "continuous"):
        return {"status": "ok", "value": value, "mode": mode}

    def focus(self, access_point: str, session_id: int, value: float, mode: str = "continuous"):
        return {"status": "ok", "value": value}

    def iris(self, access_point: str, session_id: int, value: float, mode: str = "continuous"):
        return {"status": "ok", "value": value}

    def absolute_move(self, access_point: str, session_id: int, pan: int, tilt: int, zoom: int, mask: int = 7):
        return {"status": "ok", "absolute_position": {"pan": pan, "tilt": tilt, "zoom": zoom, "mask": mask}}

    def list_presets(self, access_point: str):
        return {"status": "ok", "presets": []}

    def set_preset(self, access_point: str, session_id: int, position: int, label: str = ""):
        return {"status": "ok", "position": position, "label": label}

    def go_preset(self, access_point: str, session_id: int, position: int, speed: float = 1.0):
        return {"status": "ok", "position": position}

    def remove_preset(self, access_point: str, session_id: int, position: int):
        return {"status": "ok", "position": position}

    def auxiliary_operations(self, access_point: str):
        return {"status": "ok", "operations": ["wiper"]}


class StubSiteGraph:
    def site_graph_connect_axxon_profile(self, profile: str = "env"):
        return {"connected": True, "profile_name": profile, "mode": "read-only"}

    def build_site_graph(
        self,
        include_layouts: bool = True,
        include_maps: bool = True,
        include_permissions: bool = True,
        include_health: bool = True,
        limit: int = 500,
    ):
        return {
            "status": "ok",
            "tool": "build_site_graph",
            "include_layouts": include_layouts,
            "include_maps": include_maps,
            "include_permissions": include_permissions,
            "include_health": include_health,
            "limit": limit,
            "summary": {"node_count": 1, "edge_count": 0},
        }


class AxxonMcpServerTests(unittest.TestCase):
    def test_create_server_registers_ptz_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        ptz_tools = {
            "ptz_connect_axxon_profile", "list_telemetry_sources", "ptz_session_available",
            "ptz_acquire_session", "ptz_keepalive_session", "ptz_release_session",
            "ptz_get_position", "ptz_move", "ptz_zoom", "ptz_focus", "ptz_iris",
            "ptz_absolute_move", "ptz_list_presets", "ptz_set_preset", "ptz_go_preset",
            "ptz_remove_preset", "ptz_auxiliary_operations",
        }
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ptz_tools:
            self.assertNotIn(name, docs_only.tools)
        self.assertIn("ptz", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-ptz"])
        self.assertTrue(args.enable_ptz)
        server = module.create_server(docs=StubDocs(), ptz=StubPtz(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(ptz_tools, set(server.tools))
        ap = "hosts/Server/DeviceIpint.53/TelemetryControl.0"
        self.assertEqual(server.tools["list_telemetry_sources"](64)["count"], 1)
        self.assertEqual(server.tools["ptz_acquire_session"](ap)["session_id"], 1)
        self.assertEqual(server.tools["ptz_absolute_move"](ap, 1, 100, 50, 5)["absolute_position"]["pan"], 100)
        self.assertEqual(server.tools["ptz_move"](ap, 1, 0.5, 0.5, "continuous")["mode"], "continuous")
    def test_create_server_registers_phase_one_tools_and_resources(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        server = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)

        self.assertEqual(server.name, "Axxon One API Docs")
        self.assertEqual(
            set(server.tools),
            {
                "search_api_docs",
                "get_api_method",
                "get_http_endpoint",
                "get_verified_example",
                "explain_task_recipe",
                "list_remaining_gaps",
                "list_capabilities",
            },
        )
        self.assertIn("axxon://mcp-corpus/{name}", server.resources)
        self.assertIn("axxon://coverage/gaps", server.resources)

        self.assertEqual(server.tools["search_api_docs"]("camera", 3), {"query": "camera", "limit": 3})
        self.assertEqual(server.tools["get_api_method"]("DomainService.ListCameras"), {"fqmn": "DomainService.ListCameras"})
        self.assertEqual(server.resources["axxon://coverage/gaps"](), {"gaps": []})

    def test_create_server_registers_live_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        self.assertNotIn("connect_axxon_profile", docs_only.tools)

        server = module.create_server(docs=StubDocs(), live=StubLive(), fastmcp_factory=FakeFastMCP)
        for name in (
            "connect_axxon_profile",
            "list_cameras",
            "list_archives",
            "list_config_units",
            "list_detectors",
            "list_appdata_detectors",
            "find_event_suppliers",
            "find_metadata_endpoints",
            "preflight_task",
            "get_archive_intervals",
            "subscribe_events_bounded",
        ):
            self.assertIn(name, server.tools)

        self.assertEqual(server.tools["connect_axxon_profile"]("env"), {"profile": "env"})
        self.assertEqual(server.tools["list_cameras"]("Camera", 5)["limit"], 5)
        intervals = server.tools["get_archive_intervals"]("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", 2.0)
        self.assertEqual(intervals["camera"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(intervals["hours"], 2.0)
        bounded = server.tools["subscribe_events_bounded"](["hosts/Server/AppDataDetector.27/EventSupplier"], ["ET_DETECTOR"], 3.0, 10)
        self.assertEqual(bounded["limit"], 10)

    def test_create_server_registers_site_graph_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        site_graph_tools = {"site_graph_connect_axxon_profile", "build_site_graph"}

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in site_graph_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("site_graph", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-site-graph"])
        self.assertTrue(args.enable_site_graph)

        server = module.create_server(docs=StubDocs(), site_graph=StubSiteGraph(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(site_graph_tools, set(server.tools))
        self.assertEqual(
            server.tools["site_graph_connect_axxon_profile"]("env"),
            {"connected": True, "profile_name": "env", "mode": "read-only"},
        )
        graph = server.tools["build_site_graph"](False, True, False, True, 25)
        self.assertEqual(graph["tool"], "build_site_graph")
        self.assertFalse(graph["include_layouts"])
        self.assertFalse(graph["include_permissions"])
        self.assertEqual(graph["limit"], 25)

    def test_list_capabilities_reports_site_graph_disabled_and_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        disabled = next(g for g in docs_only.tools["list_capabilities"]()["groups"] if g["key"] == "site_graph")
        self.assertFalse(disabled["enabled"])
        self.assertEqual(disabled["enable_flag"], "--enable-site-graph")
        self.assertIn("build_site_graph", disabled["example_tools"])

        enabled_server = module.create_server(
            docs=StubDocs(),
            site_graph=StubSiteGraph(),
            fastmcp_factory=FakeFastMCP,
        )
        enabled = next(g for g in enabled_server.tools["list_capabilities"]()["groups"] if g["key"] == "site_graph")
        self.assertTrue(enabled["enabled"])
        self.assertNotIn("enable_flag", enabled)

    def test_create_server_registers_operator_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("plan_operator_workflow", "apply_operator_plan", "verify_operator_plan", "rollback_operator_plan"):
            self.assertNotIn(name, docs_only.tools)

        server = module.create_server(docs=StubDocs(), operator=StubOperator(), fastmcp_factory=FakeFastMCP)
        for name in (
            "list_operator_workflows",
            "plan_operator_workflow",
            "apply_operator_plan",
            "verify_operator_plan",
            "rollback_operator_plan",
        ):
            self.assertIn(name, server.tools)
        self.assertIn("axxon://operator/audit-log", server.resources)

        plan = server.tools["plan_operator_workflow"]("temp_camera", {"display_name_hint": "ok"})
        self.assertEqual(plan["workflow"], "temp_camera")
        applied = server.tools["apply_operator_plan"]("plan-test", "CONFIRM-temp_camera")
        self.assertEqual(applied["status"], "applied")
        verified = server.tools["verify_operator_plan"]("plan-test")
        self.assertEqual(verified["status"], "verified")
        rolled = server.tools["rollback_operator_plan"]("plan-test", "CONFIRM-temp_camera-rollback")
        self.assertEqual(rolled["status"], "rolled_back")
        audit = server.resources["axxon://operator/audit-log"]()
        self.assertEqual(audit["entries"][0]["action"], "plan")

    def test_create_server_registers_detector_archive_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        detector_archive_tools = {
            "detector_archive_connect_axxon_profile",
            "detector_kind_catalog",
            "detector_parameter_schema",
            "detector_config_get",
            "detector_visual_elements",
            "metadata_schema_catalog",
            "metadata_sample_bounded",
            "archive_policy_get",
            "archive_management_status",
            "archive_volume_probe",
            "analytics_fixture_report",
        }
        operator_workflow_tools = {
            "list_operator_workflows",
            "plan_operator_workflow",
            "apply_operator_plan",
            "verify_operator_plan",
            "rollback_operator_plan",
        }

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in detector_archive_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("detector_archive", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-detector-archive"])
        self.assertTrue(args.enable_detector_archive)

        server = module.create_server(
            docs=StubDocs(),
            detector_archive=StubDetectorArchive(),
            fastmcp_factory=FakeFastMCP,
        )
        self.assertLessEqual(detector_archive_tools, set(server.tools))
        self.assertTrue(operator_workflow_tools.isdisjoint(server.tools))
        self.assertEqual(
            server.tools["detector_archive_connect_axxon_profile"]("env"),
            {"profile": "env", "mode": "read-only"},
        )
        self.assertEqual(server.tools["detector_kind_catalog"](False)["include_live"], False)
        self.assertEqual(
            server.tools["detector_parameter_schema"]("AVDetector", "MotionDetection"),
            {"unit_type": "AVDetector", "detector_kind": "MotionDetection"},
        )
        self.assertEqual(server.tools["metadata_sample_bounded"]("vmda", 2.5, 10)["limit"], 10)
        self.assertEqual(server.tools["archive_volume_probe"]("/archive")["path_or_volume_hint"], "/archive")

    def test_create_server_registers_admin_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        admin_tools = {
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
        }

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in admin_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("admin", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-admin"])
        self.assertTrue(args.enable_admin)

        server = module.create_server(docs=StubDocs(), admin=StubAdmin(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(admin_tools, set(server.tools))
        self.assertEqual(
            server.tools["admin_connect_axxon_profile"]("env"),
            {"profile": "env", "mode": "read-only"},
        )
        self.assertEqual(server.tools["security_inventory"](False, True, False)["include_users"], False)
        self.assertEqual(server.tools["role_permissions"]("role-a", 25)["page_size"], 25)
        self.assertEqual(server.tools["license_status"](False, True, ["node-a"], 12)["include_host_info"], False)
        self.assertEqual(server.tools["license_status"](False, True, ["node-a"], 12)["node_names"], ["node-a"])
        self.assertEqual(server.tools["time_status"](False)["include_available"], False)
        domain = server.tools["domain_event_subscribe"](["hosts/Server"], ["config"], 2.5, 7, True)
        self.assertEqual(domain["notifier"], "domain")
        self.assertEqual(domain["limit"], 7)
        self.assertEqual(server.tools["node_event_subscribe"]([], [], 1.0, 1, False)["notifier"], "node")
        self.assertEqual(server.tools["schedule_descriptor_get"]("hosts/Server/DeviceIpint.1")["uid"], "hosts/Server/DeviceIpint.1")

    def test_create_server_registers_bookmark_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        bookmark_tools = {"bookmark_connect_axxon_profile", "bookmark_list", "bookmark_get"}

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in bookmark_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("bookmarks", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-bookmarks"])
        self.assertTrue(args.enable_bookmarks)

        server = module.create_server(docs=StubDocs(), bookmarks=StubBookmarks(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(bookmark_tools, set(server.tools))
        rng = {"begin_time": "a", "end_time": "b"}
        self.assertEqual(server.tools["bookmark_list"](rng, 7, "")["limit"], 7)
        self.assertEqual(server.tools["bookmark_get"]("bm-1")["bookmark_id"], "bm-1")

    def test_create_server_registers_bookmark_mutation_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        bookmark_mutation_tools = {
            "list_bookmark_mutation_workflows",
            "plan_bookmark_mutation_workflow",
            "apply_bookmark_mutation_plan",
            "verify_bookmark_mutation_plan",
            "rollback_bookmark_mutation_plan",
            "read_bookmark_mutation_audit_log",
        }

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in bookmark_mutation_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("bookmark_mutator", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-bookmark-mutations"])
        self.assertTrue(args.enable_bookmark_mutations)

        mutator = StubAdminMutator()
        server = module.create_server(docs=StubDocs(), bookmark_mutator=mutator, fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(bookmark_mutation_tools, set(server.tools))
        self.assertEqual(server.tools["plan_bookmark_mutation_workflow"]("bookmark_lifecycle")["status"], "planned")
        self.assertEqual(server.tools["apply_bookmark_mutation_plan"]("p1", "tok")["status"], "applied")

    def test_create_server_registers_admin_mutation_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        admin_mutation_tools = {
            "list_admin_mutation_workflows",
            "plan_admin_mutation_workflow",
            "apply_admin_mutation_plan",
            "verify_admin_mutation_plan",
            "rollback_admin_mutation_plan",
        }

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in admin_mutation_tools:
            self.assertNotIn(name, docs_only.tools)
        self.assertNotIn("axxon://admin-mutations/audit-log", docs_only.resources)

        self.assertIn("admin_mutator", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-admin-mutations"])
        self.assertTrue(args.enable_admin_mutations)

        mutator = StubAdminMutator()
        server = module.create_server(docs=StubDocs(), admin_mutator=mutator, fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(admin_mutation_tools, set(server.tools))
        self.assertIn("axxon://admin-mutations/audit-log", server.resources)

        workflows = server.tools["list_admin_mutation_workflows"]()
        self.assertEqual(workflows["status"], "ok")
        plan = server.tools["plan_admin_mutation_workflow"]("security_user_role_lifecycle", {"display_name_hint": "srv"})
        self.assertEqual(plan["workflow"], "security_user_role_lifecycle")
        self.assertEqual(plan["params"], {"display_name_hint": "srv"})
        applied = server.tools["apply_admin_mutation_plan"]("admin-1", "CONFIRM-admin")
        self.assertEqual(applied["confirmation"], "CONFIRM-admin")
        verified = server.tools["verify_admin_mutation_plan"]("admin-1")
        self.assertEqual(verified["status"], "verified")
        rolled = server.tools["rollback_admin_mutation_plan"]("admin-1", "CONFIRM-admin-rollback")
        self.assertEqual(rolled["status"], "rolled-back")
        self.assertEqual(
            mutator.calls,
            [
                ("list_workflows", ()),
                ("plan", ("security_user_role_lifecycle", {"display_name_hint": "srv"})),
                ("apply", ("admin-1", "CONFIRM-admin")),
                ("verify", ("admin-1",)),
                ("rollback", ("admin-1", "CONFIRM-admin-rollback")),
            ],
        )
        audit = server.resources["axxon://admin-mutations/audit-log"]()
        self.assertEqual(audit["entries"][-1]["action"], "rollback")

    def test_create_server_registers_view_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("live_view", "snapshot_batch", "archive_scrub", "archive_frame", "archive_mjpeg_bounded", "stream_health"):
            self.assertNotIn(name, docs_only.tools)

        class StubView:
            def connect_axxon_profile(self, profile: str = "env"):
                return {"connected": True, "profile_name": profile}

            def live_view(self, camera_access_point, **kwargs):
                return {"status": "ok", "tool": "live_view", "camera": camera_access_point, **kwargs}

            def snapshot_batch(self, camera_access_points, **kwargs):
                return {"status": "ok", "tool": "snapshot_batch", "n": len(camera_access_points), **kwargs}

            def archive_scrub(self, camera_access_point, **kwargs):
                return {"status": "ok", "tool": "archive_scrub", "camera": camera_access_point, **kwargs}

            def archive_frame(self, camera_access_point, ts, **kwargs):
                return {"status": "ok", "tool": "archive_frame", "camera": camera_access_point, "ts": ts, **kwargs}

            def archive_mjpeg_bounded(self, camera_access_point, begin_ts, **kwargs):
                return {"status": "ok", "tool": "archive_mjpeg_bounded", "camera": camera_access_point, "begin_ts": begin_ts, **kwargs}

            def stream_health(self, camera_access_point):
                return {"status": "ok", "tool": "stream_health", "camera": camera_access_point}

        server = module.create_server(docs=StubDocs(), view=StubView(), fastmcp_factory=FakeFastMCP)
        for name in (
            "view_connect_axxon_profile",
            "live_view",
            "snapshot_batch",
            "archive_scrub",
            "archive_frame",
            "archive_mjpeg_bounded",
            "stream_health",
        ):
            self.assertIn(name, server.tools)

        self.assertEqual(server.tools["view_connect_axxon_profile"]("env"), {"connected": True, "profile_name": "env"})
        live = server.tools["live_view"]("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(live["status"], "ok")
        self.assertEqual(live["camera"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        batch = server.tools["snapshot_batch"](["a", "b"])
        self.assertEqual(batch["n"], 2)
        scrub = server.tools["archive_scrub"]("cam", 3)
        self.assertEqual(scrub["hours"], 3)
        frame = server.tools["archive_frame"]("cam", "2026-05-16T10:00:00Z")
        self.assertEqual(frame["ts"], "2026-05-16T10:00:00Z")
        mjpeg = server.tools["archive_mjpeg_bounded"]("cam", "2026-05-16T10:00:00Z", 2, 4, 320)
        self.assertEqual(mjpeg["speed"], 2)
        self.assertEqual(mjpeg["fps"], 4)
        health = server.tools["stream_health"]("cam")
        self.assertEqual(health["camera"], "cam")

    def test_create_server_registers_alarm_read_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("list_active_alerts", "get_active_alert", "filter_active_alerts",
                     "list_alarm_history", "list_alarm_event_types", "alarm_subscribe"):
            self.assertNotIn(name, docs_only.tools)

        class StubAlarms:
            def connect_axxon_profile(self, profile="env"):
                return {"connected": True, "profile_name": profile, "mode": "read-only"}
            def list_active_alerts(self, camera_access_point=None, limit=50):
                return {"status": "ok", "tool": "list_active_alerts",
                        "camera": camera_access_point, "limit": limit}
            def get_active_alert(self, camera_access_point, alert_id):
                return {"status": "ok", "tool": "get_active_alert",
                        "camera": camera_access_point, "alert_id": alert_id}
            def filter_active_alerts(self, severity_min=None, camera=None, state="all", limit=50):
                return {"status": "ok", "tool": "filter_active_alerts",
                        "severity_min": severity_min, "camera": camera, "state": state, "limit": limit}
            def list_alarm_history(self, hours=1, limit=100, camera=None, severity_min=None):
                return {"status": "ok", "tool": "list_alarm_history",
                        "hours": hours, "limit": limit}
            def list_alarm_event_types(self):
                return {"status": "ok", "tool": "list_alarm_event_types"}
            def alarm_subscribe(self, severity_min=None, camera_access_point=None,
                                state="all", duration_s=10, limit=25):
                return {"status": "ok", "tool": "alarm_subscribe",
                        "duration_s": duration_s, "limit": limit}

        server = module.create_server(docs=StubDocs(), alarms=StubAlarms(), fastmcp_factory=FakeFastMCP)
        for name in ("alarms_connect_axxon_profile", "list_active_alerts", "get_active_alert",
                     "filter_active_alerts", "list_alarm_history",
                     "list_alarm_event_types", "alarm_subscribe"):
            self.assertIn(name, server.tools)
        self.assertEqual(server.tools["alarms_connect_axxon_profile"]("env")["connected"], True)
        self.assertEqual(server.tools["list_active_alerts"]("cam", 7)["limit"], 7)
        self.assertEqual(server.tools["alarm_subscribe"](None, None, "all", 3, 2)["limit"], 2)

    def test_create_server_registers_alarm_mutation_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("raise_alert", "alarm_begin_review", "alarm_continue_review",
                     "alarm_cancel_review", "alarm_complete_review", "alarm_escalate"):
            self.assertNotIn(name, docs_only.tools)

        class StubMutator:
            audit = []
            def raise_alert(self, camera_access_point, confirmation):
                return {"status": "ok", "tool": "raise_alert",
                        "camera": camera_access_point, "confirmation": confirmation}
            def alarm_begin_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_begin_review",
                        "camera": camera_access_point, "alert_id": alert_id}
            def alarm_continue_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_continue_review"}
            def alarm_cancel_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_cancel_review"}
            def alarm_complete_review(self, camera_access_point, alert_id, severity, bookmark_message, confirmation):
                return {"status": "ok", "tool": "alarm_complete_review",
                        "severity": severity, "bookmark_message": bookmark_message}
            def alarm_escalate(self, camera_access_point, alert_id, priority, user_roles, comment, confirmation):
                return {"status": "ok", "tool": "alarm_escalate",
                        "priority": priority, "user_roles": user_roles, "comment": comment}
            def audit_log(self):
                return self.audit

        server = module.create_server(docs=StubDocs(), alarm_mutator=StubMutator(), fastmcp_factory=FakeFastMCP)
        for name in ("raise_alert", "alarm_begin_review", "alarm_continue_review",
                     "alarm_cancel_review", "alarm_complete_review", "alarm_escalate"):
            self.assertIn(name, server.tools)
        self.assertIn("axxon://alarms/audit-log", server.resources)
        self.assertEqual(
            server.tools["raise_alert"]("cam", "CONFIRM-raise-alert")["confirmation"],
            "CONFIRM-raise-alert",
        )
        self.assertEqual(
            server.tools["alarm_complete_review"]("cam", "a", "confirmed_alarm", "msg", "CONFIRM-alarm-complete")["severity"],
            "confirmed_alarm",
        )

    def test_create_server_registers_view_objects_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in (
            "list_layouts",
            "get_layout",
            "layouts_on_view",
            "list_layout_images",
            "list_maps",
            "get_map",
            "get_map_image",
            "get_markers",
            "list_map_providers",
            "list_walls",
        ):
            self.assertNotIn(name, docs_only.tools)

        class StubViewObjects:
            def connect_axxon_profile(self, profile="env"):
                return {"connected": True, "profile_name": profile, "mode": "read-only"}

            def list_layouts(self, view="meta", limit=50):
                return {"status": "ok", "view": view, "limit": limit}

            def get_layout(self, layout_id, etag=None):
                return {"status": "ok", "id": layout_id}

            def layouts_on_view(self, layouts):
                return {"status": "ok", "pushed": len(layouts)}

            def list_layout_images(self, layout_id):
                return {"status": "ok"}

            def list_maps(self, limit=50):
                return {"status": "ok", "limit": limit}

            def get_map(self, map_id):
                return {"status": "ok", "id": map_id}

            def get_map_image(self, map_id, max_bytes=4_194_304):
                return {"status": "ok", "id": map_id, "max_bytes": max_bytes}

            def get_markers(self, map_id):
                return {"status": "ok"}

            def list_map_providers(self):
                return {"status": "ok"}

            def list_walls(self, limit=50):
                return {"status": "ok"}

        server = module.create_server(
            docs=StubDocs(),
            view_objects=StubViewObjects(),
            fastmcp_factory=FakeFastMCP,
        )
        for name in (
            "view_objects_connect_axxon_profile",
            "list_layouts",
            "get_layout",
            "layouts_on_view",
            "list_layout_images",
            "list_maps",
            "get_map",
            "get_map_image",
            "get_markers",
            "list_map_providers",
            "list_walls",
        ):
            self.assertIn(name, server.tools)
        self.assertEqual(server.tools["list_maps"](7)["limit"], 7)
        self.assertEqual(server.tools["get_map_image"]("m-1", 1024)["max_bytes"], 1024)

    def test_create_server_registers_partner_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        partner_tools = {"scaffold_plugin", "plugin_lint", "plugin_package"}

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in partner_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("partner", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-partner"])
        self.assertTrue(args.enable_partner)

        class StubPartner:
            def scaffold_plugin(self, name, language="python"):
                return {"status": "ok", "name": name, "language": language, "files": {"main.py": "x"}}

            def plugin_lint(self, path):
                return {"ok": True, "findings": []}

            def plugin_package(self, path, fmt, output, version="0.0.0"):
                return {"status": "ok", "archive": str(output), "manifest": {"format": fmt, "version": version}}

        server = module.create_server(docs=StubDocs(), partner=StubPartner(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(partner_tools, set(server.tools))
        self.assertEqual(server.tools["plugin_lint"]("/tmp/x")["ok"], True)
        self.assertEqual(server.tools["plugin_package"]("/tmp/x", "/tmp/out.zip", "zip")["manifest"]["format"], "zip")

    def test_create_server_registers_metadata_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        metadata_tools = {"metadata_connect_axxon_profile", "list_vmda_sources", "live_track_sample", "vmda_query"}

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in metadata_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("metadata", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-metadata"])
        self.assertTrue(args.enable_metadata)

        class StubMetadata:
            def connect_axxon_profile(self, profile="env"):
                return {"connected": True, "profile_name": profile}

            def list_vmda_sources(self, limit=64):
                return {"status": "ok", "count": 1, "sources": ["hosts/Server/AVDetector.1/SourceEndpoint.vmda"]}

            def live_track_sample(self, access_point, seconds=5.0, limit=40):
                return {"status": "ok", "access_point": access_point, "count": 0, "tracklets": []}

            def vmda_query(self, camera_id, query_type="motion_in_area", database=None, hours=24, max_intervals=500, timeout=60.0):
                return {"status": "ok", "camera_id": camera_id, "query_type": query_type, "interval_count": 0, "object_count": 0}

        server = module.create_server(docs=StubDocs(), metadata=StubMetadata(), fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(metadata_tools, set(server.tools))
        self.assertEqual(server.tools["list_vmda_sources"](8)["status"], "ok")
        self.assertEqual(server.tools["vmda_query"]("hosts/Server/AVDetector.1/SourceEndpoint.vmda")["query_type"], "motion_in_area")


    def test_create_server_registers_translator_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        translator_tools = {"assemble_recipe", "validate_recipe", "explain_recipe"}

        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in translator_tools:
            self.assertNotIn(name, docs_only.tools)

        self.assertIn("translator", inspect.signature(module.create_server).parameters)
        args = module.build_parser().parse_args(["--enable-translator"])
        self.assertTrue(args.enable_translator)

        class StubTranslator:
            def assemble_recipe(self, intent_text, context=None):
                return {"intent_text": intent_text, "steps": []}

            def validate_recipe(self, recipe):
                return {"valid": True, "steps": [], "risk_classes": [], "required_approvals": [], "gaps": []}

            def explain_recipe(self, recipe):
                return {"text": "stub explanation"}

        # register_translator_tools is defined in axxon_mcp_translator — server delegates to it
        from axxon_mcp_translator import AxxonMcpTranslator

        KNOWN_WFS = ["create_camera"]

        class StubOp:
            def known_workflows(self):
                return KNOWN_WFS
            def plan(self, wf, params=None):
                return {"status": "planned", "plan_id": "stub-1", "workflow": wf, "risk": "mutation",
                        "confirmation_token": f"CONFIRM-{wf}", "rollback_confirmation_token": f"CONFIRM-{wf}-rollback"}

        stub_translator = AxxonMcpTranslator(operator_factory=lambda: StubOp())
        server = module.create_server(docs=StubDocs(), translator=stub_translator, fastmcp_factory=FakeFastMCP)
        self.assertLessEqual(translator_tools, set(server.tools))
        result = server.tools["assemble_recipe"]("Create layout named X", {"name": "X"})
        self.assertIn("steps", result)
        validate_result = server.tools["validate_recipe"]([])
        self.assertIn("valid", validate_result)
        explain_result = server.tools["explain_recipe"]([])
        self.assertIsNotNone(explain_result)

    def test_all_feature_groups_register_without_duplicate_tool_names(self) -> None:
        """Enabling every feature group at once must not register two tools under one name."""
        module = importlib.import_module("axxon_mcp_server")

        class AnyStub:
            # accept any attribute access / call so each register_* function runs.
            def __getattr__(self, _name):
                return lambda *a, **k: {"status": "ok"}

        params = inspect.signature(module.create_server).parameters
        skip = {"docs", "corpus_dir", "fastmcp_factory"}
        groups = {name: AnyStub() for name in params if name not in skip}

        # FakeFastMCP raises on duplicate tool names, so this builds the full
        # server and fails loudly if any two groups collide.
        server = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP, **groups)
        self.assertGreater(len(server.tools), 0)

    def test_enable_all_flips_every_enable_flag(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        args = module.apply_enable_all(module.build_parser().parse_args(["--enable-all"]))
        enables = {k: v for k, v in vars(args).items() if k.startswith("enable_")}
        self.assertTrue(all(enables.values()))
        self.assertGreater(len(enables), 30)

    def test_enable_all_equals_all_individual_flags(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        all_args = module.apply_enable_all(module.build_parser().parse_args(["--enable-all"]))
        enables = [k for k in vars(all_args) if k.startswith("enable_") and k != "enable_all"]
        flags = [f"--enable-{k[len('enable_'):].replace('_', '-')}" for k in enables]
        each_args = module.build_parser().parse_args(flags)
        for k in enables:
            self.assertTrue(getattr(each_args, k), f"{k} not set by its individual flag")

    def test_list_capabilities_reports_disabled_with_flag(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        server = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        self.assertIn("list_capabilities", server.tools)
        caps = server.tools["list_capabilities"]()
        operator = next(g for g in caps["groups"] if g["key"] == "operator")
        self.assertFalse(operator["enabled"])
        self.assertEqual(operator["enable_flag"], "--enable-operator")
        self.assertEqual(caps["enabled_count"], 0)

    def test_list_capabilities_reports_enabled_group(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        server = module.create_server(docs=StubDocs(), operator=object(), fastmcp_factory=FakeFastMCP)
        operator = next(g for g in server.tools["list_capabilities"]()["groups"] if g["key"] == "operator")
        self.assertTrue(operator["enabled"])
        self.assertNotIn("enable_flag", operator)

    def test_default_open_enables_all_groups_and_approvals(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        env: dict[str, str] = {}
        args = module.apply_default_open(module.build_parser().parse_args([]), environ=env)
        enables = {k: v for k, v in vars(args).items() if k.startswith("enable_")}
        self.assertTrue(all(enables.values()))
        for var in module.APPROVE_ENV_VARS:
            self.assertEqual(env.get(var), "1", f"{var} should default to '1'")

    def test_read_only_enables_groups_but_no_approval_defaults(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        env: dict[str, str] = {}
        args = module.apply_default_open(module.build_parser().parse_args(["--read-only"]), environ=env)
        enables = {k: v for k, v in vars(args).items() if k.startswith("enable_")}
        self.assertTrue(all(enables.values()))  # groups register so reads work
        for var in module.APPROVE_ENV_VARS:
            self.assertNotIn(var, env, f"{var} must not be defaulted on in read-only mode")

    def test_default_open_preserves_user_set_approval(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        env = {"AXXON_OPERATOR_APPROVE": "0"}
        module.apply_default_open(module.build_parser().parse_args([]), environ=env)
        self.assertEqual(env["AXXON_OPERATOR_APPROVE"], "0")

    def test_explicit_enable_flag_not_overridden_by_default_open(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        env: dict[str, str] = {}
        args = module.apply_default_open(module.build_parser().parse_args(["--enable-live"]), environ=env)
        self.assertTrue(args.enable_live)
        self.assertFalse(args.enable_operator)

    def test_operator_group_builds_without_credentials(self) -> None:
        """Regression: the operator group must construct lazily so the server boots with no password."""
        import os
        from unittest import mock

        from axxon_api_client import AxxonApiClient, AxxonClientConfig
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AXXON_PASSWORD", None)
            config = AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[2])
        self.assertFalse(config.password)  # no creds
        # Mirrors main(): the live client is only built inside the factory, not at construction.
        registry = OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(AxxonApiClient(config)),
            host=f"hosts/{config.tls_cn}",
            enabled=False,
        )
        self.assertIsNotNone(registry)
        # Building the client eagerly would raise; deferring means only an actual call would.
        with self.assertRaises(ValueError):
            AxxonApiClient(config)


if __name__ == "__main__":
    unittest.main()
