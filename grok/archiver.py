import asyncio

from .settings import CONFIG

_write_lock = asyncio.Lock()


async def persist_account(
    address: str, secret: str,
    access_token: str = "", refresh_token: str = "", expires_at: str = ""
) -> None:
    """Write credential details to the export file (thread-safe)."""
    async with _write_lock:
        with open(CONFIG.export_path, "a", encoding="utf-8") as fh:
            if access_token and refresh_token:
                fh.write(f"{address}|{secret}|{access_token}|{refresh_token}|{expires_at}\n")
            else:
                fh.write(f"{address}|{secret}\n")
