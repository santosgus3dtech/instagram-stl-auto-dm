from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.database import CommentDatabase
from app.security import verify_meta_signature
from app.services.automations import extract_comment_events, handle_comment_event
from app.services.instagram import InstagramClient


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    settings = get_settings()

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.verify_token and challenge is not None:
        logger.info("Meta webhook verified.")
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Invalid verification token.")


@router.post("/webhook")
async def instagram_webhook(request: Request) -> dict[str, object]:
    settings = get_settings()
    raw_body = await request.body()

    signature = request.headers.get("x-hub-signature-256")
    if not verify_meta_signature(raw_body, signature, settings.meta_app_secret):
        raise HTTPException(status_code=403, detail="Invalid request signature.")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    database = CommentDatabase(settings.database_path)
    database.init()

    client = InstagramClient(settings)
    events = extract_comment_events(payload)
    outcomes = [
        handle_comment_event(event, settings.automations, database, client)
        for event in events
    ]

    sent_count = sum(1 for outcome in outcomes if outcome.action == "sent")
    error_count = sum(1 for outcome in outcomes if outcome.action == "error")

    return {
        "status": "ok",
        "received_events": len(events),
        "sent": sent_count,
        "errors": error_count,
        "results": [outcome.as_dict() for outcome in outcomes],
    }
