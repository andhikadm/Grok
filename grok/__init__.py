"""
GroK - Account registration automation via browser automation.
Educational / research only.
"""

from .settings import Settings, CONFIG
from .output import Logger, Dashboard, emit_banner
from .builder import compose_identity
from .mail_access import MailError, create_temp_address, retrieve_inbox, harvest_code
from .navigator import ManagedSession
from .requester_dispatch import in_page_post
from .captcha_bypasser import bypass_challenge
from .procedural import run_single
from .archiver import persist_account

__all__ = [
    "MailError", "Settings", "CONFIG", "Logger", "Dashboard", "emit_banner", "compose_identity",
    "create_temp_address", "retrieve_inbox", "harvest_code",
    "ManagedSession", "in_page_post", "bypass_challenge",
    "run_single", "persist_account",
]
