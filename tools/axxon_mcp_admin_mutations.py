#!/usr/bin/env python3
"""Approval-gated admin mutation workflows for Axxon One MCP."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import os
from pathlib import Path
import secrets
import string
from typing import Any, Callable
import uuid

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import redact_admin_secrets


ADMIN_MUTATION_APPROVE_ENV = "AXXON_ADMIN_MUTATION_APPROVE"

ADMIN_MUTATION_WORKFLOWS: dict[str, dict[str, str]] = {
    "security_user_role_lifecycle": {
        "risk": "security-mutation",
        "summary": "Create, verify, and rollback a temporary codex user/role assignment.",
    },
    "security_role_permissions_update": {
        "risk": "security-mutation",
        "summary": "Apply restrictive permissions to a temporary codex role and rollback.",
    },
    "security_policy_noop_probe": {
        "risk": "security-mutation",
        "summary": "Replay current policy/IP-filter/trusted-IP config as a no-op write.",
    },
    "security_ldap_temp_lifecycle": {
        "risk": "security-mutation",
        "summary": "Add, edit, verify, and remove a temporary loopback LDAP server record.",
    },
    "security_tfa_temp_user_lifecycle": {
        "risk": "security-mutation",
        "summary": "Enable and disable TFA on a temporary codex user with rollback.",
    },
}


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig | None = None) -> AxxonApiClient:
    return AxxonApiClient(config or default_config_factory())


def _approval_from_env() -> bool:
    return os.environ.get(ADMIN_MUTATION_APPROVE_ENV) == "1"


def _confirmation_token(workflow: str) -> str:
    return f"CONFIRM-admin-{workflow}"


def _rollback_confirmation_token(workflow: str) -> str:
    return f"CONFIRM-admin-{workflow}-rollback"


def _generated_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!#$_"
    return "Aa" + "".join(secrets.choice(alphabet) for _ in range(14)) + "123"


def _temp_security_ids(params: dict[str, Any]) -> dict[str, str]:
    role_uuid = str(uuid.uuid4())
    user_uuid = str(uuid.uuid4())
    suffix = user_uuid.replace("-", "")[:12]
    hint = "".join(ch for ch in str(params.get("display_name_hint") or "").lower() if ch.isalnum())[:16]
    name_suffix = f"{hint}-{suffix}" if hint else suffix
    return {
        "role_id": role_uuid,
        "user_id": user_uuid,
        "role_name": f"codex-role-{name_suffix}",
        "login": f"codex_user_{suffix[:8]}",
    }


def _temp_role_state(params: dict[str, Any]) -> dict[str, Any]:
    role_id = str(params.get("role_id") or "")
    role_name = str(params.get("role_name") or "")
    if role_id:
        return {
            "role_id": role_id,
            "role_name": role_name,
            "created_role": False,
            "camera_access_point": str(params.get("camera_access_point") or ""),
            "group_id": str(params.get("group_id") or ""),
            "macro_id": str(params.get("macro_id") or ""),
        }
    role_uuid = str(uuid.uuid4())
    suffix = role_uuid.replace("-", "")[:12]
    hint = "".join(ch for ch in str(params.get("display_name_hint") or "").lower() if ch.isalnum())[:16]
    name_suffix = f"{hint}-{suffix}" if hint else suffix
    return {
        "role_id": role_uuid,
        "role_name": f"codex-role-{name_suffix}",
        "created_role": True,
        "camera_access_point": str(params.get("camera_access_point") or ""),
        "group_id": str(params.get("group_id") or ""),
        "macro_id": str(params.get("macro_id") or ""),
    }


def _codex_role_allowed(params: dict[str, Any]) -> bool:
    role_id = str(params.get("role_id") or "")
    if not role_id:
        return True
    role_name = str(params.get("role_name") or "")
    return role_id.startswith("codex-") or role_name.startswith("codex-")


def _policy_noop_params_allowed(params: dict[str, Any]) -> bool:
    forbidden = {"pwd_policy", "ip_filters", "trusted_ip_list", "modified_pwd_policy", "modified_ip_filters"}
    return not any(key in params for key in forbidden)


def _temp_ldap_state(params: dict[str, Any]) -> dict[str, Any]:
    ldap_id = str(uuid.uuid4())
    suffix = ldap_id.replace("-", "")[:12]
    hint = "".join(ch for ch in str(params.get("display_name_hint") or "").lower() if ch.isalnum())[:16]
    name_suffix = f"{hint}-{suffix}" if hint else suffix
    return {
        "ldap_server_id": ldap_id,
        "friendly_name_add": f"codex-temp-ldap-{name_suffix}-added",
        "friendly_name_change": f"codex-temp-ldap-{name_suffix}-changed",
        "password": _generated_password(),
    }


def _body(response: Any) -> dict[str, Any]:
    if isinstance(response, dict) and isinstance(response.get("body"), dict):
        return response["body"]
    if isinstance(response, dict):
        return response
    return {}


def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


@dataclass
class AxxonAdminMutationRegistry:
    """In-memory plan/apply/verify/rollback scaffold for Phase 5F-B1."""

    client_factory: Callable[[], Any] = default_client_factory
    enabled: bool | None = None
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit: list[dict[str, Any]] = field(default_factory=list)
    client: Any | None = None

    def __post_init__(self) -> None:
        if self.enabled is None:
            self.enabled = _approval_from_env()

    def _audit(self, action: str, payload: dict[str, Any]) -> None:
        entry = {
            "ts": dt.datetime.now(dt.UTC).isoformat(),
            "action": action,
            **redact_admin_secrets(payload),
        }
        self.audit.append(entry)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.client = self.client_factory()
        return self.client

    def list_workflows(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "approval_env": ADMIN_MUTATION_APPROVE_ENV,
            "enabled": bool(self.enabled),
            "workflows": [
                {"name": name, **metadata}
                for name, metadata in sorted(ADMIN_MUTATION_WORKFLOWS.items())
            ],
        }

    def plan(self, workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if workflow not in ADMIN_MUTATION_WORKFLOWS:
            result = {
                "status": "gap",
                "workflow": workflow,
                "message": f"{workflow} is not in Phase 5F-B1 scope.",
            }
            self._audit("plan_gap", result)
            return result
        clean_params = redact_admin_secrets(dict(params or {}))
        if workflow == "security_role_permissions_update" and not _codex_role_allowed(dict(params or {})):
            result = {
                "status": "rejected",
                "workflow": workflow,
                "reason": "non-codex-role-target",
                "message": "5F-B1 only mutates generated or explicitly codex-* roles.",
            }
            self._audit("plan_rejected", result)
            return result
        if workflow == "security_policy_noop_probe" and not _policy_noop_params_allowed(dict(params or {})):
            result = {
                "status": "rejected",
                "workflow": workflow,
                "reason": "caller-policy-payload-not-allowed",
                "message": "5F-B1 policy probe replays the current snapshot only.",
            }
            self._audit("plan_rejected", result)
            return result
        plan_id = f"admin-{workflow}-{uuid.uuid4()}"
        plan = {
            "status": "planned",
            "plan_id": plan_id,
            "workflow": workflow,
            "risk": ADMIN_MUTATION_WORKFLOWS[workflow]["risk"],
            "summary": ADMIN_MUTATION_WORKFLOWS[workflow]["summary"],
            "params": clean_params,
            "confirmation_token": _confirmation_token(workflow),
            "rollback_confirmation_token": _rollback_confirmation_token(workflow),
            "enabled": bool(self.enabled),
            "applied": False,
            "rolled_back": False,
        }
        if workflow == "security_user_role_lifecycle":
            state = _temp_security_ids(clean_params)
            state["password"] = _generated_password()
            plan["_state"] = state
            plan["expected"] = {
                "role_id": state["role_id"],
                "user_id": state["user_id"],
                "role_name": state["role_name"],
                "login": state["login"],
            }
        elif workflow == "security_role_permissions_update":
            state = _temp_role_state(dict(params or {}))
            plan["_state"] = state
            plan["expected"] = {
                "role_id": state["role_id"],
                "role_name": state["role_name"],
                "created_role": state["created_role"],
            }
        elif workflow == "security_policy_noop_probe":
            plan["_state"] = {}
            plan["expected"] = {"policy_payload": "current-snapshot-only"}
        elif workflow == "security_ldap_temp_lifecycle":
            state = _temp_ldap_state(dict(params or {}))
            plan["_state"] = state
            plan["expected"] = {
                "ldap_server_id": state["ldap_server_id"],
                "friendly_name_change": state["friendly_name_change"],
            }
        self.plans[plan_id] = plan
        self._audit("plan", _public_plan(plan))
        return _public_plan(plan)

    def _plan_or_gap(self, plan_id: str) -> dict[str, Any]:
        plan = self.plans.get(plan_id)
        if plan is None:
            return {"status": "gap", "plan_id": plan_id, "message": "Unknown admin mutation plan id."}
        return plan

    def apply(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("apply_gap", plan)
            return plan
        if not self.enabled:
            result = {
                "status": "rejected",
                "plan_id": plan_id,
                "message": f"Set {ADMIN_MUTATION_APPROVE_ENV}=1 before applying admin mutations.",
            }
            self._audit("apply_rejected", result)
            return result
        if confirmation != plan["confirmation_token"]:
            result = {"status": "rejected", "plan_id": plan_id, "reason": "confirmation-token-mismatch"}
            self._audit("apply_rejected", result)
            return result
        if plan["workflow"] == "security_user_role_lifecycle":
            result = self._apply_security_user_role_lifecycle(plan)
            self._audit("apply", result)
            return result
        if plan["workflow"] == "security_role_permissions_update":
            result = self._apply_security_role_permissions_update(plan)
            self._audit("apply", result)
            return result
        if plan["workflow"] == "security_policy_noop_probe":
            result = self._apply_security_policy_noop_probe(plan)
            self._audit("apply", result)
            return result
        if plan["workflow"] == "security_ldap_temp_lifecycle":
            result = self._apply_security_ldap_temp_lifecycle(plan)
            self._audit("apply", result)
            return result
        result = {
            "status": "fixture-needed",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "message": "Workflow scaffold is present; mutation implementation is added in later tasks.",
        }
        plan["applied"] = True
        self._audit("apply", result)
        return result

    def verify(self, plan_id: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("verify_gap", plan)
            return plan
        if plan["workflow"] == "security_user_role_lifecycle":
            result = self._verify_security_user_role_lifecycle(plan)
            self._audit("verify", result)
            return result
        if plan["workflow"] == "security_role_permissions_update":
            result = self._verify_security_role_permissions_update(plan)
            self._audit("verify", result)
            return result
        if plan["workflow"] == "security_policy_noop_probe":
            result = self._verify_security_policy_noop_probe(plan)
            self._audit("verify", result)
            return result
        if plan["workflow"] == "security_ldap_temp_lifecycle":
            result = self._verify_security_ldap_temp_lifecycle(plan)
            self._audit("verify", result)
            return result
        result = {
            "status": "fixture-needed",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "message": "Workflow verification is added in later tasks.",
        }
        self._audit("verify", result)
        return result

    def rollback(self, plan_id: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan_or_gap(plan_id)
        if plan.get("status") == "gap":
            self._audit("rollback_gap", plan)
            return plan
        if not self.enabled:
            result = {
                "status": "rejected",
                "plan_id": plan_id,
                "message": f"Set {ADMIN_MUTATION_APPROVE_ENV}=1 before rolling back admin mutations.",
            }
            self._audit("rollback_rejected", result)
            return result
        if confirmation != plan["rollback_confirmation_token"]:
            result = {"status": "rejected", "plan_id": plan_id, "reason": "confirmation-token-mismatch"}
            self._audit("rollback_rejected", result)
            return result
        if plan["workflow"] == "security_user_role_lifecycle":
            result = self._rollback_security_user_role_lifecycle(plan)
            self._audit("rollback", result)
            return result
        if plan["workflow"] == "security_role_permissions_update":
            result = self._rollback_security_role_permissions_update(plan)
            self._audit("rollback", result)
            return result
        if plan["workflow"] == "security_policy_noop_probe":
            result = self._rollback_security_policy_noop_probe(plan)
            self._audit("rollback", result)
            return result
        if plan["workflow"] == "security_ldap_temp_lifecycle":
            result = self._rollback_security_ldap_temp_lifecycle(plan)
            self._audit("rollback", result)
            return result
        result = {
            "status": "fixture-needed",
            "plan_id": plan_id,
            "workflow": plan["workflow"],
            "message": "Workflow rollback is added in later tasks.",
        }
        plan["rolled_back"] = True
        self._audit("rollback", result)
        return result

    def audit_log(self) -> dict[str, Any]:
        return {"entries": list(self.audit)}

    def _apply_security_user_role_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        payload = {
            "added_roles": [
                {
                    "index": state["role_id"],
                    "name": state["role_name"],
                    "comment": "codex temporary role, remove after smoke",
                }
            ],
            "added_users": [
                {
                    "index": state["user_id"],
                    "login": state["login"],
                    "name": "codex temporary user",
                    "comment": "codex temporary user, remove after smoke",
                    "enabled": True,
                }
            ],
            "added_users_assignments": [{"user_id": state["user_id"], "role_id": state["role_id"]}],
            "modified_user_passwords": [
                {
                    "user_index": state["user_id"],
                    "password": state["password"],
                    "must_change_password": False,
                }
            ],
        }
        response = _body(client.security_change_config(payload))
        plan["applied"] = True
        return {
            "status": "applied",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_id": state["role_id"],
            "user_id": state["user_id"],
            "role_name": state["role_name"],
            "login": state["login"],
            "response_keys": sorted(str(key) for key in response.keys()),
        }

    def _verify_security_user_role_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        roles = _body(client.security_list_roles()).get("roles", [])
        users_body = _body(client.security_list_users(role_ids=[state["role_id"]]))
        users = users_body.get("users", [])
        assignments = users_body.get("user_assignments", [])
        role_present = any(item.get("index") == state["role_id"] for item in roles if isinstance(item, dict))
        user_present = any(item.get("index") == state["user_id"] for item in users if isinstance(item, dict))
        assigned_user_count = sum(
            1
            for item in assignments
            if isinstance(item, dict)
            and item.get("user_id") == state["user_id"]
            and item.get("role_id") == state["role_id"]
        )
        return {
            "status": "verified" if role_present and user_present and assigned_user_count == 1 else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_present": role_present,
            "user_present": user_present,
            "assigned_user_count": assigned_user_count,
        }

    def _rollback_security_user_role_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        payload = {
            "removed_users_assignments": [{"user_id": state["user_id"], "role_id": state["role_id"]}],
            "removed_users": [state["user_id"]],
            "removed_roles": [state["role_id"]],
        }
        response = _body(client.security_change_config(payload))
        roles = _body(client.security_list_roles()).get("roles", [])
        users = _body(client.security_list_users()).get("users", [])
        role_present = any(item.get("index") == state["role_id"] for item in roles if isinstance(item, dict))
        user_present = any(item.get("index") == state["user_id"] for item in users if isinstance(item, dict))
        plan["rolled_back"] = True
        return {
            "status": "rolled-back" if not role_present and not user_present else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_removed": not role_present,
            "user_removed": not user_present,
            "response_keys": sorted(str(key) for key in response.keys()),
        }

    def _apply_security_role_permissions_update(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        if state.get("created_role"):
            client.security_change_config(
                {
                    "added_roles": [
                        {
                            "index": state["role_id"],
                            "name": state["role_name"],
                            "comment": "codex temporary permission role, remove after smoke",
                        }
                    ]
                }
            )
        global_permissions = {
            "unrestricted_access": "UNRESTRICTED_ACCESS_NO",
            "maps_access": "MAP_ACCESS_FORBID",
            "alert_access": "ALERT_ACCESS_FORBID",
            "bookmark_access": "BOOKMARK_ACCESS_NO",
            "user_rights_setup_access": "USER_RIGHTS_SETUP_ACCESS_NO",
            "feature_access": ["FEATURE_ACCESS_FORBID_ALL"],
        }
        global_response = _body(client.security_set_global_permissions(state["role_id"], global_permissions))
        object_failed_count = 0
        if state.get("camera_access_point"):
            object_response = _body(
                client.security_set_object_permissions(
                    state["role_id"],
                    {"camera_access": {state["camera_access_point"]: "CAMERA_ACCESS_FORBID"}},
                )
            )
            object_failed_count = len(object_response.get("failed", []))
        group_permission_count = 0
        if state.get("group_id"):
            group_response = _body(
                client.security_set_groups_permissions(
                    [
                        {
                            "role_id": state["role_id"],
                            "groups_permissions": {
                                state["group_id"]: {
                                    "camera_access": "CAMERA_ACCESS_FORBID",
                                    "microphone_access": "MICROPHONE_ACCESS_FORBID",
                                    "telemetry_priority": "TELEMETRY_PRIORITY_NO_ACCESS",
                                }
                            },
                        }
                    ]
                )
            )
            group_permission_count = 0 if group_response.get("failed") else 1
        macro_permission_count = 0
        if state.get("macro_id"):
            macro_response = _body(
                client.security_set_macros_permissions(
                    state["role_id"],
                    {state["macro_id"]: "MACROS_ACCESS_FORBID"},
                )
            )
            macro_permission_count = 0 if macro_response.get("failed") else 1
        plan["applied"] = True
        return {
            "status": "applied",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_id": state["role_id"],
            "role_name": state["role_name"],
            "global_role_present": state["role_id"] in (global_response.get("permissions") or {}),
            "object_failed_count": object_failed_count,
            "group_permission_count": group_permission_count,
            "macro_permission_count": macro_permission_count,
        }

    def _verify_security_role_permissions_update(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        global_data = _body(client.security_list_global_permissions([state["role_id"]]))
        permissions = global_data.get("permissions") if isinstance(global_data.get("permissions"), dict) else {}
        roles = _body(client.security_list_roles()).get("roles", [])
        role_present = any(item.get("index") == state["role_id"] for item in roles if isinstance(item, dict))
        global_role_present = state["role_id"] in permissions
        return {
            "status": "verified" if global_role_present and (role_present or not state.get("created_role")) else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_present": role_present,
            "global_role_present": global_role_present,
            "permission_key_count": len(permissions.get(state["role_id"], {})) if global_role_present else 0,
        }

    def _rollback_security_role_permissions_update(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        response: dict[str, Any] = {}
        if state.get("created_role"):
            response = _body(client.security_change_config({"removed_roles": [state["role_id"]]}))
        roles = _body(client.security_list_roles()).get("roles", [])
        role_present = any(item.get("index") == state["role_id"] for item in roles if isinstance(item, dict))
        plan["rolled_back"] = True
        return {
            "status": "rolled-back" if not role_present or not state.get("created_role") else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "role_removed": not role_present if state.get("created_role") else False,
            "response_keys": sorted(str(key) for key in response.keys()),
        }

    def _policy_counts(self) -> dict[str, int]:
        data = _body(self.ensure_client().security_get_policies())
        return {
            "pwd_policy_count": len(data.get("pwd_policy", [])),
            "ip_filter_count": len(data.get("ip_filters", [])),
            "trusted_ip_count": len(data.get("trusted_ip_list", [])),
        }

    def _apply_security_policy_noop_probe(self, plan: dict[str, Any]) -> dict[str, Any]:
        client = self.ensure_client()
        before = _body(client.security_get_policies())
        payload = {
            "modified_pwd_policy": {"method": "MM_OVERWRITE_DATA", "data": list(before.get("pwd_policy", []))},
            "modified_ip_filters": {"method": "MM_OVERWRITE_DATA", "data": list(before.get("ip_filters", []))},
            "modified_trusted_ip_list": {
                "method": "MM_OVERWRITE_DATA",
                "data": list(before.get("trusted_ip_list", [])),
            },
        }
        client.security_change_config(payload)
        counts = self._policy_counts()
        plan["_state"]["policy_counts"] = counts
        plan["applied"] = True
        return {
            "status": "applied",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            **counts,
        }

    def _verify_security_policy_noop_probe(self, plan: dict[str, Any]) -> dict[str, Any]:
        expected = dict((plan.get("_state") or {}).get("policy_counts") or {})
        current = self._policy_counts()
        return {
            "status": "verified" if current == expected else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "policy_counts_restored": current == expected,
            **current,
        }

    def _rollback_security_policy_noop_probe(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan["rolled_back"] = True
        return {
            "status": "rolled-back",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "message": "Policy no-op probe already restored the current snapshot.",
        }

    def _ldap_server_payload(self, state: dict[str, Any], friendly_name: str) -> dict[str, Any]:
        return {
            "index": state["ldap_server_id"],
            "server_name": "127.0.0.1",
            "friendly_name": friendly_name,
            "port": 389,
            "base_dn": "dc=codex,dc=local",
            "login": "cn=codex",
            "password": state["password"],
            "use_ssl": False,
            "search_filter": "(objectClass=person)",
            "username_attribute": "uid",
            "dn_attribute": "dn",
            "group_search_filter": "(objectClass=group)",
        }

    def _apply_security_ldap_temp_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        client.security_change_config(
            {"added_ldap_servers": [self._ldap_server_payload(state, state["friendly_name_add"])]}
        )
        after_add = _body(client.security_list_ldap_servers()).get("ldap_servers", [])
        client.security_change_config(
            {"modified_ldap_servers": [self._ldap_server_payload(state, state["friendly_name_change"])]}
        )
        after_change = _body(client.security_list_ldap_servers()).get("ldap_servers", [])
        present_after_add = any(item.get("index") == state["ldap_server_id"] for item in after_add if isinstance(item, dict))
        present_after_change = any(
            item.get("index") == state["ldap_server_id"]
            and item.get("friendly_name") == state["friendly_name_change"]
            for item in after_change
            if isinstance(item, dict)
        )
        plan["applied"] = True
        return {
            "status": "applied" if present_after_add and present_after_change else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "ldap_server_id_len": len(state["ldap_server_id"]),
            "present_after_add": present_after_add,
            "present_after_change": present_after_change,
        }

    def _verify_security_ldap_temp_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        servers = _body(self.ensure_client().security_list_ldap_servers()).get("ldap_servers", [])
        present_after_change = any(
            item.get("index") == state["ldap_server_id"]
            and item.get("friendly_name") == state["friendly_name_change"]
            for item in servers
            if isinstance(item, dict)
        )
        return {
            "status": "verified" if present_after_change else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "present_after_change": present_after_change,
        }

    def _rollback_security_ldap_temp_lifecycle(self, plan: dict[str, Any]) -> dict[str, Any]:
        state = dict(plan.get("_state") or {})
        client = self.ensure_client()
        client.security_change_config({"removed_ldap_servers": [state["ldap_server_id"]]})
        servers = _body(client.security_list_ldap_servers()).get("ldap_servers", [])
        present_after_remove = any(item.get("index") == state["ldap_server_id"] for item in servers if isinstance(item, dict))
        plan["rolled_back"] = True
        return {
            "status": "rolled-back" if not present_after_remove else "warn",
            "plan_id": plan["plan_id"],
            "workflow": plan["workflow"],
            "ldap_removed": not present_after_remove,
        }
