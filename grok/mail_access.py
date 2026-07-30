import asyncio
import json
import logging
import ssl
import urllib.request as ureq
from typing import Any

from fake_useragent import UserAgent as UAPicker

from .settings import CONFIG

_agent = UAPicker()
_log = logging.getLogger(__name__)

# ── Retry configuration ──
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class MailError(Exception):
    """Raised when a mail API request fails."""


async def _with_retry(func, *args, retries: int = _MAX_RETRIES, label: str = "request"):
    """Run a blocking function with asyncio.to_thread and retry on failure."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await asyncio.to_thread(func, *args)
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                delay = _BASE_DELAY * (2 ** (attempt - 1))
                _log.debug("%s attempt %d/%d failed (%s), retrying in %.1fs",
                           label, attempt, retries, exc, delay)
                await asyncio.sleep(delay)
    _log.warning("%s failed after %d attempts: %s", label, retries, last_err)
    raise MailError(f"{label} failed after {retries} attempts: {last_err}") from last_err


def _build_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": _agent.random,
    }


def _transmit(url: str, data: bytes | None = None, timeout: float = 10) -> Any:
    method = "POST" if data else "GET"
    req = ureq.Request(url, data=data, method=method, headers=_build_headers())
    try:
        with ureq.urlopen(req, context=ssl.create_default_context(), timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _log.debug("Request to %s failed: %s", url, exc)
        raise MailError(f"{method} {url} failed: {exc}") from exc


async def create_temp_address(suffix: str | None = None) -> dict | None:
    """Procure a disposable inbox and return the response dict."""
    suffix = suffix or CONFIG.mailbox_domain
    endpoint = f"{CONFIG.mail_origin}/api/new"
    body = json.dumps({"domain": suffix}).encode("utf-8")
    return await _with_retry(_transmit, endpoint, body, CONFIG.network_gate,
                             label="create_temp_address")


async def retrieve_inbox(target: str) -> dict | None:
    """Collect messages from a given inbox."""
    uri = f"{CONFIG.mail_origin}/api/inbox/{target}"
    return await _with_retry(_transmit, uri, None, CONFIG.network_gate,
                             label="retrieve_inbox")


def harvest_code(payload: Any) -> str | None:
    """Scan mailbox content for the confirmation token."""
    if not isinstance(payload, dict):
        return None
    for entry in payload.get("emails", []):
        for tag in ("subject", "preview"):
            match = CONFIG.token_matcher.search(entry.get(tag, ""))
            if match:
                return match.group(1)
    return None
