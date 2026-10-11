# Validation record

This file distinguishes software checks from real-world product acceptance.

## Executed locally (through 2026-10-11)

- 30 passing Python unit/API tests: metrics, score boundaries, unusable masks, provider contract
  handling, unsupported/truncated/oversize images, EXIF stripping, private asset
  access, ownership, full scan lifecycle, deletion, capacity and rate limits.
- 12 passing Playwright tests: English landing, camera-denial backup, photo preview, actual HTTP
  upload/report/history/delete flow and no horizontal overflow at 320 px. Desktop
  and mobile projects pass. The model in these tests is a labelled test double.
  A canvas MediaStream exercises capture, retake and track cleanup; this does not
  verify physical camera hardware. Camera permission races and invalid file
  replacement are covered. Cleanup assertions wait for the dialog close event.
- Real SegFormer loaded from pinned safetensors and analyzed the ADE20K exterior
  photograph `ADE_val_00000001.jpg`. The first warm inference under the initial
  working runtime took 0.69 seconds. This is not end-to-end or phone latency.
- Homepage and mobile report screenshots were visually inspected.
- A separate real-model browser upload/report run completed in 1.26 seconds with
  the model already loaded and no JavaScript errors. Desktop and mobile report
  screenshots were captured. Rules and template fallbacks were explicitly shown.
- Docker image built successfully on Docker Desktop's Linux engine. The container
  served the health endpoint with truthful unconfigured/unloaded provider states.
  Container model inference and target-host behavior remain unverified.
- Ruff and the Tailwind production build passed. npm audit reported zero known
  vulnerabilities; pip-audit also reported zero known vulnerabilities. The
  Parcel watcher override to 2.6.0 removes the vulnerable
  micromatch/braces dependency from the development toolchain.
- Graphify's deterministic AST map contains 107 nodes and 222 edges over ten
  first-party code files. Its extraction reports 37 dangling endpoint edges and
  26 collapsed directed edges: this map is an approximate navigation aid, not
  a complete dependency proof. No semantic model API was used.

Detailed generated evidence stays under ignored `artifacts/`. Run
`scripts/validate_scenes.py` for JSON metrics, timings and overlays with the final
installed model runtime. Provider transport tests use mocked responses; no live
Jev or Gemma success is claimed without credentials/runtime.

## Required ten-scene field acceptance set

Capture your own photographs or use images you have permission to redistribute.
Place them in a folder and run the validation script, then manually inspect every
mask and decision. The two downloaded ADE20K fixtures are smoke tests only.

| Filename to prepare | Scene | Expected check | Field status |
|---|---|---|---|
| 01-park.jpg | Vegetated park | Vegetation dominates; preserve when appropriate | Pending |
| 02-concrete-street.jpg | Concrete street | Hard surfaces correctly segmented | Pending |
| 03-parking.jpg | Parking area | Paving proportion excludes vehicles | Pending |
| 04-trees-road.jpg | Trees and road | Tree presence without invented counts | Pending |
| 05-building.jpg | Building with little vegetation | Building coverage and cautious intervention | Pending |
| 06-open-ground.jpg | Open soil | Soil is a candidate, not confirmed plantability | Pending |
| 07-dark.jpg | Dark image | Reject with actionable recapture instruction | Pending |
| 08-blurred.jpg | Heavily blurred image | Reject rather than fabricate precision | Pending |
| 09-interior.jpg | Indoor room | Reject; validate actual indoor classification | Pending |
| 10-unrelated.jpg | Irrelevant close-up/object | Reject or human review | Pending |

Also pending: actual phone camera on HTTPS, 3–5 outdoor locations, live Jev response,
live Gemma explanation, target-host latency, public hosting and submission video.
Present this as a working prototype with those limits disclosed. Field-validated
environmental claims require the field checks above.
