from __future__ import annotations

import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_bookmarks_smoke as module


def make_args(report_dir, *, camera_access_point="", begin_time="", end_time=""):
    return types.SimpleNamespace(
        host="100.0.0.5",
        grpc_port=20109,
        http_port=80,
        http_url="http://100.0.0.5",
        username="root",
        password="root",
        tls_cn="Server",
        ca=Path("/tmp/ca.crt"),
        report_dir=report_dir,
        camera_access_point=camera_access_point,
        begin_time=begin_time,
        end_time=end_time,
        verbose=False,
    )


class FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_workflows(self):
        return {"status": "ok", "workflows": [{"name": "bookmark_lifecycle"}]}

    def plan(self, workflow, params=None):
        self.calls.append("plan")
        return {
            "status": "planned",
            "plan_id": "bookmark-bookmark_lifecycle-1",
            "confirmation_token": "CONFIRM-bookmark-bookmark_lifecycle",
            "rollback_confirmation_token": "CONFIRM-bookmark-bookmark_lifecycle-rollback",
        }

    def apply(self, plan_id, confirmation):
        self.calls.append("apply")
        return {"status": "applied", "bookmark_id": "bm-created-1"}

    def verify(self, plan_id):
        self.calls.append("verify")
        return {"status": "verified", "bookmark_present": True}

    def rollback(self, plan_id, confirmation):
        self.calls.append("rollback")
        return {"status": "rolled-back", "bookmark_removed": True}


class FakeListClient:
    def __init__(self) -> None:
        self.host = "100.0.0.5"

    def bookmark_list(self, time_range, *, page_size=100, page_token=""):
        return {"body": {"bookmarks": [], "next_page_token": ""}}


class SanitizeTests(unittest.TestCase):
    def test_rejects_cli_connection_flags(self) -> None:
        forbidden = module._cli_connection_flags(["--host", "x", "--password=y", "--report-dir", "z"])
        self.assertIn("--host", forbidden)
        self.assertIn("--password", forbidden)
        self.assertNotIn("--report-dir", forbidden)

    def test_sanitize_redacts_host_and_user(self) -> None:
        smoke = module.BookmarksSmoke(make_args(Path("/tmp")), registry=FakeRegistry(), client=FakeListClient())
        clean = smoke.sanitize({"host": "100.0.0.5", "username": "root", "note": "ok"})
        self.assertNotIn("100.0.0.5", str(clean))
        self.assertEqual(clean["username"], "<demo-user>")


class RunTests(unittest.TestCase):
    def test_run_writes_sanitized_report_skipped_without_approval(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            registry = FakeRegistry()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AXXON_BOOKMARK_MUTATION_APPROVE", None)
                smoke = module.BookmarksSmoke(make_args(report_dir), registry=registry, client=FakeListClient())
                report = smoke.run()
            self.assertEqual(report["summary"].get("FAIL", 0), 0)
            self.assertIn("plan", registry.calls)
            self.assertNotIn("apply", registry.calls)
            lifecycle = [r for r in report["results"] if r["group"] == "bookmark_lifecycle"][0]
            self.assertEqual(lifecycle["status"], "WARN")
            latest = report_dir / "phase-5g-bookmarks-smoke-latest.json"
            self.assertTrue(latest.exists())
            self.assertNotIn("100.0.0.5", latest.read_text())

    def test_run_fixture_needed_when_approved_without_camera(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeRegistry()
            with mock.patch.dict(os.environ, {"AXXON_BOOKMARK_MUTATION_APPROVE": "1"}):
                smoke = module.BookmarksSmoke(make_args(Path(tmp)), registry=registry, client=FakeListClient())
                report = smoke.run()
            lifecycle = [r for r in report["results"] if r["group"] == "bookmark_lifecycle"][0]
            self.assertEqual(lifecycle["status"], "WARN")
            self.assertNotIn("apply", registry.calls)

    def test_run_exercises_lifecycle_when_approved_with_fixture(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeRegistry()
            args = make_args(
                Path(tmp),
                camera_access_point="hosts/X/Camera.1",
                begin_time="20260101T000000.000",
                end_time="20260101T010000.000",
            )
            with mock.patch.dict(os.environ, {"AXXON_BOOKMARK_MUTATION_APPROVE": "1"}):
                smoke = module.BookmarksSmoke(args, registry=registry, client=FakeListClient())
                report = smoke.run()
            self.assertEqual(report["summary"].get("FAIL", 0), 0)
            self.assertIn("apply", registry.calls)
            self.assertIn("rollback", registry.calls)

    def test_run_marks_read_pass(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            smoke = module.BookmarksSmoke(make_args(Path(tmp)), registry=FakeRegistry(), client=FakeListClient())
            report = smoke.run()
            read_results = [r for r in report["results"] if r["group"] == "bookmark_list"]
            self.assertEqual(read_results[0]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
