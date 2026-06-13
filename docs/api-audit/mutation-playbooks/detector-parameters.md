# Mutation Playbook: Detector Parameters

Use the `detector_playbooks` MCP group for task-first detector configuration. It keeps
descriptor discovery separate from mutation transport:

- `detector_playbook_parameter_schema(unit_type, detector_kind, intent)` reads the
  detector descriptor through `detector_archive.detector_parameter_schema`.
- `plan_detector_playbook("update_detector_parameters", ...)` delegates to operator
  workflow `update_detector_parameters`.
- `plan_detector_playbook("update_detector_geometry", ...)` delegates to operator
  workflow `update_detector_visual_element`, but only after a VisualElement descriptor
  proves the requested shape field.
- `apply_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks")` requires
  `AXXON_DETECTOR_PLAYBOOKS_APPROVE=1`.
- `rollback_detector_playbook_plan(plan_id, "CONFIRM-detector-playbooks-rollback")`
  delegates to the stored operator rollback token internally.

## Parameter Edits

1. Call `detector_playbook_parameter_schema` for the detector unit type and kind.
2. Build `properties` from descriptor paths and exact value fields such as
   `value_bool`, `value_int32`, or `value_string`.
3. Plan with:

```json
{
  "intent": "update_detector_parameters",
  "params": {
    "detector_uid": "hosts/Server/AVDetector.1",
    "properties": [
      {"id": "sensitivity", "value_int32": 42}
    ]
  }
}
```

4. Review the public diff. The public plan ID starts with `detector-playbook-plan-`;
   underlying operator plan IDs and confirmation tokens are not exposed.
5. Apply, verify, and roll back only with the detector playbooks confirmation tokens.

## Masks, Areas, And Lines

Visual geometry must be descriptor-backed. Do not guess string payloads.

1. Get schema or visual elements for the detector.
2. Find the VisualElement property and its `value_kind`.
3. Plan using the exact typed field:

```json
{
  "intent": "update_detector_geometry",
  "params": {
    "detector_uid": "hosts/Server/AppDataDetector.2",
    "visual_element_uid": "hosts/Server/AppDataDetector.2/VisualElement.zone",
    "property_path": "area",
    "value_kind": "value_simple_polygon",
    "value": {
      "points": [
        {"x": 0.1, "y": 0.1},
        {"x": 0.8, "y": 0.1},
        {"x": 0.8, "y": 0.7}
      ]
    }
  }
}
```

Accepted descriptor shape fields are `value_rectangle`, `value_polyline`,
`value_mask`, and `value_simple_polygon`. If the requested `value_kind` does not
match the descriptor, the playbook must reject the plan before creating an
operator plan.

## Safety Notes

- Do not put passwords, tokens, cookies, CA material, tickets, license keys, raw
  media, raw metadata payloads, or biometric vectors in detector properties.
- Public responses and audit entries are sanitized.
- GlobalTracker profile mutations, RealtimeRecognizerExternal, and Tag&Track remain
  fixture-needed unless a future safe fixture-backed implementation proves them.
