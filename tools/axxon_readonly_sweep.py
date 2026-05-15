#!/usr/bin/env python3
"""Sweep read-oriented Axxon One gRPC APIs one by one.

This is intentionally conservative. It uses the generated API catalog as input,
executes only read/read-like methods by default, summarizes response shape
instead of storing full payloads, and skips downloads, long-lived streams, and
session-acquire APIs unless explicitly included later with fixtures.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, config_from_args


SKIP_PREFIXES = (
    "Acquire",
    "Await",
    "Collect",
    "Download",
    "Pull",
    "Stream",
)
SKIP_METHODS = {
    "axxonsoft.bl.media.MediaService.Stream",
    "axxonsoft.bl.media.MediaService.AwaitConnection",
    "axxonsoft.bl.metadata.MetadataService.PullMetadata",
}
SKIP_SERVICES = {
    # Requires realtime stream control fixtures; covered by the comprehensive
    # probe and should not be generic-swept with empty requests.
    "axxonsoft.bl.media.MediaService",
}


class ReadOnlySweep:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.pb: dict[str, Any] = {}
        self.stubs: dict[str, Any] = {}
        self.results: list[dict[str, Any]] = []
        self.started_at = dt.datetime.now(dt.UTC)
        self.inventory: dict[str, Any] = {}
        self.archive_volume_id_cache: str | None = None
        self.security_role_id_cache: str | None = None
        self.layout_id_cache: str | None = None

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.inventory = self.client.load_inventory()
        self.pb["empty"] = self.client.import_module("google.protobuf.empty_pb2")

    def msg(self, message: Any) -> dict[str, Any]:
        return self.client.message_to_dict(message)

    def load_catalog(self) -> list[dict[str, str]]:
        with self.args.catalog.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        selected: list[dict[str, str]] = []
        service_filter = set(self.args.service or [])
        method_filter = set(self.args.method or [])
        for row in rows:
            fq_service = f"{row['package']}.{row['service']}"
            fqmn = row["fqmn"]
            if service_filter and row["service"] not in service_filter and fq_service not in service_filter:
                continue
            if method_filter and row["method"] not in method_filter and fqmn not in method_filter:
                continue
            if row["safety"] not in {"read", "stream_read"}:
                continue
            if not self.args.include_high_risk and self.should_skip(row):
                continue
            selected.append(row)
        return selected[: self.args.max_methods or None]

    def should_skip(self, row: dict[str, str]) -> bool:
        fq_service = f"{row['package']}.{row['service']}"
        if fq_service in SKIP_SERVICES:
            return True
        if row["fqmn"] in SKIP_METHODS:
            return True
        return row["method"].startswith(SKIP_PREFIXES)

    def import_for_row(self, row: dict[str, str]) -> tuple[Any, Any]:
        module_base = row["proto"].removesuffix(".proto").replace("/", ".")
        pb2_name = f"{module_base}_pb2"
        grpc_name = f"{module_base}_pb2_grpc"
        if pb2_name not in self.pb:
            self.pb[pb2_name] = self.client.import_module(pb2_name)
        if grpc_name not in self.pb:
            self.pb[grpc_name] = self.client.import_module(grpc_name)
        fq_service = f"{row['package']}.{row['service']}"
        if fq_service not in self.stubs:
            stub_class = getattr(self.pb[grpc_name], f"{row['service']}Stub")
            self.stubs[fq_service] = stub_class(self.client.grpc_channel)
        return self.pb[pb2_name], self.stubs[fq_service]

    def request_for(self, row: dict[str, str], pb2_module: Any) -> Any:
        fixture = getattr(self, f"fixture_{row['package'].replace('.', '_')}_{row['service']}_{row['method']}", None)
        if fixture:
            return fixture(pb2_module)
        request_name = row["request"].split(".")[-1]
        if row["request"] == "google.protobuf.Empty":
            return self.pb["empty"].Empty()
        request_class = getattr(pb2_module, request_name)
        return request_class()

    def fixture_axxonsoft_bl_domain_DomainService_ListCameras(self, pb2_module: Any) -> Any:
        return pb2_module.ListCamerasRequest(page_size=100)

    def fixture_axxonsoft_bl_domain_DomainService_ListArchives(self, pb2_module: Any) -> Any:
        return pb2_module.ListArchivesRequest(page_size=100)

    def fixture_axxonsoft_bl_domain_DomainService_ListComponents(self, pb2_module: Any) -> Any:
        return pb2_module.ListComponentsRequest(page_size=200)

    def fixture_axxonsoft_bl_domain_DomainService_BatchGetCameras(self, pb2_module: Any) -> Any:
        locator = pb2_module.ResourceLocator
        items = [
            locator(access_point=c["access_point"], view=locator.FULL)
            for c in self.inventory.get("cameras", [])
            if c.get("access_point")
        ]
        return pb2_module.BatchGetCamerasRequest(items=items)

    def fixture_axxonsoft_bl_domain_DomainService_GetCamerasByComponents(self, pb2_module: Any) -> Any:
        locator = pb2_module.ResourceLocator
        items = [
            locator(access_point=c["access_point"], view=locator.FULL)
            for c in self.inventory.get("components", [])[:5]
            if c.get("access_point")
        ]
        return pb2_module.GetCamerasByComponentsRequest(items=items)

    def fixture_axxonsoft_bl_domain_DomainService_BatchGetArchives(self, pb2_module: Any) -> Any:
        locator = pb2_module.ResourceLocator
        items = [
            locator(access_point=a["access_point"], view=locator.FULL)
            for a in self.inventory.get("archives", [])
            if a.get("access_point")
        ]
        return pb2_module.BatchGetArchivesRequest(items=items)

    def fixture_axxonsoft_bl_domain_DomainService_ListControlPanels(self, pb2_module: Any) -> Any:
        return pb2_module.ListControlPanelsRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListCommonDevices(self, pb2_module: Any) -> Any:
        return pb2_module.ListCommonDevicesRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListGlobalTrackers(self, pb2_module: Any) -> Any:
        return pb2_module.ListGlobalTrackersRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListGlobalTrackerCameras(self, pb2_module: Any) -> Any:
        return pb2_module.ListGlobalTrackerCamerasRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListAcfaComponents(self, pb2_module: Any) -> Any:
        return pb2_module.ListAcfaComponentsRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListAcfaComponents2(self, pb2_module: Any) -> Any:
        return pb2_module.ListAcfaComponentsRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_ListPluginComponents(self, pb2_module: Any) -> Any:
        return pb2_module.ListPluginComponentsRequest(page_size=50)

    def fixture_axxonsoft_bl_domain_DomainService_BatchGetAcfaComponents(self, pb2_module: Any) -> Any:
        return pb2_module.BatchGetAcfaComponentsRequest()

    def archive_access_point(self) -> str:
        archives = self.inventory.get("archives", [])
        main = next((a for a in archives if "AliceBlue" in a.get("access_point", "")), archives[0] if archives else None)
        if not main or not main.get("access_point"):
            raise RuntimeError("no archive access point available")
        return main["access_point"]

    def archive_source_access_point(self) -> str:
        sources = [
            item["access_point"]
            for item in self.inventory.get("components", [])
            if "/Sources/src." in item.get("access_point", "")
        ]
        if not sources:
            raise RuntimeError("no archive source access point available")
        return sources[0]

    def archive_time_range_1900_ms(self, hours: float = 1.0) -> tuple[int, int]:
        epoch_1900_ms = 2208988800000
        now = dt.datetime.now(dt.UTC)
        begin = int((now - dt.timedelta(hours=hours)).timestamp() * 1000) + epoch_1900_ms
        end = int(now.timestamp() * 1000) + epoch_1900_ms
        return begin, end

    def archive_time_range_legacy(self, hours: float = 1.0) -> tuple[str, str]:
        now = dt.datetime.now(dt.UTC)
        begin = (now - dt.timedelta(hours=hours)).strftime("%Y%m%dT%H%M%S.%f")
        end = now.strftime("%Y%m%dT%H%M%S.%f")
        return begin, end

    def archive_volume_id(self, pb2_module: Any) -> str:
        if self.archive_volume_id_cache is not None:
            return self.archive_volume_id_cache
        self.archive_volume_id_cache = self.client.archive_volume_id()
        return self.archive_volume_id_cache

    def fixture_axxonsoft_bl_archive_ArchiveService_GetArchiveTraits(self, pb2_module: Any) -> Any:
        return pb2_module.GetArchiveTraitsRequest(access_point=self.archive_access_point())

    def fixture_axxonsoft_bl_archive_ArchiveService_GetRecordingInfo(self, pb2_module: Any) -> Any:
        return pb2_module.RecInfoRequest(access_point=self.archive_access_point())

    def fixture_axxonsoft_bl_archive_ArchiveService_GetHistory(self, pb2_module: Any) -> Any:
        begin, end = self.archive_time_range_legacy()
        return pb2_module.GetHistoryRequest(
            access_point=self.archive_source_access_point(),
            begin_time=begin,
            end_time=end,
            max_count=8,
            min_gap=1000,
        )

    def fixture_axxonsoft_bl_archive_ArchiveService_GetHistory2(self, pb2_module: Any) -> Any:
        begin, end = self.archive_time_range_1900_ms()
        return pb2_module.GetHistory2Request(
            access_point=self.archive_source_access_point(),
            begin_time=begin,
            end_time=end,
            max_count=8,
            min_gap_ms=1000,
            scan_mode=pb2_module.GetHistory2Request.SM_APPROXIMATE,
        )

    def fixture_axxonsoft_bl_archive_ArchiveService_GetHistoryStream(self, pb2_module: Any) -> Any:
        return self.fixture_axxonsoft_bl_archive_ArchiveService_GetHistory2(pb2_module)

    def fixture_axxonsoft_bl_archive_ArchiveService_GetCalendar(self, pb2_module: Any) -> Any:
        begin, end = self.archive_time_range_1900_ms(hours=24.0)
        return pb2_module.GetCalendarRequest(
            access_point=self.archive_source_access_point(),
            begin_time=begin,
            end_time=end,
        )

    def fixture_axxonsoft_bl_archive_ArchiveService_GetSize(self, pb2_module: Any) -> Any:
        begin, end = self.archive_time_range_legacy()
        return pb2_module.GetSizeRequest(
            access_point=self.archive_source_access_point(),
            begin_time=begin,
            end_time=end,
        )

    def fixture_axxonsoft_bl_archive_ArchiveService_GetVolumesState(self, pb2_module: Any) -> Any:
        return pb2_module.GetVolumesStateRequest(access_point=self.archive_access_point())

    def fixture_axxonsoft_bl_archive_ArchiveService_GetDiskSpace(self, pb2_module: Any) -> Any:
        return pb2_module.GetDiskSpaceRequest(
            storage_access_point=self.archive_access_point(),
            volume_id=self.archive_volume_id(pb2_module),
        )

    def fixture_axxonsoft_bl_config_DevicesCatalog_ListVendors(self, pb2_module: Any) -> Any:
        return pb2_module.ListVendorsRequest(page_size=100)

    def fixture_axxonsoft_bl_config_DevicesCatalog_ListVendorsV2(self, pb2_module: Any) -> Any:
        return pb2_module.ListVendorsRequest(page_size=100)

    def fixture_axxonsoft_bl_config_DevicesCatalog_ListDevices(self, pb2_module: Any) -> Any:
        return pb2_module.ListDevicesRequest(vendor="Virtual", page_size=100)

    def fixture_axxonsoft_bl_config_DevicesCatalog_ListDevicesV2(self, pb2_module: Any) -> Any:
        return pb2_module.ListDevicesRequest(vendor="Virtual", page_size=100)

    def fixture_axxonsoft_bl_config_DevicesCatalog_GetDevice(self, pb2_module: Any) -> Any:
        return pb2_module.GetDeviceRequest(vendor="Virtual", model="Virtual")

    def fixture_axxonsoft_bl_config_FileSystemBrowser_ListDirectory(self, pb2_module: Any) -> Any:
        return pb2_module.ListDirectoryRequest(path="/data", page_size=50)

    def fixture_axxonsoft_bl_config_FileSystemBrowser_GetFileInfo(self, pb2_module: Any) -> Any:
        return pb2_module.GetFileInfoRequest(path="/data")

    def fixture_axxonsoft_bl_config_FileSystemBrowser_GetSpace(self, pb2_module: Any) -> Any:
        return pb2_module.GetSpaceRequest(path="/data")

    def fixture_axxonsoft_bl_logic_LogicService_ListMacros(self, pb2_module: Any) -> Any:
        return pb2_module.ListMacrosRequest(page_size=50)

    def fixture_axxonsoft_bl_logic_LogicService_ListMacrosV2(self, pb2_module: Any) -> Any:
        return pb2_module.ListMacrosRequest(page_size=50)

    def fixture_axxonsoft_bl_logic_LogicService_ListCounters(self, pb2_module: Any) -> Any:
        return pb2_module.ListCountersRequest(page_size=50)

    def fixture_axxonsoft_bl_logic_LogicService_BatchGetCounters(self, pb2_module: Any) -> Any:
        return pb2_module.BatchGetCountersRequest()

    def fixture_axxonsoft_bl_logic_LogicService_BatchGetActiveAlerts(self, pb2_module: Any) -> Any:
        node = self.node_name()
        return pb2_module.BatchGetActiveAlertsRequest(nodes=[node] if node else [])

    def fixture_axxonsoft_bl_logic_LogicService_GetActiveAlerts(self, pb2_module: Any) -> Any:
        cameras = self.inventory.get("cameras", [])
        camera = next((item for item in cameras if item.get("access_point")), None)
        return pb2_module.GetActiveAlertsRequest(camera_ap=camera["access_point"] if camera else "")

    def fixture_axxonsoft_bl_logic_LogicService_BatchFilterActiveAlerts(self, pb2_module: Any) -> Any:
        node = self.node_name()
        return pb2_module.BatchFilterActiveAlertsRequest(nodes=[node] if node else [])

    def fixture_axxonsoft_bl_logic_LogicService_GetUserScripts(self, pb2_module: Any) -> Any:
        host_id = f"hosts/{self.args.tls_cn}"
        return pb2_module.GetUserScriptsRequest(host_ids=[host_id])

    def fixture_axxonsoft_bl_bookmarks_BookmarkService_ListBookmarks(self, pb2_module: Any) -> Any:
        primitive = importlib.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        timestamp_pb2 = importlib.import_module("google.protobuf.timestamp_pb2")
        now = dt.datetime.now(dt.UTC)
        begin = timestamp_pb2.Timestamp()
        begin.FromDatetime(now - dt.timedelta(hours=24))
        end = timestamp_pb2.Timestamp()
        end.FromDatetime(now)
        return pb2_module.ListBookmarksRequest(
            range=primitive.TimeRangeTS(begin_time=begin, end_time=end),
            page_size=20,
        )

    def fixture_axxonsoft_bl_license_LicenseService_IsPossibleToLaunch(self, pb2_module: Any) -> Any:
        return pb2_module.IsPossibleToLaunchRequest(service_name="AVDetector", quantity=1)

    def fixture_axxonsoft_bl_security_SecurityService_ListRoles(self, pb2_module: Any) -> Any:
        return pb2_module.ListRolesRequest(page_size=100)

    def fixture_axxonsoft_bl_security_SecurityService_ListUsers(self, pb2_module: Any) -> Any:
        return pb2_module.ListUsersRequest(page_size=100)

    def fixture_axxonsoft_bl_security_SecurityService_ListLDAPServers(self, pb2_module: Any) -> Any:
        return pb2_module.ListLDAPServersRequest(page_size=100)

    def fixture_axxonsoft_bl_security_SecurityService_ListGroupsPermissions(self, pb2_module: Any) -> Any:
        groups_pb2 = importlib.import_module("axxonsoft.bl.security.GroupsPermissions_pb2")
        return groups_pb2.ListGroupsPermissionsRequest()

    def fixture_axxonsoft_bl_security_SecurityService_ListGroupsPermissionsInfo(self, pb2_module: Any) -> Any:
        groups_info_pb2 = importlib.import_module("axxonsoft.bl.security.GroupsPermissionsInfo_pb2")
        return groups_info_pb2.ListGroupsPermissionsInfoRequest(page_size=50)

    def fixture_axxonsoft_bl_security_SecurityService_ListMacrosPermissionsPaged(self, pb2_module: Any) -> Any:
        return pb2_module.ListMacrosPermissionsPagedRequest(page_size=100)

    def security_role_id(self) -> str:
        if self.security_role_id_cache is not None:
            return self.security_role_id_cache
        security_pb2 = self.client.import_module("axxonsoft.bl.security.SecurityService_pb2")
        security = self.stubs.get("axxonsoft.bl.security.SecurityService")
        if security is None:
            security = self.client.stub_from_proto("axxonsoft/bl/security/SecurityService.proto", "SecurityService")
            self.stubs["axxonsoft.bl.security.SecurityService"] = security
        roles = security.ListRoles(security_pb2.ListRolesRequest(page_size=100), timeout=self.args.timeout)
        role_items = self.msg(roles).get("roles", [])
        role = next((item for item in role_items if item.get("name") == "admin"), role_items[0] if role_items else None)
        if not role or not role.get("index"):
            raise RuntimeError("no security role id available")
        self.security_role_id_cache = role["index"]
        return self.security_role_id_cache

    def fixture_axxonsoft_bl_security_SecurityService_ListObjectsPermissionsInfo(self, pb2_module: Any) -> Any:
        return pb2_module.ListObjectsPermissionsInfoRequest(
            node_name=self.node_name(),
            role_id=self.security_role_id(),
            page_size=50,
        )

    def layout_id(self) -> str:
        if self.layout_id_cache is not None:
            return self.layout_id_cache
        layout_pb2 = self.client.import_module("axxonsoft.bl.layout.LayoutManager_pb2")
        layout = self.client.stub_from_proto("axxonsoft/bl/layout/LayoutManager.proto", "LayoutManager")
        response = layout.ListLayouts(
            layout_pb2.ListLayoutsRequest(view=layout_pb2.VIEW_MODE_ONLY_META),
            timeout=self.args.timeout,
        )
        data = self.msg(response)
        layout_id = data.get("current") or next(
            (item.get("meta", {}).get("layout_id") for item in data.get("items", []) if item.get("meta", {}).get("layout_id")),
            "",
        )
        if not layout_id:
            raise RuntimeError("no layout id available")
        self.layout_id_cache = layout_id
        return self.layout_id_cache

    def fixture_axxonsoft_bl_layout_LayoutImagesManager_ListLayoutImages(self, pb2_module: Any) -> Any:
        return pb2_module.ListLayoutImagesRequest(layout_id=self.layout_id())

    def fixture_axxonsoft_bl_events_EventHistoryService_ReadCount(self, pb2_module: Any) -> Any:
        primitive = importlib.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        now = dt.datetime.now(dt.UTC)
        begin = (now - dt.timedelta(minutes=15)).strftime("%Y%m%dT%H%M%S.%f")
        end = now.strftime("%Y%m%dT%H%M%S.%f")
        return pb2_module.ReadCountRequest(
            range=primitive.TimeRange(begin_time=begin, end_time=end),
            node_description=pb2_module.NodeDescription(node_name=self.node_name()),
        )

    def fixture_axxonsoft_bl_events_EventHistoryService_ReadEvents(self, pb2_module: Any) -> Any:
        primitive = importlib.import_module("axxonsoft.bl.primitive.Primitives_pb2")
        now = dt.datetime.now(dt.UTC)
        begin = (now - dt.timedelta(minutes=15)).strftime("%Y%m%dT%H%M%S.%f")
        end = now.strftime("%Y%m%dT%H%M%S.%f")
        return pb2_module.ReadEventsRequest(
            range=primitive.TimeRange(begin_time=begin, end_time=end),
            node_descriptions=[pb2_module.NodeDescription(node_name=self.node_name())],
            limit=5,
        )

    def node_name(self) -> str:
        nodes = self.inventory.get("nodes", [])
        return nodes[0].get("node_name", self.args.tls_cn) if nodes else self.args.tls_cn

    def invoke(self, row: dict[str, str]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            pb2_module, stub = self.import_for_row(row)
            request = self.request_for(row, pb2_module)
            method = getattr(stub, row["method"])
            response = method(request, timeout=self.args.timeout)
            if row["streaming"] == "server":
                pages = []
                for item in response:
                    pages.append(self.response_shape(item))
                    if len(pages) >= self.args.max_stream_pages:
                        break
                details = {
                    "stream_pages_read": len(pages),
                    "page_shapes": pages,
                }
            else:
                details = self.response_shape(response)
            return self.result(row, "PASS", details, start)
        except Exception as exc:
            details = {
                "error_type": exc.__class__.__name__,
                "error": str(exc)[:800],
            }
            code = getattr(exc, "code", lambda: None)()
            if code is not None:
                details["grpc_code"] = str(code)
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "WARN" if self.is_expected_fixture_gap(details) else "FAIL"
            return self.result(row, status, details, start)

    def is_expected_fixture_gap(self, details: dict[str, Any]) -> bool:
        text = f"{details.get('grpc_code', '')} {details.get('error', '')}".lower()
        expected = (
            "invalid_argument",
            "not_found",
            "unimplemented",
            "unknown",
            "permission_denied",
            "deadline_exceeded",
        )
        return any(item in text for item in expected)

    def response_shape(self, response: Any) -> dict[str, Any]:
        return self.client.shape_protobuf(response)

    def shape_message(self, message: Any) -> dict[str, Any]:
        shape: dict[str, Any] = {}
        for field, value in message.ListFields():
            if field.is_repeated:
                shape[field.name] = {"type": "list", "count": len(value)}
            elif field.message_type:
                shape[field.name] = {"type": "object", "present": True}
            else:
                shape[field.name] = {"type": field.type.name if hasattr(field.type, "name") else "scalar", "present": True}
        return shape

    def shape_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.client.shape(data)

    def result(self, row: dict[str, str], status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {
            "fqmn": row["fqmn"],
            "package": row["package"],
            "service": row["service"],
            "method": row["method"],
            "proto": row["proto"],
            "streaming": row["streaming"],
            "safety": row["safety"],
            "status": status,
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
            "details": details,
        }

    def run(self) -> dict[str, Any]:
        self.setup()
        selected = self.load_catalog()
        skipped = self.count_skipped()
        for row in selected:
            self.results.append(self.invoke(row))
        report = self.report(selected_count=len(selected), skipped_count=skipped)
        self.write_report(report)
        return report

    def count_skipped(self) -> int:
        with self.args.catalog.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        return sum(1 for row in rows if row["safety"] in {"read", "stream_read"} and self.should_skip(row))

    def report(self, selected_count: int, skipped_count: int) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "host": self.args.host,
                "grpc_port": self.args.grpc_port,
                "tls_cn": self.args.tls_cn,
                "username": self.args.username,
                "password": "<redacted>",
            },
            "selection": {
                "catalog": str(self.args.catalog),
                "selected_methods": selected_count,
                "skipped_high_risk_read_methods": skipped_count,
                "timeout_seconds": self.args.timeout,
                "max_stream_pages": self.args.max_stream_pages,
            },
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"readonly-sweep-{stamp}.json"
        md_path = self.args.report_dir / f"readonly-sweep-{stamp}.md"
        latest_json = self.args.report_dir / "live-readonly-sweep-latest.json"
        latest_md = self.args.report_dir / "live-readonly-sweep-latest.md"
        json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        json_path.write_text(json_text)
        latest_json.write_text(json_text)
        md_text = self.render_markdown(report)
        md_path.write_text(md_text)
        latest_md.write_text(md_text)
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Read-Only gRPC Sweep",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- TLS CN override: `{self.args.tls_cn}`",
            f"- Selected methods: `{report['selection']['selected_methods']}`",
            f"- Skipped high-risk read methods: `{report['selection']['skipped_high_risk_read_methods']}`",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "## Results",
                "",
                "| Status | Method | ms | Notes |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for result in report["results"]:
            note = self.short_note(result).replace("|", "\\|")
            lines.append(f"| {result['status']} | `{result['fqmn']}` | {result['elapsed_ms']} | {note} |")
        lines.append("")
        return "\n".join(lines)

    def short_note(self, result: dict[str, Any]) -> str:
        details = result.get("details", {})
        if result["status"] == "PASS":
            if "stream_pages_read" in details:
                return f"stream_pages_read={details['stream_pages_read']}"
            fields = details.get("fields", {})
            if fields:
                return ", ".join(f"{key}:{value.get('count', value.get('type'))}" for key, value in list(fields.items())[:5])
            return f"bytes={details.get('serialized_bytes', 0)}"
        code = details.get("grpc_code", "")
        error = details.get("error", "")
        return f"{code} {error[:180]}".strip()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("AXXON_HOST", "127.0.0.1"))
    parser.add_argument("--grpc-port", type=int, default=int(os.getenv("AXXON_GRPC_PORT", "20109")))
    parser.add_argument("--http-port", type=int, default=int(os.getenv("AXXON_HTTP_PORT", "8000")))
    parser.add_argument("--http-url", default=os.getenv("AXXON_HTTP_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--username", default=os.getenv("AXXON_USERNAME", "root"))
    parser.add_argument("--password", default=os.getenv("AXXON_PASSWORD"))
    parser.add_argument("--tls-cn", default=os.getenv("AXXON_TLS_CN", "F4E66972EC19"))
    parser.add_argument("--ca", type=Path, default=Path(os.getenv("AXXON_CA", str(repo_root / "docs/grpc-proto-files/api.ngp.root-ca.crt"))))
    parser.add_argument("--proto-dir", type=Path, default=repo_root / "docs/grpc-proto-files")
    parser.add_argument("--stubs-dir", type=Path, default=Path(os.getenv("AXXON_GRPC_STUBS", "/tmp/axxon-grpc-py")))
    parser.add_argument("--catalog", type=Path, default=repo_root / "docs/api-audit/grpc-api-catalog.csv")
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--service", action="append", help="Limit to service name or fully qualified service.")
    parser.add_argument("--method", action="append", help="Limit to method name or fully qualified method.")
    parser.add_argument("--max-methods", type=int, default=0)
    parser.add_argument("--max-stream-pages", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--include-high-risk", action="store_true", help="Include downloads, long-lived streams, and acquire-style reads.")
    parser.add_argument("--skip-http", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    sweep = ReadOnlySweep(args)
    report = sweep.run()
    print("Summary:", report["summary"])
    return 1 if report["summary"].get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
