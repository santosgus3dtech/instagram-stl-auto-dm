from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class CommentDatabase:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def init(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comment_deliveries (
                    comment_id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    username TEXT,
                    keyword TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 1,
                    response_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def claim_comment(
        self,
        *,
        comment_id: str,
        media_id: str,
        username: str,
        keyword: str,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO comment_deliveries (
                    comment_id,
                    media_id,
                    username,
                    keyword,
                    status
                )
                VALUES (?, ?, ?, ?, 'processing')
                ON CONFLICT(comment_id) DO UPDATE SET
                    status = 'processing',
                    attempts = attempts + 1,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE comment_deliveries.status = 'failed'
                """,
                (comment_id, media_id, username, keyword),
            )

            return cursor.rowcount == 1

    def mark_sent(self, comment_id: str, response: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE comment_deliveries
                SET
                    status = 'sent',
                    response_json = ?,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE comment_id = ?
                """,
                (json.dumps(response, ensure_ascii=True), comment_id),
            )

    def mark_failed(self, comment_id: str, error_message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE comment_deliveries
                SET
                    status = 'failed',
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE comment_id = ?
                """,
                (error_message[:2000], comment_id),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
