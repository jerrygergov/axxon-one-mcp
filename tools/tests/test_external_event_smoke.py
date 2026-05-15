from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ExternalEventSmokeTests(unittest.TestCase):
    def test_requires_explicit_mutation_flag(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")
        args = SimpleNamespace(i_understand_this_mutates=False, confirm=module.CONFIRMATION)

        self.assertFalse(module.mutation_approved(args))

    def test_accepts_only_exact_confirmation(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")
        args = SimpleNamespace(i_understand_this_mutates=True, confirm="yes")

        self.assertFalse(module.mutation_approved(args))

    def test_event_ids_are_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        self.assertTrue(module.temp_event_id().startswith("codex-external-event-"))

    def test_occasional_body_uses_pdf_fields(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        body = module.occasional_http_body("hosts/Server/AppDataDetector.1/EventSupplier", "codex-event", "2026-05-07T12:00:00Z")

        self.assertEqual(body["accessPoint"], "hosts/Server/AppDataDetector.1/EventSupplier")
        self.assertEqual(body["eventType"], "codex-event")
        self.assertEqual(body["eventState"], "HAPPENED")
        self.assertIn("timestamp", body)
        self.assertIn("data", body)

    def test_realtime_recognizer_properties_are_non_secret_fixture(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        props = module.realtime_recognizer_external_properties("codex-rre")

        self.assertIn({"id": "enabled", "value_bool": False}, props)
        self.assertIn({"id": "display_name", "value_string": "codex-rre"}, props)
        self.assertNotIn("password", {prop["id"] for prop in props})

    def test_detector_ex_properties_are_minimal_and_codex_scoped(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        props = module.detector_ex_properties("codex-detector-ex")

        self.assertIn({"id": "display_name", "value_string": "codex-detector-ex"}, props)
        self.assertIn({"id": "enabled", "value_bool": True}, props)

    def test_candidate_access_points_include_detector_ex_shapes(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        candidates = module.candidate_access_points({"uid": "hosts/Server/RealtimeRecognizerExternal.1", "access_point": ""})

        self.assertIn("hosts/Server/RealtimeRecognizerExternal.1", candidates)
        self.assertIn("hosts/Server/RealtimeRecognizerExternal.1/EventSupplier", candidates)

    def test_default_detector_ex_probe_access_points_cover_pdf_shapes(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")
        args = SimpleNamespace(tls_cn="Server", access_point=[])

        candidates = module.detector_ex_probe_access_points(args)

        self.assertIn("DetectorEx.1", candidates)
        self.assertIn("hosts/Server/DetectorEx.1", candidates)
        self.assertIn("hosts/Server/DetectorEx.1/EventSupplier", candidates)

    def test_explicit_probe_access_points_preserve_order_and_dedupe(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")
        args = SimpleNamespace(tls_cn="Server", access_point=["DetectorEx.1", "DetectorEx.1", "DetectorEx.2"])

        candidates = module.detector_ex_probe_access_points(args)

        self.assertEqual(candidates, ["DetectorEx.1", "DetectorEx.2"])

    def test_first_added_uid_reports_empty_response(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        with self.assertRaisesRegex(RuntimeError, "returned no uid"):
            module.first_added_uid({"added": [], "failed": []}, "DetectorEx add")

    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_external_event_smoke")

        self.assertIn("ConfigurationService.ChangeConfig.add_temp_appdata_detector", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ConfigurationService.ChangeConfig.add_temp_detector_ex", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ConfigurationService.ChangeConfig.add_temp_realtime_recognizer_external", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ExternalDetectorService.RaiseOccasionalEvent.temp_detector", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ExternalDetectorService.RaiseOccasionalEvent.explicit_access_point_probe", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)
        self.assertIn("ConfigurationService.ChangeConfig.remove_temp_external_fixture", module.EXTERNAL_EVENT_MUTATIONS_REQUIRING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
