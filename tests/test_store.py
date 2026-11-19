from __future__ import annotations

from pathlib import Path

import pytest

from telegram_kalshi.store import OrderStore


@pytest.fixture()
def store(tmp_path: Path) -> OrderStore:
    return OrderStore(tmp_path / "test.db")


def test_start_returns_true_on_first_insert(store: OrderStore) -> None:
    result = store.start(123, 1, "text", "tg-aaa", {"preview": True})
    assert result is True


def test_start_returns_false_on_duplicate(store: OrderStore) -> None:
    store.start(123, 1, "text", "tg-aaa", {"preview": True})
    result = store.start(123, 1, "text", "tg-aaa", {"preview": True})
    assert result is False


def test_mark_submitted(store: OrderStore) -> None:
    store.start(123, 1, "text", "tg-aaa", {"preview": True})
    store.mark_submitted("tg-aaa", {"order_id": "xyz"})
    row = store.get(123, 1)
    assert row is not None
    assert row["status"] == "submitted"


def test_mark_dry_run(store: OrderStore) -> None:
    store.start(123, 2, "text", "tg-bbb", {"preview": True})
    store.mark_dry_run("tg-bbb")
    row = store.get(123, 2)
    assert row is not None
    assert row["status"] == "dry_run"


def test_mark_failed(store: OrderStore) -> None:
    store.start(123, 3, "text", "tg-ccc", {"preview": True})
    store.mark_failed("tg-ccc", "timeout")
    row = store.get(123, 3)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] == "timeout"


def test_get_returns_none_for_missing(store: OrderStore) -> None:
    assert store.get(999, 999) is None


def test_unique_client_order_id_rejected(store: OrderStore) -> None:
    assert store.start(123, 1, "text", "tg-same", {"a": 1}) is True
    assert store.start(456, 2, "text", "tg-same", {"b": 2}) is False
