# Maestro v2.1

The v2.1 patch promotes the technical "Project Setup" choices from a
per-pipeline sidebar to a per-project configuration. Every project now
bakes in its own aspect ratio, resolution, workflow mode, video + image
models, audio default, default LoRAs and advanced defaults the moment
the project is created. The Director's right column is now strictly
per-take.

## Highlights

- **Project Setup lives on the workspace.** Aspect ratio, resolution,
  Seamless / Auto toggles, video + image model, music source, and
  Advanced defaults are now stored in `outputs/<project>/setup.json`.
  Old in-pipeline `director_ui_snapshot` values still load when you
  open a saved pipeline — the migration is automatic on first read.
- **The New project dialog collects setup up front.** No more flipping
  back to the right column after planning starts. The "Project setup
  is locked after planning begins" warning is gone — those choices
  are settled once, at creation.
- **Edit setup from the project card.** A gear icon next to each
  project lets the user change the project defaults at any time.
  Changes apply on the next workspace switch.
- **The right column is per-take.** Shows a "Project defaults" chip at
  the top with a Reset button so per-take overrides stay explicit.
  Removing the lock means the user can change aspect ratio or model
  mid-take without a separate "Edit project" detour.
- **Robust endpoint surface.** New `GET /api/v1/workspaces/<name>/setup`
  and `PUT /api/v1/workspaces/<name>/setup`. The list endpoint embeds
  the setup so the project card can render the "16:9 · 720p · LTX-2"
  chip without a second round-trip. Atomic temp-file write so a
  crashed save never corrupts setup.json.
- **Validation + forward-compat.** Bad payloads are rejected at the
  HTTP boundary (HTTP 400) with a clear message. Unknown keys are
  stripped before persist. Schema version 1 with a forward-compat path
  for v2 fields when the schema bumps.

## API changes

```
GET   /api/v1/workspaces                 # now embeds `setup` per workspace
GET   /api/v1/workspaces/<name>/setup    # 200 + setup defaults if absent
PUT   /api/v1/workspaces/<name>/setup    # 200 on success, 400 on bad shape
```

## Schema

`setup.json` shape (persisted at `outputs/<project>/setup.json`):

```json
{
  "schema_version": 1,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "seamless": false,
  "auto_mode": false,
  "video_model": "ltx2_22B_distilled_1_1",
  "image_model": "flux2_klein_9b",
  "music_source": "upload",
  "music_model": "",
  "default_image_loras": {},
  "default_video_loras": {},
  "advanced": {}
}
```

Field semantics:

| key                 | type    | meaning                                              |
|---------------------|---------|------------------------------------------------------|
| aspect_ratio        | string  | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / 21:9 (H3 only)      |
| resolution          | string  | 480p / 540p / 720p / 1080p (no `auto` — per-take)   |
| seamless            | bool    | Continuous sliding-window timeline                   |
| auto_mode           | bool    | Skip every review step                               |
| video_model         | string  | Project's default video model id (empty = inherit)   |
| image_model         | string  | Project's default image model id                     |
| music_source        | string  | "upload" or "generate"                               |
| music_model         | string  | Music model id when music_source = "generate"        |
| default_image_loras | object  | Activated + multipliers for image LoRAs              |
| default_video_loras | object  | Activated + multipliers for video LoRAs              |
| advanced            | object  | Free-form forward-compat blob                        |
| schema_version      | integer | Bump on breaking changes                             |

## Tests

- 13 new backend tests in `tests/test_project_setup.py` covering
  validation, atomic persist, partial-persist, traversal rejection,
  unknown-key stripping, future-schema resilience, and default-workspace
  refusal.
- All 13 pass in a clean venv. Full project test count went from 102
  → 115 (same 1 pre-existing Playwright failure remains; unrelated
  to this patch).

## Migration notes

- **For users opening an existing project for the first time after
  v2.1 lands**: the workspace falls back to schema defaults (16:9,
  720p, both toggles off, no model). Open the Edit setup dialog to
  fill in the values from your last run; subsequent runs use those.
- **For pipelines opened from `director_ui_snapshot`**: values from
  the snapshot still hydrate the runtime fields, so Open & Edit
  preserves whatever aspect ratio + resolution the user had when
  the pipeline ran. The new Project Setup applies only on the next
  fresh planning session.
