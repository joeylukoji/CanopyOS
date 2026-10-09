# Sources and provenance

Checked during implementation on 2026-10-08.

| Component | Primary source |
|---|---|
| FastAPI upload handling | https://fastapi.tiangolo.com/tutorial/request-files/ |
| SegFormer model and ADE20K label map | https://huggingface.co/nvidia/segformer-b0-finetuned-ade-512-512 |
| Pinned model revision | 489d5cd81a0b59fab9b7ea758d3548ebe99677da |
| Jev Choice request, probabilities and confidence | https://docs.typesafe.ai/api and https://docs.typesafe.ai/primitives/choice |
| Jev introduction supplied by the user | https://typesafe.ai/blog/introducing-system-one-models-and-jev |
| Gemma through Ollama JSON-schema chat | https://docs.ollama.com/api/chat |
| HTMX | https://htmx.org/docs/ |
| Tailwind compilation | https://tailwindcss.com/docs/installation/tailwind-cli |
| Persistent Render storage | https://render.com/docs/disks |
| Two real validation photographs | https://huggingface.co/datasets/hf-internal-testing/fixtures_ade20k |

Validation images were downloaded locally into ignored `artifacts/validation/`.
They are not bundled or redistributed with the application. They are visual model
smoke tests, not user field observations or evidence of model accuracy.

The homepage streetscape is an original SVG illustration, explicitly labelled as
an illustration. It is not a photograph, segmentation output or analyzed scan.

Agent Skills, Ponytail and Graphify assisted development and do not run inside the
product's inference pipeline. The Graphify map covers application Python code and
the first-party browser script; it excludes vendor libraries and personal images.
