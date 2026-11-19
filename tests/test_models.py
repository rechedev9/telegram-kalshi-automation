from __future__ import annotations

from decimal import Decimal

from telegram_kalshi.models import Selection, Signal, telegram_client_order_id


def _signal(
    odds: str = "1.77",
    stake: str = "10",
    stake_unit: str = "1",
    teams: list[str] | None = None,
) -> Signal:
    selections = tuple(Selection(t) for t in (teams or ["BIG"]))
    return Signal(selections, Decimal(odds), Decimal(stake), Decimal(stake_unit))


def test_price_floor_177() -> None:
    assert _signal("1.77").price == Decimal("0.56")


def test_price_floor_168() -> None:
    assert _signal("1.68").price == Decimal("0.59")


def test_price_floor_200() -> None:
    assert _signal("2.00").price == Decimal("0.50")


def test_price_floor_144() -> None:
    assert _signal("1.44").price == Decimal("0.69")


def test_price_floor_231() -> None:
    assert _signal("2.31").price == Decimal("0.43")


def test_price_floor_162() -> None:
    assert _signal("1.62").price == Decimal("0.61")


def test_budget_usd() -> None:
    s = _signal("1.77", "10", "1")
    assert s.budget_usd == Decimal("10")


def test_budget_usd_custom_unit() -> None:
    s = _signal("1.77", "10", "0.50")
    assert s.budget_usd == Decimal("5.00")


def test_contracts_calculation() -> None:
    s = _signal("1.77", "10", "1")
    assert s.contracts == 17


def test_contracts_200() -> None:
    s = _signal("2.00", "10", "1")
    assert s.contracts == 20


def test_notional_usd() -> None:
    s = _signal("1.77", "10", "1")
    assert s.notional_usd == Decimal("9.52")


def test_is_combo_single() -> None:
    assert not _signal(teams=["BIG"]).is_combo


def test_is_combo_multiple() -> None:
    assert _signal(teams=["BIG", "GamerLegion"]).is_combo


def test_to_kalshi_payload() -> None:
    s = _signal("1.77", "10", "1")
    payload = s.to_kalshi_payload("KXCS2GAME-XYZ", "tg-abc")
    assert payload["ticker"] == "KXCS2GAME-XYZ"
    assert payload["side"] == "bid"
    assert payload["count"] == "17"
    assert payload["price"] == "0.5600"
    assert payload["time_in_force"] == "immediate_or_cancel"
    assert payload["client_order_id"] == "tg-abc"


def test_client_order_id_deterministic() -> None:
    a = telegram_client_order_id(-1002160464787, 100)
    b = telegram_client_order_id(-1002160464787, 100)
    assert a == b
    assert a.startswith("tg-")


def test_client_order_id_unique_per_message() -> None:
    a = telegram_client_order_id(-1002160464787, 100)
    b = telegram_client_order_id(-1002160464787, 101)
    assert a != b
