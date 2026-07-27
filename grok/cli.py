import asyncio
import sys

from .settings import CONFIG
from .output import Logger, emit_banner
from .procedural import orchestrate


def resolve_target(argv: list[str]) -> int:
    """Obtain desired registration count from argument or prompt."""
    if len(argv) >= 1:
        try:
            n = int(argv[0])
            if n > 0:
                return n
        except ValueError:
            pass
        print("Provide a valid positive number (e.g., 5)")
        sys.exit(2)

    while True:
        raw = input("How many accounts ? ").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Please enter a valid positive number")


def entry() -> None:
    emit_banner()
    asyncio.run(orchestrate(resolve_target(sys.argv[1:])))
