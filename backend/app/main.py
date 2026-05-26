import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handler import (
    global_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError


def _setup_logging() -> None:
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


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

    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

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
        _setup_logging()
        logger = logging.getLogger("startup")

        from app.models.scan_result import ScanResult
        from app.core.database import engine, Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB tables ensured")

        if settings.skip_initial_scan:
            logger.info(
                "SKIP_INITIAL_SCAN=1, scanner not started (use /api/v1/scan to trigger)"
            )
            return

        import asyncio
        from app.services.scanner import scan_loop

        asyncio.create_task(scan_loop())
        logger.info("Scanner background task created")

    return app


app = create_app()
