from __future__ import annotations

from decimal import Decimal

import pytest

from telegram_kalshi.parser import SignalParseError, looks_like_signal, parse_signal


REAL_SIGNALS = [
    (
        "YOUNGLINGS @1.68 (stake 10)\n\nSINQU equipo finlandes muy flojo.",
        ["YOUNGLINGS"],
        [None],
        Decimal("1.68"),
        Decimal("10"),
    ),
    (
        "Inner Circle Academy mapa 2 @1.72 (stake 10)\n\nHan elegido ancient.",
        ["Inner Circle Academy"],
        [2],
        Decimal("1.72"),
        Decimal("10"),
    ),
    (
        "Hype Tech + Spirit @2.31 (stake 10)\n\n2 selecciones muy claras.",
        ["Hype Tech", "Spirit"],
        [None, None],
        Decimal("2.31"),
        Decimal("10"),
    ),
    (
        "G2 Ares mapa 2 @2.00 (stake 10)\n\nG2 Ares han elegido inferno.",
        ["G2 Ares"],
        [2],
        Decimal("2.00"),
        Decimal("10"),
    ),
    (
        "JUMBO @1.62 (stake 10)\n\nJUMBO son rusos de +3800 elo.",
        ["JUMBO"],
        [None],
        Decimal("1.62"),
        Decimal("10"),
    ),
    (
        "Privateer @1.44 (stake 10)\n\nSpirit HU son HORRIBLES.",
        ["Privateer"],
        [None],
        Decimal("1.44"),
        Decimal("10"),
    ),
    (
        "JUMBO @1.44 (stake 10)\n\nRounds finlandeses muy malos.",
        ["JUMBO"],
        [None],
        Decimal("1.44"),
        Decimal("10"),
    ),
    (
        "BIG + GamerLegion @1.77 (stake 10)\n\n2 selecciones muy claras, os explico.",
        ["BIG", "GamerLegion"],
        [None, None],
        Decimal("1.77"),
        Decimal("10"),
    ),
]


@pytest.mark.parametrize(
    "text,teams,maps,odds,stake",
    REAL_SIGNALS,
    ids=[
        "younglings-simple",
        "inner-circle-map2",
        "hype-tech-spirit-combo",
        "g2-ares-map2",
        "jumbo-1.62",
        "privateer",
        "jumbo-1.44",
        "big-gamerlegion-combo",
    ],
)
def test_parse_real_signals(
    text: str,
    teams: list[str],
    maps: list[int | None],
    odds: Decimal,
    stake: Decimal,
) -> None:
    signal = parse_signal(text)
    assert len(signal.selections) == len(teams)
    for selection, expected_team, expected_map in zip(
        signal.selections, teams, maps, strict=True
    ):
        assert selection.team == expected_team
        assert selection.map_number == expected_map
    assert signal.odds == odds
    assert signal.stake == stake


def test_recommendation_message_is_not_a_signal() -> None:
    text = (
        "Os recomiendo que hagáis la apuesta en "
        "Polymarket/Kalshi, ya que esta a @1.90."
    )
    assert not looks_like_signal(text)


def test_recommendation_raises_on_parse() -> None:
    text = (
        "Os recomiendo que hagáis la apuesta en "
        "Polymarket/Kalshi, ya que esta a @1.90."
    )
    with pytest.raises(SignalParseError):
        parse_signal(text)


def test_looks_like_signal_accepts_real_signals() -> None:
    for text, *_ in REAL_SIGNALS:
        assert looks_like_signal(text), f"Should detect: {text[:40]}"


def test_empty_and_nonsense_ignored() -> None:
    assert not looks_like_signal("")
    assert not looks_like_signal("Hola a todos")
    assert not looks_like_signal("@1.50 sin stake")
    assert not looks_like_signal("foto de resultados")


def test_odds_must_be_above_one() -> None:
    with pytest.raises(SignalParseError):
        parse_signal("Team @0.90 (stake 10)")


def test_stake_must_be_positive() -> None:
    with pytest.raises(SignalParseError):
        parse_signal("Team @1.50 (stake 0)")


def test_too_many_selections() -> None:
    teams = " + ".join(f"T{i}" for i in range(11))
    with pytest.raises(SignalParseError):
        parse_signal(f"{teams} @1.50 (stake 10)")


def test_comma_decimal_separator() -> None:
    signal = parse_signal("Team @1,68 (stake 10)")
    assert signal.odds == Decimal("1.68")
