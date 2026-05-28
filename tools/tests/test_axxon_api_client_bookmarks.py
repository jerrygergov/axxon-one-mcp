from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig

BOOKMARK_SVC = "axxonsoft.bl.bookmarks.BookmarkService"


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local",
            grpc_port=20109,
            http_port=80,
            http_url="http://example.local",
            username="fixture-admin",
            password="secret",
            tls_cn="Server",
            ca=Path("/tmp/ca.crt"),
            proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"),
            timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"ok": True}}


class BookmarkApiWrappersTests(unittest.TestCase):
    def test_bookmark_list_posts_range_and_paging(self) -> None:
        c = _FakeClient()
        rng = {"begin_time": "19700101T000000.000", "end_time": "20400101T000000.000"}

        c.bookmark_list(rng, page_size=10, page_token="tok")

        self.assertEqual(
            c.calls[0],
            (
                f"{BOOKMARK_SVC}.ListBookmarks",
                {"range": rng, "page_size": 10, "page_token": "tok"},
            ),
        )

    def test_bookmark_list_omits_empty_page_token(self) -> None:
        c = _FakeClient()
        rng = {"begin_time": "a", "end_time": "b"}

        c.bookmark_list(rng, page_size=5)

        self.assertEqual(c.calls[0][1], {"range": rng, "page_size": 5})

    def test_bookmark_get_posts_id(self) -> None:
        c = _FakeClient()

        c.bookmark_get("bm-1")

        self.assertEqual(c.calls[0], (f"{BOOKMARK_SVC}.GetBookmark", {"id": "bm-1"}))

    def test_bookmark_create_posts_bookmark(self) -> None:
        c = _FakeClient()
        bookmark = {"message": "codex-bm", "range": {"begin_time": "a", "end_time": "b"}}

        c.bookmark_create(bookmark)

        self.assertEqual(
            c.calls[0],
            (f"{BOOKMARK_SVC}.CreateBookmark", {"bookmark": bookmark}),
        )

    def test_bookmark_update_posts_bookmark(self) -> None:
        c = _FakeClient()
        bookmark = {"id": "bm-1", "message": "codex-bm-2"}

        c.bookmark_update(bookmark)

        self.assertEqual(
            c.calls[0],
            (f"{BOOKMARK_SVC}.UpdateBookmark", {"bookmark": bookmark}),
        )

    def test_bookmark_delete_posts_id(self) -> None:
        c = _FakeClient()

        c.bookmark_delete("bm-1")

        self.assertEqual(c.calls[0], (f"{BOOKMARK_SVC}.DeleteBookmark", {"id": "bm-1"}))

    def test_bookmark_set_exported_time_posts_id_and_time(self) -> None:
        c = _FakeClient()

        c.bookmark_set_exported_time("bm-1", "20260101T000000.000")

        self.assertEqual(
            c.calls[0],
            (
                f"{BOOKMARK_SVC}.SetExportedTime",
                {"id": "bm-1", "exported_time": "20260101T000000.000"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
