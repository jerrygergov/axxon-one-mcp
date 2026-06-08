from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class ExternalClientPreflightTests(unittest.TestCase):
    def test_mutating_operations_are_declared_approval_only(self) -> None:
        module = importlib.import_module("axxon_external_client_preflight")
        names = {item["operation"] for item in module.EXTERNAL_CLIENT_MUTATIONS_REQUIRING_APPROVAL}

        self.assertIn("ClientHTTP.SwitchLayout", names)
        self.assertIn("ClientHTTP.AddCameraToDisplay", names)
        self.assertIn("ClientHTTP.SetArchiveMode", names)
        self.assertIn("EmbeddableComponent.BrowserRender", names)

    def test_component_signature_uses_small_text_prefix(self) -> None:
        module = importlib.import_module("axxon_external_client_preflight")
        text_prefix = "<html><script src='/component/video.js'></script></html>"
        signature = module.component_host_signature(
            status=200,
            content_type="text/html",
            size=512,
            text_prefix=text_prefix,
        )

        self.assertTrue(signature["mentions_component"])
        self.assertTrue(signature["mentions_video"])
        self.assertEqual(signature["text_prefix_len"], len(text_prefix))
        self.assertNotIn("text_prefix", signature)

    def test_embedded_component_signature_accepts_pdf_entrypoint(self) -> None:
        module = importlib.import_module("axxon_external_client_preflight")
        text_prefix = "<html><title>Video component</title><script src='./embedded.js'></script></html>"
        signature = module.component_host_signature(
            status=200,
            content_type="text/html",
            size=856,
            text_prefix=text_prefix,
            path="/embedded.html",
        )

        self.assertTrue(signature["mentions_component"])
        self.assertTrue(signature["mentions_video"])
        self.assertTrue(signature["mentions_embed"])
        self.assertEqual(signature["path"], "/embedded.html")


if __name__ == "__main__":
    unittest.main()
