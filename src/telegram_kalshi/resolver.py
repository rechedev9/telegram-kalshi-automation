from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from .kalshi import KalshiClient
from .models import Selection, Signal


class MarketResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedSelection:
    team: str
    ticker: str
    event_ticker: str
    title: str
    event_title: str

    def as_combo_leg(self) -> dict[str, str]:
        return {
            "market_ticker": self.ticker,
            "event_ticker": self.event_ticker,
            "side": "yes",
        }


_TEAM_ALIASES = {
    "spirit": {"team spirit"},
    "team spirit": {"spirit"},
}


class MarketResolver:
    def __init__(self, kalshi: KalshiClient, cache_seconds: int = 30):
        self.kalshi = kalshi
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def resolve(self, signal: Signal) -> list[ResolvedSelection]:
        return [self._resolve_selection(selection) for selection in signal.selections]

    def _resolve_selection(self, selection: Selection) -> ResolvedSelection:
        series = "KXCS2MAP" if selection.map_number else "KXCS2GAME"
        accepted_names = {_normalize(selection.team)}
        accepted_names.update(_TEAM_ALIASES.get(next(iter(accepted_names)), set()))
        candidates: list[ResolvedSelection] = []

        for event in self._events(series):
            event_title = event.get("title", "")
            if selection.map_number and not re.search(
                rf":\s*Map\s+{selection.map_number}\s+Winner\s*$",
                event_title,
                re.IGNORECASE,
            ):
                continue
            for market in event.get("markets", []):
                if market.get("status") != "active":
                    continue
                team_name = market.get("yes_sub_title") or ""
                if _normalize(team_name) not in accepted_names:
                    continue
                candidates.append(
                    ResolvedSelection(
                        team=team_name,
                        ticker=market["ticker"],
                        event_ticker=market.get("event_ticker", event["event_ticker"]),
                        title=market.get("title", ""),
                        event_title=event_title,
                    )
                )

        unique = {candidate.ticker: candidate for candidate in candidates}
        candidates = list(unique.values())
        if not candidates:
            market_type = f"mapa {selection.map_number}" if selection.map_number else "partido"
            raise MarketResolutionError(
                f"No hay mercado CS2 abierto para {selection.team} ({market_type})"
            )
        if len(candidates) > 1:
            events = ", ".join(candidate.event_title for candidate in candidates[:3])
            raise MarketResolutionError(
                f"Selección ambigua para {selection.team}: {events}"
            )
        return candidates[0]

    def _events(self, series: str) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._cache.get(series)
        if cached and now - cached[0] < self.cache_seconds:
            return cached[1]
        events = self.kalshi.list_events(series)
        self._cache[series] = (now, events)
        return events


def _normalize(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()
