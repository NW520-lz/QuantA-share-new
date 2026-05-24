import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    frontend_dir = _app_dir() / "前端"
    if frontend_dir.exists():
        app.mount(
            "/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend"
        )

    @app.on_event("startup")
    async def start_scanner():
        import logging

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("startup")

        from app.models.scan_result import ScanResult
        from app.core.database import engine, Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB tables ensured, starting scanner task...")

        import asyncio
        from app.services.scanner import scan_loop

        asyncio.create_task(scan_loop())
        logger.info("Scanner background task created")

    return app


app = create_app()
