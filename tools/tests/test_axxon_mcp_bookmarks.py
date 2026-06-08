from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import axxon_mcp_bookmarks as module


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "CONFIG_PASSWORD_SHOULD_NOT_LEAK"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeBookmarkClient:
    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self.calls: list[tuple[str, dict]] = []

    def bookmark_list(self, time_range, *, page_size=100, page_token=""):
        self.calls.append(("list", {"range": time_range, "page_size": page_size, "page_token": page_token}))
        return {
            "body": {
                "bookmarks": [
                    {
                        "id": "bm-1",
                        "message": "front gate review",
                        "user_id": "root",
                        "range": time_range,
                        "creation_time": "20260101T000000.000",
                    }
                ],
                "next_page_token": "",
            }
        }

    def bookmark_get(self, bookmark_id):
        self.calls.append(("get", {"id": bookmark_id}))
        return {"body": {"id": bookmark_id, "message": "front gate review", "user_id": "root"}}


def build_tools(client=None):
    cfg = FakeConfig()
    client = client or FakeBookmarkClient(cfg)
    return module.AxxonMcpBookmarks(
        client_factory=lambda c: client,
        config_factory=lambda: cfg,
    ), client


class BookmarkReadToolTests(unittest.TestCase):
    def test_list_requires_range(self) -> None:
        tools, _ = build_tools()
        result = tools.bookmark_list(time_range={})
        self.assertEqual(result["status"], "error")
        self.assertIn("range", result["message"].lower())

    def test_list_returns_summarized_bookmarks(self) -> None:
        tools, client = build_tools()
        rng = {"begin_time": "a", "end_time": "b"}
        result = tools.bookmark_list(time_range=rng, limit=5)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["bookmarks"][0]["id"], "bm-1")
        self.assertEqual(client.calls[0][1]["range"], rng)

    def test_list_clamps_limit_to_cap(self) -> None:
        tools, client = build_tools()
        tools.bookmark_list(time_range={"begin_time": "a", "end_time": "b"}, limit=99999)
        self.assertLessEqual(client.calls[0][1]["page_size"], module.BOOKMARK_PAGE_CAP)
        self.assertEqual(result_caps(tools), module.BOOKMARK_PAGE_CAP)

    def test_get_returns_bookmark(self) -> None:
        tools, _ = build_tools()
        result = tools.bookmark_get("bm-1")
        self.assertEqual(result["bookmark"]["id"], "bm-1")

    def test_config_summary_does_not_leak_password(self) -> None:
        tools, _ = build_tools()
        connected = tools.bookmark_connect_axxon_profile("env")
        self.assertNotIn("CONFIG_PASSWORD_SHOULD_NOT_LEAK", str(connected))
        self.assertTrue(connected["profile"]["password_present"])


def result_caps(tools) -> int:
    return tools.last_page_size


if __name__ == "__main__":
    unittest.main()
