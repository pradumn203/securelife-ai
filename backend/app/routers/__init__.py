"""HTTP routers. `register_routers(app)` is the single wiring entry point."""
from fastapi import FastAPI

from app.routers import analysis, chat, documents, health, leads


def register_routers(app: FastAPI) -> None:
    """Attach every router under the /api prefix."""
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
