#!/usr/bin/env python3
"""Controlled security user/role mutation smoke with rollback."""

from __future__ import annotations

import argparse
import datetime as dt
import base64
import hashlib
import json
import hmac
from pathlib import Path
import secrets
import string
import struct
import time
import traceback
from typing import Any
import uuid

from axxon_api_client import AxxonApiClient, add_common_args, config_from_args


CONFIRMATION = "CONFIRM-security-mutation-smoke"

SECURITY_MUTATIONS_REQUIRING_APPROVAL = [
    "SecurityService.ChangeConfig.add_role",
    "SecurityService.ChangeConfig.add_user",
    "SecurityService.ChangeConfig.assign_user_role",
    "SecurityService.ChangeConfig.set_generated_user_password",
    "SecurityService.SetGlobalPermissions.temp_role",
    "SecurityService.SetObjectPermissions.temp_role",
    "SecurityService.SetGroupsPermissions.temp_role",
    "SecurityService.SetMacrosPermissions.temp_role",
    "SecurityService.ChangeConfig.noop_password_policy",
    "SecurityService.ChangeConfig.noop_ip_filters",
    "SecurityService.ChangeConfig.add_edit_remove_temp_ldap_server",
    "SecurityService.ChangeConfig.remove_user_role",
    "SecurityService.ChangeConfig.remove_user",
    "SecurityService.ChangeConfig.remove_role",
    "SecurityService.GenGoogleAuthSecret",
    "SecurityService.EnableGoogleAuth.temp_user",
    "SecurityService.DisableGoogleAuth.temp_user",
]


def mutation_approved(args: argparse.Namespace) -> bool:
    return bool(args.i_understand_this_mutates and args.confirm == CONFIRMATION)


def temp_security_ids() -> dict[str, str]:
    role_uuid = str(uuid.uuid4())
    user_uuid = str(uuid.uuid4())
    suffix = user_uuid.replace("-", "")[:12]
    return {
        "role_id": role_uuid,
        "user_id": user_uuid,
        "role_name": f"codex-role-{suffix}",
        "login": f"codex_user_{suffix[:8]}",
    }


def generated_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!#$_"
    return "Aa" + "".join(secrets.choice(alphabet) for _ in range(14)) + "123"


