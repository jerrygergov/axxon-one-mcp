from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class GrpcBookmarkSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_grpc_bookmark_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x"])
        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_grpc_bookmark_smoke")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", module.CONFIRMATION])
        self.assertTrue(module.mutation_approved(args))

        wrong = parser.parse_args(["--password", "x", "--i-understand-this-mutates", "--confirm", "wrong"])
        self.assertFalse(module.mutation_approved(wrong))

    def test_bookmark_request_data_is_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_grpc_bookmark_smoke")
        data = module.bookmark_request_data(
            camera_ap="hosts/Server/DeviceIpint.1/SourceEndpoint.video",
            archive_ap="hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
            message_suffix="20260506T010203",
        )

        self.assertEqual(data["message"], "codex-grpc-bookmark-smoke-20260506T010203")
        self.assertEqual(data["protection"], "NOT_PROTECTED")
        self.assertEqual(data["access"], "PUBLIC")
        self.assertEqual(data["categories"], ["codex-smoke"])
        self.assertEqual(data["camera_descriptions"][0]["camera_access_point"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video")
        self.assertEqual(
            data["camera_descriptions"][0]["bindings"][0]["access_point"],
            "hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage",
        )


if __name__ == "__main__":
    unittest.main()
