from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class DeleteVideoNoopProbeTests(unittest.TestCase):
    def test_requires_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_delete_video_noop_probe")
        original_argv = sys.argv
        try:
            sys.argv = ["axxon_delete_video_noop_probe.py", "--password", "x"]
            with self.assertRaises(SystemExit):
                module.parse_args()
            sys.argv = [
                "axxon_delete_video_noop_probe.py",
                "--password",
                "x",
                "--i-understand-delete-video-noop",
                module.CONFIRMATION,
            ]
            args = module.parse_args()
        finally:
            sys.argv = original_argv
        self.assertEqual(args.i_understand_delete_video_noop, module.CONFIRMATION)

    def test_noop_query_is_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_delete_video_noop_probe")
        query = module.noop_delete_query(host_name="Server", stamp="20260512T080000.000000")
        self.assertEqual(query["begins_at"], query["ends_at"])
        self.assertIn("codex-nonexistent-delete-video", query["endpoint"])
        self.assertIn("codex-nonexistent-delete-video", query["storage_id"])
        self.assertTrue(query["endpoint"].startswith("hosts/Server/"))
        self.assertTrue(query["storage_id"].startswith("hosts/Server/"))


if __name__ == "__main__":
    unittest.main()
