from .settings import CONFIG


async def persist_account(address: str, secret: str) -> None:
    """Write a single credential line to the export file."""
    with open(CONFIG.export_path, "a", encoding="utf-8") as fh:
        fh.write(f"{address}|{secret}\n")
