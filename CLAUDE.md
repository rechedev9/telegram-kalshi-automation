# Telegram-Kalshi Automation

## Safety

- Operate in `DRY_RUN=true` by default. Do not change `DRY_RUN`, `ALLOW_LIVE_TRADING` or `KALSHI_ENV` without an explicit user instruction.
- Do not send real or demo orders. Do not create combo markets.
- Do not print, log or return credentials, API keys, private keys or session tokens.
- Do not add fuzzy matching or aliases to the resolver without fixtures and review.

## Commands

Parse a signal offline (no network, no order):

```bash
.venv/Scripts/python -m telegram_kalshi parse --message "BIG + GamerLegion @1.77 (stake 10)"
```

Resolve against live markets without trading:

```bash
set KALSHI_ENV=production& set DRY_RUN=true& .venv/Scripts/python -m telegram_kalshi process --message "TEAM @2.00 (stake 10)" --chat-id -1002160464787 --message-id 1001
```

Run tests:

```bash
.venv/Scripts/python -m pytest tests -v
```

## Code

- Python 3.11, source in `src/telegram_kalshi/`.
- Virtual environment in `.venv/` (already created, editable install).
- Dependencies: cryptography, python-dotenv, requests, telethon.
- Dev dependencies: pytest (add with `pip install pytest` if missing).
- Do not add type: ignore, noqa or lint disable comments.
- Keep kebab-case file names.

## Architecture

- `parser.py`: regex on the first line; `+` means combo, `mapa N` picks a map market.
- `models.py`: Selection, Signal with price/budget/contracts math, Kalshi payload.
- `resolver.py`: matches teams to open CS2 markets via public Kalshi API.
- `processor.py`: risk checks, deduplication, preview, DRY_RUN gate, order dispatch.
- `kalshi.py`: REST client with Ed25519/RSA signing.
- `store.py`: SQLite with `(chat_id, message_id)` PK and `client_order_id` unique.
- `listener.py`: Telethon NewMessage handler with sequential lock.
- `cli.py`: entry point with listen, parse, process, check-market, check-auth.
