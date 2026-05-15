# Axxon One Layout Read Smoke

- Started: `2026-05-06T18:24:21.837228+00:00`
- Finished: `2026-05-06T18:24:23.218030+00:00`
- gRPC target: `<demo-host>:20109`

This smoke is read-only. It does not call `LayoutManager.Update`, `LayoutsOnView`, or Client HTTP.

## Summary

- PASS: 3
- WARN: 0
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `list_layouts` | 521 | layouts=20 current=05f95dac-69db-4398-8825-a5709acbabf7 map_ids=20 map_arrangements=11 |
| PASS | `batch_get` | 118 | requested=05f95dac-69db-4398-8825-a5709acbabf7 items=1 not_found=0 |
| PASS | `list_images` | 139 | layout=05f95dac-69db-4398-8825-a5709acbabf7 images=0 |

## Layout Samples

| Layout ID | Name | Map ID | Map View Mode | Cells | Has Arrangement | Arrangement Keys |
| --- | --- | --- | --- | ---: | --- | --- |
| `a7cf0082-6aa6-4c57-a46c-8fc1f3c61d2f` | New layout 20 | `00000000-0000-0000-0000-000000000000` | `` | 2 | False |  |
| `7f4036f2-25e7-49f1-8a7e-dfb25e79ccaa` | Grundig | `00000000-0000-0000-0000-000000000000` | `` | 3 | True | zoom_position |
| `f709381f-d746-47e7-a2aa-e9883578e23a` | Traffic Monitor / Statistics | `00000000-0000-0000-0000-000000000000` | `` | 1 | True | zoom_position |
| `d97f487e-0996-44c4-abf8-2a277e378cd4` | Cyclysts counter (custom NN) | `00000000-0000-0000-0000-000000000000` | `` | 3 | True | zoom_position |
| `25d6f633-3a4b-42ad-8579-2158fdabb045` | Parking Lot Occupancy | `00000000-0000-0000-0000-000000000000` | `` | 2 | True | zoom_position |
| `c6120b2a-f240-4507-b933-19476ee85ed6` | Counter | `00000000-0000-0000-0000-000000000000` | `` | 1 | True | zoom_position |
| `b74bf4cd-6aca-4eb7-a62c-9a116e3ce3dd` | Fight detection | `00000000-0000-0000-0000-000000000000` | `` | 2 | True | zoom_position |
| `7fd904ac-4b03-4ac1-9b6b-cf115857d1b1` | Crowd VA | `00000000-0000-0000-0000-000000000000` | `` | 1 | True | zoom_position |
| `0dc82f98-6f47-4210-82f4-b383b033bdb6` | ACFA | `23965d15-3389-42b5-98ab-1bed739b8ab3` | `MAP_VIEW_MODE_MAP_AND_LAYOUT` | 3 | True | is_thumbnail_3d_on, map_top_viewport_position, video_transparency_collection, zoom_position |
| `e141acc5-f45a-4c33-903c-fe08de974fcf` | Multicamera tracking | `d4eb775e-e82a-4aef-9484-04ca646d36b8` | `MAP_VIEW_MODE_MAP_AND_LAYOUT` | 3 | True | map_top_viewport_position, video_transparency_collection, zoom_position |
