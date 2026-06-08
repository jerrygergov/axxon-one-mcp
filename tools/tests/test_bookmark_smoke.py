from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class BookmarkSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_bookmark_smoke")
        original_argv = sys.argv
        try:
            sys.argv = ["axxon_bookmark_smoke.py", "--password", "x"]
            with self.assertRaises(SystemExit):
                module.parse_args()
        finally:
            sys.argv = original_argv

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_bookmark_smoke")
        original_argv = sys.argv
        try:
            sys.argv = [
                "axxon_bookmark_smoke.py",
                "--password",
                "x",
                "--mutate-bookmark",
                "--i-understand-bookmark-mutation",
                "yes",
            ]
            with self.assertRaises(SystemExit):
                module.parse_args()
            sys.argv[-1] = "CREATE_EDIT_DELETE_TEMP_BOOKMARK"
            args = module.parse_args()
        finally:
            sys.argv = original_argv
        self.assertTrue(args.mutate_bookmark)

    def test_create_payload_is_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_bookmark_smoke")
        payload = module.bookmark_create_payload(
            begin="20260506T220000.000000",
            end="20260506T220010.000000",
            endpoint="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            storage_id="hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
            comment_suffix="unit-test",
        )
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["comment"].startswith("codex-"))
        self.assertFalse(payload[0]["is_protected"])

    def test_delete_payload_clears_endpoint_and_storage(self) -> None:
        module = importlib.import_module("axxon_bookmark_smoke")
        bookmark = {
            "id": "bookmark-id",
            "begins_at": "20260506T220000.000000",
            "ends_at": "20260506T220010.000000",
            "comment": "codex-temp",
            "endpoint": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "storage_id": "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
        }
        payload = module.bookmark_delete_payload(bookmark, host_name="Server")
        self.assertEqual(payload[0]["endpoint"], "")
        self.assertEqual(payload[0]["storage_id"], "")
        self.assertEqual(payload[0]["hostname"], "Server")

    def test_create_paths_include_pdf_and_trailing_slash_variant(self) -> None:
        module = importlib.import_module("axxon_bookmark_smoke")
        self.assertEqual(
            module.BOOKMARK_CREATE_PATHS,
            ["/archive/contents/bookmarks/create", "/archive/contents/bookmarks/create/"],
        )


if __name__ == "__main__":
    unittest.main()
