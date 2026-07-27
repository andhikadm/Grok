import sys
from dataclasses import dataclass
from colorama import Fore, Style, init

init(autoreset=True)


@dataclass
class Logger:
    marker: str = ""

    def _fmt(self, msg: str) -> str:
        return f"{self.marker} {msg}" if self.marker else msg

    def plain(self, msg: str) -> None:
        print(self._fmt(msg))

    def progress(self, msg: str) -> None:
        print(self._fmt(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}"))

    def confirm(self, msg: str) -> None:
        print(self._fmt(f"{Fore.GREEN}{msg}{Style.RESET_ALL}"))

    def alert(self, msg: str) -> None:
        print(self._fmt(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}"))

    def fail(self, msg: str) -> None:
        print(self._fmt(f"{Fore.RED}{msg}{Style.RESET_ALL}"))

    def raw(self, msg: str) -> None:
        print(msg)


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
