from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import CommentDatabase
from app.routes.webhook import router as webhook_router
from app.services.instagram import InstagramClient
from app.services.poller import CommentPoller


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    database = CommentDatabase(settings.database_path)
    database.init()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        poller: CommentPoller | None = None
        if settings.comment_polling_enabled:
            poller = CommentPoller(settings, database, InstagramClient(settings))
            application.state.comment_poller = poller
            poller.start()
        try:
            yield
        finally:
            if poller is not None:
                await poller.stop()

    application = FastAPI(
        title="Instagram STL Auto DM",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(webhook_router)

    @application.get("/health")
    async def health() -> dict[str, str | int]:
        stats = database.delivery_stats()
        return {
            "status": "ok",
            "automations": len(settings.automations),
            "comment_poller": int(settings.comment_polling_enabled),
            **stats,
        }

    return application


app = create_app()
