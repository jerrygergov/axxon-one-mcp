#!/usr/bin/env python3
"""Generated runnable plugin scaffold: axxon-reference-plugin.

A minimal but complete Axxon One plugin entrypoint. It authenticates over direct gRPC
(CN from AXXON_TLS_CN), lists cameras via DomainService.ListCameras with a bounded retry,
and prints a JSON summary. Credentials come only from the environment. Extend `run_plugin`
with your own logic; keep all calls bounded and credentials env-only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

PLUGIN_NAME = "axxon-reference-plugin"
DURATION_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

REQUIRED_ENV = ("AXXON_HOST", "AXXON_TLS_CN", "AXXON_USERNAME", "AXXON_PASSWORD")


def redact(value: str) -> str:
    if not value:
        return ""
    return value[:2] + "***"


def load_ca() -> bytes | None:
    ca_path = os.environ.get("AXXON_CA")
    if ca_path and os.path.isfile(ca_path):
        with open(ca_path, "rb") as fh:
            return fh.read()
    return None


def with_retry(call, label: str):
    """Run `call` with bounded retries and linear backoff. Returns its result or raises."""
    import grpc

    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return call()
        except grpc.RpcError as exc:
            last_exc = exc
            logging.warning("%s attempt %d/%d failed: %s", label, attempt + 1, MAX_RETRIES, exc.code())
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_exc


def run_plugin() -> dict:
    sys.path.insert(0, os.environ.get("AXXON_STUBS_PATH", "/tmp/axxon-grpc-py"))
    import grpc
    from axxonsoft.bl.auth.Authentication_pb2 import AuthenticateRequest
    from axxonsoft.bl.auth.Authentication_pb2_grpc import AuthenticationServiceStub
    from axxonsoft.bl.domain.Domain_pb2 import ListCamerasRequest
    from axxonsoft.bl.domain.Domain_pb2_grpc import DomainServiceStub

    host = os.environ["AXXON_HOST"]
    tls_cn = os.environ["AXXON_TLS_CN"]
    user = os.environ["AXXON_USERNAME"]
    logging.info("plugin=%s user=%s password=%s host=%s", PLUGIN_NAME, user, redact(os.environ["AXXON_PASSWORD"]), host)

    ca = load_ca()
    base_creds = grpc.ssl_channel_credentials(root_certificates=ca) if ca else grpc.ssl_channel_credentials()
    options = (("grpc.ssl_target_name_override", tls_cn),)

    def authenticate():
        with grpc.secure_channel(host, base_creds, options=options) as auth_channel:
            return AuthenticationServiceStub(auth_channel).AuthenticateEx2(
                AuthenticateRequest(user_name=user, password=os.environ["AXXON_PASSWORD"]),
                timeout=DURATION_SECONDS,
            )

    token = with_retry(authenticate, "authenticate")
    if token.error_code != 0:
        raise RuntimeError(f"auth failed error_code={token.error_code}")
    metadata_pair = ((token.token_name, token.token_value),)
    auth_creds = grpc.metadata_call_credentials(lambda _ctx, cb: cb(metadata_pair, None))
    composite = grpc.composite_channel_credentials(base_creds, auth_creds)

    cameras = []
    def list_cameras():
        collected = []
        with grpc.secure_channel(host, composite, options=options) as channel:
            for response in DomainServiceStub(channel).ListCameras(ListCamerasRequest(view=0), timeout=DURATION_SECONDS):
                for camera in response.items:
                    collected.append(getattr(camera, "access_point", ""))
        return collected

    cameras = with_retry(list_cameras, "list_cameras")
    return {"plugin": PLUGIN_NAME, "cameras": len(cameras)}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        logging.error("missing env: %s", ",".join(missing))
        return 2
    summary = run_plugin()
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
