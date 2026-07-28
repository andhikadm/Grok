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


def _require_env(key: str, description: str) -> str:
    """Return env var value or exit with a clear message if missing."""
    val = os.getenv(key)
    if not val:
        print(f"[!] Missing required environment variable: {key} ({description})")
        print(f"    Set it in your .env or shell:  export {key}=<value>")
        sys.exit(1)
    return val


@dataclass
class Settings:
    # Provider — REQUIRED via env vars (no hardcoded defaults)
    mail_origin: str = field(
        default_factory=lambda: _require_env("MAIL_ORIGIN", "Base URL for temp-mail API"))
    mailbox_domain: str = field(
        default_factory=lambda: _require_env("MAILBOX_DOMAIN", "Domain for generated mailboxes"))
    export_path: str = field(
        default_factory=lambda: os.getenv("EXPORT_PATH", "accounts.txt"))

    # Remote targets
    target_login: str = "https://console.x.ai"
    dispatch_code: str = "https://console.x.ai/api/auth/send-verification-code"
    confirm_email: str = "https://console.x.ai/api/auth/sign-up/verify-email"
    finish_signup: str = "https://console.x.ai/api/auth/sign-up/create-account"
    captcha_reference: str = "https://console.x.ai/login?mode=sign-up"

    # Solvers — REQUIRED via env var
    captcha_site_key: str = field(
        default_factory=lambda: _require_env("CAPTCHA_KEY", "Turnstile site key"))
    token_matcher: re.Pattern = field(
        default_factory=lambda: re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")
    )

    # Timings
    poll_delay: float = field(
        default_factory=lambda: float(os.getenv("POLL_GAP", "3")))
    poll_deadline: float = field(
        default_factory=lambda: float(os.getenv("POLL_MAX", "60")))
    captcha_window: float = field(
        default_factory=lambda: float(os.getenv("CAPTCHA_WINDOW", "25")))
    network_gate: float = field(
        default_factory=lambda: float(os.getenv("NETWORK_TIMEOUT", "10")))

    # Browser
    show_gui: bool = field(
        default_factory=lambda: os.getenv("SHOW_BROWSER", "False").lower() not in ("0", "false", "no", "off"))

    # Concurrency
    max_concurrency: int = field(
        default_factory=lambda: int(os.getenv("CONCURRENCY", "3")))

    def __post_init__(self):
        self.token_matcher = re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")


CONFIG = Settings()
