from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MESSAGE_TEMPLATE = (
    "Oi!\n\n"
    "Vi que voce comentou {keyword}.\n\n"
    "Aqui esta o link:\n"
    "{link}\n\n"
    "Qualquer duvida e so me chamar!"
)


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class AutomationConfig:
    media_id: str
    keyword: str
    link: str
    active: bool = True
    message_template: str | None = None


@dataclass(frozen=True)
class Settings:
    verify_token: str
    meta_app_secret: str
    ig_access_token: str
    ig_user_id: str
    graph_version: str
    graph_base_url: str
    database_path: Path
    request_timeout_seconds: float
    log_level: str
    automations: tuple[AutomationConfig, ...]
    comment_polling_enabled: bool
    comment_polling_interval_seconds: float
    comment_polling_limit: int

    @property
    def message_endpoint(self) -> str:
        base_url = self.graph_base_url.rstrip("/")
        return f"{base_url}/{self.graph_version}/{self.ig_user_id}/messages"


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _automation_from_mapping(item: dict[str, Any]) -> AutomationConfig:
    try:
        media_id = str(item["media_id"]).strip()
        keyword = str(item["keyword"]).strip()
        link = str(item["link"]).strip()
    except KeyError as exc:
        raise ConfigError(
            "Each automation needs media_id, keyword, and link."
        ) from exc

    if not media_id or not keyword or not link:
        raise ConfigError("Automation media_id, keyword, and link cannot be empty.")

    message_template = item.get("message_template")
    if message_template is not None:
        message_template = str(message_template)

    return AutomationConfig(
        media_id=media_id,
        keyword=keyword,
        link=link,
        active=_parse_bool(item.get("active"), default=True),
        message_template=message_template,
    )


def _load_automations_from_json(raw_json: str) -> tuple[AutomationConfig, ...]:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ConfigError("AUTOMATIONS_JSON is not valid JSON.") from exc

    if isinstance(payload, dict):
        items = []
        for media_id, value in payload.items():
            if not isinstance(value, dict):
                raise ConfigError("AUTOMATIONS_JSON dict values must be objects.")
            items.append({"media_id": media_id, **value})
    elif isinstance(payload, list):
        items = payload
    else:
        raise ConfigError("AUTOMATIONS_JSON must be a list or object.")

    return tuple(_automation_from_mapping(dict(item)) for item in items)


def _load_automations_from_env() -> tuple[AutomationConfig, ...]:
    raw_json = os.getenv("AUTOMATIONS_JSON", "").strip()
    if raw_json:
        return _load_automations_from_json(raw_json)

    media_id = os.getenv("TARGET_MEDIA_ID", "").strip()
    keyword = os.getenv("STL_KEYWORD", "STL").strip()
    link = os.getenv("STL_LINK", "").strip()

    if not media_id or not keyword or not link:
        return ()

    return (
        AutomationConfig(
            media_id=media_id,
            keyword=keyword,
            link=link,
        ),
    )


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    return Settings(
        verify_token=os.getenv("VERIFY_TOKEN", ""),
        meta_app_secret=os.getenv("META_APP_SECRET", ""),
        ig_access_token=os.getenv("IG_ACCESS_TOKEN", ""),
        ig_user_id=os.getenv("IG_USER_ID", ""),
        graph_version=os.getenv("GRAPH_VERSION", "v26.0"),
        graph_base_url=os.getenv("GRAPH_BASE_URL", "https://graph.instagram.com"),
        database_path=_resolve_path(os.getenv("DATABASE_PATH", "data/instagram_bot.db")),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        automations=_load_automations_from_env(),
        comment_polling_enabled=_parse_bool(
            os.getenv("COMMENT_POLLING_ENABLED"),
            default=False,
        ),
        comment_polling_interval_seconds=float(
            os.getenv("COMMENT_POLLING_INTERVAL_SECONDS", "30")
        ),
        comment_polling_limit=int(os.getenv("COMMENT_POLLING_LIMIT", "25")),
    )
