#!/usr/bin/env python3
"""DevicesCatalog read tools for Axxon One MCP (Phase A).

Browse the supported-device catalog: vendors (ListVendors / ListVendorsV2), device models
(ListDevices / ListDevicesV2), and a single model's traits (GetDevice). This is what an
assistant uses to pick a driver when adding a camera aligned with the documentation. All reads,
no approval gate. The V2 RPCs are server streams and are page-capped. Device default credentials
are never surfaced. Direct gRPC against `DevicesCatalog`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

DEVICES_CATALOG_PROTO = "axxonsoft/bl/config/DevicesCatalog.proto"
DEVICES_CATALOG_PB2 = "axxonsoft.bl.config.DevicesCatalog_pb2"

DEVICES_CATALOG_TOOL_NAMES = (
    "devices_catalog_connect_axxon_profile",
    "list_vendors",
    "list_vendors_v2",
    "list_devices",
    "list_devices_v2",
    "get_device",
)

MAX_PAGES = 64
DEFAULT_PAGES = 8


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpDevicesCatalog:
    """Phase A DevicesCatalog read tools (vendors, device models, model traits)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def devices_catalog_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.devices_catalog_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.devices_catalog_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(DEVICES_CATALOG_PROTO, "DevicesCatalog"), client.import_module(DEVICES_CATALOG_PB2)

    @staticmethod
    def _category_value(pb2: Any, category: str) -> int | None:
        if not category:
            return 0
        try:
            return pb2.EDeviceCategory.Value(category)
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _device_summary(pb2: Any, device: Any) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "vendor": device.vendor,
            "model": device.model,
            "firmware": list(device.firmware),
            "categories": [pb2.EDeviceCategory.Name(c) for c in device.categories],
        }
        if device.HasField("traits"):
            traits = device.traits
            # default_credentials (login/password) is intentionally never surfaced.
            summary["traits"] = {
                "has_storage": traits.has_storage,
                "has_text_event_sources": traits.has_text_event_sources,
                "has_motion_detection": traits.has_motion_detection,
                "video_channels_count": traits.video_channels_count,
                "default_port": traits.default_port.value if traits.HasField("default_port") else None,
            }
        return summary

    def list_vendors(self, category: str = "", filter: str = "", node_name: str = "") -> dict[str, Any]:
        """List supported device vendors, optionally filtered by category and text."""
        stub, pb2 = self._stub_and_pb2()
        category_value = self._category_value(pb2, category)
        if category_value is None:
            return {"status": "gap", "tool": "list_vendors", "message": f"Unknown category: {category!r}."}
        request = pb2.ListVendorsRequest(category=category_value, filter=filter, node_name=node_name)
        response = stub.ListVendors(request, timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "list_vendors", "count": len(response.vendors), "vendors": list(response.vendors), "next_page_token": response.next_page_token}

    def list_vendors_v2(self, category: str = "", filter: str = "", node_name: str = "", max_pages: int | None = None) -> dict[str, Any]:
        """Stream supported device vendors (page-capped), de-duplicated across pages."""
        stub, pb2 = self._stub_and_pb2()
        category_value = self._category_value(pb2, category)
        if category_value is None:
            return {"status": "gap", "tool": "list_vendors_v2", "message": f"Unknown category: {category!r}."}
        cap = _clamp(int(max_pages if max_pages is not None else DEFAULT_PAGES), 1, MAX_PAGES)
        request = pb2.ListVendorsRequest(category=category_value, filter=filter, node_name=node_name)
        vendors: list[str] = []
        pages_seen = 0
        truncated = False
        for response in stub.ListVendorsV2(request, timeout=self.ensure_client().config.timeout):
            vendors.extend(response.vendors)
            pages_seen += 1
            if pages_seen >= cap:
                truncated = True
                break
        deduped = list(dict.fromkeys(vendors))
        return {"status": "ok", "tool": "list_vendors_v2", "pages_seen": pages_seen, "count": len(deduped), "vendors": deduped, "truncated": truncated}

    def list_devices(self, category: str = "", vendor: str = "", filter: str = "", node_name: str = "") -> dict[str, Any]:
        """List supported device models, optionally filtered by category/vendor/text."""
        stub, pb2 = self._stub_and_pb2()
        category_value = self._category_value(pb2, category)
        if category_value is None:
            return {"status": "gap", "tool": "list_devices", "message": f"Unknown category: {category!r}."}
        request = pb2.ListDevicesRequest(category=category_value, vendor=vendor, filter=filter, node_name=node_name)
        response = stub.ListDevices(request, timeout=self.ensure_client().config.timeout)
        devices = list(response.devices)
        return {"status": "ok", "tool": "list_devices", "count": len(devices), "devices": [self._device_summary(pb2, d) for d in devices], "next_page_token": response.next_page_token}

    def list_devices_v2(self, category: str = "", vendor: str = "", filter: str = "", node_name: str = "", max_pages: int | None = None) -> dict[str, Any]:
        """Stream supported device models (page-capped)."""
        stub, pb2 = self._stub_and_pb2()
        category_value = self._category_value(pb2, category)
        if category_value is None:
            return {"status": "gap", "tool": "list_devices_v2", "message": f"Unknown category: {category!r}."}
        cap = _clamp(int(max_pages if max_pages is not None else DEFAULT_PAGES), 1, MAX_PAGES)
        request = pb2.ListDevicesRequest(category=category_value, vendor=vendor, filter=filter, node_name=node_name)
        devices: list[dict[str, Any]] = []
        pages_seen = 0
        truncated = False
        for response in stub.ListDevicesV2(request, timeout=self.ensure_client().config.timeout):
            devices.extend(self._device_summary(pb2, d) for d in response.devices)
            pages_seen += 1
            if pages_seen >= cap:
                truncated = True
                break
        return {"status": "ok", "tool": "list_devices_v2", "pages_seen": pages_seen, "count": len(devices), "devices": devices, "truncated": truncated}

    def get_device(self, vendor: str = "", model: str = "", node_name: str = "") -> dict[str, Any]:
        """Read one supported model's traits. Both vendor and model are required.

        Args:
            vendor (str): Device vendor (from list_vendors).
            model (str): Device model (from list_devices).
            node_name (str, optional): Node name; empty for the current node.

        Returns:
            (dict): {"status": "ok", "tool": "get_device", "device": {...}} or a gap if vendor/model missing.
        """
        if not vendor or not model:
            return {"status": "gap", "tool": "get_device", "message": "Both vendor and model are required (pick from list_vendors / list_devices)."}
        stub, pb2 = self._stub_and_pb2()
        request = pb2.GetDeviceRequest(vendor=vendor, model=model, node_name=node_name)
        response = stub.GetDevice(request, timeout=self.ensure_client().config.timeout)
        return {"status": "ok", "tool": "get_device", "device": self._device_summary(pb2, response.device)}
