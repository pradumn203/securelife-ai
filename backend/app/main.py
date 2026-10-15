"""FastAPI application entrypoint.

All routers are registered here. All startup/shutdown lifecycle lives in
`lifespan`. No business logic in this file.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_db, init_db, shutdown_db
from app.routers import register_routers
from app.settings import get_settings


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=level_name.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _sweep_orphaned_processing() -> None:
    """Mark any Document stuck in PROCESSING across a restart as FAILED.

    Prod path replaces this with a durable queue (see ARCHITECTURE.md §11).
    """
    from app.repositories.documents import DocumentRepository

    async with get_db().session() as session:
        swept = await DocumentRepository(session).sweep_orphaned_processing(
            older_than_seconds=600
        )
        if swept:
            logging.getLogger("securelife").warning(
                "Startup orphan sweep: marked %d PROCESSING rows as FAILED", swept
            )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create DB tables on startup; dispose engine on shutdown."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    log = logging.getLogger("securelife")
    log.info("Starting SecureLife AI backend")
    await init_db()
    await _sweep_orphaned_processing()
    try:
        yield
    finally:
        log.info("Shutting down SecureLife AI backend")
        await shutdown_db()


def create_app() -> FastAPI:
    """Application factory. Use this from tests, not the module-level `app`."""
    settings = get_settings()
    app = FastAPI(
        title="SecureLife AI",
        description="Lead qualification + document intelligence API.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routers(app)
    return app


app = create_app()
