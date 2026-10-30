from __future__ import annotations

import logging
import mimetypes
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .models import Event
from .queue.worker import JobWorker, recover_jobs
from .routers import dashboard, diagnostics, events, gallery, google, settings as settings_router
from .security import auth_enabled, login, login_page, logout, require_admin, valid_session, COOKIE_NAME
from .utils.logging import configure_logging
from .watcher.service import watcher_manager

configure_logging()
log = logging.getLogger("photoflow")
worker = JobWorker(settings.max_workers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        recover_jobs()
        for event in db.query(Event).filter(Event.status == "LIVE").all():
            watcher_manager.start_event(event)
    worker.start()
    log.info("CS.BXXM STUDIO local started")
    yield
    watcher_manager.stop_all()
    worker.stop()


app = FastAPI(title="CS.BXXM STUDIO Local", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    response = await require_admin(request, call_next)
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.get("/login")
def login_view():
    return login_page()


@app.post("/api/auth/login")
async def login_post(request: Request):
    return await login(request)


@app.post("/api/auth/logout")
def logout_post():
    return logout()


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {
        "enabled": auth_enabled(),
        "authenticated": (not auth_enabled()) or valid_session(request.cookies.get(COOKIE_NAME, "")),
    }

app.include_router(events.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(diagnostics.router)
app.include_router(gallery.router)
app.include_router(google.router)

app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")
gallery_dir = settings.frontend_dir.parent.parent / "gallery"
app.mount("/css", StaticFiles(directory=gallery_dir / "css"), name="gallery-css")
app.mount("/js", StaticFiles(directory=gallery_dir / "js"), name="gallery-js")
frames_dir = settings.frontend_dir.parent.parent / "assets" / "frames"
app.mount("/frames", StaticFiles(directory=frames_dir), name="photobooth-frames")


@app.get("/")
def index():
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/events")
def events_page():
    return FileResponse(settings.frontend_dir / "event.html")


@app.get("/settings")
def settings_page():
    return FileResponse(settings.frontend_dir / "settings.html")


@app.get("/setup")
def setup_page():
    return FileResponse(settings.frontend_dir / "setup.html")


@app.get("/diagnostics")
def diagnostics_page():
    return FileResponse(settings.frontend_dir / "diagnostics.html")


@app.get("/gallery")
def gallery_preview_page():
    return FileResponse(settings.frontend_dir / "gallery-preview.html")


@app.get("/archive")
def archive_page():
    return FileResponse(settings.frontend_dir / "archive.html")


@app.get("/gallery/{public_id}")
def local_gallery_redirect(public_id: str):
    if public_id == "local-preview":
        return FileResponse(settings.frontend_dir / "gallery-preview.html")
    return FileResponse(gallery_dir / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/media/{event_id}/{variant}/{filename}")
def media(event_id: str, variant: str, filename: str):
    allowed = {"THUMBNAILS", "PREVIEWS", "FINISHED"}
    if variant not in allowed or "/" in filename or "\\" in filename:
        raise HTTPException(404, "Not found")
    with SessionLocal() as db:
        event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Not found")
    root = Path(event.root_path).resolve()
    path = (root / variant / filename).resolve()
    if root not in path.parents or not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "image/jpeg")


@app.get("/healthz")
def healthz():
    return {"ok": True}
