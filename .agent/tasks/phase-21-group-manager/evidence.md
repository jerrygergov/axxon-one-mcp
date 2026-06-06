# Evidence Bundle: phase-21-group-manager

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — module + gating idiom — PASS
- `tools/axxon_mcp_groups.py` (`AxxonMcpGroups`) exposes read `list_groups` and
  gated writes `change_groups`, `set_objects_membership`. `_write_gate` returns
  `disabled` (env unset) / `gap` (bad token) before any wire call. Env
  `AXXON_GROUPS_APPROVE=1` + confirmation `CONFIRM-groups-set`.
- Proof: `GatingTests` (disabled/gap, no calls recorded); live `[gating]` block in
  raw/live-verify.txt.

## AC2 — list_groups + change_groups — PASS
- `list_groups` returns `{group_id,name,parent,description}` rows. `change_groups`
  is gated, errors with no wire call when no edit field is given, builds
  ChangeGroupsRequest (removed_groups + added/changed Group), sends it.
- Proof: `ReadTests`, `ChangeGroupsTests` (add/remove + changed shape),
  `EmptyInputTests.test_change_groups_no_edit_errors`; live add throwaway group ->
  remove (5 -> 6 -> 5).

## AC3 — set_objects_membership — PASS
- Gated; errors with no wire call when neither added nor removed is given; builds
  SetObjectsMembershipRequest from Membership{group_id,object} lists; returns
  failed_added/failed_removed.
- Proof: `MembershipTests` (add/remove shape),
  `EmptyInputTests.test_membership_no_edit_errors`; live add object membership ->
  remove (failed=0 each).

## AC4 — server registration — PASS
- 6-edit pattern in `tools/axxon_mcp_server.py`: `groups` param,
  `register_groups_tools` call, the function (4 tools), `--enable-groups` flag,
  flag-gated instantiation, passed to `create_server`.
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit + full suite green — PASS
- 10 new tests. Full suite `Ran 781 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp + coverage doc — PASS
- ChangeGroups, SetObjectsMembership -> tested-pass. Coverage 197 pass-class /
  126 pending / 38 fixture-warn; GroupManager 4/4. Restamp dry-run reports 0 after
  --write.

## Stand hygiene
- A throwaway group was added under the Demo root then removed; an object
  membership was added then removed. Stand ends at its original 5 groups with no
  probe membership. Object names must be lowercase `hosts/...`. No proto/CA/PDF
  committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`, group GUIDs
  -> `<uuid>`, Demo root -> `<demo-root>`.
