# Mutation Playbook: External Events And Virtual Trigger

Use the `detector_playbooks` MCP group for external detector event injection. It
wraps the existing operator workflows instead of adding direct HTTP mutation code.

## Occasional Events

Plan a one-shot event with `raise_external_event`, which maps to operator workflow
`external_event_inject`:

```json
{
  "intent": "raise_external_event",
  "params": {
    "access_point": "hosts/Server/DetectorEx.1/EventSupplier",
    "event_type": "VirtualTrigger"
  }
}
```

The access point must be an external detector event supplier. Planning never sends
the event. Apply requires:

- `AXXON_DETECTOR_PLAYBOOKS_APPROVE=1`
- `confirmation: "CONFIRM-detector-playbooks"`

Rollback uses `CONFIRM-detector-playbooks-rollback`, but occasional event injection
is a no-op rollback because the event is already one-shot on the wire.

## Periodical Target-List Events

Plan periodical events with `raise_periodical_external_event`, which maps to
operator workflow `raise_periodical_event`:

```json
{
  "intent": "raise_periodical_external_event",
  "params": {
    "access_point": "hosts/Server/DetectorEx.1/EventSupplier",
    "event_type": "TargetList",
    "tracklets": [
      {
        "objectId": 1,
        "objectType": 0,
        "rectangle": {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
      }
    ]
  }
}
```

Tracklet count is bounded by the playbook layer. Do not include raw images, video
frames, raw metadata payloads, embeddings, biometric vectors, bearer tokens, or
credentials. Public responses preserve status/error summaries from the operator
while redacting secret-like payload fields.

## Review Checklist

- Confirm the event supplier access point belongs to the intended external detector.
- Confirm the public plan has rollback classification `noop` for event injection.
- Apply only with the detector playbooks approval env and confirmation token.
- Verify through the returned playbook plan ID; do not use or expose stored operator
  plan IDs.
