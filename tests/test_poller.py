from __future__ import annotations

import pytest

from app.config import Settings, AutomationConfig
from app.database import CommentDatabase
from app.services.poller import CommentPoller


class FakeInstagramClient:
    def __init__(self):
        self.comments = []
        self.sent = []

    def list_media_comments(self, media_id: str, limit: int = 25):
        return list(self.comments[:limit])

    def send_private_reply(self, comment_id: str, message: str):
        self.sent.append((comment_id, message))
        return {"message_id": f"mid.{comment_id}"}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        verify_token="verify",
        meta_app_secret="secret",
        ig_access_token="token",
        ig_user_id="17841400000000000",
        graph_version="v26.0",
        graph_base_url="https://graph.instagram.com",
        database_path=tmp_path / "bot.db",
        request_timeout_seconds=1,
        log_level="INFO",
        automations=(
            AutomationConfig(
                media_id="18000000000000000",
                keyword="STL",
                link="https://example.com/modelo.stl",
            ),
        ),
        comment_polling_enabled=True,
        comment_polling_interval_seconds=30,
        comment_polling_limit=25,
    )


def test_poller_seeds_existing_comments_before_sending_new_ones(settings):
    database = CommentDatabase(settings.database_path)
    database.init()
    instagram = FakeInstagramClient()
    instagram.comments = [
        {"id": "old-comment", "text": "STL", "username": "cliente"},
    ]
    poller = CommentPoller(settings, database, instagram)

    assert poller.seed_existing_comments()["seen"] == 1
    assert poller._poll_once_sync()["sent"] == 0

    instagram.comments.insert(
        0,
        {"id": "new-comment", "text": "stl", "username": "cliente"},
    )
    result = poller._poll_once_sync()

    assert result["sent"] == 1
    assert instagram.sent == [
        (
            "new-comment",
            (
                "Oi!\n\n"
                "Vi que voce comentou STL.\n\n"
                "Aqui esta o link:\n"
                "https://example.com/modelo.stl\n\n"
                "Qualquer duvida e so me chamar!"
            ),
        )
    ]
