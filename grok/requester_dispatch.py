from typing import Any


async def in_page_post(
    tab: Any, target_url: str, data_payload: dict[str, Any]
) -> dict[str, Any] | None:
    """
    Relay a POST request through the live browser context.
    Preserves cookies and origin headers automatically.
    """
    raw = await tab.evaluate(
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
    )
    if raw is None:
        return None
    return {"status": raw.get("code"), "body": raw.get("data")}
