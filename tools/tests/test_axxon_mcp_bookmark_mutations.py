from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_bookmark_mutations as module


class FakeBookmarkMutationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.store: dict[str, dict] = {}

    def bookmark_create(self, bookmark):
        self.calls.append(("create", {"bookmark": bookmark}))
        bookmark_id = "bm-created-1"
        stored = dict(bookmark)
        stored["id"] = bookmark_id
        self.store[bookmark_id] = stored
        return {"body": {"bookmark": {"id": bookmark_id}}}

    def bookmark_get(self, bookmark_id):
        self.calls.append(("get", {"id": bookmark_id}))
        item = self.store.get(bookmark_id)
        if item is None:
            return {"body": {"errorMessage": "Bookmark was not found.", "grpcErrorCode": 5}}
        return {"body": {"bookmark": dict(item)}}

    def bookmark_delete(self, bookmark_id):
        self.calls.append(("delete", {"id": bookmark_id}))
        self.store.pop(bookmark_id, None)
        return {"body": {}}


def build_registry(client=None, enabled=True):
    client = client or FakeBookmarkMutationClient()
    return module.AxxonBookmarkMutationRegistry(
        client_factory=lambda: client,
        enabled=enabled,
    ), client


class BookmarkMutationPlanTests(unittest.TestCase):
    def test_plan_unknown_workflow_is_gap(self) -> None:
        registry, _ = build_registry()
        result = registry.plan("nope")
        self.assertEqual(result["status"], "gap")

    def test_plan_rejects_non_codex_message(self) -> None:
        registry, _ = build_registry()
        result = registry.plan(
            "bookmark_lifecycle",
            {"camera_access_point": "hosts/X/Camera.1", "range": {"begin_time": "a", "end_time": "b"}, "message": "not allowed"},
        )
        self.assertEqual(result["status"], "rejected")

    def test_plan_emits_tokens(self) -> None:
        registry, _ = build_registry()
        result = registry.plan(
            "bookmark_lifecycle",
            {"camera_access_point": "hosts/X/Camera.1", "range": {"begin_time": "a", "end_time": "b"}},
        )
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["confirmation_token"], "CONFIRM-bookmark-bookmark_lifecycle")
        self.assertEqual(result["rollback_confirmation_token"], "CONFIRM-bookmark-bookmark_lifecycle-rollback")
        self.assertNotIn("_state", result)


class BookmarkMutationFixtureNeededTests(unittest.TestCase):
    def test_apply_without_fixture_returns_fixture_needed(self) -> None:
        registry, client = build_registry()
        plan = registry.plan("bookmark_lifecycle", {})
        result = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(result["status"], "fixture-needed")
        self.assertIn("camera_access_point", result["required"])
        self.assertIn("range", result["required"])
        self.assertEqual(client.calls, [])


class BookmarkMutationAppliedTests(unittest.TestCase):
    def _planned(self, registry):
        return registry.plan(
            "bookmark_lifecycle",
            {"camera_access_point": "hosts/X/Camera.1", "range": {"begin_time": "20260101T000000.000", "end_time": "20260101T010000.000"}},
        )

    def test_apply_rejected_without_env(self) -> None:
        registry, _ = build_registry(enabled=False)
        plan = self._planned(registry)
        result = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(result["status"], "rejected")

    def test_apply_rejected_on_bad_token(self) -> None:
        registry, _ = build_registry()
        plan = self._planned(registry)
        result = registry.apply(plan["plan_id"], "wrong")
        self.assertEqual(result["status"], "rejected")

    def test_apply_creates_bookmark(self) -> None:
        registry, client = build_registry()
        plan = self._planned(registry)
        result = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["bookmark_id"], "bm-created-1")
        self.assertEqual(client.calls[0][0], "create")
        sent = client.calls[0][1]["bookmark"]
        self.assertEqual(
            sent["camera_descriptions"],
            {"descriptions": [{"camera_access_point": "hosts/X/Camera.1"}]},
        )

    def test_verify_finds_created_bookmark(self) -> None:
        registry, _ = build_registry()
        plan = self._planned(registry)
        registry.apply(plan["plan_id"], plan["confirmation_token"])
        result = registry.verify(plan["plan_id"])
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["bookmark_present"])

    def test_rollback_deletes_bookmark(self) -> None:
        registry, client = build_registry()
        plan = self._planned(registry)
        registry.apply(plan["plan_id"], plan["confirmation_token"])
        result = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(result["status"], "rolled-back")
        self.assertTrue(result["bookmark_removed"])
        self.assertNotIn("bm-created-1", client.store)

    def test_codex_message_default_prefix(self) -> None:
        registry, client = build_registry()
        plan = self._planned(registry)
        registry.apply(plan["plan_id"], plan["confirmation_token"])
        created = client.store["bm-created-1"]
        self.assertTrue(str(created.get("message", "")).startswith("codex"))


if __name__ == "__main__":
    unittest.main()
