# -*- coding: utf-8 -*-
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from routers.dashboard import router as dashboard_router
from services.run_manager import run_manager

app = FastAPI(
    title="Dashboard Querying API",
    description="Independent dashboard querying and runtime configuration service",
    version="1.0.0",
)

MODULE_ROOT = Path(__file__).resolve().parent
WEBUI_DIR = MODULE_ROOT / "webui"

app.include_router(dashboard_router)


@app.get("/")
async def index():
    html_path = WEBUI_DIR / "dashboard_query.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return {"message": "dashboard_query.html not found"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    await run_manager.start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    await run_manager.stop_scheduler()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
