import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

_io_lock = threading.Lock()

# Rotating palette for thread identification
_THREAD_COLORS = [
    Fore.CYAN, Fore.MAGENTA, Fore.BLUE,
    Fore.LIGHTYELLOW_EX, Fore.LIGHTGREEN_EX,
    Fore.LIGHTCYAN_EX, Fore.LIGHTMAGENTA_EX, Fore.LIGHTBLUE_EX,
]


def _pick_color(index: int) -> str:
    """Return a color based on thread index (1-based)."""
    return _THREAD_COLORS[(index - 1) % len(_THREAD_COLORS)]


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


@dataclass
class Logger:
    marker: str = ""
    thread_index: int = 0
    _color: str = field(init=False, default="")

    def __post_init__(self):
        if self.thread_index > 0:
            self._color = _pick_color(self.thread_index)
        else:
            self._color = ""

    def _prefix(self) -> str:
        ts = f"{Fore.WHITE}{_timestamp()}{Style.RESET_ALL}"
        tag = f"{self._color}{self.marker}{Style.RESET_ALL}" if self.marker else ""
        return f"{ts} {tag}" if tag else ts

    def _safe_print(self, msg: str) -> None:
        with _io_lock:
            print(msg)

    def plain(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {msg}")

    def progress(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {Fore.YELLOW}{msg}{Style.RESET_ALL}")

    def confirm(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {Fore.GREEN}{msg}{Style.RESET_ALL}")

    def alert(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {Fore.YELLOW}{msg}{Style.RESET_ALL}")

    def fail(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {Fore.RED}{msg}{Style.RESET_ALL}")

    def raw(self, msg: str) -> None:
        self._safe_print(f"{self._prefix()} {msg}")


def emit_banner() -> None:
    artwork = f"""
{Fore.CYAN} ██████╗ ██████╗  ██████╗ ██╗  ██╗
██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝
██║  ███╗██████╔╝██║   ██║█████╔╝
██║   ██║██╔══██╗██║   ██║██╔═██╗
╚██████╔╝██║  ██║╚██████╔╝██║  ██╗
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
                                  {Style.RESET_ALL}
"""
    print(artwork)
