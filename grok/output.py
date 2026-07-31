import threading
from dataclasses import dataclass, field
from typing import Optional

from colorama import Fore, Style, init
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.panel import Panel
from rich.text import Text

init(autoreset=True)

# ── Thread colors for tag labels ──
_THREAD_STYLES = [
    "cyan", "magenta", "blue",
    "yellow", "green", "bright_cyan",
    "bright_magenta", "bright_blue",
]


def _style_for(index: int) -> str:
    return _THREAD_STYLES[(index - 1) % len(_THREAD_STYLES)]


# ── Status icons ──
_ICONS = {
    "progress": "[yellow]*[/yellow]",
    "confirm":  "[green]V[/green]",
    "fail":     "[red]X[/red]",
    "plain":    "[white]-[/white]",
    "alert":    "[yellow]![/yellow]",
}


class Dashboard:
    """Rich-powered live dashboard: progress bar + 1 status line per thread."""

    def __init__(self, total: int, threads: int) -> None:
        self._total = total
        self._threads = threads
        self._lock = threading.Lock()

        # Per-thread latest status  {thread_index: (style_key, message)}
        self._status: dict[int, tuple[str, str]] = {}

        self._completed = 0
        self._success = 0

        self._console = Console()
        self._progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold cyan]GroK"),
            BarColumn(bar_width=40, complete_style="cyan", finished_style="green"),
            TextColumn("[bold]{task.completed}/{task.total}[/bold]"),
            TextColumn("[dim]{task.percentage:>5.1f}%[/dim]"),
            TextColumn("[dim]{task.fields[info]}[/dim]"),
            console=self._console,
        )
        self._task_id = self._progress.add_task(
            "register", total=total, info=f"{threads}T"
        )
        self._live: Optional[Live] = None

    # ── lifecycle ──

    def start(self) -> "Dashboard":
        self._live = Live(
            self._build_layout(),
            console=self._console,
            refresh_per_second=8,
            transient=False,
        )
        self._live.start()
        return self

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def __enter__(self) -> "Dashboard":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ── thread-safe updates ──

    def advance(self, success: bool) -> None:
        with self._lock:
            self._completed += 1
            if success:
                self._success += 1
            self._progress.update(
                self._task_id,
                completed=self._completed,
                info=f"{self._threads}T  {self._success}V  {self._completed - self._success}X",
            )
            self._refresh()

    def set_status(self, thread_index: int, kind: str, message: str) -> None:
        with self._lock:
            self._status[thread_index] = (kind, message)
            self._refresh()

    def clear_thread(self, thread_index: int) -> None:
        with self._lock:
            self._status.pop(thread_index, None)
            self._refresh()

    # ── layout builder ──

    def _build_layout(self):
        table = Table.grid(padding=(0, 1))
        table.add_row(self._progress)

        # Status lines sorted by thread index
        for idx in sorted(self._status.keys()):
            kind, msg = self._status[idx]
            icon = _ICONS.get(kind, _ICONS["plain"])
            style = _style_for(idx)
            tag = f"[{style}][{idx}/{self._total}][/{style}]"
            table.add_row(Text.from_markup(f" {icon} {tag} {msg}"))

        return Panel(table, border_style="cyan", padding=(0, 1))

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._build_layout())


@dataclass
class Logger:
    """Per-thread logger that writes to a shared Dashboard."""
    marker: str = ""
    thread_index: int = 0
    _dashboard: Optional[Dashboard] = field(default=None, repr=False)

    def bind(self, dashboard: Dashboard) -> "Logger":
        self._dashboard = dashboard
        return self

    def _emit(self, kind: str, msg: str) -> None:
        if self._dashboard:
            self._dashboard.set_status(self.thread_index, kind, msg)
        else:
            # Fallback when no dashboard (e.g. single-thread mode)
            print(f"{self.marker} {msg}")

    def plain(self, msg: str) -> None:
        self._emit("plain", msg)

    def progress(self, msg: str) -> None:
        self._emit("progress", msg)

    def confirm(self, msg: str) -> None:
        self._emit("confirm", msg)

    def alert(self, msg: str) -> None:
        self._emit("alert", msg)

    def fail(self, msg: str) -> None:
        self._emit("fail", msg)

    def raw(self, msg: str) -> None:
        self._emit("progress", msg)


def emit_banner() -> None:
    artwork = fr"""
{Fore.CYAN}  ____               _  __
 / ___|_ __ ___   __| |/ /
| |  _| '__/ _ \ / _` ' /
| |_| | | | (_) | (_| . \
 \____|_|  \___/ \__,_|\_\
                           {Style.RESET_ALL}
"""
    try:
        print(artwork)
    except Exception:
        # Fallback if terminal can't print ANSI/Unicode
        print("=== GroK Account Creator ===")
