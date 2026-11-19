from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .models import Selection, Signal


class SignalParseError(ValueError):
    pass


_SIGNAL_PATTERN = re.compile(
    r"^(?P<selections>.+?)\s*@(?P<odds>\d+(?:[.,]\d+)?)"
    r"\s*\(\s*stake\s+(?P<stake>\d+(?:[.,]\d+)?)\s*\)",
    re.IGNORECASE,
)
_MAP_PATTERN = re.compile(r"^(?P<team>.+?)(?:\s+mapa\s+(?P<map>[1-3]))?$", re.IGNORECASE)


def looks_like_signal(text: str) -> bool:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return _SIGNAL_PATTERN.match(first_line) is not None


def parse_signal(text: str, stake_unit_usd: Decimal = Decimal("1")) -> Signal:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    match = _SIGNAL_PATTERN.match(first_line)
    if match is None:
        raise SignalParseError("No tiene el formato 'Equipo @1.77 (stake 10)'")

    try:
        odds = _decimal(match.group("odds"))
        stake = _decimal(match.group("stake"))
    except InvalidOperation as exc:
        raise SignalParseError("La cuota o el stake no son números válidos") from exc
    if not odds.is_finite() or not stake.is_finite() or odds <= 1 or stake <= 0:
        raise SignalParseError("La cuota debe ser mayor que 1 y el stake mayor que 0")
    if stake_unit_usd <= 0:
        raise SignalParseError("STAKE_UNIT_USD debe ser positivo")

    raw_selections = re.split(r"\s+\+\s+", match.group("selections").strip())
    if not raw_selections or len(raw_selections) > 10:
        raise SignalParseError("La señal debe contener entre 1 y 10 selecciones")

    selections: list[Selection] = []
    for raw_selection in raw_selections:
        selection_match = _MAP_PATTERN.fullmatch(raw_selection.strip())
        if selection_match is None:
            raise SignalParseError(f"Selección no válida: {raw_selection}")
        team = selection_match.group("team").strip()
        if not team:
            raise SignalParseError("Hay una selección sin equipo")
        map_number = selection_match.group("map")
        selections.append(Selection(team, int(map_number) if map_number else None))

    signal = Signal(tuple(selections), odds, stake, stake_unit_usd)
    if signal.price < Decimal("0.01"):
        raise SignalParseError("La cuota produce un precio inferior a un céntimo")
    return signal


def _decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(",", "."))
