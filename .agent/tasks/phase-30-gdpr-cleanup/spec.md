# Spec: phase-30-gdpr-cleanup

## Original task statement
Close the two GDPR user-data cleanup gaps that can be live-verified with zero
collateral: `LayoutManager.UserDataCleanup` and `MapService.UserDataCleanup`. Both
take `{repeated user_ids}` and remove that user's layouts/maps. With a throwaway user
id that owns nothing, the RPC executes successfully and deletes nothing real, giving a
genuine live pass without destroying any data on the shared stand. Ship a single
approval-gated GDPR-cleanup module (mutations, so gated like the audit-injector idiom).

Probe results (live, <demo-host>):
- LayoutManager.UserDataCleanup(user_ids=["axxon-mcp-nonexistent-<rand>"]) -> {} (ok).
- MapService.UserDataCleanup(user_ids=["axxon-mcp-nonexistent-<rand>"]) -> {} (ok).
  Both responses are empty messages; both executed and deleted nothing real.
- VMDAService.Cleanup deliberately NOT included: it wipes a real camera's analytics DB
  on the shared stand (collateral on data we did not create); deferred.
- EMailNotifier.SendEMail / GSMNotifier.SendSMS deferred: no notifier/SMTP/GSM infra
  configured on the stand ("Can't resolve reference to .../NotifyService"); they are
  environment-walled, not permission-walled, so they cannot be honestly live-passed.

## Acceptance criteria

- AC1: New module `tools/axxon_mcp_gdpr_cleanup.py` defines `AxxonMcpGdprCleanup` with
  the gated idiom: env `AXXON_GDPR_APPROVE=1` + per-call confirmation token
  `CONFIRM-gdpr-cleanup`. `_write_gate(confirmation)` returns {"status":"disabled"}
  when the env is unset, {"status":"gap"} on a wrong token, and None to proceed BEFORE
  any wire call. Empty `user_ids` returns {"status":"error"} with no wire call.
- AC2: Two tools — `layout_user_data_cleanup(user_ids, confirmation)` and
  `map_user_data_cleanup(user_ids, confirmation)` — call LayoutManager.UserDataCleanup
  and MapService.UserDataCleanup respectively, returning {"status":"applied", tool,
  user_ids}. A connect tool + ensure_client/_stub_and_pb2 mirror the groups module.
- AC3: Server wired with the 6-edit pattern: create_server param `gdpr_cleanup`,
  conditional register call, `register_gdpr_cleanup_tools`, `--enable-gdpr-cleanup`
  CLI flag, flag-gated instantiation in main, passed into create_server.
- AC4: Unit tests in tools/tests cover: disabled (env off), gap (bad token), error
  (empty ids), applied (good token records the right RPC + user_ids), and no config
  secret leak. Full suite `python3.12 -m unittest discover -s tools/tests` green.
- AC5: Corpus restamp `("LayoutManager","UserDataCleanup")` and
  `("MapService","UserDataCleanup")` -> tested-pass; restamp dry-run 0 after --write.
  Coverage doc updated (count + new item). Live verify with throwaway ids recorded in
  raw/live-verify.txt.

## Constraints
- Mutations are approval-gated (env + token), default-off.
- Live verification uses ONLY throwaway/nonexistent user ids so nothing real is
  deleted. No VMDA Cleanup, no notifier sends in this phase.
- Reuse the groups-module gating idiom and the 6-edit server registration pattern.

## Non-goals
- VMDAService.Cleanup (destructive on shared analytics data) — deferred.
- EMailNotifier.SendEMail / GSMNotifier.SendSMS — environment-walled, deferred.

## Verification plan
- Build: pyimport smoke (server + new module import clean)
- Unit tests: disabled/gap/error/applied/no-leak for both tools
- Integration tests: full suite discover
- Lint: n/a (repo convention)
- Manual checks: live layout_user_data_cleanup + map_user_data_cleanup with a throwaway
  id and the real token -> status applied; disabled without env; gap on bad token;
  restamp dry-run == 0 after write
