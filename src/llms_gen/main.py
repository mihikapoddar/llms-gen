from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from llms_gen.api.routes.jobs import router as jobs_router
from llms_gen.api.routes.monitored import router as monitored_router
from llms_gen.config import get_settings
from llms_gen.db_session import init_db
from llms_gen.services.monitor_scheduler import monitor_loop

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    monitor_task: Optional[asyncio.Task] = None
    if get_settings().monitor_enabled:
        monitor_task = asyncio.create_task(monitor_loop())
    yield
    if monitor_task is not None:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


_cfg = get_settings()
_openapi = _cfg.expose_openapi

app = FastAPI(
    title="llms-gen",
    description="Generate llms.txt files from public websites",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _openapi else None,
    redoc_url="/redoc" if _openapi else None,
    openapi_url="/openapi.json" if _openapi else None,
)
app.include_router(jobs_router)
app.include_router(monitored_router)


@app.get("/")
async def index(request: Request):
    s = get_settings()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "expose_openapi": s.expose_openapi,
            "public_base_url": s.public_base_url,
        },
    )


@app.head("/")
async def index_head() -> Response:
    """Render and other platforms often probe the service root with HEAD."""
    return Response(status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok"}
