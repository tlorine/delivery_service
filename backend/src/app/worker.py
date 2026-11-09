"""Outbox worker process: `python -m app.worker`."""

import asyncio
import contextlib
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.di import build_container
from app.modules.notifications.worker import OutboxProcessor, listen_for_wakeups


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = build_container(settings)
    processor = await container.get(OutboxProcessor)
    stop, wake = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    listener = asyncio.create_task(listen_for_wakeups(settings.database_url, wake))
    try:
        await processor.run_forever(stop, wake)
    finally:
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await listener
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
