from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class LegacyAuthProbeTests(unittest.TestCase):
    def test_probe_endpoint_groups_cover_server_and_macros(self) -> None:
        module = importlib.import_module("axxon_legacy_auth_probe")
        groups = {endpoint["group"] for endpoint in module.probe_endpoints()}
        self.assertTrue({"server", "macros"}.issubset(groups))

    def test_parser_can_select_group(self) -> None:
        module = importlib.import_module("axxon_legacy_auth_probe")
        parser = module.build_parser()
        args = parser.parse_args(["--password", "x", "--group", "server"])
        self.assertEqual(args.group, ["server"])


if __name__ == "__main__":
    unittest.main()
