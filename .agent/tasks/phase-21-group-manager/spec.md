# Spec: phase-21-group-manager

## Original task statement
Close the two pending GroupManager mutations (`ChangeGroups`,
`SetObjectsMembership`) so the service reaches 4/4 tested-pass. Ship them as
approval-gated MCP tools behind a new `--enable-groups` flag, live-verify both
reversibly against the demo stand, and restamp the corpus. Both writes are
reversible (add group then remove; add object membership then remove).

## Acceptance criteria
- **AC1**: New module `tools/axxon_mcp_groups.py` (`AxxonMcpGroups`) mirrors the
  audit-injector gating idiom. `_write_gate(confirmation)` returns
  `{"status":"disabled"}` when `AXXON_GROUPS_APPROVE` != "1", `{"status":"gap"}`
  on a wrong confirmation token, and `None` (proceed) only when both pass. No wire
  call happens before the gate passes.
- **AC2**: `list_groups(tree=False)` reads via `ListGroups` returning the group
  list ({group_id,name,parent,description}). `change_groups(removed_groups=None,
  added_groups=None, changed_groups=None, confirmation="")` is gated, errors with
  `{"status":"error"}` (no wire call) when no edit field is given, builds
  `ChangeGroupsRequest` (removed_groups + added/changed `Group` from
  {group_id,name,parent?,description?}), sends ChangeGroups, returns applied with
  the affected ids.
- **AC3**: `set_objects_membership(added=None, removed=None, confirmation="")` is
  gated, errors (no wire call) when neither added nor removed is given, builds
  `SetObjectsMembershipRequest` from `Membership{group_id,object}` lists, sends
  the RPC, returns applied with `failed_added`/`failed_removed` counts+lists.
- **AC4**: `tools/axxon_mcp_server.py` registers the tools behind a new
  `--enable-groups` flag using the established 6-edit pattern: `groups` param on
  `create_server`, registration call, `register_groups_tools` (4 tools:
  `groups_connect_axxon_profile`, `list_groups`, `change_groups`,
  `set_objects_membership`), `--enable-groups` CLI flag, flag-gated instantiation
  in `main`, and the value passed to `create_server`.
- **AC5**: Unit tests in `tools/tests/test_axxon_mcp_groups.py` (fake pb2
  stand-ins) cover: list read, gating (disabled/gap with no wire call recorded),
  no-edit error (no wire call) for both writes, change_groups add/remove request
  shape, and set_objects_membership add/remove request shape. Full suite stays
  green (`python3.12 -m unittest discover -s tools/tests`).
- **AC6**: `tools/axxon_corpus_restamp.py` restamps `ChangeGroups` and
  `SetObjectsMembership` to `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json`
  reflects it (GroupManager 4/4); coverage doc count moves to 197 pass-class /
  126 pending / 38 fixture-warn and notes GroupManager 4/4. Restamp dry-run
  reports 0 after `--write`.

## Constraints
- Probe-first already done: both RPCs live-verified reversibly through direct gRPC
  against the stand before any code (see raw/live-verify.txt). A throwaway group
  was added under the Demo root then removed; an object membership was added then
  removed. Stand ends at its original 5 groups.
- Membership `object` is a lowercase access-point name, e.g.
  `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0` (uppercase HOSTS/ fails
  with "Can not parse name").
- GroupManager carries no etag; writes are plain field builds. ChangeGroups
  returns google.protobuf.Empty; SetObjectsMembership returns failed lists.
- Reuse the timezone/server_settings module idiom exactly (dataclass, factories,
  `connect_axxon_profile`/`ensure_client`, `_stub_and_pb2`, `_write_gate`).
- Secrets env-only; never hardcode creds in the repo.
- Committed evidence sanitized: host -> `<demo-host>`, creds -> `<redacted>`,
  group GUIDs -> `<uuid>`. Node name `Server` and `hosts/Server/...` object names
  may stay. No proto/CA/PDF committed.
- TDD: write the unit tests first, watch them fail, then implement.

## Non-goals
- No group permissions editing (the Group.permissions subtree is out of scope).
- No recursive tree builder beyond what ListGroups returns flat.
- changed_groups_info is plumbed through but the live proof focuses on add/remove
  (the reversible path).

## Gating idiom
- Env `AXXON_GROUPS_APPROVE=1`, confirmation token `CONFIRM-groups-set`.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_groups"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_groups.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
