from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import AutomationConfig, DEFAULT_MESSAGE_TEMPLATE
from app.database import CommentDatabase


logger = logging.getLogger(__name__)


class PrivateReplyClient(Protocol):
    def send_private_reply(self, comment_id: str, message: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class CommentEvent:
    comment_id: str
    media_id: str
    text: str
    username: str


@dataclass(frozen=True)
class DeliveryOutcome:
    action: str
    reason: str
    comment_id: str | None = None
    media_id: str | None = None
    username: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "action": self.action,
            "reason": self.reason,
            "comment_id": self.comment_id,
            "media_id": self.media_id,
            "username": self.username,
        }


def extract_comment_events(payload: dict[str, Any]) -> list[CommentEvent]:
    events: list[CommentEvent] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue

            value = change.get("value", {})
            media = value.get("media") or {}
            author = value.get("from") or {}

            comment_id = str(value.get("id") or "").strip()
            media_id = str(media.get("id") or value.get("media_id") or "").strip()
            text = str(value.get("text") or "")
            username = str(author.get("username") or "desconhecido")

            events.append(
                CommentEvent(
                    comment_id=comment_id,
                    media_id=media_id,
                    text=text,
                    username=username,
                )
            )

    return events


def find_matching_automation(
    event: CommentEvent,
    automations: tuple[AutomationConfig, ...],
) -> AutomationConfig | None:
    normalized_text = event.text.strip().casefold()

    for automation in automations:
        if not automation.active:
            continue
        if str(automation.media_id) != str(event.media_id):
            continue
        if automation.keyword.strip().casefold() != normalized_text:
            continue
        return automation

    return None


def render_message(automation: AutomationConfig) -> str:
    template = automation.message_template or DEFAULT_MESSAGE_TEMPLATE
    return template.format(
        keyword=automation.keyword,
        link=automation.link,
        media_id=automation.media_id,
    )


def handle_comment_event(
    event: CommentEvent,
    automations: tuple[AutomationConfig, ...],
    database: CommentDatabase,
    private_reply_client: PrivateReplyClient,
) -> DeliveryOutcome:
    if not event.comment_id:
        return DeliveryOutcome(
            action="ignored",
            reason="missing_comment_id",
            media_id=event.media_id,
            username=event.username,
        )

    automation = find_matching_automation(event, automations)
    if automation is None:
        return DeliveryOutcome(
            action="ignored",
            reason="no_matching_automation",
            comment_id=event.comment_id,
            media_id=event.media_id,
            username=event.username,
        )

    claimed = database.claim_comment(
        comment_id=event.comment_id,
        media_id=event.media_id,
        username=event.username,
        keyword=automation.keyword,
    )
    if not claimed:
        return DeliveryOutcome(
            action="ignored",
            reason="already_claimed_or_sent",
            comment_id=event.comment_id,
            media_id=event.media_id,
            username=event.username,
        )

    try:
        response = private_reply_client.send_private_reply(
            event.comment_id,
            render_message(automation),
        )
    except Exception as exc:
        logger.exception(
            "Failed to send private reply for comment %s",
            event.comment_id,
        )
        database.mark_failed(event.comment_id, str(exc))
        return DeliveryOutcome(
            action="error",
            reason="delivery_failed",
            comment_id=event.comment_id,
            media_id=event.media_id,
            username=event.username,
        )

    database.mark_sent(event.comment_id, response)
    return DeliveryOutcome(
        action="sent",
        reason="matched_keyword",
        comment_id=event.comment_id,
        media_id=event.media_id,
        username=event.username,
    )
