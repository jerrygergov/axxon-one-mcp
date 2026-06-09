#!/usr/bin/env python3
"""FileSystemBrowser read tools for Axxon One MCP (Phase A).

Browse server-side filesystem paths (ListDirectory), inspect a file or directory
(GetFileInfo), and read filesystem capacity/free space (GetSpace). Useful for export-path
picking and storage UX. All three are reads, no approval gate. Directory listings are
entry-capped. Direct gRPC against `FileSystemBrowser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig
from axxon_mcp_admin import public_config_summary

FILESYSTEM_BROWSER_PROTO = "axxonsoft/bl/config/FileSystemBrowser.proto"
FILESYSTEM_BROWSER_PB2 = "axxonsoft.bl.config.FileSystemBrowser_pb2"

FILESYSTEM_BROWSER_TOOL_NAMES = (
    "filesystem_browser_connect_axxon_profile",
    "list_directory",
    "get_file_info",
    "get_space",
)

MAX_ENTRIES = 1000
DEFAULT_ENTRIES = 200


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


@dataclass
class AxxonMcpFilesystemBrowser:
    """Phase A FileSystemBrowser read tools (directory listing, file info, free space)."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None

    def filesystem_browser_connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {"connected": False, "status": "gap", "message": "Only the env profile is supported.", "profile_name": profile}
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        return {"connected": True, "profile_name": profile, "profile": public_config_summary(config), "mode": "read"}

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        return self.filesystem_browser_connect_axxon_profile(profile)

    def ensure_client(self) -> Any:
        if self.client is None:
            self.filesystem_browser_connect_axxon_profile("env")
        return self.client

    def _stub_and_pb2(self) -> tuple[Any, Any]:
        client = self.ensure_client()
        client.authenticate_grpc()
        return client.stub_from_proto(FILESYSTEM_BROWSER_PROTO, "FileSystemBrowser"), client.import_module(FILESYSTEM_BROWSER_PB2)

    @staticmethod
    def _error(pb2: Any, tool: str, error: Any) -> dict[str, Any] | None:
        if error.status == 0:
            return None
        return {"status": "error", "tool": tool, "error_code": pb2.FSError.ECode.Name(error.status), "message": error.message}

    @staticmethod
    def _file_entry(pb2: Any, info: Any) -> dict[str, Any]:
        return {
            "path": info.path,
            "name": info.name,
            "type": pb2.EFileType.Name(info.type),
            "perms": pb2.EFSPermissions.Name(info.perms),
            "size_bytes": info.size_bytes,
        }

    def list_directory(self, path: str = "", node_name: str = "", type: str = "", name_pattern: str = "", page_size: int | None = None, page_token: str = "") -> dict[str, Any]:
        """List a server-side directory (entry-capped); empty path lists the root.

        Args:
            path (str, optional): Directory path; empty for the root.
            node_name (str, optional): Node name; empty for the current node.
            type (str, optional): Filter by file type ("REGULAR_FILE"|"DIRECTORY"|"BLOCK_DEVICE").
            name_pattern (str, optional): POSIX-extended regex name filter (case-insensitive).
            page_size (int, optional): Max entries; clamped to MAX_ENTRIES.
            page_token (str, optional): Continuation token from a prior page.

        Returns:
            (dict): {"status": "ok", "tool": "list_directory", "count", "entries", "next_page_token"}.
        """
        stub, pb2 = self._stub_and_pb2()
        type_value = 0
        if type:
            try:
                type_value = pb2.EFileType.Value(type)
            except (KeyError, ValueError):
                return {"status": "gap", "tool": "list_directory", "message": f"Unknown file type: {type!r}. Use REGULAR_FILE, DIRECTORY, or BLOCK_DEVICE."}
        cap = _clamp(int(page_size if page_size is not None else DEFAULT_ENTRIES), 1, MAX_ENTRIES)
        request = pb2.ListDirectoryRequest(node_name=node_name, path=path, type=type_value, name_pattern=name_pattern, page_size=cap, page_token=page_token)
        response = stub.ListDirectory(request, timeout=self.ensure_client().config.timeout)
        err = self._error(pb2, "list_directory", response.error)
        if err:
            return err
        entries = list(response.entries)
        return {
            "status": "ok",
            "tool": "list_directory",
            "count": len(entries),
            "entries": [self._file_entry(pb2, entry) for entry in entries],
            "next_page_token": response.next_page_token,
        }

    def get_file_info(self, path: str = "", node_name: str = "") -> dict[str, Any]:
        """Read info for one file or directory (path, type, perms, size, parent path)."""
        stub, pb2 = self._stub_and_pb2()
        request = pb2.GetFileInfoRequest(node_name=node_name, path=path)
        response = stub.GetFileInfo(request, timeout=self.ensure_client().config.timeout)
        err = self._error(pb2, "get_file_info", response.error)
        if err:
            return err
        return {"status": "ok", "tool": "get_file_info", "file_info": self._file_entry(pb2, response.file_info), "parent_path": response.parent_path}

    def get_space(self, path: str = "", node_name: str = "") -> dict[str, Any]:
        """Read filesystem capacity and free space for a path."""
        stub, pb2 = self._stub_and_pb2()
        request = pb2.GetSpaceRequest(node_name=node_name, path=path)
        response = stub.GetSpace(request, timeout=self.ensure_client().config.timeout)
        err = self._error(pb2, "get_space", response.error)
        if err:
            return err
        return {"status": "ok", "tool": "get_space", "capacity_bytes": response.space_info.capacity_bytes, "free_bytes": response.space_info.free_bytes}
