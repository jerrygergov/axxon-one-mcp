#!/usr/bin/env python3
"""Comprehensive Axxon One gRPC/HTTP API probe.

Credentials are read from environment variables or CLI args. Reports are
sanitized before they are written to disk.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import traceback
import uuid

from axxon_api_client import AxxonApiClient, config_from_args
from examples.metadata_tracker_stream import try_pull_metadata_sample


class Probe:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.results: list[dict] = []
        self.inventory: dict = {}
        self.grpc = None
        self.pb = self.client.pb
        self.base_creds = None
        self.auth_response = None
        self.channel = None
        self.http_token = None
        self.started_at = dt.datetime.now(dt.UTC)

    def ensure_stubs(self) -> None:
        self.client.ensure_stubs()

    def import_proto_modules(self) -> None:
        self.client.import_common_modules()
        names = {
            "json_format": "google.protobuf.json_format",
            "empty": "google.protobuf.empty_pb2",
            "auth_pb2": "axxonsoft.bl.auth.Authentication_pb2",
            "auth_grpc": "axxonsoft.bl.auth.Authentication_pb2_grpc",
            "domain_pb2": "axxonsoft.bl.domain.Domain_pb2",
            "domain_grpc": "axxonsoft.bl.domain.Domain_pb2_grpc",
            "config_pb2": "axxonsoft.bl.config.ConfigurationService_pb2",
            "config_grpc": "axxonsoft.bl.config.ConfigurationService_pb2_grpc",
            "prop_pb2": "axxonsoft.bl.config.Property_pb2",
            "shared_pb2": "axxonsoft.bl.config.SharedKeyValueStorage_pb2",
            "shared_grpc": "axxonsoft.bl.config.SharedKeyValueStorage_pb2_grpc",
            "archive_pb2": "axxonsoft.bl.archive.ArchiveSupport_pb2",
            "archive_grpc": "axxonsoft.bl.archive.ArchiveSupport_pb2_grpc",
            "metadata_pb2": "axxonsoft.bl.metadata.MetadataService_pb2",
            "metadata_grpc": "axxonsoft.bl.metadata.MetadataService_pb2_grpc",
            "media_pb2": "axxonsoft.bl.media.Media_pb2",
            "export_pb2": "axxonsoft.bl.mmexport.ExportService_pb2",
            "export_grpc": "axxonsoft.bl.mmexport.ExportService_pb2_grpc",
            "license_pb2": "axxonsoft.bl.license.LicenseService_pb2",
            "license_grpc": "axxonsoft.bl.license.LicenseService_pb2_grpc",
            "stats_pb2": "axxonsoft.bl.statistics.Statistics_pb2",
            "stats_grpc": "axxonsoft.bl.statistics.Statistics_pb2_grpc",
            "events_pb2": "axxonsoft.bl.events.EventHistory_pb2",
            "events_grpc": "axxonsoft.bl.events.EventHistory_pb2_grpc",
            "primitive_pb2": "axxonsoft.bl.primitive.Primitives_pb2",
            "health_pb2": "grpc.health.v1.health_pb2",
            "health_grpc": "grpc.health.v1.health_pb2_grpc",
        }
        for key, module in names.items():
            try:
                self.pb[key] = self.client.import_module(module)
            except Exception as exc:
                self.pb[key] = exc
        self.grpc = self.client.grpc

    def sanitize(self, value):
        return self.client.sanitize(value)

    def msg(self, message) -> dict:
        return self.client.message_to_dict(message)

    def record(self, name: str, status: str, details=None, elapsed_ms: int = 0) -> None:
        self.results.append(
            {
                "name": name,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "details": self.sanitize(details or {}),
            }
        )

    def case(self, name: str, func, warn: bool = False):
        start = time.perf_counter()
        try:
            details = func()
            self.record(name, "PASS", details, int((time.perf_counter() - start) * 1000))
            return details
        except Exception as exc:
            status = "WARN" if warn else "FAIL"
            details = {
                "error": str(exc),
                "type": exc.__class__.__name__,
            }
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            self.record(name, status, details, int((time.perf_counter() - start) * 1000))
            return None

    def socket_check(self, host: str, port: int) -> dict:
        return self.client.socket_check(host, port)

    def make_base_channel(self):
        channel = self.client.connect_grpc()
        self.base_creds = self.client.base_creds
        return channel

    def authenticate_grpc(self) -> dict:
        response = self.client.authenticate_grpc()
        self.auth_response = response
        self.base_creds = self.client.base_creds
        self.channel = self.client.grpc_channel
        self.grpc = self.client.grpc
        return {
            "error_code": response.error_code,
            "token_name": response.token_name,
            "token_present": bool(response.token_value),
            "expires_at": response.expires_at,
            "expires_in": response.expires_in,
            "is_unrestricted": response.is_unrestricted,
            "user_id": response.user_id,
            "roles_count": len(response.roles_ids),
        }

    def stubs(self) -> dict:
        return {
            "auth": self.pb["auth_grpc"].AuthenticationServiceStub(self.channel),
            "domain": self.pb["domain_grpc"].DomainServiceStub(self.channel),
            "config": self.pb["config_grpc"].ConfigurationServiceStub(self.channel),
            "shared": self.pb["shared_grpc"].SharedKVStorageServiceStub(self.channel),
            "archive": self.pb["archive_grpc"].ArchiveServiceStub(self.channel),
            "metadata": self.pb["metadata_grpc"].MetadataServiceStub(self.channel),
            "export": self.pb["export_grpc"].ExportServiceStub(self.channel),
            "license": self.pb["license_grpc"].LicenseServiceStub(self.channel),
            "stats": self.pb["stats_grpc"].StatisticServiceStub(self.channel),
            "events": self.pb["events_grpc"].EventHistoryServiceStub(self.channel),
        }

    def get_inventory(self, s: dict) -> dict:
        self.inventory = self.client.load_inventory()
        version = self.inventory["version"]
        platform = self.inventory["platform"]
        nodes = self.inventory["nodes"]
        cameras = self.inventory["cameras"]
        archives = self.inventory["archives"]
        components = self.inventory["components"]
        host_unit = self.inventory["host_unit"]
        return {
            "version": version,
            "platform": {
                "os": platform.get("os_sys_name"),
                "machine": platform.get("os_machine"),
                "server_version": platform.get("server_version"),
                "integrity": platform.get("host_system_integrity_state"),
            },
            "node_count": len(nodes),
            "camera_count": len(cameras),
            "archive_count": len(archives),
            "component_count": len(components),
            "host_factory_count": len(host_unit.get("units", [{}])[0].get("factory", [])) if host_unit.get("units") else 0,
        }

    def run_domain_tests(self, s: dict) -> None:
        domain = s["domain"]

        def batch_get_cameras():
            aps = [c["access_point"] for c in self.inventory["cameras"] if c.get("access_point")]
            responses = []
            locator = self.pb["domain_pb2"].ResourceLocator
            request = self.pb["domain_pb2"].BatchGetCamerasRequest(
                items=[locator(access_point=ap, view=locator.FULL) for ap in aps]
            )
            for page in domain.BatchGetCameras(request, timeout=20):
                responses.append(self.msg(page))
            return {"requested": len(aps), "responses": len(responses), "items": sum(len(r.get("items", [])) for r in responses)}

        def host_timezone():
            return self.msg(domain.GetHostTimeZone(self.pb["domain_pb2"].GetHostTimeZoneRequest(), timeout=10))

        self.case("gRPC DomainService.BatchGetCameras", batch_get_cameras)
        self.case("gRPC DomainService.GetHostTimeZone", host_timezone)

    def run_config_tests(self, s: dict) -> None:
        config = s["config"]
        camera_aps = [c["access_point"] for c in self.inventory["cameras"] if c.get("access_point")]
        tracker_aps = [
            item["access_point"]
            for item in self.inventory["components"]
            if item.get("access_point", "").endswith("/EventSupplier")
            and "AVDetector" in item.get("access_point", "")
        ]

        def list_root_domain():
            root = self.msg(config.ListUnits(self.pb["config_pb2"].ListUnitsRequest(unit_uids=["root"]), timeout=15))
            domain_uid = None
            if root.get("units") and root["units"][0].get("units"):
                domain_uid = root["units"][0]["units"][0].get("uid")
            return {"root_units": len(root.get("units", [])), "domain_uid": domain_uid}

        def list_by_access_points():
            request = self.pb["config_pb2"].ListUnitsByAccessPointsRequest(access_points=camera_aps + tracker_aps)
            response = self.msg(config.ListUnitsByAccessPoints(request, timeout=20))
            return {
                "requested": len(camera_aps + tracker_aps),
                "units": [
                    {
                        "uid": u.get("uid"),
                        "type": u.get("type"),
                        "name": u.get("display_name"),
                        "access_point": u.get("access_point"),
                    }
                    for u in response.get("units", [])
                ],
                "not_found": response.get("not_found_objects", []),
                "unreachable": response.get("unreachable_objects", []),
            }

        def list_templates():
            response = self.msg(config.ListTemplates(self.pb["config_pb2"].ListTemplatesRequest(), timeout=20))
            return {"template_count": len(response.get("items", response.get("templates", []))), "keys": sorted(response.keys())}

        self.case("gRPC ConfigurationService.ListUnits(root)", list_root_domain)
        self.case("gRPC ConfigurationService.ListUnitsByAccessPoints(cameras+trackers)", list_by_access_points)
        self.case("gRPC ConfigurationService.ListTemplates", list_templates, warn=True)

    def run_shared_kv_test(self, s: dict) -> None:
        shared = s["shared"]
        prefix = ""
        key = f"codex-api-probe-run-{uuid.uuid4()}"
        value = json.dumps({"created_at": self.started_at.isoformat(), "purpose": "api_probe"}).encode()

        def cleanup_probe_records() -> int:
            cleaned = 0
            records = shared.ListRecords(
                self.pb["shared_pb2"].ListRecordsRequest(prefix=prefix, view=self.pb["shared_pb2"].ESHKV_FULL),
                timeout=10,
            )
            for item in records.items:
                if not item.key.startswith("codex-api-probe-"):
                    continue
                response = shared.Commit(
                    self.pb["shared_pb2"].SharedKVCommitRequest(
                        prefix=prefix,
                        removed=[self.pb["shared_pb2"].SharedKVRecordInfo(key=item.key, revision=item.revision)],
                    ),
                    timeout=10,
                )
                if response.error_code == 0:
                    cleaned += 1
            return cleaned

        def write_read_remove():
            cleaned_before = cleanup_probe_records()
            record = self.pb["shared_pb2"].SharedKVRecord(key=key, value=value)
            commit = shared.Commit(self.pb["shared_pb2"].SharedKVCommitRequest(prefix=prefix, set=[record]), timeout=10)
            commit_d = self.msg(commit)
            if commit.error_code != 0:
                raise RuntimeError(f"commit set failed: {commit_d}")
            revision = commit.updated[0].revision if commit.updated else ""

            got = shared.BatchGetRecords(
                self.pb["shared_pb2"].BatchGetRecordsRequest(
                    prefix=prefix,
                    items=[self.pb["shared_pb2"].SharedKVRecordInfo(key=key)],
                ),
                timeout=10,
            )
            got_d = self.msg(got)
            if not got.items:
                raise RuntimeError("record was not readable after set")
            if got.items[0].value != value:
                raise RuntimeError(f"record value mismatch after set: {got_d}")

            chunks = []
            for chunk in shared.GetRecordsStream(
                self.pb["shared_pb2"].GetRecordsStreamRequest(
                    prefix=prefix,
                    chunk_size_kb=16,
                    items=[self.pb["shared_pb2"].SharedKVRecordInfo(key=key)],
                ),
                timeout=10,
            ):
                chunks.append(self.msg(chunk))

            removed = shared.Commit(
                self.pb["shared_pb2"].SharedKVCommitRequest(
                    prefix=prefix,
                    removed=[self.pb["shared_pb2"].SharedKVRecordInfo(key=key, revision=revision)],
                ),
                timeout=10,
            )
            removed_d = self.msg(removed)
            if removed.error_code != 0:
                raise RuntimeError(f"commit remove failed: {removed_d}")
            listed_after_remove = shared.ListRecords(
                self.pb["shared_pb2"].ListRecordsRequest(prefix=prefix, view=self.pb["shared_pb2"].ESHKV_FULL),
                timeout=10,
            )
            after = shared.BatchGetRecords(
                self.pb["shared_pb2"].BatchGetRecordsRequest(
                    prefix=prefix,
                    items=[self.pb["shared_pb2"].SharedKVRecordInfo(key=key)],
                ),
                timeout=10,
            )
            list_contains_after_remove = any(item.key == key for item in listed_after_remove.items)
            batch_get_after_remove_has_value = any(item.key == key and bool(item.value) for item in after.items)
            if list_contains_after_remove or batch_get_after_remove_has_value:
                raise RuntimeError(
                    "record was not removed cleanly: "
                    f"list_contains={list_contains_after_remove} "
                    f"batch_has_value={batch_get_after_remove_has_value}"
                )
            return {
                "prefix": prefix,
                "key": key,
                "cleanup_before": cleaned_before,
                "revision_created": bool(revision),
                "batch_get_items": len(got.items),
                "stream_chunks": len(chunks),
                "removed_error_code": removed.error_code,
                "list_contains_after_remove": list_contains_after_remove,
                "batch_get_after_remove_items": len(after.items),
                "batch_get_after_remove_has_value": batch_get_after_remove_has_value,
            }

        self.case("gRPC SharedKVStorageService write/read/stream/remove", write_read_remove)

    def run_archive_tests(self, s: dict) -> None:
        archive = s["archive"]
        archives = self.inventory.get("archives", [])
        main = next((a for a in archives if "AliceBlue" in a.get("access_point", "")), archives[0] if archives else None)
        storage_sources = [
            c["access_point"]
            for c in self.inventory.get("components", [])
            if "/Sources/src." in c.get("access_point", "")
        ]

        def archive_traits_and_volume():
            if not main:
                raise RuntimeError("no archive available")
            ap = main["access_point"]
            traits = self.msg(archive.GetArchiveTraits(self.pb["archive_pb2"].GetArchiveTraitsRequest(access_point=ap), timeout=10))
            state = self.msg(archive.GetVolumesState(self.pb["archive_pb2"].GetVolumesStateRequest(access_point=ap), timeout=10))
            disk = {}
            volume_ids = list(state.get("volumes_state", {}).keys())
            if volume_ids:
                disk = self.msg(
                    archive.GetDiskSpace(
                        self.pb["archive_pb2"].GetDiskSpaceRequest(storage_access_point=ap, volume_id=volume_ids[0]),
                        timeout=10,
                    )
                )
            return {
                "archive": ap,
                "traits": traits.get("traits", []),
                "volume_count": len(state.get("volumes_state", {})),
                "disk_status": disk.get("status_code"),
                "disk_space": disk.get("space", {}),
            }

        def history_on_sources():
            now = dt.datetime.now(dt.UTC)
            epoch_1900_ms = 2208988800000
            begin = int((now - dt.timedelta(hours=1)).timestamp() * 1000) + epoch_1900_ms
            end = int(now.timestamp() * 1000) + epoch_1900_ms
            results = []
            for ap in storage_sources[:4]:
                try:
                    response = archive.GetHistory2(
                        self.pb["archive_pb2"].GetHistory2Request(
                            access_point=ap,
                            begin_time=begin,
                            end_time=end,
                            max_count=8,
                            min_gap_ms=1000,
                            scan_mode=self.pb["archive_pb2"].GetHistory2Request.SM_APPROXIMATE,
                        ),
                        timeout=10,
                    )
                    results.append({"access_point": ap, "response": self.msg(response)})
                except Exception as exc:
                    results.append({"access_point": ap, "error": str(exc)})
            return {"source_count": len(storage_sources), "tested": results}

        self.case("gRPC ArchiveService traits/volumes/disk", archive_traits_and_volume)
        self.case("gRPC ArchiveService.GetHistory2(storage sources)", history_on_sources, warn=True)

    def run_metadata_test(self, s: dict) -> None:
        candidates = [
            item["access_point"]
            for item in self.inventory.get("components", [])
            if item.get("access_point", "").endswith("/SourceEndpoint.vmda")
        ]

        def pull_metadata():
            if not candidates:
                raise RuntimeError("no VMDA metadata endpoint found")
            attempts = []
            ordered = sorted(candidates, key=lambda item: (0 if "AVDetector.2" in item else 1, item))
            for endpoint in ordered[:6]:
                try:
                    result = try_pull_metadata_sample(
                        self.client,
                        endpoint,
                        samples=5,
                        idle_ms=15000,
                        timeout=20,
                    )
                except Exception as exc:
                    attempts.append({"endpoint": endpoint, "error": str(exc)[:240]})
                    continue
                attempts.append(result)
                if result.get("samples", 0) > 0:
                    result["attempts"] = attempts
                    return result
            raise RuntimeError(f"no metadata samples received from {len(attempts)} VMDA candidates")

        self.case("gRPC MetadataService.PullMetadata(VMDA)", pull_metadata)

    def run_other_service_tests(self, s: dict) -> None:
        export = s["export"]
        license_stub = s["license"]
        stats = s["stats"]
        events = s["events"]
        node_name = self.inventory.get("nodes", [{}])[0].get("node_name", self.args.tls_cn)

        def export_sessions():
            pages = []
            for page in export.ListSessions(self.pb["export_pb2"].ListSessionsRequest(page_size=10), timeout=10):
                pages.append(self.msg(page))
                if len(pages) >= 2:
                    break
            return {"pages": len(pages), "session_count": sum(len(p.get("sessions", [])) for p in pages)}

        def license_info():
            info = self.msg(license_stub.LicenseKeyInfo(self.pb["license_pb2"].LicenseKeyInfoRequest(), timeout=10))
            global_restrictions = self.msg(
                license_stub.GetGlobalRestrictions(self.pb["license_pb2"].GetGlobalRestrictionsRequest(), timeout=10)
            )
            node_pages = []
            for page in license_stub.GetNodeRestrictions(
                self.pb["license_pb2"].GetNodeRestrictionsRequest(nodes=[self.pb["license_pb2"].Node(name=node_name)]),
                timeout=10,
            ):
                node_pages.append(self.msg(page))
            possible = self.msg(
                license_stub.IsPossibleToLaunch(
                    self.pb["license_pb2"].IsPossibleToLaunchRequest(service_name="AVDetector", quantity=1),
                    timeout=10,
                )
            )
            return {
                "status": info.get("ls_status"),
                "type": info.get("type"),
                "is_license_expiring": info.get("is_license_expiring"),
                "global_constraint_count": len(global_restrictions.get("constraints", {}).get("constraints", [])),
                "node_restriction_pages": len(node_pages),
                "can_launch_avdetector": possible.get("is_possible"),
            }

        def statistics():
            request = self.pb["stats_pb2"].StatsRequest(
                keys=[
                    self.pb["stats_pb2"].StatPointKey(type=self.pb["stats_pb2"].SPT_CpuTotalUsage, name=node_name),
                    self.pb["stats_pb2"].StatPointKey(type=self.pb["stats_pb2"].SPT_MemoryTotalUsage, name=node_name),
                    self.pb["stats_pb2"].StatPointKey(type=self.pb["stats_pb2"].SPT_ArchiveUsage, name=""),
                ]
            )
            response = self.msg(stats.GetStatistics(request, timeout=10))
            return {
                "stats_count": len(response.get("stats", [])),
                "fails_count": len(response.get("fails", [])),
                "stats": response.get("stats", []),
                "fails": response.get("fails", []),
            }

        def event_counts():
            now = dt.datetime.now(dt.UTC)
            begin = (now - dt.timedelta(minutes=30)).strftime("%Y%m%dT%H%M%S.%f")
            end = now.strftime("%Y%m%dT%H%M%S.%f")
            time_range = self.pb["primitive_pb2"].TimeRange(begin_time=begin, end_time=end)
            request = self.pb["events_pb2"].ReadCountRequest(
                range=time_range,
                node_description=self.pb["events_pb2"].NodeDescription(node_name=node_name),
            )
            pages = []
            for page in events.ReadCount(request, timeout=15):
                pages.append(self.msg(page))
            return {"range_begin": begin, "range_end": end, "pages": pages}

        self.case("gRPC ExportService.ListSessions", export_sessions)
        self.case("gRPC LicenseService info/restrictions/launch", license_info, warn=True)
        self.case("gRPC StatisticService.GetStatistics", statistics, warn=True)
        self.case("gRPC EventHistoryService.ReadCount", event_counts, warn=True)

    def http_request(self, method: str, path: str, body=None, headers=None, basic=False, bearer=None) -> dict:
        return self.client.http_request(
            method,
            path,
            body=body,
            headers=headers,
            basic=basic,
            bearer=bearer or False,
            max_items=5,
        )

    def parse_http_body(self, raw: bytes, content_type: str | None):
        return self.client.parse_http_body(raw, content_type, max_items=5)

    def run_http_tests(self) -> None:
        if self.args.skip_http:
            self.record("HTTP tests", "WARN", {"skipped": True})
            return

        def http_auth():
            response = self.http_request(
                "POST",
                "/grpc",
                {
                    "method": "axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2",
                    "data": {"user_name": self.args.username, "password": self.args.password},
                },
                basic=True,
            )
            if response["status"] != 200:
                raise RuntimeError(f"HTTP auth failed: {response}")
            body = response.get("body", {})
            if body.get("error_code") not in (0, "AUTHENTICATE_CODE_OK"):
                raise RuntimeError(f"HTTP auth error: {body}")
            self.http_token = body.get("token_value")
            return {
                "status": response["status"],
                "token_name": body.get("token_name"),
                "token_present": bool(self.http_token),
                "expires_at": body.get("expires_at"),
                "is_unrestricted": body.get("is_unrestricted"),
            }

        def http_grpc_get_version():
            response = self.http_request(
                "POST",
                "/grpc",
                {"method": "axxonsoft.bl.domain.DomainService.GetVersion", "data": {}},
                bearer=self.http_token,
            )
            if response["status"] != 200:
                raise RuntimeError(response)
            return response

        def http_grpc_list_cameras():
            response = self.http_request(
                "POST",
                "/grpc",
                {
                    "method": "axxonsoft.bl.domain.DomainService.ListCameras",
                    "data": {"page_size": 100},
                },
                bearer=self.http_token,
            )
            if response["status"] != 200:
                raise RuntimeError(response)
            return response

        def rest_nodes():
            response = self.http_request("GET", "/v1/domain/nodes", bearer=self.http_token)
            if response["status"] != 200:
                raise RuntimeError(response)
            return response

        def rest_cameras():
            response = self.http_request("GET", "/v1/domain/cameras", bearer=self.http_token)
            if response["status"] != 200:
                raise RuntimeError(response)
            return response

        def rest_license_info():
            response = self.http_request("GET", "/v1/license:info", bearer=self.http_token)
            if response["status"] != 200:
                raise RuntimeError(response)
            return response

        self.case("HTTP /grpc AuthenticateEx2 with Basic", http_auth)
        self.case("HTTP /grpc DomainService.GetVersion with Bearer", http_grpc_get_version)
        self.case("HTTP /grpc DomainService.ListCameras streaming wrapper", http_grpc_list_cameras, warn=True)
        self.case("HTTP REST GET /v1/domain/nodes", rest_nodes, warn=True)
        self.case("HTTP REST GET /v1/domain/cameras", rest_cameras, warn=True)
        self.case("HTTP REST GET /v1/license:info", rest_license_info, warn=True)

    def run_health_grpc(self) -> None:
        health_grpc = self.pb.get("health_grpc")
        health_pb2 = self.pb.get("health_pb2")
        if isinstance(health_grpc, Exception) or isinstance(health_pb2, Exception):
            self.record("gRPC Health service import", "WARN", {"error": "health proto import unavailable"})
            return

        def check():
            stub = health_grpc.HealthStub(self.channel)
            response = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=5)
            return self.msg(response)

        self.case("gRPC Health.Check", check, warn=True)

    def run(self) -> None:
        self.ensure_stubs()
        self.import_proto_modules()
        self.case("TCP connect web port", lambda: self.socket_check(self.args.host, self.args.http_port))
        self.case("TCP connect gRPC port", lambda: self.socket_check(self.args.host, self.args.grpc_port))
        self.case("gRPC AuthenticationService.AuthenticateEx2", self.authenticate_grpc)
        if not self.channel:
            raise RuntimeError("cannot continue without authenticated gRPC channel")

        stubs = self.stubs()
        self.case("gRPC inventory snapshot", lambda: self.get_inventory(stubs))
        self.run_health_grpc()
        self.run_domain_tests(stubs)
        self.run_config_tests(stubs)
        self.run_archive_tests(stubs)
        self.run_metadata_test(stubs)
        self.run_other_service_tests(stubs)
        self.run_shared_kv_test(stubs)
        self.run_http_tests()
        self.write_reports()

    def summary_counts(self) -> dict:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return counts

    def report_data(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "host": self.args.host,
                "grpc_port": self.args.grpc_port,
                "http_url": self.args.http_url,
                "tls_cn": self.args.tls_cn,
                "username": self.args.username,
                "password": "<redacted>",
            },
            "summary": self.summary_counts(),
            "inventory_summary": {
                "version": self.inventory.get("version", {}),
                "node_count": len(self.inventory.get("nodes", [])),
                "camera_count": len(self.inventory.get("cameras", [])),
                "archive_count": len(self.inventory.get("archives", [])),
                "component_count": len(self.inventory.get("components", [])),
                "cameras": [
                    {
                        "access_point": c.get("access_point"),
                        "display_name": c.get("display_name"),
                        "display_id": c.get("display_id"),
                        "enabled": c.get("enabled"),
                    }
                    for c in self.inventory.get("cameras", [])
                ],
                "archives": [
                    {
                        "access_point": a.get("access_point"),
                        "display_name": a.get("display_name"),
                        "enabled": a.get("enabled"),
                    }
                    for a in self.inventory.get("archives", [])
                ],
            },
            "results": self.results,
            "expert_notes": self.expert_notes(),
        }

    def expert_notes(self) -> list[str]:
        return [
            "Direct gRPC uses TLS on 20109 and needs the server certificate CN as grpc.ssl_target_name_override.",
            "The first auth call can be made over direct gRPC without metadata; later calls need token metadata.",
            "HTTP /grpc requires Basic auth for AuthenticateEx2, then Bearer auth for later requests.",
            "Many Axxon list methods are server-streaming; client code must iterate responses.",
            "The local test server accepts DeviceIpint vendor/model Virtual/Virtual; the PDF example axxonsoft/Virtual failed on this build.",
            "For local ARM Docker, object tracker DecoderMode should be CPU; GPU mode logs CUDA initialization failures.",
            "MetadataService.PullMetadata from AVDetector SourceEndpoint.vmda is a strong end-to-end tracker validation because it returns live tracklets.",
            "SharedKVStorageService is useful for safe write/read/remove API testing without changing server video configuration.",
            "On this build, SharedKV writes work with an empty prefix; non-empty prefixes returned EConflict in testing.",
            "After SharedKV removal, BatchGetRecords may return a key-only tombstone; ListRecords and value presence are better deletion checks.",
            "ArchiveService calls should prefer the real archive AP, e.g. MultimediaStorage.AliceBlue; embedded storage APs may be unresolved.",
        ]

    def write_reports(self) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"axxon-api-probe-{stamp}.json"
        md_path = self.args.report_dir / f"axxon-api-probe-{stamp}.md"
        latest_json = self.args.report_dir / "latest.json"
        latest_md = self.args.report_dir / "latest.md"

        data = self.report_data()
        json_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        json_path.write_text(json_text)
        latest_json.write_text(json_text)

        md_text = self.render_markdown(data)
        md_path.write_text(md_text)
        latest_md.write_text(md_text)
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, data: dict) -> str:
        lines = [
            "# Axxon One API Probe Report",
            "",
            f"- Started: `{data['started_at']}`",
            f"- Finished: `{data['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- TLS CN override: `{self.args.tls_cn}`",
            "",
            "## Summary",
            "",
        ]
        for key, val in data["summary"].items():
            lines.append(f"- {key}: {val}")
        inv = data["inventory_summary"]
        lines.extend(
            [
                "",
                "## Inventory",
                "",
                f"- Version: `{inv.get('version', {}).get('Version', 'unknown')}`",
                f"- Nodes: {inv['node_count']}",
                f"- Cameras: {inv['camera_count']}",
                f"- Archives: {inv['archive_count']}",
                f"- Components: {inv['component_count']}",
                "",
                "### Cameras",
                "",
            ]
        )
        for camera in inv["cameras"]:
            lines.append(
                f"- `{camera.get('access_point')}` name=`{camera.get('display_name')}` "
                f"id=`{camera.get('display_id')}` enabled=`{camera.get('enabled')}`"
            )
        lines.extend(["", "### Archives", ""])
        for archive in inv["archives"]:
            lines.append(
                f"- `{archive.get('access_point')}` name=`{archive.get('display_name')}` enabled=`{archive.get('enabled')}`"
            )
        lines.extend(
            [
                "",
                "## Test Results",
                "",
                "| Status | Test | ms | Notes |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for result in data["results"]:
            details = result.get("details", {})
            note = ""
            if result["status"] != "PASS":
                note = str(details.get("error", details))[:220].replace("|", "\\|")
            else:
                note = self.short_note(result["name"], details).replace("|", "\\|")
            lines.append(f"| {result['status']} | `{result['name']}` | {result['elapsed_ms']} | {note} |")
        lines.extend(["", "## Expert Notes", ""])
        for note in data["expert_notes"]:
            lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines)

    def short_note(self, name: str, details: dict) -> str:
        for key in ("camera_count", "archive_count", "component_count", "samples", "tracklets_seen", "session_count", "stats_count"):
            if key in details:
                return f"{key}={details[key]}"
        if "status" in details:
            return f"status={details['status']}"
        if "token_present" in details:
            return f"token_present={details['token_present']}"
        return ""


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
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-test-runs")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AXXON_TIMEOUT", "10.0")))
    parser.add_argument("--skip-http", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    args = parse_args()
    probe = Probe(args)
    probe.run()
    summary = probe.summary_counts()
    print("Summary:", summary)
    return 1 if summary.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
