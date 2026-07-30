import asyncio
from typing import Any

from .settings import CONFIG


async def in_page_post(
    tab: Any, target_url: str, data_payload: dict[str, Any],
    timeout: float | None = None,
) -> dict[str, Any] | None:
    """
    Relay a POST request through the live browser context.
    Preserves cookies and origin headers automatically.
    Times out after *timeout* seconds (default: CONFIG.network_gate).
    """
    timeout = timeout if timeout is not None else CONFIG.network_gate
    try:
        raw = await asyncio.wait_for(
            tab.evaluate(
                """
                async ([url, body]) => {
                    try {
                        const r = await fetch(url, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        let data = null;
                        try { data = await r.json(); } catch { data = await r.text(); }
                        return { code: r.status, data };
                    } catch (e) { return null; }
                }
                """,
                [target_url, data_payload],
            ),
            timeout=timeout,
        )
    except Exception:
        return None
    if raw is None:
        return None
    return {"status": raw.get("code"), "body": raw.get("data")}
