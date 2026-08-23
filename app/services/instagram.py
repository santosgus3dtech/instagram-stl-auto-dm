from __future__ import annotations

from typing import Any

import requests

from app.config import ConfigError, Settings


class InstagramAPIError(RuntimeError):
    def __init__(self, status_code: int, response_text: str):
        super().__init__(f"Instagram API error {status_code}: {response_text}")
        self.status_code = status_code
        self.response_text = response_text


class InstagramClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()

    def send_private_reply(self, comment_id: str, message: str) -> dict[str, Any]:
        if not self.settings.ig_access_token:
            raise ConfigError("IG_ACCESS_TOKEN is required to send private replies.")
        if not self.settings.ig_user_id:
            raise ConfigError("IG_USER_ID is required to send private replies.")

        payload = {
            "recipient": {
                "comment_id": str(comment_id),
            },
            "message": {
                "text": message,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.ig_access_token}",
            "Content-Type": "application/json",
        }

        response = self.session.post(
            self.settings.message_endpoint,
            headers=headers,
            json=payload,
            timeout=self.settings.request_timeout_seconds,
        )

        if not response.ok:
            raise InstagramAPIError(response.status_code, response.text)

        return response.json()

    def list_media_comments(self, media_id: str, limit: int = 25) -> list[dict[str, Any]]:
        if not self.settings.ig_access_token:
            raise ConfigError("IG_ACCESS_TOKEN is required to list comments.")

        base_url = self.settings.graph_base_url.rstrip("/")
        response = self.session.get(
            f"{base_url}/{self.settings.graph_version}/{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp",
                "limit": limit,
                "access_token": self.settings.ig_access_token,
            },
            timeout=self.settings.request_timeout_seconds,
        )

        if not response.ok:
            raise InstagramAPIError(response.status_code, response.text)

        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]
