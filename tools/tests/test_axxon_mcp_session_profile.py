from __future__ import annotations

from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class SessionConnectionProfileTests(unittest.TestCase):
    def test_unconfigured_profile_reports_required_fields_without_env_fallback(self) -> None:
        from axxon_mcp_session_profile import AxxonSessionConnectionProfile

        profile = AxxonSessionConnectionProfile(
            repo_root=Path("/repo"),
            environ={
                "AXXON_HOST": "persisted.example",
                "AXXON_HTTP_URL": "http://persisted.example:80",
                "AXXON_HTTP_PORT": "80",
                "AXXON_GRPC_PORT": "20109",
                "AXXON_USERNAME": "persisted-user",
                "AXXON_PASSWORD": "persisted-password",
                "AXXON_CA": "/repo/docs/grpc-proto-files/api.ngp.root-ca.crt",
                "AXXON_PROTO_DIR": "/repo/docs/grpc-proto-files",
                "AXXON_GRPC_STUBS": "/tmp/stubs",
            },
        )

        status = profile.get_axxon_connection_status()

        self.assertEqual(status["status"], "needs_connection_profile")
        self.assertFalse(status["configured"])
        self.assertEqual(
            status["required_fields"],
            ["host", "grpc_port", "http_port", "username", "password"],
        )
        self.assertNotIn("persisted.example", repr(status))
        with self.assertRaisesRegex(Exception, "configure_axxon_connection"):
            profile.config_factory()

    def test_configure_stores_runtime_profile_and_redacts_password(self) -> None:
        from axxon_mcp_session_profile import AxxonSessionConnectionProfile

        profile = AxxonSessionConnectionProfile(repo_root=Path("/repo"), environ={})

        configured = profile.configure_axxon_connection(
            host="100.76.150.18",
            grpc_port=20109,
            http_port=80,
            username="root",
            password="SHOULD_NOT_LEAK",
            tls_cn="Server",
        )
        config = profile.config_factory()

        self.assertEqual(config.host, "100.76.150.18")
        self.assertEqual(config.grpc_port, 20109)
        self.assertEqual(config.http_port, 80)
        self.assertEqual(config.http_url, "http://100.76.150.18:80")
        self.assertEqual(config.username, "root")
        self.assertEqual(config.password, "SHOULD_NOT_LEAK")
        self.assertEqual(config.tls_cn, "Server")
        self.assertEqual(profile.host_uid(), "hosts/Server")
        self.assertEqual(configured["status"], "configured")
        self.assertTrue(configured["profile"]["password_present"])
        self.assertNotIn("SHOULD_NOT_LEAK", repr(configured["profile"]))

    def test_configure_validates_required_fields_and_ports(self) -> None:
        from axxon_mcp_session_profile import AxxonSessionConnectionProfile

        profile = AxxonSessionConnectionProfile(repo_root=Path("/repo"), environ={})

        missing = profile.configure_axxon_connection(
            host="",
            grpc_port=20109,
            http_port=80,
            username="root",
            password="root",
        )
        bad_port = profile.configure_axxon_connection(
            host="10.0.0.5",
            grpc_port=70000,
            http_port=80,
            username="root",
            password="root",
        )

        self.assertEqual(missing["status"], "invalid")
        self.assertIn("host", missing["missing_fields"])
        self.assertEqual(bad_port["status"], "invalid")
        self.assertIn("grpc_port", bad_port["invalid_fields"])
        self.assertEqual(profile.get_axxon_connection_status()["status"], "needs_connection_profile")

    def test_clear_removes_runtime_profile(self) -> None:
        from axxon_mcp_session_profile import AxxonSessionConnectionProfile

        profile = AxxonSessionConnectionProfile(repo_root=Path("/repo"), environ={})
        profile.configure_axxon_connection(
            host="10.0.0.5",
            grpc_port=20109,
            http_port=80,
            username="root",
            password="root",
        )

        cleared = profile.clear_axxon_connection()

        self.assertEqual(cleared["status"], "cleared")
        self.assertEqual(profile.get_axxon_connection_status()["status"], "needs_connection_profile")

    def test_clear_invalidates_cached_clients_on_wrapped_capabilities(self) -> None:
        from axxon_mcp_live import AxxonMcpLive
        from axxon_mcp_session_profile import AxxonSessionConnectionProfile

        class FakeClient:
            def load_inventory(self) -> dict[str, object]:
                return {"cameras": []}

        profile = AxxonSessionConnectionProfile(repo_root=Path("/repo"), environ={})
        live = AxxonMcpLive(
            config_factory=profile.config_factory,
            client_factory=lambda config: FakeClient(),
        )
        wrapped = profile.wrap(live)
        profile.configure_axxon_connection(
            host="10.0.0.5",
            grpc_port=20109,
            http_port=80,
            username="root",
            password="root",
        )
        self.assertEqual(wrapped.connect_axxon_profile("env")["connected"], True)
        self.assertIsNotNone(live.client)

        profile.clear_axxon_connection()
        after_clear = wrapped.list_cameras()

        self.assertIsNone(live.client)
        self.assertEqual(after_clear["status"], "needs_connection_profile")

    def test_wrapper_converts_missing_profile_exception_to_structured_response(self) -> None:
        from axxon_mcp_session_profile import AxxonConnectionProfileRequired, AxxonSessionConnectionProfile

        class NeedsProfile:
            def connect_axxon_profile(self, profile: str = "env") -> dict[str, object]:
                raise AxxonConnectionProfileRequired()

        profile = AxxonSessionConnectionProfile(repo_root=Path("/repo"), environ={})
        wrapped = profile.wrap(NeedsProfile())

        response = wrapped.connect_axxon_profile("env")

        self.assertEqual(response["status"], "needs_connection_profile")
        self.assertEqual(response["tool"], "connect_axxon_profile")
        self.assertIn("configure_axxon_connection", response["message"])


if __name__ == "__main__":
    unittest.main()
