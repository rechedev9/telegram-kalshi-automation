from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class OrderStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    client_order_id TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, message_id)
                )
                """
            )

    def start(
        self,
        chat_id: int,
        message_id: int,
        message_text: str,
        client_order_id: str,
        payload: dict[str, Any],
    ) -> bool:
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO orders (
                        chat_id, message_id, message_text, client_order_id,
                        payload_json, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'processing', ?, ?)
                    """,
                    (
                        chat_id,
                        message_id,
                        message_text,
                        client_order_id,
                        _json(payload),
                        now,
                        now,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def mark_submitted(self, client_order_id: str, response: dict[str, Any]) -> None:
        self._finish(client_order_id, "submitted", response=_json(response))

    def mark_dry_run(self, client_order_id: str) -> None:
        self._finish(client_order_id, "dry_run")

    def mark_failed(self, client_order_id: str, error: str) -> None:
        self._finish(client_order_id, "failed", error=error)

    def get(self, chat_id: int, message_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id),
            ).fetchone()
        return dict(row) if row else None

    def _finish(
        self,
        client_order_id: str,
        status: str,
        response: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET status = ?, response_json = ?, error = ?, updated_at = ?
                WHERE client_order_id = ?
                """,
                (status, response, error, _now(), client_order_id),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
