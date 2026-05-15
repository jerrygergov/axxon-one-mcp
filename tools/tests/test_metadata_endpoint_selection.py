from __future__ import annotations

import importlib
import unittest


class MetadataEndpointSelectionTests(unittest.TestCase):
    def test_example_exports_candidate_selection(self) -> None:
        module = importlib.import_module("examples.metadata_tracker_stream")
        self.assertTrue(callable(getattr(module, "choose_vmda_endpoint", None)))
        self.assertTrue(callable(getattr(module, "try_pull_metadata_sample", None)))
