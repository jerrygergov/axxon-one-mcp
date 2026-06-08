#!/usr/bin/env python3
"""Read-only preflight for users, roles, permissions, policy, and LDAP fixtures."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import time
import traceback
from typing import Any

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


SECURITY_MUTATIONS_REQUIRING_APPROVAL = [
    {
        "rpc": "SecurityService.ChangeConfig",
        "risk": "creates, edits, or removes users, roles, LDAP servers, password policies, IP filters, trusted IP lists, and cloud config",
        "requirement": "codex-prefixed test user/role plus explicit rollback for assignments and passwords",
    },
    {
        "rpc": "SecurityService.SetGlobalPermissions",
        "risk": "changes role-wide feature permissions",
        "requirement": "isolated role id and pre/post permission snapshot",
    },
    {
        "rpc": "SecurityService.SetObjectPermissions",
        "risk": "changes object access for cameras, archives, telemetry, plugins, and video walls",
        "requirement": "isolated role and non-production object scope",
    },
    {
        "rpc": "SecurityService.SetGroupsPermissions",
        "risk": "changes role permissions inherited through object groups",
        "requirement": "isolated role/group scope and rollback snapshot",
    },
    {
        "rpc": "SecurityService.SetMacrosPermissions",
        "risk": "changes macro execution visibility for a role",
        "requirement": "isolated disabled macro and test role",
    },
    {
        "rpc": "SecurityService.StartLDAPSynchronization",
        "risk": "starts directory synchronization",
        "requirement": "configured test LDAP server and maintenance-window approval",
    },
    {
        "rpc": "SecurityService.StopLDAPSynchronization",
        "risk": "stops directory synchronization",
        "requirement": "only for a known test synchronization started by this workflow",
    },
]


def security_inventory_summary(
    *,
    roles: list[dict[str, Any]],
    users: list[dict[str, Any]],
    ldap_servers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "roles_count": len(roles),
        "users_count": len(users),
        "ldap_servers_count": len(ldap_servers),
        "role_id_lengths": sorted(len(str(item.get("index", ""))) for item in roles),
        "user_id_lengths": sorted(len(str(item.get("index", ""))) for item in users),
        "ldap_id_lengths": sorted(len(str(item.get("index", ""))) for item in ldap_servers),
        "enabled_users_count": sum(1 for item in users if item.get("enabled") is True),
        "ldap_linked_users_count": sum(1 for item in users if item.get("ldap_link") or item.get("ldap_server_id")),
    }


def policy_summary(
    *,
    policies: dict[str, Any],
    ldap_sync: dict[str, Any],
    ldap_state: dict[str, Any],
    cloud_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pwd_policy_count": len(policies.get("pwd_policy", [])),
        "ip_filter_count": len(policies.get("ip_filters", [])),
        "trusted_ip_count": len(policies.get("trusted_ip_list", [])),
        "system_integrity_modes_count": len(policies.get("system_integrity_reaction_modes", [])),
        "ldap_sync_keys": sorted(ldap_sync.keys()),
        "ldap_state_keys": sorted(ldap_state.keys()),
        "cloud_public_key_present": bool(cloud_config.get("cloud_public_key")),
    }


def restricted_config_summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_user_present": bool(data.get("current_user")),
        "current_roles_count": len(data.get("current_roles", [])),
        "all_roles_count": len(data.get("all_roles", [])),
        "all_users_count": len(data.get("all_users", [])),
        "pwd_policy_count": len(data.get("pwd_policy", [])),
        "system_integrity_modes_count": len(data.get("system_integrity_reaction_modes", [])),
    }


class SecurityAdminPreflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.results: list[dict[str, Any]] = []
        self.fixtures: dict[str, Any] = {}

    def setup(self) -> None:
        self.client.authenticate_grpc()
        self.client.load_inventory()
        self.fixtures["node_name"] = self.client.node_name()

    def run(self) -> dict[str, Any]:
        self.setup()
        self.results.append(self.read_inventory())
        self.results.append(self.read_policies())
        self.results.append(self.read_permissions())
        self.results.append(self.read_restricted_config())
        self.results.append(
            {
                "group": "approval_only_mutations",
                "status": "WARN",
                "elapsed_ms": 0,
                "details": {"not_executed": SECURITY_MUTATIONS_REQUIRING_APPROVAL},
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def security_stub_and_pb2(self) -> tuple[Any, Any]:
        pb2 = self.client.import_module("axxonsoft.bl.security.SecurityService_pb2")
        return self.client.stub_from_proto("axxonsoft/bl/security/SecurityService.proto", "SecurityService"), pb2

    def read_inventory(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.security_stub_and_pb2()
            roles = self.collect_pages(stub.ListRoles, pb2.ListRolesRequest(page_size=100), "roles")
            users_data = self.collect_user_pages(stub, pb2)
            ldap_servers = self.collect_pages(stub.ListLDAPServers, pb2.ListLDAPServersRequest(page_size=100), "ldap_servers")
            role = next((item for item in roles if item.get("name") == "admin"), roles[0] if roles else None)
            self.fixtures["role_id"] = role.get("index", "") if role else ""
            details = security_inventory_summary(roles=roles, users=users_data["users"], ldap_servers=ldap_servers)
            details["user_assignment_count"] = users_data["assignment_count"]
            details["selected_role_id_len"] = len(self.fixtures.get("role_id", ""))
            status = "PASS" if roles and users_data["users"] else "WARN"
            return self.result("security_inventory", status, details, start)
        except Exception as exc:
            return self.exception_result("security_inventory", exc, start)

    def collect_pages(self, method: Any, request: Any, item_key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            response = method(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            items.extend(data.get(item_key, []))
            if not getattr(response, "next_page_token", ""):
                break
            request.page_token = response.next_page_token
        return items

    def collect_user_pages(self, stub: Any, pb2: Any) -> dict[str, Any]:
        users: list[dict[str, Any]] = []
        assignment_count = 0
        request = pb2.ListUsersRequest(page_size=100)
        while True:
            response = stub.ListUsers(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            users.extend(data.get("users", []))
            assignment_count += len(data.get("user_assignments", []))
            if not response.next_page_token:
                break
            request.page_token = response.next_page_token
        return {"users": users, "assignment_count": assignment_count}

    def read_policies(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.security_stub_and_pb2()
            policies = self.client.message_to_dict(stub.GetPolicies(pb2.GetPoliciesRequest(), timeout=self.args.timeout))
            ldap_sync = self.client.message_to_dict(stub.GetLDAPSynchronization(pb2.GetLDAPSynchronizationRequest(), timeout=self.args.timeout))
            ldap_state_status = "PASS"
            try:
                ldap_state = self.client.message_to_dict(stub.GetLDAPSynchronizationState(pb2.GetLDAPSynchronizationStateRequest(), timeout=self.args.timeout))
            except Exception as exc:
                ldap_state = {"unavailable": exc.__class__.__name__, "error": str(exc)[:300]}
                ldap_state_status = "WARN"
            cloud_config = self.client.message_to_dict(stub.GetCloudConfig(pb2.GetCloudConfigRequest(), timeout=self.args.timeout))
            details = policy_summary(policies=policies, ldap_sync=ldap_sync, ldap_state=ldap_state, cloud_config=cloud_config)
            if ldap_state_status == "WARN":
                details["ldap_state_status"] = "WARN"
                details["ldap_state_error_type"] = ldap_state.get("unavailable", "")
                details["ldap_state_error"] = ldap_state.get("error", "")
            return self.result("security_policies", ldap_state_status, details, start)
        except Exception as exc:
            return self.exception_result("security_policies", exc, start)

    def read_permissions(self) -> dict[str, Any]:
        start = time.perf_counter()
        role_id = self.fixtures.get("role_id", "")
        if not role_id:
            return self.result("security_permissions", "WARN", {"skipped": "no role id"}, start)
        try:
            stub, pb2 = self.security_stub_and_pb2()
            groups_pb2 = self.client.import_module("axxonsoft.bl.security.GroupsPermissions_pb2")
            groups_info_pb2 = self.client.import_module("axxonsoft.bl.security.GroupsPermissionsInfo_pb2")
            global_permissions = self.client.message_to_dict(
                stub.ListGlobalPermissions(pb2.ListGlobalPermissionsRequest(role_ids=[role_id]), timeout=self.args.timeout)
            )
            group_permissions = self.client.message_to_dict(
                stub.ListGroupsPermissions(groups_pb2.ListGroupsPermissionsRequest(role_ids=[role_id]), timeout=self.args.timeout)
            )
            group_info = self.client.message_to_dict(
                stub.ListGroupsPermissionsInfo(groups_info_pb2.ListGroupsPermissionsInfoRequest(role_id=role_id, page_size=50), timeout=self.args.timeout)
            )
            object_info = self.client.message_to_dict(
                stub.ListObjectsPermissionsInfo(
                    pb2.ListObjectsPermissionsInfoRequest(node_name=self.fixtures["node_name"], role_id=role_id, page_size=50),
                    timeout=self.args.timeout,
                )
            )
            macros = self.client.message_to_dict(
                stub.ListMacrosPermissionsPaged(pb2.ListMacrosPermissionsPagedRequest(role_id=role_id, page_size=50), timeout=self.args.timeout)
            )
            details = {
                "role_id_len": len(role_id),
                "global_permission_roles": len(global_permissions.get("permissions", {})),
                "group_permission_roles": len(group_permissions.get("permissions", [])),
                "group_info_items": len(group_info.get("items", [])),
                "object_info_items": len(object_info.get("items", [])),
                "object_info_has_next_page": bool(object_info.get("next_page_token")),
                "macros_permission_items": len(macros.get("macros_access", [])),
                "macros_has_next_page": bool(macros.get("next_page_token")),
            }
            return self.result("security_permissions", "PASS", details, start)
        except Exception as exc:
            return self.exception_result("security_permissions", exc, start)

    def read_restricted_config(self) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            stub, pb2 = self.security_stub_and_pb2()
            response = stub.GetRestrictedConfig(pb2.GetRestrictedConfigRequest(), timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            details = restricted_config_summary(data)
            return self.result("restricted_config", "PASS", details, start)
        except Exception as exc:
            return self.exception_result("restricted_config", exc, start)

    def result(self, group: str, status: str, details: dict[str, Any], start: float) -> dict[str, Any]:
        return {"group": group, "status": status, "elapsed_ms": int((time.perf_counter() - start) * 1000), "details": details}

    def exception_result(self, group: str, exc: Exception, start: float) -> dict[str, Any]:
        details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
        if self.args.verbose:
            details["traceback"] = traceback.format_exc()
        return self.result(group, "FAIL", details, start)

    def report(self) -> dict[str, Any]:
        counts = Counter(result["status"] for result in self.results)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"grpc_target": f"{self.args.host}:{self.args.grpc_port}", "http_url": self.args.http_url, "username": self.args.username, "password": "<redacted>"},
            "summary": {"PASS": counts.get("PASS", 0), "WARN": counts.get("WARN", 0), "FAIL": counts.get("FAIL", 0)},
            "fixtures": {"node_name": self.fixtures.get("node_name", ""), "selected_role_id_len": len(self.fixtures.get("role_id", ""))},
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"security-admin-preflight-{stamp}.json"
        md_path = self.args.report_dir / f"security-admin-preflight-{stamp}.md"
        latest_json = self.args.report_dir / "security-admin-preflight-latest.json"
        latest_md = self.args.report_dir / "security-admin-preflight-latest.md"
        json_text = json.dumps(self.client.sanitize(report), indent=2, ensure_ascii=True) + "\n"
        json_path.write_text(json_text, encoding="utf-8")
        latest_json.write_text(json_text, encoding="utf-8")
        md_text = self.render_markdown(report)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {md_path}")
        print(f"Latest markdown: {latest_md}")

    def render_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Axxon One Security Admin Preflight",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            f"- HTTP target: `{self.args.http_url}`",
            f"- Node: `{report['fixtures']['node_name']}`",
            "",
            "Read-only preflight for security administration mutations. It does not create users, change passwords, edit roles, change permissions, start LDAP synchronization, or change policy/IP filters.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            lines.append(f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {self.note_for(result).replace('|', '\\|')[:220]} |")
        lines.append("")
        return "\n".join(lines)

    def note_for(self, result: dict[str, Any]) -> str:
        details = result.get("details", {})
        if details.get("error"):
            return details["error"]
        if result["group"] == "security_inventory":
            return f"roles={details.get('roles_count')} users={details.get('users_count')} ldap_servers={details.get('ldap_servers_count')} assignments={details.get('user_assignment_count')}"
        if result["group"] == "security_permissions":
            return f"global_roles={details.get('global_permission_roles')} object_items={details.get('object_info_items')} group_items={details.get('group_info_items')} macros={details.get('macros_permission_items')}"
        if result["group"] == "security_policies":
            return f"pwd_policies={details.get('pwd_policy_count')} ip_filters={details.get('ip_filter_count')} trusted_ips={details.get('trusted_ip_count')} ldap_state={details.get('ldap_state_status', 'PASS')}"
        if result["group"] == "approval_only_mutations":
            return ", ".join(item["rpc"] for item in details.get("not_executed", []))
        return f"keys={len(details)}"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--verbose", action="store_true")
    return parser


def parse_args() -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    return args


def main() -> int:
    preflight = SecurityAdminPreflight(parse_args())
    report = preflight.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
