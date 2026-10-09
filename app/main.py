import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.pipeline import Pipeline
from app.services.providers import ACTIONS
from app.services.vision import SegFormer, decode_image
from app.storage import ScanBusy, Store

load_dotenv()
ROOT = Path(__file__).parent
MAX_IMAGE = 8 * 1024 * 1024
MAX_BODY = MAX_IMAGE + 64 * 1024
AREA = Literal["urban_open_space", "street", "park", "campus", "parking"]


def create_app(data_dir: Path | None = None, vision=None):
    store = Store(data_dir or Path(os.getenv("DATA_DIR", "data")))
    settings = {
        "jev_key": os.getenv("JEV_API_KEY", ""),
        "jev_model": os.getenv("JEV_MODEL", "jev-latest"),
        "gemma_endpoint": os.getenv("GEMMA_ENDPOINT", ""),
        "gemma_key": os.getenv("GEMMA_API_KEY", ""),
        "gemma_model": os.getenv("GEMMA_MODEL", "gemma3:1b"),
    }
    secret_file = store.root / ".session-key"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
    vision = vision or SegFormer()
    pipeline = Pipeline(store, vision, settings)

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield

    app = FastAPI(title="CanopyOS", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.pipeline = store, pipeline
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_file.read_text(),
        session_cookie="canopy_session",
        same_site="strict",
        https_only=os.getenv("APP_ENV") == "production",
        max_age=30 * 86400,
    )
    (ROOT / "static").mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.globals["actions"] = ACTIONS

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.method in ("POST", "DELETE", "PUT", "PATCH"):
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if (origin and origin != expected) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                return JSONResponse(
                    {"detail": "Cross-origin requests are not allowed."}, status_code=403
                )
            body, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY:
                    return JSONResponse(
                        {"detail": "Image exceeds the 8 MiB limit."}, status_code=413
                    )
                body.append(chunk)
            request._body = b"".join(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if not request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        if os.getenv("APP_ENV") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    def owner(request):
        if "owner" not in request.session:
            request.session["owner"] = secrets.token_hex(24)
        return request.session["owner"]

    def get_scan(scan_id, request):
        scan = store.get(str(scan_id), owner(request))
        if not scan:
            raise HTTPException(404, "Scan not found.")
        return scan

    def rate(request, kind, personal, total):
        if not store.allow(owner(request), kind, personal, total):
            raise HTTPException(
                429,
                "Too many requests. Please try again in one minute.",
                headers={"Retry-After": "60"},
            )

    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok"
            if vision.status == "ready"
            and pipeline.jev_status == "ready"
            and pipeline.llm_status == "ready"
            else "degraded",
            "vision": vision.status,
            "jev": pipeline.jev_status,
            "llm": pipeline.llm_status,
        }

    @app.post("/api/v1/scans", status_code=201)
    async def upload(
        request: Request,
        image: Annotated[UploadFile, File()],
        area_type: Annotated[AREA, Form()] = "urban_open_space",
    ):
        rate(request, "upload", 20, 60)
        try:
            if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
                raise HTTPException(415, "Use a JPEG, PNG or WebP image.")
            content = await image.read(MAX_IMAGE + 1)
            if len(content) > MAX_IMAGE:
                raise HTTPException(413, "Image exceeds the 8 MiB limit.")
            try:
                clean = decode_image(content)
            except ValueError as exc:
                raise HTTPException(415, str(exc)) from exc
        finally:
            await image.close()
        scan_id = store.create(owner(request), area_type)
        try:
            clean.save(store.folder(scan_id) / "original.jpg", quality=90)
        except Exception:
            store.delete(scan_id, owner(request))
            raise HTTPException(503, "Unable to save this scan. Please try again.") from None
        store.prune(owner(request))
        return get_scan(scan_id, request)

    @app.post("/api/v1/scans/{scan_id}/analyze", status_code=202)
    def analyze(scan_id: UUID, request: Request, background: BackgroundTasks):
        scan = get_scan(scan_id, request)
        if scan["status"] in ("completed", "processing"):
            return scan
        rate(request, "analysis", 6, 15)
        if not pipeline.slot.acquire(blocking=False):
            raise HTTPException(409, "Another scan is being analyzed. Please retry shortly.")
        try:
            if not store.claim(str(scan_id), owner(request)):
                raise HTTPException(409, "This scan changed. Refresh the page before retrying.")
            background.add_task(pipeline.run, scan)
            return get_scan(scan_id, request)
        except Exception:
            pipeline.slot.release()
            raise

    @app.get("/api/v1/scans")
    def history(
        request: Request, limit: int = Query(20, ge=1, le=20), offset: int = Query(0, ge=0)
    ):
        return store.list(owner(request), limit, offset)

    @app.get("/api/v1/scans/{scan_id}")
    def retrieve(scan_id: UUID, request: Request):
        return get_scan(scan_id, request)

    @app.delete("/api/v1/scans/{scan_id}", status_code=204)
    def delete(scan_id: UUID, request: Request):
        scan = get_scan(scan_id, request)
        if scan["status"] == "processing":
            raise HTTPException(409, "Wait for analysis to finish before deleting this scan.")
        try:
            store.delete(str(scan_id), owner(request))
        except ScanBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(status_code=204)

    @app.get("/assets/{scan_id}/{filename}")
    def asset(scan_id: UUID, filename: str, request: Request):
        get_scan(scan_id, request)
        if filename not in ("original.jpg", "segmentation.jpg", "concept.jpg"):
            raise HTTPException(404, "Image not found.")
        path = store.folder(str(scan_id)) / filename
        if not path.is_file():
            raise HTTPException(404, "Image not found.")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/")
    def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"scans": store.list(owner(request), 3), "page": "home"},
        )

    @app.get("/history")
    def history_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="history.html",
            context={"scans": store.list(owner(request)), "page": "history"},
        )

    @app.get("/scans/{scan_id}")
    def report_page(scan_id: UUID, request: Request):
        return templates.TemplateResponse(
            request=request,
            name="scan.html",
            context={"scan": get_scan(scan_id, request), "page": "report"},
        )

    @app.get("/scans/{scan_id}/fragment")
    def report_fragment(scan_id: UUID, request: Request):
        return templates.TemplateResponse(
            request=request, name="report.html", context={"scan": get_scan(scan_id, request)}
        )

    return app


app = create_app()