def totp_code(secret_key: str, *, for_time: int | None = None, step_seconds: int = 30, digits: int = 6) -> str:
    if for_time is None:
        for_time = int(time.time())
    padded_secret = secret_key.upper() + "=" * ((8 - len(secret_key) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    counter = int(for_time // step_seconds)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10 ** digits):0{digits}d}"


class SecurityMutationSmoke:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.client = AxxonApiClient(config_from_args(args))
        self.started_at = dt.datetime.now(dt.UTC)
        self.ids = temp_security_ids()
        self.password = generated_password()
        self.ldap_server_id = str(uuid.uuid4())
        self.results: list[dict[str, Any]] = []

    def setup(self) -> None:
        if not mutation_approved(self.args):
            raise RuntimeError("explicit mutation approval is required")
        self.client.authenticate_grpc()

    @property
    def security_pb2(self) -> Any:
        return self.client.import_module("axxonsoft.bl.security.SecurityService_pb2")

    @property
    def stub(self) -> Any:
        return self.client.stub_from_proto("axxonsoft/bl/security/SecurityService.proto", "SecurityService")

    def change_config(self, request: Any) -> dict[str, Any]:
        response = self.stub.ChangeConfig(request, timeout=self.args.timeout)
        return self.client.message_to_dict(response)

    def list_roles(self) -> list[dict[str, Any]]:
        request = self.security_pb2.ListRolesRequest(page_size=100)
        roles: list[dict[str, Any]] = []
        while True:
            response = self.stub.ListRoles(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            roles.extend(data.get("roles", []))
            if not response.next_page_token:
                return roles
            request.page_token = response.next_page_token

    def list_users(self, *, role_id: str = "") -> dict[str, Any]:
        request = self.security_pb2.ListUsersRequest(page_size=100)
        if role_id:
            request.role_ids.append(role_id)
        users: list[dict[str, Any]] = []
        assignments: list[dict[str, Any]] = []
        while True:
            response = self.stub.ListUsers(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            users.extend(data.get("users", []))
            assignments.extend(data.get("user_assignments", []))
            if not response.next_page_token:
                return {"users": users, "assignments": assignments}
            request.page_token = response.next_page_token

    def list_ldap_servers(self) -> list[dict[str, Any]]:
        request = self.security_pb2.ListLDAPServersRequest(page_size=100)
        servers: list[dict[str, Any]] = []
        while True:
            response = self.stub.ListLDAPServers(request, timeout=self.args.timeout)
            data = self.client.message_to_dict(response)
            servers.extend(data.get("ldap_servers", []))
            if not response.next_page_token:
                return servers
            request.page_token = response.next_page_token

    def add_role_user(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        return self.change_config(
            pb2.ChangeConfigRequest(
                added_roles=[
                    pb2.Role(
                        index=self.ids["role_id"],
                        name=self.ids["role_name"],
                        comment="codex temporary role, remove after smoke",
                    )
                ],
                added_users=[
                    pb2.User(
                        index=self.ids["user_id"],
                        login=self.ids["login"],
                        name="codex temporary user",
                        comment="codex temporary user, remove after smoke",
                        enabled=True,
                    )
                ],
                added_users_assignments=[
                    pb2.UserAssignment(user_id=self.ids["user_id"], role_id=self.ids["role_id"])
                ],
                modified_user_passwords=[
                    pb2.UserPasswordAssignment(
                        user_index=self.ids["user_id"],
                        password=self.password,
                        must_change_password=False,
                    )
                ],
            )
        )

    def remove_role_user(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        return self.change_config(
            pb2.ChangeConfigRequest(
                removed_users_assignments=[
                    pb2.UserAssignment(user_id=self.ids["user_id"], role_id=self.ids["role_id"])
                ],
                removed_users=[self.ids["user_id"]],
                removed_roles=[self.ids["role_id"]],
            )
        )

    def run_permission_mutations(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        global_pb2 = self.client.import_module("axxonsoft.bl.security.GlobalPermissions_pb2")
        objects_pb2 = self.client.import_module("axxonsoft.bl.security.ObjectsPermissions_pb2")
        groups_pb2 = self.client.import_module("axxonsoft.bl.security.GroupsPermissions_pb2")
        groups_info_pb2 = self.client.import_module("axxonsoft.bl.security.GroupsPermissionsInfo_pb2")

        global_perm = global_pb2.GlobalPermissions(
            unrestricted_access=global_pb2.UNRESTRICTED_ACCESS_NO,
            maps_access=global_pb2.MAP_ACCESS_FORBID,
            alert_access=global_pb2.ALERT_ACCESS_FORBID,
            bookmark_access=global_pb2.BOOKMARK_ACCESS_NO,
            user_rights_setup_access=global_pb2.USER_RIGHTS_SETUP_ACCESS_NO,
        )
        global_perm.feature_access.append(global_pb2.FEATURE_ACCESS_FORBID_ALL)
        global_request = pb2.SetGlobalPermissionsRequest()
        global_request.permissions[self.ids["role_id"]].CopyFrom(global_perm)
        self.stub.SetGlobalPermissions(global_request, timeout=self.args.timeout)
        global_after = self.client.message_to_dict(
            self.stub.ListGlobalPermissions(pb2.ListGlobalPermissionsRequest(role_ids=[self.ids["role_id"]]), timeout=self.args.timeout)
        )

        inventory = self.client.load_inventory()
        camera_ap = next((item.get("access_point", "") for item in inventory.get("cameras", []) if item.get("access_point")), "")
        archive_ap = self.client.archive_access_point()
        object_request = pb2.SetObjectPermissionsRequest()
        object_permissions = objects_pb2.ObjectsPermissions()
        if camera_ap:
            object_permissions.camera_access[camera_ap] = objects_pb2.CAMERA_ACCESS_FORBID
        if archive_ap:
            object_permissions.archive_access[archive_ap] = objects_pb2.ARCHIVE_ACCESS_FORBID
        object_request.role_to_permissions[self.ids["role_id"]].CopyFrom(object_permissions)
        object_response = self.stub.SetObjectPermissions(object_request, timeout=self.args.timeout)

        group_id = ""
        group_info = self.stub.ListGroupsPermissionsInfo(
            groups_info_pb2.ListGroupsPermissionsInfoRequest(role_id=self.ids["role_id"], page_size=10),
            timeout=self.args.timeout,
        )
        if group_info.items:
            group_id = group_info.items[0].id
            group_permissions = groups_pb2.RoleBasedGroupsPermissions(role_id=self.ids["role_id"])
            group_permissions.groups_permissions[group_id].camera_access = objects_pb2.CAMERA_ACCESS_FORBID
            group_permissions.groups_permissions[group_id].microphone_access = objects_pb2.MICROPHONE_ACCESS_FORBID
            group_permissions.groups_permissions[group_id].telemetry_priority = objects_pb2.TELEMETRY_PRIORITY_NO_ACCESS
            self.stub.SetGroupsPermissions(groups_pb2.SetGroupsPermissionsRequest(permissions=[group_permissions]), timeout=self.args.timeout)

        macro_id = ""
        macros = self.stub.ListMacrosPermissionsPaged(
            pb2.ListMacrosPermissionsPagedRequest(role_id=self.ids["role_id"], page_size=10),
            timeout=self.args.timeout,
        )
        if macros.macros_access:
            macro_id = macros.macros_access[0].id
            self.stub.SetMacrosPermissions(
                pb2.SetMacrosPermissionsRequest(
                    role_id=self.ids["role_id"],
                    macros_access={macro_id: objects_pb2.MACROS_ACCESS_FORBID},
                ),
                timeout=self.args.timeout,
            )

        return {
            "global_role_present": self.ids["role_id"] in global_after.get("permissions", {}),
            "object_failed_count": len(object_response.failed),
            "camera_permission_ap_len": len(camera_ap),
            "archive_permission_ap_len": len(archive_ap),
            "group_permission_id_len": len(group_id),
            "macro_permission_id_len": len(macro_id),
        }

    def run_policy_noop_mutation(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        before = self.stub.GetPolicies(pb2.GetPoliciesRequest(), timeout=self.args.timeout)
        request = pb2.ChangeConfigRequest()
        request.modified_pwd_policy.method = pb2.MM_OVERWRITE_DATA
        request.modified_pwd_policy.data.extend(before.pwd_policy)
        request.modified_ip_filters.method = pb2.MM_OVERWRITE_DATA
        request.modified_ip_filters.data.extend(before.ip_filters)
        request.modified_trusted_ip_list.method = pb2.MM_OVERWRITE_DATA
        request.modified_trusted_ip_list.data.extend(before.trusted_ip_list)
        self.stub.ChangeConfig(request, timeout=self.args.timeout)
        after = self.stub.GetPolicies(pb2.GetPoliciesRequest(), timeout=self.args.timeout)
        return {
            "pwd_policy_count_restored": len(before.pwd_policy) == len(after.pwd_policy),
            "ip_filter_count_restored": len(before.ip_filters) == len(after.ip_filters),
            "trusted_ip_count_restored": len(before.trusted_ip_list) == len(after.trusted_ip_list),
            "pwd_policy_count": len(after.pwd_policy),
            "ip_filter_count": len(after.ip_filters),
            "trusted_ip_count": len(after.trusted_ip_list),
        }

    def temp_ldap_server(self, *, friendly_suffix: str) -> Any:
        pb2 = self.security_pb2
        return pb2.LDAPServer(
            index=self.ldap_server_id,
            server_name="127.0.0.1",
            friendly_name=f"codex-temp-ldap-{friendly_suffix}",
            port=389,
            base_dn="dc=codex,dc=local",
            login="cn=codex",
            password=generated_password(),
            use_ssl=False,
            search_filter="(objectClass=person)",
            username_attribute="uid",
            dn_attribute="dn",
            group_search_filter="(objectClass=group)",
        )

    def run_ldap_config_lifecycle(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        before_count = len(self.list_ldap_servers())
        self.change_config(pb2.ChangeConfigRequest(added_ldap_servers=[self.temp_ldap_server(friendly_suffix="added")]))
        after_add = self.list_ldap_servers()
        self.change_config(pb2.ChangeConfigRequest(modified_ldap_servers=[self.temp_ldap_server(friendly_suffix="changed")]))
        after_change = self.list_ldap_servers()
        self.change_config(pb2.ChangeConfigRequest(removed_ldap_servers=[self.ldap_server_id]))
        after_remove = self.list_ldap_servers()
        return {
            "ldap_server_id_len": len(self.ldap_server_id),
            "before_count": before_count,
            "after_remove_count": len(after_remove),
            "present_after_add": any(item.get("index") == self.ldap_server_id for item in after_add),
            "present_after_change": any(
                item.get("index") == self.ldap_server_id and str(item.get("friendly_name", "")).endswith("changed")
                for item in after_change
            ),
            "present_after_remove": any(item.get("index") == self.ldap_server_id for item in after_remove),
        }

    def tfa_verification_codes(self, secret_key: str) -> list[str]:
        now = int(time.time())
        return [
            totp_code(secret_key, for_time=now),
            totp_code(secret_key, for_time=now - 30),
            totp_code(secret_key, for_time=now + 30),
        ]

    def run_tfa_google_auth(self) -> dict[str, Any]:
        pb2 = self.security_pb2
        secret_response = self.stub.GenGoogleAuthSecret(pb2.GenGoogleAuthSecretRequest(), timeout=self.args.timeout)
        secret_key = secret_response.secret_key
        enable_response = self.stub.EnableGoogleAuth(
            pb2.EnableGoogleAuthRequest(
                assignments=[
                    pb2.EnableGoogleAuthRequest.Assignment(user_index=self.ids["user_id"], secret_key=secret_key)
                ]
            ),
            timeout=self.args.timeout,
        )
        enable_results = [pb2.EEnableTFAResult.Name(item.result) for item in enable_response.assignments]
        disable_results: list[str] = []
        attempts = 0
        for verification_code in self.tfa_verification_codes(secret_key):
            attempts += 1
            disable_response = self.stub.DisableGoogleAuth(
                pb2.DisableGoogleAuthRequest(
                    assignments=[
                        pb2.DisableGoogleAuthRequest.Assignment(
                            user_index=self.ids["user_id"],
                            verification_code=verification_code,
                        )
                    ]
                ),
                timeout=self.args.timeout,
            )
            disable_results = [pb2.EDisableTFAResult.Name(item.result) for item in disable_response.assignments]
            if disable_results and all(result == "DTR_OK" for result in disable_results):
                break
        if not disable_results or any(result != "DTR_OK" for result in disable_results):
            raise RuntimeError(f"DisableGoogleAuth failed: {disable_results}")
        return {
            "user_id": self.ids["user_id"],
            "secret_len": len(secret_key),
            "enable_results": enable_results,
            "disable_results": disable_results,
            "disable_attempts": attempts,
        }

    def run_lifecycle(self) -> dict[str, Any]:
        before_roles = len(self.list_roles())
        before_users = len(self.list_users().get("users", []))
        add_response = self.add_role_user()
        permission_mutations = self.run_permission_mutations()
        policy_noop = self.run_policy_noop_mutation()
        ldap_lifecycle = self.run_ldap_config_lifecycle()
        tfa_lifecycle = self.run_tfa_google_auth()
        roles_after_add = self.list_roles()
        users_after_add = self.list_users()
        assigned_users = self.list_users(role_id=self.ids["role_id"])
        remove_response = self.remove_role_user()
        roles_after_remove = self.list_roles()
        users_after_remove = self.list_users()
        role_present_after_add = any(item.get("index") == self.ids["role_id"] for item in roles_after_add)
        user_present_after_add = any(item.get("index") == self.ids["user_id"] for item in users_after_add.get("users", []))
        assigned_user_count = sum(1 for item in assigned_users.get("users", []) if item.get("index") == self.ids["user_id"])
        role_present_after_remove = any(item.get("index") == self.ids["role_id"] for item in roles_after_remove)
        user_present_after_remove = any(item.get("index") == self.ids["user_id"] for item in users_after_remove.get("users", []))
        return {
            "role_id": self.ids["role_id"],
            "user_id": self.ids["user_id"],
            "role_name": self.ids["role_name"],
            "login_len": len(self.ids["login"]),
            "before_roles": before_roles,
            "before_users": before_users,
            "after_roles": len(roles_after_remove),
            "after_users": len(users_after_remove.get("users", [])),
            "add_response_keys": sorted(add_response.keys()),
            "remove_response_keys": sorted(remove_response.keys()),
            "role_present_after_add": role_present_after_add,
            "user_present_after_add": user_present_after_add,
            "assigned_user_count": assigned_user_count,
            "role_present_after_remove": role_present_after_remove,
            "user_present_after_remove": user_present_after_remove,
            "role_count_restored": before_roles == len(roles_after_remove),
            "user_count_restored": before_users == len(users_after_remove.get("users", [])),
            "permission_mutations": permission_mutations,
            "policy_noop": policy_noop,
            "ldap_lifecycle": ldap_lifecycle,
            "tfa_lifecycle": tfa_lifecycle,
        }

    def cleanup(self) -> list[dict[str, Any]]:
        cleanup_results = []
        try:
            users = self.list_users().get("users", [])
            roles = self.list_roles()
            if any(item.get("index") == self.ids["user_id"] for item in users) or any(item.get("index") == self.ids["role_id"] for item in roles):
                body = self.remove_role_user()
                cleanup_results.append({"status": "security_objects_removed", "body_keys": sorted(body.keys())})
        except Exception as exc:
            cleanup_results.append({"status": "security_cleanup_failed", "error": str(exc)[:400]})
        try:
            if any(item.get("index") == self.ldap_server_id for item in self.list_ldap_servers()):
                body = self.change_config(self.security_pb2.ChangeConfigRequest(removed_ldap_servers=[self.ldap_server_id]))
                cleanup_results.append({"status": "ldap_server_removed", "body_keys": sorted(body.keys())})
        except Exception as exc:
            cleanup_results.append({"status": "ldap_cleanup_failed", "error": str(exc)[:400]})
        return cleanup_results

    def run(self) -> dict[str, Any]:
        self.setup()
        start = time.perf_counter()
        try:
            details = self.run_lifecycle()
            status = "PASS"
        except Exception as exc:
            details = {"error_type": exc.__class__.__name__, "error": str(exc)[:800]}
            if self.args.verbose:
                details["traceback"] = traceback.format_exc()
            status = "FAIL"
        cleanup_results = self.cleanup()
        if cleanup_results:
            details["cleanup"] = cleanup_results
        self.results.append(
            {
                "group": "security_user_role_lifecycle",
                "status": status,
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
                "details": details,
            }
        )
        report = self.report()
        self.write_report(report)
        return report

    def report(self) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for result in self.results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {
                "grpc_target": f"{self.args.host}:{self.args.grpc_port}",
                "username": self.args.username,
                "password": "<redacted>",
            },
            "approval_only_operations": SECURITY_MUTATIONS_REQUIRING_APPROVAL,
            "summary": counts,
            "results": self.results,
        }

    def write_report(self, report: dict[str, Any]) -> None:
        self.args.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        json_path = self.args.report_dir / f"security-mutation-smoke-{stamp}.json"
        md_path = self.args.report_dir / f"security-mutation-smoke-{stamp}.md"
        latest_json = self.args.report_dir / "security-mutation-smoke-latest.json"
        latest_md = self.args.report_dir / "security-mutation-smoke-latest.md"
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
            "# Axxon One Security Mutation Smoke",
            "",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- gRPC target: `{self.args.host}:{self.args.grpc_port}`",
            "",
            "Controlled smoke for temporary `codex-*` security records. It does not store generated passwords in the report.",
            "",
            "## Summary",
            "",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Results", "", "| Status | Group | ms | Evidence |", "| --- | --- | ---: | --- |"])
        for result in report["results"]:
            details = result.get("details", {})
            note = (
                details.get("error")
                or (
                    f"role={details.get('role_id', '')} user={details.get('user_id', '')} "
                    f"assigned={details.get('assigned_user_count')} restored_roles={details.get('role_count_restored')} "
                    f"restored_users={details.get('user_count_restored')} perms={bool(details.get('permission_mutations'))} "
                    f"policy_noop={bool(details.get('policy_noop'))} ldap={bool(details.get('ldap_lifecycle'))} "
                    f"tfa={bool(details.get('tfa_lifecycle'))}"
                )
            )
            lines.append(
                f"| {result['status']} | `{result['group']}` | {result['elapsed_ms']} | {str(note).replace('|', '\\|')[:260]} |"
            )
        lines.append("")
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser, repo_root=repo_root)
    parser.add_argument("--report-dir", type=Path, default=repo_root / "docs/api-audit")
    parser.add_argument("--i-understand-this-mutates", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.password:
        parser.error("password is required via --password or AXXON_PASSWORD")
    if not mutation_approved(args):
        parser.error(f"--i-understand-this-mutates and --confirm {CONFIRMATION} are required")
    return args


def main() -> int:
    smoke = SecurityMutationSmoke(parse_args())
    report = smoke.run()
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"].get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
