# Deployment

## Local demo

Run one Uvicorn worker and warm the model using a non-sensitive test photo before
presenting. Do not start with `--reload` for a demo: a restart interrupts analysis.
The liveness endpoint `/api/v1/health` returns HTTP 200 even when optional providers
are unconfigured, but its JSON says `degraded` and describes each provider honestly.
`configured_unverified` means settings exist; it does not claim a successful API call.
Provider readiness reflects the last attempted scan, not an active availability probe.

## Render

Use the provided Dockerfile with a Render web service. The `render.yaml` blueprint
is a starting configuration, not an already-created service. It requires a paid
persistent disk; review current Render costs before creating it.

1. Push this repository to your own GitHub repository.
2. Create the web service from `render.yaml`, review the plan and disk cost.
3. Set `JEV_API_KEY` and, if available, an HTTPS Ollama-compatible `GEMMA_ENDPOINT`.
4. Preserve `DATA_DIR=/var/data/canopyos` and `HF_HOME=/var/data/model-cache`.
5. Wait for the image to build, run one scan, and check logs plus health JSON.
6. Test capture on an actual phone over the Render HTTPS address.

SQLite, session signing key, images and model cache must survive restarts. An
ephemeral free instance is unsuitable for persistent scan history. Run one instance
and one worker; the in-process analysis lock is intentionally not distributed.
No automatic deployment or paid service creation is performed by these files.

## Docker

```sh
docker build -t canopyos .
docker run --rm -p 8000:8000 -v canopy-data:/var/data --env-file .env canopyos
```

Use `APP_ENV=development` for HTTP localhost Docker testing; production enables
Secure cookies and HSTS and must sit behind HTTPS. The application never renders
provider credentials. A local Linux-container build and HTTP health check passed;
model inference and deployment must still be verified on the target Linux host.
The startup command uses the platform's PORT value and must remain single-worker.

## Operational checks

Keep disk usage and scan latency visible. Use a reverse proxy request limit as an
additional layer. Back up the SQLite database consistently and protect its signing
key. Removing the signing key invalidates access to existing anonymous scans.
The application limits retained scans per browser; operators must manage retention
of abandoned browser histories before opening the service broadly to the public.

Interrupted processing is marked failed on restart and can be retried. To roll back,
deploy the previous image with the same data volume; the current schema is additive.
Verify upload, asset authorization, analysis and deletion after any rollback.
