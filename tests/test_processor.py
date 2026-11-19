from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from telegram_kalshi.config import Settings
from telegram_kalshi.processor import OrderProcessor
from telegram_kalshi.resolver import MarketResolver, ResolvedSelection
from telegram_kalshi.store import OrderStore


def _settings(
    dry_run: bool = True,
    max_contracts: int = 100,
    max_notional: str = "100.00",
) -> Settings:
    return Settings(
        telegram_api_id=None,
        telegram_api_hash="",
        telegram_channel=-1002160464787,
        telegram_session="data/telegram",
        kalshi_env="demo",
        kalshi_api_key_id="",
        kalshi_private_key_path="",
        dry_run=dry_run,
        allow_live_trading=False,
        stake_unit_usd=Decimal("1"),
        max_contracts_per_order=max_contracts,
        max_notional_per_order_usd=Decimal(max_notional),
        allowed_tickers=frozenset(),
        combo_collection="KXMVECROSSCATEGORY-R",
        database_path=Path("unused"),
    )


def _resolved(team: str, ticker: str, event: str) -> ResolvedSelection:
    return ResolvedSelection(team, ticker, event, f"{team} winner", f"Match {event}")


def _processor(
    tmp_path: Path,
    settings: Settings | None = None,
    resolved: list[ResolvedSelection] | None = None,
) -> OrderProcessor:
    settings = settings or _settings()
    store = OrderStore(tmp_path / "test.db")
    kalshi = MagicMock()
    resolver = MagicMock(spec=MarketResolver)
    if resolved is not None:
        resolver.resolve.return_value = resolved
    return OrderProcessor(settings, store, kalshi, resolver)


def test_non_signal_is_ignored(tmp_path: Path) -> None:
    proc = _processor(tmp_path)
    result = proc.process(123, 1, "Hola a todos")
    assert result.status == "ignored"


def test_dry_run_records_preview(tmp_path: Path) -> None:
    resolved = [_resolved("BIG", "KXCS2GAME-BIG", "EVT1")]
    proc = _processor(tmp_path, resolved=resolved)
    result = proc.process(123, 1, "BIG @1.77 (stake 10)")
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["max_price"] == "0.5600"
    assert result.payload["count"] == "17"


def test_duplicate_message_detected(tmp_path: Path) -> None:
    resolved = [_resolved("BIG", "KXCS2GAME-BIG", "EVT1")]
    proc = _processor(tmp_path, resolved=resolved)
    proc.process(123, 1, "BIG @1.77 (stake 10)")
    result = proc.process(123, 1, "BIG @1.77 (stake 10)")
    assert result.status == "duplicate"


def test_risk_rejects_exceeds_max_contracts(tmp_path: Path) -> None:
    settings = _settings(max_contracts=5)
    resolved = [_resolved("BIG", "KXCS2GAME-BIG", "EVT1")]
    proc = _processor(tmp_path, settings=settings, resolved=resolved)
    result = proc.process(123, 1, "BIG @1.77 (stake 10)")
    assert result.status == "rejected"
    assert "MAX_CONTRACTS" in (result.error or "")


def test_risk_rejects_exceeds_max_notional(tmp_path: Path) -> None:
    settings = _settings(max_notional="5.00")
    resolved = [_resolved("BIG", "KXCS2GAME-BIG", "EVT1")]
    proc = _processor(tmp_path, settings=settings, resolved=resolved)
    result = proc.process(123, 1, "BIG @1.77 (stake 10)")
    assert result.status == "rejected"
    assert "MAX_NOTIONAL" in (result.error or "")


def test_combo_same_event_rejected(tmp_path: Path) -> None:
    resolved = [
        _resolved("BIG", "KXCS2GAME-BIG", "EVT1"),
        _resolved("GamerLegion", "KXCS2GAME-GL", "EVT1"),
    ]
    proc = _processor(tmp_path, resolved=resolved)
    result = proc.process(123, 1, "BIG + GamerLegion @1.77 (stake 10)")
    assert result.status == "rejected"
    assert "mismo evento" in (result.error or "")


def test_combo_different_events_accepted(tmp_path: Path) -> None:
    resolved = [
        _resolved("BIG", "KXCS2GAME-BIG", "EVT1"),
        _resolved("GamerLegion", "KXCS2GAME-GL", "EVT2"),
    ]
    proc = _processor(tmp_path, resolved=resolved)
    result = proc.process(123, 1, "BIG + GamerLegion @1.77 (stake 10)")
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["type"] == "combo"


def test_allowed_tickers_rejects_unlisted(tmp_path: Path) -> None:
    settings = Settings(
        telegram_api_id=None,
        telegram_api_hash="",
        telegram_channel=-1002160464787,
        telegram_session="data/telegram",
        kalshi_env="demo",
        kalshi_api_key_id="",
        kalshi_private_key_path="",
        dry_run=True,
        allow_live_trading=False,
        stake_unit_usd=Decimal("1"),
        max_contracts_per_order=100,
        max_notional_per_order_usd=Decimal("100"),
        allowed_tickers=frozenset({"KXCS2GAME-ALLOWED"}),
        combo_collection="KXMVECROSSCATEGORY-R",
        database_path=Path("unused"),
    )
    resolved = [_resolved("BIG", "KXCS2GAME-BIG", "EVT1")]
    proc = _processor(tmp_path, settings=settings, resolved=resolved)
    result = proc.process(123, 1, "BIG @1.77 (stake 10)")
    assert result.status == "rejected"
    assert "ALLOWED_TICKERS" in (result.error or "")
