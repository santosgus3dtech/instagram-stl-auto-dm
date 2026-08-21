from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import get_settings
from app.database import CommentDatabase
from app.routes.webhook import router as webhook_router


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    CommentDatabase(settings.database_path).init()

    application = FastAPI(
        title="Instagram STL Auto DM",
        version="0.1.0",
    )
    application.include_router(webhook_router)

    @application.get("/health")
    async def health() -> dict[str, str | int]:
        return {
            "status": "ok",
            "automations": len(settings.automations),
        }

    return application


app = create_app()
