# Demo Metadata Tracklets Proof

- Date: `2026-05-02`
- gRPC target: `<demo-host>:20109`
- Endpoint: `hosts/Server/AVDetector.1/SourceEndpoint.vmda`
- Tool: `arm64-docker/tools/examples/metadata_tracker_stream.py`

This verifies the PDF `Get tracks using GO` section. The server API is `MetadataService.PullMetadata`; the Go example receives `MetadataSample_Tracklets`, and the Python example receives the same tracklet samples through generated gRPC stubs.

Command:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py \
  --endpoint hosts/Server/AVDetector.1/SourceEndpoint.vmda \
  --timeout 25 \
  --samples 3
```

Result:

- Samples: 3
- Config updates: 1
- Heartbeats: 0
- Tracklets per sample: 21, 21, 21

No image frames, raw track payloads, credentials, or tokens were persisted.
