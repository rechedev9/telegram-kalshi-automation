from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

from dotenv import load_dotenv

from .config import ConfigurationError, Settings
from .kalshi import KalshiAPIError, KalshiClient
from .listener import run_listener
from .parser import SignalParseError, parse_signal
from .processor import OrderProcessor
from .store import OrderStore


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="telegram-kalshi",
        description="Ejecuta señales de Apuesta Segura CS2 en Kalshi",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("listen", help="Escucha nuevos mensajes del canal")

    parse_command = subparsers.add_parser("parse", help="Interpreta una señal sin enviarla")
    parse_command.add_argument("--message", required=True)

    process_command = subparsers.add_parser(
        "process", help="Resuelve una señal y aplica DRY_RUN y la deduplicación"
    )
    process_command.add_argument("--message", required=True)
    process_command.add_argument("--chat-id", type=int, default=0)
    process_command.add_argument("--message-id", type=int, required=True)

    market_command = subparsers.add_parser(
        "check-market", help="Consulta un mercado público de Kalshi"
    )
    market_command.add_argument("ticker")

    subparsers.add_parser("check-auth", help="Consulta el balance con la API firmada")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = Settings.from_env()
        if args.command == "listen":
            processor = _processor(settings)
            asyncio.run(run_listener(settings, processor))
        elif args.command == "parse":
            signal = parse_signal(args.message, settings.stake_unit_usd)
            _print(
                {
                    "selections": [
                        {"team": selection.team, "map_number": selection.map_number}
                        for selection in signal.selections
                    ],
                    "odds": str(signal.odds),
                    "stake": str(signal.stake),
                    "budget_usd": str(signal.budget_usd),
                    "max_price": str(signal.price),
                    "contracts": signal.contracts,
                    "notional_usd": str(signal.notional_usd),
                    "is_combo": signal.is_combo,
                }
            )
        elif args.command == "process":
            result = _processor(settings).process(
                args.chat_id, args.message_id, args.message
            )
            _print(asdict(result))
            if result.status in {"failed", "rejected"}:
                raise SystemExit(1)
        elif args.command == "check-market":
            _print(KalshiClient(settings).get_market(args.ticker.upper()))
        elif args.command == "check-auth":
            _print(KalshiClient(settings).get_balance())
    except (ConfigurationError, SignalParseError, KalshiAPIError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    except KeyboardInterrupt:
        pass


def _processor(settings: Settings) -> OrderProcessor:
    return OrderProcessor(
        settings,
        OrderStore(settings.database_path),
        KalshiClient(settings),
    )


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
