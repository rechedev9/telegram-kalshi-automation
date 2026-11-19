from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .kalshi import KalshiAPIError, KalshiClient
from .models import Signal, telegram_client_order_id
from .parser import SignalParseError, looks_like_signal, parse_signal
from .resolver import MarketResolutionError, MarketResolver, ResolvedSelection
from .store import OrderStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    status: str
    client_order_id: str | None = None
    payload: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    error: str | None = None


class OrderProcessor:
    def __init__(
        self,
        settings: Settings,
        store: OrderStore,
        kalshi: KalshiClient,
        resolver: MarketResolver | None = None,
    ):
        self.settings = settings
        self.store = store
        self.kalshi = kalshi
        self.resolver = resolver or MarketResolver(kalshi)

    def process(self, chat_id: int, message_id: int, text: str) -> ProcessResult:
        if not looks_like_signal(text):
            return ProcessResult("ignored")

        try:
            signal = parse_signal(text, self.settings.stake_unit_usd)
            self._validate_risk(signal)
            resolved = self.resolver.resolve(signal)
            self._validate_tickers(resolved)
        except (SignalParseError, MarketResolutionError, KalshiAPIError, ValueError) as exc:
            logger.warning("Señal rechazada (%s:%s): %s", chat_id, message_id, exc)
            return ProcessResult("rejected", error=str(exc))

        client_order_id = telegram_client_order_id(chat_id, message_id)
        preview = self._preview(signal, resolved, client_order_id)
        if not self.store.start(chat_id, message_id, text, client_order_id, preview):
            logger.info("Mensaje duplicado ignorado: %s:%s", chat_id, message_id)
            return ProcessResult("duplicate", client_order_id, preview)

        if self.settings.dry_run:
            self.store.mark_dry_run(client_order_id)
            logger.info("DRY RUN %s: %s", client_order_id, preview)
            return ProcessResult("dry_run", client_order_id, preview)

        try:
            combo_response = None
            if signal.is_combo:
                combo_response = self.kalshi.create_combo(
                    [selection.as_combo_leg() for selection in resolved]
                )
                ticker = combo_response.get("market_ticker")
                if not ticker:
                    raise KalshiAPIError("Kalshi no devolvió el ticker de la combinada")
            else:
                ticker = resolved[0].ticker

            order = signal.to_kalshi_payload(ticker, client_order_id)
            order_response = self.kalshi.create_order(order)
        except Exception as exc:
            self.store.mark_failed(client_order_id, str(exc))
            logger.exception("Fallo al enviar %s", client_order_id)
            return ProcessResult("failed", client_order_id, preview, error=str(exc))

        response = {"order": order_response}
        if combo_response is not None:
            response["combo"] = combo_response
        self.store.mark_submitted(client_order_id, response)
        logger.info("Orden enviada %s: %s", client_order_id, response)
        return ProcessResult("submitted", client_order_id, preview, response=response)

    def _preview(
        self,
        signal: Signal,
        resolved: list[ResolvedSelection],
        client_order_id: str,
    ) -> dict[str, Any]:
        preview: dict[str, Any] = {
            "type": "combo" if signal.is_combo else "single",
            "odds": str(signal.odds),
            "stake": str(signal.stake),
            "budget_usd": str(signal.budget_usd),
            "max_price": f"{signal.price:.4f}",
            "count": str(signal.contracts),
            "markets": [
                {
                    "team": selection.team,
                    "ticker": selection.ticker,
                    "event_ticker": selection.event_ticker,
                    "title": selection.title,
                    "event_title": selection.event_title,
                }
                for selection in resolved
            ],
        }
        if signal.is_combo:
            preview["collection_ticker"] = self.settings.combo_collection
            preview["selected_markets"] = [
                selection.as_combo_leg() for selection in resolved
            ]
        else:
            preview["order"] = signal.to_kalshi_payload(
                resolved[0].ticker, client_order_id
            )
        return preview

    def _validate_risk(self, signal: Signal) -> None:
        if signal.contracts < 1:
            raise ValueError("STAKE_UNIT_USD y el stake no alcanzan un contrato")
        if signal.contracts > self.settings.max_contracts_per_order:
            raise ValueError(
                f"Supera MAX_CONTRACTS_PER_ORDER={self.settings.max_contracts_per_order}"
            )
        if signal.notional_usd > self.settings.max_notional_per_order_usd:
            raise ValueError(
                "Supera MAX_NOTIONAL_PER_ORDER_USD="
                f"{self.settings.max_notional_per_order_usd}"
            )

    def _validate_tickers(self, resolved: list[ResolvedSelection]) -> None:
        if len({selection.event_ticker for selection in resolved}) != len(resolved):
            raise ValueError("No se pueden combinar selecciones del mismo evento")
        if not self.settings.allowed_tickers:
            return
        for selection in resolved:
            if selection.ticker not in self.settings.allowed_tickers:
                raise ValueError(
                    f"El ticker {selection.ticker} no está incluido en ALLOWED_TICKERS"
                )
