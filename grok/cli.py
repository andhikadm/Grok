import asyncio
import signal
import sys

from rich.prompt import Prompt, IntPrompt

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

    return IntPrompt.ask("[cyan]How many accounts ?[/cyan]")


def resolve_threads(argv: list[str]) -> int:
    """Obtain desired thread count from argument or prompt."""
    if len(argv) >= 2:
        try:
            n = int(argv[1])
            if n > 0:
                return n
        except ValueError:
            pass

    return IntPrompt.ask("[cyan]How much thread ?[/cyan]")


def resolve_mail_mode(argv: list[str]) -> str:
    """Obtain mail mode from argument or prompt (api or imap)."""
    if len(argv) >= 3:
        mode = argv[2].lower().strip()
        if mode in ("api", "imap"):
            return mode

    print("\n[bold]Select mail mode:[/bold]")
    print(" 1. Temp-Mail API")
    print(" 2. IMAP (Personal catch-all)")
    choice = Prompt.ask("Choose mode", choices=["1", "2"])
    return "api" if choice == "1" else "imap"


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


def _make_loop() -> asyncio.AbstractEventLoop:
    """Create event loop with custom exception handler to suppress Playwright TargetClosedError."""
    loop = asyncio.new_event_loop()

    def _handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if exc is None:
            return
        # Suppress Playwright TargetClosedError — internal futures we can't await
        exc_name = type(exc).__name__
        if exc_name == "TargetClosedError" or "Target" in str(exc) and "closed" in str(exc):
            return
        # Suppress CancelledError during shutdown
        if isinstance(exc, asyncio.CancelledError):
            return
        # Let everything else through
        loop.default_exception_handler(context)

    loop.set_exception_handler(_handle_exception)
    return loop


def entry() -> None:
    emit_banner()
    target = resolve_target(sys.argv[1:])
    threads = resolve_threads(sys.argv[1:])
    mode = resolve_mail_mode(sys.argv[1:])
    CONFIG.max_concurrency = threads
    CONFIG.mail_mode = mode
    CONFIG.validate()

    loop = _make_loop()
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(orchestrate(target))
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[!] Cancelled. Browser instances cleaned up.")
    finally:
        # Cancel and wait for all remaining tasks to complete to avoid Playwright pending task errors
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                # Run loop until all cancelled tasks are done (suppress cancelled exceptions)
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        # Clean up remaining async generators / tasks
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
