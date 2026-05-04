from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

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


app = FastAPI(
    title="llms-gen",
    description="Generate llms.txt files from public websites",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(jobs_router)
app.include_router(monitored_router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}
