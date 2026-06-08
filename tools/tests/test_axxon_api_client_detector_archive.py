from __future__ import annotations

import sys
from pathlib import Path
import unittest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local",
            grpc_port=20109,
            http_port=80,
            http_url="http://example.local",
            username="root",
            password="secret",
            tls_cn="Server",
            ca=Path("/tmp/ca.crt"),
            proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"),
            timeout=5.0,
        )
        super().__init__(cfg)
        self.inventory = {"nodes": [{"node_name": "Server"}]}
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"ok": True}}


class DetectorArchiveWrappersTests(unittest.TestCase):
    def test_batch_get_factories_passes_requested_factories(self) -> None:
        c = _FakeClient()
        c.batch_get_factories(
            [
                {
                    "unit_type": "AVDetector",
                    "parent_uid": "hosts/Server",
                    "ignore_possible_limits": True,
                }
            ]
        )
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.config.ConfigurationService.BatchGetFactories",
                {
                    "factories": [
                        {
                            "unit_type": "AVDetector",
                            "parent_uid": "hosts/Server",
                            "ignore_possible_limits": True,
                        }
                    ]
                },
            ),
        )

    def test_list_similar_units_uses_current_node_and_type_search(self) -> None:
        c = _FakeClient()
        c.list_similar_units("hosts/Server/AVDetector.1")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.config.ConfigurationService.ListSimilarUnits",
                {
                    "uid": "hosts/Server/AVDetector.1",
                    "node_name": "Server",
                    "page_size": 1000,
                    "search_mode": "BY_UNIT_TYPE",
                },
            ),
        )

    def test_acquire_dynamic_parameters_omits_empty_property_path(self) -> None:
        c = _FakeClient()
        c.acquire_dynamic_parameters("hosts/Server/AVDetector.1", property_path=None)
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.config.DynamicParametersService.AcquireDynamicParameters",
                {"uid": "hosts/Server/AVDetector.1"},
            ),
        )

    def test_acquire_device_additional_data_passes_uid(self) -> None:
        c = _FakeClient()
        c.acquire_device_additional_data("hosts/Server/DeviceIpint.1")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.config.DynamicParametersService.AcquireDeviceAdditionalData",
                {"uid": "hosts/Server/DeviceIpint.1"},
            ),
        )

    def test_archive_format_volumes_wraps_volume_ids(self) -> None:
        c = _FakeClient()
        c.archive_format_volumes("hosts/Server/MultimediaStorage.1/MultimediaStorage", ["v-1", "v-2"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.archive.ArchiveService.FormatVolumes",
                {
                    "access_point": "hosts/Server/MultimediaStorage.1/MultimediaStorage",
                    "volumes": [{"id": "v-1"}, {"id": "v-2"}],
                },
            ),
        )

    def test_archive_reindex_sets_full_reindex_by_default(self) -> None:
        c = _FakeClient()
        c.archive_reindex("archive-ap", ["v-1"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.archive.ArchiveService.Reindex",
                {"access_point": "archive-ap", "volume_ids": ["v-1"], "full_reindex": {}},
            ),
        )

    def test_archive_cancel_reindex_passes_volume_ids(self) -> None:
        c = _FakeClient()
        c.archive_cancel_reindex("archive-ap", ["v-1", "v-2"])
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.archive.ArchiveService.CancelReindex",
                {"access_point": "archive-ap", "volume_ids": ["v-1", "v-2"]},
            ),
        )

    def test_archive_probe_volume_wraps_local_path_hint(self) -> None:
        c = _FakeClient()
        c.archive_probe_volume("/mnt/archive-volume")
        self.assertEqual(
            c.calls[0],
            (
                "axxonsoft.bl.archive.ArchiveVolumeService.ProbeVolume",
                {
                    "volume_type": "local",
                    "connection_params": {"path": "/mnt/archive-volume"},
                },
            ),
        )


if __name__ == "__main__":
    unittest.main()
