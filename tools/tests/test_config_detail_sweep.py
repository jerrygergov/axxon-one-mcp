from __future__ import annotations

import importlib
import unittest


class ConfigDetailSweepTests(unittest.TestCase):
    def test_read_groups_cover_pdf_config_sections(self) -> None:
        module = importlib.import_module("axxon_config_detail_sweep")
        groups = set(module.read_groups())
        self.assertTrue({"templates", "macros", "users", "maps", "detectors"}.issubset(groups))
