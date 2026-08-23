from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.services.instagram import InstagramClient


SECRET = "test_app_secret"


def _signature(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("META_APP_SECRET", SECRET)
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("IG_USER_ID", "17841400000000000")
    monkeypatch.setenv("TARGET_MEDIA_ID", "18000000000000000")
    monkeypatch.setenv("STL_KEYWORD", "STL")
    monkeypatch.setenv("STL_LINK", "https://example.com/modelo.stl")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "bot.db"))
    get_settings.cache_clear()

    yield TestClient(create_app())

    get_settings.cache_clear()


def test_webhook_verification_returns_challenge(client: TestClient):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "abc123",
        },
    )

    assert response.status_code == 200
    assert response.text == "abc123"


def test_matching_comment_sends_private_reply_once(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    sent_messages = []

    def fake_send_private_reply(
        self: InstagramClient,
        comment_id: str,
        message: str,
    ) -> dict[str, str]:
        sent_messages.append((comment_id, message))
        return {"message_id": "mid.test"}

    monkeypatch.setattr(
        InstagramClient,
        "send_private_reply",
        fake_send_private_reply,
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "17900000000000000",
                            "text": " stl ",
                            "from": {"username": "cliente"},
                            "media": {"id": "18000000000000000"},
                        },
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "x-hub-signature-256": _signature(body),
    }

    first = client.post("/webhook", content=body, headers=headers)
    second = client.post("/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["sent"] == 1
    assert second.status_code == 200
    assert second.json()["sent"] == 0
    assert client.get("/health").json()["messages_sent"] == 1
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "17900000000000000"
    assert "https://example.com/modelo.stl" in sent_messages[0][1]


def test_ignores_comments_that_do_not_match(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    sent_messages = []

    monkeypatch.setattr(
        InstagramClient,
        "send_private_reply",
        lambda self, comment_id, message: sent_messages.append(comment_id),
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "17900000000000001",
                            "text": "PDF",
                            "from": {"username": "cliente"},
                            "media": {"id": "18000000000000000"},
                        },
                    },
                    {
                        "field": "comments",
                        "value": {
                            "id": "17900000000000002",
                            "text": "STL",
                            "from": {"username": "cliente"},
                            "media": {"id": "18099999999999999"},
                        },
                    },
                ]
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": _signature(body),
        },
    )

    assert response.status_code == 200
    assert response.json()["sent"] == 0
    assert sent_messages == []


def test_rejects_invalid_signature(client: TestClient):
    body = json.dumps({"entry": []}).encode("utf-8")

    response = client.post(
        "/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256=invalid",
        },
    )

    assert response.status_code == 403


def test_accepts_comma_separated_app_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    monkeypatch.setenv("VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("META_APP_SECRET", f"wrong-secret,{SECRET}")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("IG_USER_ID", "17841400000000000")
    monkeypatch.setenv("TARGET_MEDIA_ID", "18000000000000000")
    monkeypatch.setenv("STL_KEYWORD", "STL")
    monkeypatch.setenv("STL_LINK", "https://example.com/modelo.stl")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "bot.db"))
    get_settings.cache_clear()

    test_client = TestClient(create_app())
    body = json.dumps({"entry": []}).encode("utf-8")

    response = test_client.post(
        "/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": _signature(body),
        },
    )

    assert response.status_code == 200
