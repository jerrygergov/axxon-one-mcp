# Mutation Playbook: Maps And Markers

- PDF pages: 505-519.
- APIs involved: map create/change/remove, markers, map image, layout display control.
- Fixture requirements: map id prefixed `codex-`, minimal image fixture, marker set, isolated operator layout if display control is tested.
- Preflight read snapshot: list maps, batch-get target map, marker list, layout/display state if relevant.
- Mutation request: create/change only a `codex-` map or marker.
- Verification command: list/batch-get maps and markers; render map image shape.
- Rollback request: remove marker/map or restore saved map body.
- Post-rollback verification: list/batch-get returns baseline.
- Risk level: medium; high for display control.
- Approval requirement: explicit map/layout approval before display actions.
