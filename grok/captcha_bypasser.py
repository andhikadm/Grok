import asyncio
import time
from typing import Any

from .settings import CONFIG
from .output import Logger


async def bypass_challenge(
    active_tab: Any,
    logger: Logger,
    site_key: str | None = None,
    landing_page: str | None = None,
    hard_limit: float | None = None,
) -> str | None:
    """
    Embed a Turnstile widget in a synthetic same-origin page,
    then harvest the generated token.
    """
    key = site_key or CONFIG.captcha_site_key
    origin = landing_page or CONFIG.captcha_reference
    deadline = hard_limit if hard_limit is not None else CONFIG.captcha_window

    if not origin.endswith("/"):
        origin += "/"

    markup = _build_widget_page(key)

    route = f"{origin}__rt_solver__"

    async def intercept(route_to_handle):
        try:
            await route_to_handle.fulfill(
                status=200, content_type="text/html", body=markup
            )
        except Exception:
            pass

    try:
        await active_tab.route(route, intercept)
    except Exception:
        logger.fail("Browser closed before challenge setup")
        return None

    try:
        try:
            await active_tab.goto(route, wait_until="domcontentloaded")
            await active_tab.wait_for_selector(".cf-turnstile", timeout=8000)
        except Exception:
            logger.fail("Widget container never appeared")
            return None

        begin = time.time()
        while time.time() - begin < deadline:
            try:
                await active_tab.locator(".cf-turnstile").click(timeout=500, force=True)
            except Exception:
                pass

            try:
                candidate = await active_tab.evaluate(
                    """
                    () => {
                        const el = document.querySelector('input[name="cf-turnstile-response"]');
                        return el && el.value && el.value.length > 30 ? el.value : null;
                    }
                    """
                )
            except Exception:
                logger.fail("Browser closed during challenge")
                return None

            if candidate:
                spent = time.time() - begin
                logger.confirm(f"Challenge solved in {spent:.1f}s")
                return candidate

            await asyncio.sleep(0.4)

        logger.fail("Challenge timed out")
        return None
    finally:
        try:
            await active_tab.unroute(route)
        except Exception:
            pass


def _build_widget_page(k: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>
<style>body{{margin:0;height:100vh;display:flex;justify-content:center;align-items:center;background:#1a1a1a}}</style>
</head><body><div class="cf-turnstile" data-sitekey="{k}"></div></body></html>"""
