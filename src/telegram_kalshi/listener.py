from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telethon import TelegramClient, events

from .config import Settings
from .processor import OrderProcessor

logger = logging.getLogger(__name__)


async def run_listener(settings: Settings, processor: OrderProcessor) -> None:
    settings.validate_telegram()
    Path(settings.telegram_session).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    lock = asyncio.Lock()

    await client.start()
    entity = await client.get_entity(settings.telegram_channel)

    async def on_message(event: events.NewMessage.Event) -> None:
        text = event.message.message
        if not text:
            return
        async with lock:
            await asyncio.to_thread(
                processor.process,
                event.chat_id,
                event.message.id,
                text,
            )

    client.add_event_handler(on_message, events.NewMessage(chats=entity))
    logger.info(
        "Escuchando %s | entorno=%s | DRY_RUN=%s",
        settings.telegram_channel,
        settings.kalshi_env,
        settings.dry_run,
    )
    await client.run_until_disconnected()
