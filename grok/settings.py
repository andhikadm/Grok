import os
import re
import sys
import warnings
from dataclasses import dataclass, field


# Silence benign asyncio pipe warnings from browser subprocesses
warnings.filterwarnings("ignore", message=".*unclosed transport.*")
warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")

_original_hook = sys.unraisablehook


def _suppress_pipe_noise(hook_args):
    err = hook_args.exc_value
    if isinstance(err, ValueError) and "closed pipe" in str(err):
        return
    _original_hook(hook_args)


sys.unraisablehook = _suppress_pipe_noise


@dataclass
class Settings:
    # Provider
    mail_origin: str = field(default_factory=lambda: os.getenv("MAIL_ORIGIN", "https://mail.cskh-group.com"))
    mailbox_domain: str = field(default_factory=lambda: os.getenv("MAILBOX_DOMAIN", "vin-groupvn.com"))
    export_path: str = field(default_factory=lambda: os.getenv("EXPORT_PATH", "accounts.txt"))

    # Remote targets
    target_login: str = "https://console.x.ai"
    dispatch_code: str = "https://console.x.ai/api/auth/send-verification-code"
    confirm_email: str = "https://console.x.ai/api/auth/sign-up/verify-email"
    finish_signup: str = "https://console.x.ai/api/auth/sign-up/create-account"
    captcha_reference: str = "https://console.x.ai/login?mode=sign-up"

    # Solvers
    captcha_site_key: str = field(default_factory=lambda: os.getenv("CAPTCHA_KEY", "0x4AAAAAAAhr9JGVDZbrZOo0"))
    token_matcher: re.Pattern = field(
        default_factory=lambda: re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")
    )

    # Timings
    poll_delay: float = float(os.getenv("POLL_GAP", "3"))
    poll_deadline: float = float(os.getenv("POLL_MAX", "60"))
    captcha_window: float = float(os.getenv("CAPTCHA_WINDOW", "25"))
    network_gate: float = float(os.getenv("NETWORK_TIMEOUT", "10"))

    # Browser
    show_gui: bool = field(default_factory=lambda: os.getenv("SHOW_BROWSER", "False").lower() not in ("0", "false", "no", "off"))

    # Concurrency
    max_concurrency: int = int(os.getenv("CONCURRENCY", "3"))

    def __post_init__(self):
        self.token_matcher = re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")


CONFIG = Settings()
