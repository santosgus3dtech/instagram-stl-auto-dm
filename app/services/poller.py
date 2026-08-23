from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from app.config import AutomationConfig, Settings
from app.database import CommentDatabase
from app.services.automations import CommentEvent, handle_comment_event
from app.services.instagram import InstagramClient


logger = logging.getLogger(__name__)


class CommentPoller:
    def __init__(
        self,
        settings: Settings,
        database: CommentDatabase,
        instagram_client: InstagramClient,
    ):
        self.settings = settings
        self.database = database
        self.instagram_client = instagram_client
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="instagram-comment-poller")
        logger.info(
            "Instagram comment poller started: interval=%ss automations=%s",
            self.settings.comment_polling_interval_seconds,
            len(self.settings.automations),
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception:
                logger.exception("Instagram comment poller failed.")
            await asyncio.sleep(self.settings.comment_polling_interval_seconds)

    async def poll_once(self) -> dict[str, int]:
        return await asyncio.to_thread(self._poll_once_sync)

    def seed_existing_comments(self) -> dict[str, int]:
        totals = {"seen": 0, "errors": 0}
        for automation in self.settings.automations:
            try:
                comments = self.instagram_client.list_media_comments(
                    automation.media_id,
                    limit=self.settings.comment_polling_limit,
                )
            except Exception:
                totals["errors"] += 1
                logger.exception(
                    "Failed to seed existing comments for media %s.",
                    automation.media_id,
                )
                continue

            for item in comments:
                event = _comment_event_from_api_item(automation.media_id, item)
                if not event.comment_id:
                    continue
                if self.database.remember_comment(
                    comment_id=event.comment_id,
                    media_id=event.media_id,
                    username=event.username,
                    keyword=automation.keyword,
                ):
                    totals["seen"] += 1

        logger.info(
            "Instagram comment poller seeded existing comments: seen=%s errors=%s",
            totals["seen"],
            totals["errors"],
        )
        return totals

    def _poll_once_sync(self) -> dict[str, int]:
        totals = {"checked": 0, "sent": 0, "ignored": 0, "errors": 0}
        for automation in self.settings.automations:
            try:
                comments = self.instagram_client.list_media_comments(
                    automation.media_id,
                    limit=self.settings.comment_polling_limit,
                )
            except Exception:
                totals["errors"] += 1
                logger.exception(
                    "Failed to list comments for media %s.",
                    automation.media_id,
                )
                continue

            for item in comments:
                totals["checked"] += 1
                event = _comment_event_from_api_item(automation.media_id, item)
                outcome = handle_comment_event(
                    event,
                    self.settings.automations,
                    self.database,
                    self.instagram_client,
                )
                if outcome.action == "sent":
                    totals["sent"] += 1
                elif outcome.action == "error":
                    totals["errors"] += 1
                else:
                    totals["ignored"] += 1

        logger.info(
            "Instagram comment poller processed: checked=%s sent=%s ignored=%s errors=%s",
            totals["checked"],
            totals["sent"],
            totals["ignored"],
            totals["errors"],
        )
        return totals


def _comment_event_from_api_item(media_id: str, item: dict[str, Any]) -> CommentEvent:
    return CommentEvent(
        comment_id=str(item.get("id") or "").strip(),
        media_id=str(media_id),
        text=str(item.get("text") or ""),
        username=str(item.get("username") or "desconhecido"),
    )
