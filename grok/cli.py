import asyncio
import signal
import sys

from .settings import CONFIG
from .output import emit_banner
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
        raw = input("How many accounts? ").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Please enter a valid positive number")


def resolve_threads(argv: list[str]) -> int:
    """Obtain desired thread count from argument or prompt."""
    if len(argv) >= 2:
        try:
            n = int(argv[1])
            if n > 0:
                return n
        except ValueError:
            pass

    while True:
        raw = input("How many threads? ").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Please enter a valid positive number")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel all running tasks on SIGINT/SIGTERM for clean shutdown."""

    def _shutdown(sig: signal.Signals) -> None:
        print(f"\n[!] Received {sig.name}, shutting down gracefully...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown, sig)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler; fall back to signal.signal
            signal.signal(sig, lambda s, f: _shutdown(signal.Signals(s)))


def entry() -> None:
    emit_banner()
    target = resolve_target(sys.argv[1:])
    threads = resolve_threads(sys.argv[1:])
    CONFIG.max_concurrency = threads

    loop = asyncio.new_event_loop()
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(orchestrate(target))
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[!] Cancelled. Browser instances cleaned up.")
    finally:
        # Clean up remaining async generators / tasks
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
