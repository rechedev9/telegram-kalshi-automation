from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ConfigurationError(ValueError):
    pass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} debe ser true o false")


@dataclass(frozen=True)
class Settings:
    telegram_api_id: int | None
    telegram_api_hash: str
    telegram_channel: int | str
    telegram_session: str
    kalshi_env: str
    kalshi_api_key_id: str
    kalshi_private_key_path: str
    dry_run: bool
    allow_live_trading: bool
    stake_unit_usd: Decimal
    max_contracts_per_order: int
    max_notional_per_order_usd: Decimal
    allowed_tickers: frozenset[str]
    combo_collection: str
    database_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
        try:
            api_id = int(api_id_raw) if api_id_raw else None
        except ValueError as exc:
            raise ConfigurationError("TELEGRAM_API_ID debe ser un entero") from exc

        channel_raw = os.getenv("TELEGRAM_CHANNEL", "").strip()
        try:
            channel: int | str = int(channel_raw)
        except ValueError:
            channel = channel_raw

        try:
            stake_unit = Decimal(os.getenv("STAKE_UNIT_USD", "1.00"))
            max_contracts = int(os.getenv("MAX_CONTRACTS_PER_ORDER", "100"))
            max_notional = Decimal(os.getenv("MAX_NOTIONAL_PER_ORDER_USD", "100.00"))
        except (ValueError, InvalidOperation) as exc:
            raise ConfigurationError("Los límites de riesgo no son válidos") from exc

        if stake_unit <= 0 or max_contracts < 1 or max_notional <= 0:
            raise ConfigurationError("Los límites de riesgo deben ser positivos")

        settings = cls(
            telegram_api_id=api_id,
            telegram_api_hash=os.getenv("TELEGRAM_API_HASH", "").strip(),
            telegram_channel=channel,
            telegram_session=os.getenv("TELEGRAM_SESSION", "data/telegram").strip(),
            kalshi_env=os.getenv("KALSHI_ENV", "demo").strip().lower(),
            kalshi_api_key_id=os.getenv("KALSHI_API_KEY_ID", "").strip(),
            kalshi_private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH", "").strip(),
            dry_run=_bool("DRY_RUN", True),
            allow_live_trading=os.getenv("ALLOW_LIVE_TRADING", "NO").strip() == "YES",
            stake_unit_usd=stake_unit,
            max_contracts_per_order=max_contracts,
            max_notional_per_order_usd=max_notional,
            allowed_tickers=frozenset(
                ticker.strip().upper()
                for ticker in os.getenv("ALLOWED_TICKERS", "").split(",")
                if ticker.strip()
            ),
            combo_collection=os.getenv(
                "KALSHI_COMBO_COLLECTION", "KXMVECROSSCATEGORY-R"
            ).strip(),
            database_path=Path(os.getenv("DATABASE_PATH", "data/orders.db")),
        )
        settings._validate()
        return settings

    def _validate(self) -> None:
        if self.kalshi_env not in {"demo", "production"}:
            raise ConfigurationError("KALSHI_ENV debe ser demo o production")
        if not self.combo_collection:
            raise ConfigurationError("KALSHI_COMBO_COLLECTION no puede estar vacío")
        if self.kalshi_env == "production" and not self.dry_run and not self.allow_live_trading:
            raise ConfigurationError(
                "Producción requiere ALLOW_LIVE_TRADING=YES y DRY_RUN=false"
            )

    @property
    def kalshi_base_url(self) -> str:
        if self.kalshi_env == "production":
            return "https://external-api.kalshi.com/trade-api/v2"
        return "https://external-api.demo.kalshi.co/trade-api/v2"

    def validate_telegram(self) -> None:
        if not self.telegram_channel:
            raise ConfigurationError("TELEGRAM_CHANNEL es obligatorio")
        if self.telegram_api_id is None or not self.telegram_api_hash:
            raise ConfigurationError(
                "Configura TELEGRAM_API_ID y TELEGRAM_API_HASH en .env"
            )

    def validate_kalshi(self) -> None:
        if not self.kalshi_api_key_id or not self.kalshi_private_key_path:
            raise ConfigurationError(
                "Configura KALSHI_API_KEY_ID y KALSHI_PRIVATE_KEY_PATH en .env"
            )
