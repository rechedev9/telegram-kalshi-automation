from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR


@dataclass(frozen=True)
class Selection:
    team: str
    map_number: int | None = None


@dataclass(frozen=True)
class Signal:
    selections: tuple[Selection, ...]
    odds: Decimal
    stake: Decimal
    stake_unit_usd: Decimal

    @property
    def price(self) -> Decimal:
        implied_price = Decimal("1") / self.odds
        return implied_price.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)

    @property
    def budget_usd(self) -> Decimal:
        return self.stake * self.stake_unit_usd

    @property
    def contracts(self) -> int:
        return int((self.budget_usd / self.price).to_integral_value(rounding=ROUND_FLOOR))

    @property
    def notional_usd(self) -> Decimal:
        return self.price * self.contracts

    @property
    def is_combo(self) -> bool:
        return len(self.selections) > 1

    def to_kalshi_payload(self, ticker: str, client_order_id: str) -> dict[str, str]:
        return {
            "ticker": ticker,
            "side": "bid",
            "count": str(self.contracts),
            "price": f"{self.price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "client_order_id": client_order_id,
        }


def telegram_client_order_id(chat_id: int, message_id: int) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"telegram:{chat_id}:{message_id}")
    return f"tg-{value}"
