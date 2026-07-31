import os
import re
import sys
import warnings
from dataclasses import dataclass, field


# Silence benign asyncio pipe warnings from browser subprocesses
warnings.filterwarnings("ignore", message=".*unclosed transport.*")
warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")

_original_hook = sys.unraisablehook


def _load_dotenv():
    # Load .env file manually from the project root if it exists
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k:
                        os.environ.setdefault(k, v)


_load_dotenv()


def _suppress_pipe_noise(hook_args):
    err = hook_args.exc_value
    if isinstance(err, ValueError) and "closed pipe" in str(err):
        return
    # Suppress Playwright TargetClosedError surfacing via __del__ / gc
    err_name = type(err).__name__ if err else ""
    if err_name == "TargetClosedError":
        return
    _original_hook(hook_args)


sys.unraisablehook = _suppress_pipe_noise



@dataclass
class Settings:
    # Mail mode: "api" (temp-mail API) or "imap" (personal IMAP catch-all)
    mail_mode: str = field(
        default_factory=lambda: os.getenv("MAIL_MODE", "api").lower())

    # Provider — REQUIRED when MAIL_MODE=api
    mail_origin: str = field(
        default_factory=lambda: os.getenv("MAIL_ORIGIN", ""))
    mailbox_domain: str = field(
        default_factory=lambda: os.getenv("MAILBOX_DOMAIN", ""))
    export_path: str = field(
        default_factory=lambda: os.getenv("EXPORT_PATH", "accounts.txt"))

    # IMAP — REQUIRED when MAIL_MODE=imap
    imap_host: str = field(
        default_factory=lambda: os.getenv("IMAP_HOST", ""))
    imap_port: int = field(
        default_factory=lambda: int(os.getenv("IMAP_PORT", "993")))
    imap_user: str = field(
        default_factory=lambda: os.getenv("IMAP_USER", ""))
    imap_pass: str = field(
        default_factory=lambda: os.getenv("IMAP_PASS", ""))
    imap_domain: str = field(
        default_factory=lambda: os.getenv("IMAP_DOMAIN", ""))
    imap_folder: str = field(
        default_factory=lambda: os.getenv("IMAP_FOLDER", "INBOX"))

    # Remote targets
    target_login: str = "https://console.x.ai"
    dispatch_code: str = "https://console.x.ai/api/auth/send-verification-code"
    confirm_email: str = "https://console.x.ai/api/auth/sign-up/verify-email"
    finish_signup: str = "https://console.x.ai/api/auth/sign-up/create-account"
    captcha_reference: str = "https://console.x.ai/login?mode=sign-up"

    # Solvers
    captcha_site_key: str = field(
        default_factory=lambda: os.getenv("CAPTCHA_KEY", ""))
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

    # Per-account hard timeout (seconds)
    per_account_timeout: float = field(
        default_factory=lambda: float(os.getenv("ACCOUNT_TIMEOUT", "180")))

    def __post_init__(self):
        self.token_matcher = re.compile(r"SpaceXAI confirmation code:\s*([A-Z0-9\-]+)")
        # Do not auto-validate here so cli can change mail_mode first

    def validate(self):
        """Validate config properties based on the selected mail_mode."""
        if self.mail_mode == "api":
            for key, val, desc in [
                ("MAIL_ORIGIN", self.mail_origin, "Base URL for temp-mail API"),
                ("MAILBOX_DOMAIN", self.mailbox_domain, "Domain for generated mailboxes"),
                ("CAPTCHA_KEY", self.captcha_site_key, "Turnstile site key"),
            ]:
                if not val:
                    print(f"[!] Missing required env var: {key} ({desc})")
                    sys.exit(1)

        elif self.mail_mode == "imap":
            for key, val, desc in [
                ("IMAP_HOST", self.imap_host, "IMAP server hostname"),
                ("IMAP_USER", self.imap_user, "IMAP login username"),
                ("IMAP_PASS", self.imap_pass, "IMAP login password"),
                ("IMAP_DOMAIN", self.imap_domain, "Catch-all domain for generated addresses"),
                ("CAPTCHA_KEY", self.captcha_site_key, "Turnstile site key"),
            ]:
                if not val:
                    print(f"[!] Missing required env var: {key} ({desc})")
                    sys.exit(1)

        else:
            print(f"[!] Invalid MAIL_MODE: {self.mail_mode!r} (use 'api' or 'imap')")
            sys.exit(1)


CONFIG = Settings()
