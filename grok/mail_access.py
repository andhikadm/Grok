import json
import ssl
import urllib.request as ureq
from typing import Any

from fake_useragent import UserAgent as UAPicker

from .settings import CONFIG

_agent = UAPicker()


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
    except Exception:
        return None


def create_temp_address(suffix: str | None = None) -> dict | None:
    """Procure a disposable inbox and return the response dict."""
    suffix = suffix or CONFIG.mailbox_domain
    endpoint = f"{CONFIG.mail_origin}/api/new"
    body = json.dumps({"domain": suffix}).encode("utf-8")
    return _transmit(endpoint, data=body, timeout=CONFIG.network_gate)


def retrieve_inbox(target: str) -> dict | None:
    """Collect messages from a given inbox."""
    uri = f"{CONFIG.mail_origin}/api/inbox/{target}"
    return _transmit(uri, timeout=CONFIG.network_gate)


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
