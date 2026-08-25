from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import gallery, sync

ROOT_DIR = Path(__file__).resolve().parents[2]
GALLERY_DIR = ROOT_DIR / "gallery"

app = FastAPI(title="MomentLink Cloud", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(sync.router)
app.include_router(gallery.router)

if GALLERY_DIR.exists():
    app.mount("/css", StaticFiles(directory=GALLERY_DIR / "css"), name="gallery-css")
    app.mount("/js", StaticFiles(directory=GALLERY_DIR / "js"), name="gallery-js")


@app.get("/")
def index():
    return {"ok": True, "service": "MomentLink Cloud", "gallery": "/gallery/{public_id}"}


@app.get("/gallery/{public_id}")
def gallery_page(public_id: str):
    return FileResponse(GALLERY_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/healthz")
def healthz():
    return {"ok": True}
