from __future__ import annotations

from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .routers import gallery, sync

ROOT_DIR = Path(__file__).resolve().parents[2]
GALLERY_DIR = ROOT_DIR / "gallery"

app = FastAPI(title="MomentLink Cloud", version="1.0.0")
configured_origins = os.getenv("GALLERY_CORS_ORIGINS", "https://photoflow-seven.vercel.app")
gallery_origins = [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=gallery_origins, allow_credentials=True, allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["*"])
app.include_router(sync.router)
app.include_router(gallery.router)

if GALLERY_DIR.exists():
    app.mount("/css", StaticFiles(directory=GALLERY_DIR / "css"), name="gallery-css")
    app.mount("/js", StaticFiles(directory=GALLERY_DIR / "js"), name="gallery-js")


@app.get("/")
def index():
    return {"ok": True, "service": "MomentLink Cloud", "gallery_api": "/api/gallery/{public_id}"}


@app.head("/", include_in_schema=False)
def index_head():
    return Response(status_code=200)


@app.get("/gallery/{public_id}")
def gallery_page(public_id: str):
    return FileResponse(GALLERY_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.head("/healthz", include_in_schema=False)
def healthz_head():
    return Response(status_code=200)
