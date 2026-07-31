import asyncio

from .settings import CONFIG

_write_lock = asyncio.Lock()


async def persist_account(address: str, secret: str) -> None:
    """Write a single credential line to the export file (thread-safe)."""
    async with _write_lock:
        with open(CONFIG.export_path, "a", encoding="utf-8") as fh:
            fh.write(f"{address}|{secret}\n")
