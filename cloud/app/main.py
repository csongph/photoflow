from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import gallery, sync

app = FastAPI(title="PhotoFlow Cloud", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(sync.router)
app.include_router(gallery.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}

