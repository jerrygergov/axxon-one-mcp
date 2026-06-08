"""Smoke test for the axxon-reference-plugin plugin scaffold."""
from __future__ import annotations

import os
import unittest

import main


class PluginScaffoldSmokeTests(unittest.TestCase):
    """Offline checks that do not require a live server."""

    def test_required_env_declared(self) -> None:
        """The entrypoint declares the four credential env names."""
        for name in ("AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD"):
            self.assertIn(name, main.REQUIRED_ENV)

    def test_missing_env_returns_nonzero(self) -> None:
        """With no credentials in the environment, main() exits non-zero rather than connecting."""
        saved = {name: os.environ.pop(name, None) for name in main.REQUIRED_ENV}
        try:
            self.assertNotEqual(main.main(), 0)
        finally:
            for name, value in saved.items():
                if value is not None:
                    os.environ[name] = value

    def test_retry_bounds(self) -> None:
        """Retry count is bounded and positive."""
        self.assertGreaterEqual(main.MAX_RETRIES, 1)
        self.assertLessEqual(main.MAX_RETRIES, 5)


if __name__ == "__main__":
    unittest.main()
