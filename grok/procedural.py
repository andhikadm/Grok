import asyncio
import sys
import time
import base64
import hashlib
import secrets
import urllib.parse
import urllib.request
import json
from colorama import Fore, Style

from .settings import CONFIG
from .output import Logger, Dashboard
from .builder import compose_identity
from .mail_access import create_temp_address, retrieve_inbox, harvest_code
from .imap_access import generate_imap_address, poll_imap_code
from .navigator import ManagedSession
from .requester_dispatch import in_page_post
from .captcha_bypasser import bypass_challenge
from .archiver import persist_account
from .injector import inject_to_9router


class _Abort(Exception):
    """Raised inside run_single to break out to the common failure path."""


def _generate_pkce_pair() -> tuple[str, str]:
    raw = secrets.token_bytes(96)
    verifier = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _extract_code_from_url(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        if "/callback" in (parsed.path or "") or "code=" in url:
            params = urllib.parse.parse_qs(parsed.query)
            vals = params.get("code")
            return vals[0] if vals else None
    except Exception:
        pass
    return None


def _exchange_auth_code_sync(code: str, verifier: str) -> dict | None:
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
        "code": code,
        "redirect_uri": "http://127.0.0.1:56121/callback",
        "code_verifier": verifier,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://auth.x.ai/oauth2/token",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


async def run_single(
    sequence: int, total: int, dashboard: Dashboard
) -> tuple[bool, float]:
    """Execute one full registration cycle.  Returns (succeeded, elapsed)."""
    stamp = f"[{sequence}/{total}]"
    log = Logger(stamp, thread_index=sequence).bind(dashboard)
    started = time.time()
    positive = False

    def _elapsed() -> float:
        return time.time() - started

    try:
        # Build persona
        first, last, secret = compose_identity()
        log.plain(f"Full Name: {first} {last}")

        # Acquire mailbox
        if CONFIG.mail_mode == "imap":
            inbox = generate_imap_address()
        else:
            log.progress("Securing temporary mailbox...")
            try:
                inbox_raw = await create_temp_address()
            except Exception:
                inbox_raw = None
            if not inbox_raw or "email" not in inbox_raw:
                raise _Abort("Could not obtain mailbox")
            inbox = inbox_raw["email"]

        log.confirm(f"Mailbox: {inbox}")

        # Launch browser & execute sign-up sequence
        async with ManagedSession() as driver:
            tab = await driver.new_page()

            log.progress("Loading target platform...")
            await tab.goto(CONFIG.target_login, wait_until="load", timeout=30000)
            await asyncio.sleep(2)

            # Send verification code
            log.progress("Dispatching verification request...")
            dispatch = await in_page_post(tab, CONFIG.dispatch_code, {"email": inbox})
            if not dispatch or dispatch.get("status") != 200:
                raise _Abort(f"Dispatch rejected: {dispatch}")
            log.confirm("Verification dispatched")

            # Poll for verification code
            log.progress("Awaiting confirmation token...")
            if CONFIG.mail_mode == "imap":
                verification_code = await poll_imap_code(inbox, CONFIG.poll_deadline, CONFIG.poll_delay, log)
            else:
                verification_code = await _poll_for_code(inbox, log)

            if not verification_code:
                raise _Abort("Token never arrived")

            # Confirm email
            log.progress("Confirming email address...")
            confirm = await in_page_post(
                tab, CONFIG.confirm_email,
                {"email": inbox, "code": verification_code},
            )
            if not confirm or confirm.get("status") != 200:
                raise _Abort(f"Confirmation failed: {confirm}")
            log.confirm("Email confirmed")

            # Solve CAPTCHA
            log.progress("Solving browser challenge...")
            challenge_token = await bypass_challenge(tab, log)
            if not challenge_token:
                raise _Abort("Challenge unsolved")

            # Register
            log.progress("Registering account...")
            registration = await in_page_post(tab, CONFIG.finish_signup, {
                "email": inbox,
                "password": secret,
                "givenName": first,
                "familyName": last,
                "emailValidationCode": verification_code,
                "turnstileToken": challenge_token,
            })

            elapsed = _elapsed()
            positive = bool(registration and registration.get("status") == 200)

            access_token = ""
            refresh_token = ""
            expires_at = ""

            if positive:
                log.confirm(f"Account registered ({elapsed:.1f}s)")
                # Go to main console first to trigger any onboarding/TOS accept if needed
                log.progress("Loading console dashboard...")
                try:
                    await tab.goto("https://console.x.ai", wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    console_url = tab.url
                    console_text = await tab.evaluate("() => document.body.innerText")
                    log.plain(f"Dashboard URL: {console_url}")
                    log.plain(f"Page text: {console_text[:500].replace(chr(10), ' ')}")
                    buttons = await tab.evaluate("() => Array.from(document.querySelectorAll('button')).map(b => b.innerText)")
                    log.plain(f"Buttons found: {', '.join(buttons)}")
                    # Try to click any accept/agree/continue/confirm/start button
                    inputs = await tab.evaluate("() => Array.from(document.querySelectorAll('input')).map(i => ({type: i.type, placeholder: i.placeholder, name: i.name}))")
                    log.plain(f"Inputs found on welcome: {inputs}")

                    # Fill team name if input exists
                    team_input = tab.locator('input[type="text"], input[placeholder*="team"], input[placeholder*="Team"]').first
                    if await team_input.count() > 0:
                        log.progress("Filling team name...")
                        await team_input.fill(f"{first} Team")
                        await asyncio.sleep(0.5)

                    # Click a role option (e.g. Engineer or Hobbyist)
                    role_btn = tab.locator('button:has-text("Engineer"), button:has-text("Hobbyist")').first
                    if await role_btn.count() > 0:
                        log.progress("Selecting role...")
                        await role_btn.click()
                        await asyncio.sleep(0.5)

                    agree_btn = tab.locator('button:has-text("Agree"), button:has-text("Accept"), button:has-text("Continue"), button:has-text("Next"), button:has-text("Get Started"), button:has-text("Confirm")').first
                    if await agree_btn.count() > 0 and await agree_btn.is_enabled(timeout=1000):
                        log.progress("Clicking onboarding button...")
                        await agree_btn.click(timeout=1500)
                        await asyncio.sleep(5) # Wait longer for navigation/creation
                        log.plain(f"URL after onboarding click: {tab.url}")
                except Exception as e:
                    log.alert(f"Dashboard navigation/onboarding failed: {e!r}")

                # Give some time for the account session to stabilize on the server
                await asyncio.sleep(2)

                # Execute OAuth PKCE flow to acquire tokens
                log.progress("Executing OAuth PKCE...")
                verifier, challenge = _generate_pkce_pair()
                state = secrets.token_urlsafe(24)
                nonce = secrets.token_hex(16)

                params = {
                    "response_type": "code",
                    "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
                    "redirect_uri": "http://127.0.0.1:56121/callback",
                    "scope": "openid profile email offline_access grok-cli:access api:access",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "state": state,
                    "nonce": nonce,
                    "plan": "generic",
                    "referrer": "cli-proxy-api",
                }
                auth_url = f"https://auth.x.ai/oauth2/authorize?{urllib.parse.urlencode(params)}"
                auth_code = {"code": None}

                async def _handle_route(route):
                    req_url = route.request.url
                    if "/callback" in req_url and ("127.0.0.1" in req_url or "localhost" in req_url):
                        log.confirm(f"Intercepted OAuth callback: {req_url}")
                        c = _extract_code_from_url(req_url)
                        if c:
                            auth_code["code"] = c
                        try:
                            await route.abort()
                        except Exception:
                            pass
                        return
                    try:
                        await route.continue_()
                    except Exception:
                        pass

                try:
                    await tab.route("**/*", _handle_route)
                    await tab.goto(auth_url, wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    pass

                # Dismiss cookie banner if it appears initially
                try:
                    cookie_btn = tab.locator('#onetrust-accept-btn-handler')
                    await cookie_btn.wait_for(state="visible", timeout=3000)
                    log.progress("Cookie banner detected. Dismissing...")
                    await cookie_btn.click(timeout=1500)
                    await cookie_btn.wait_for(state="hidden", timeout=3000)
                    log.confirm("Cookie banner dismissed")
                except Exception:
                    pass

                # Allow dialog / Login page handler
                for i in range(15):
                    if auth_code.get("code"):
                        break

                    current_url = tab.url
                    log.progress(f"OAuth flow ({i+1}/15) URL: {current_url}")

                    # 1. Dismiss cookie banner if it appears
                    try:
                        cookie_btn = tab.locator('#onetrust-accept-btn-handler:visible, #onetrust-reject-all-handler:visible, button:has-text("Accept All Cookies"):visible').first
                        if await cookie_btn.count() > 0 and await cookie_btn.is_enabled(timeout=1000):
                            log.progress("Dismissing cookie banner...")
                            await cookie_btn.click(timeout=1500)
                            await asyncio.sleep(2)
                            continue
                    except Exception as e:
                        pass

                    try:
                        # Cek tombol Allow / Authorize
                        allow_btn = tab.locator('button:text-is("Allow"):visible, button:text-is("Authorize"):visible, button:has-text("Allow"):visible, button:has-text("Authorize"):visible').first
                        if await allow_btn.count() > 0 and await allow_btn.is_enabled(timeout=1000):
                            log.progress("Clicking Allow/Authorize button...")
                            await allow_btn.click(timeout=1500)
                            await asyncio.sleep(2)
                        elif await allow_btn.count() > 0:
                            log.plain("Allow button exists but is disabled/hidden")
                            # Print consent page details
                            consent_text = await tab.evaluate("() => document.body.innerText")
                            consent_buttons = await tab.evaluate("() => Array.from(document.querySelectorAll('button')).map(b => b.innerText + ' (' + b.disabled + ')')")
                            log.plain(f"Consent text: {consent_text[:300].replace(chr(10), ' ')}")
                            log.plain(f"Consent buttons: {', '.join(consent_buttons)}")
                        else:
                            page_text = await tab.evaluate("() => document.body.innerText")
                            if "Access denied" in page_text or "Failed to generate" in page_text:
                                log.alert(f"OAuth page error: {page_text[:100].replace(chr(10), ' ')}")
                    except Exception as e:
                        log.alert(f"Error click Allow: {e!r}")

                    try:
                        # Cek input login jika diminta login ulang
                        pw_input = tab.locator('input[type="password"]:visible').first
                        if await pw_input.count() > 0:
                            log.progress("OAuth page requested login. Filling credentials...")
                            email_in = tab.locator('input[type="email"]:visible').first
                            if await email_in.count() > 0:
                                await email_in.fill(inbox, timeout=1500)
                            await pw_input.fill(secret, timeout=1500)

                            login_btn = tab.locator('button:has-text("Log in"):visible, button:has-text("Sign in"):visible, button[type="submit"]:visible').first
                            if await login_btn.count() > 0 and await login_btn.is_enabled(timeout=1000):
                                await login_btn.click(timeout=1500)
                    except Exception as e:
                        log.alert(f"Error filling login: {e!r}")

                    await asyncio.sleep(1)

                try:
                    await tab.unroute("**/*")
                except Exception:
                    pass

                code = auth_code.get("code")
                if code:
                    log.confirm("OAuth Code captured. Fetching tokens...")
                    token_res = await asyncio.to_thread(_exchange_auth_code_sync, code, verifier)
                    if token_res:
                        access_token = token_res.get("access_token", "")
                        refresh_token = token_res.get("refresh_token", "")
                        expires_in = int(token_res.get("expires_in", 21600))
                        from datetime import datetime, timezone
                        expires_at = datetime.fromtimestamp(time.time() + expires_in, timezone.utc).isoformat().replace("+00:00", "Z")
                        log.confirm("Tokens successfully fetched")
                    else:
                        log.alert("Token exchange failed")
                else:
                    log.alert("Failed to capture OAuth Code")

                # Tulis ke file
                await persist_account(inbox, secret, access_token, refresh_token, expires_at)

                # Auto-inject ke 9Router jika token lengkap dan opsi diaktifkan
                if CONFIG.auto_inject_9router and access_token and refresh_token:
                    injected, msg = inject_to_9router(inbox, access_token, refresh_token, expires_at)
                    if injected:
                        log.confirm("Automatically connected to 9Router DB")
                    elif msg == "ALREADY_EXISTS":
                        log.plain("Already exists in 9Router DB")
                    elif msg == "DB_NOT_FOUND":
                        log.alert("9Router database not found on this system")
                    else:
                        log.alert(f"9Router connection failed: {msg}")
            else:
                code = registration.get("status") if registration else "?"
                log.fail(f"Registration rejected (code {code}) ({elapsed:.1f}s)")

            return positive, elapsed

    except _Abort as exc:
        log.fail(str(exc))
        return False, _elapsed()

    except Exception as exc:
        log.fail(f"Unexpected error: {exc!r} ({_elapsed():.1f}s)")
        return False, _elapsed()

    finally:
        dashboard.advance(success=positive)
        dashboard.clear_thread(sequence)


async def _poll_for_code(inbox: str, log: Logger) -> str | None:
    """Poll the temporary mailbox until a verification code appears."""
    deadline = time.time() + CONFIG.poll_deadline
    while time.time() < deadline:
        await asyncio.sleep(CONFIG.poll_delay)
        elapsed = CONFIG.poll_deadline - (deadline - time.time())
        log.progress(f"Scanning inbox... ({int(elapsed)}s)")
        try:
            mail = await retrieve_inbox(inbox)
        except Exception:
            mail = None
        code = harvest_code(mail)
        if code:
            log.confirm(f"Token captured: {code} ({int(elapsed)}s)")
            return code
    return None


async def _safe_run(
    sequence: int, total: int, dashboard: Dashboard
) -> tuple[bool, float]:
    """Wrap run_single with a hard timeout so no task can hang forever."""
    try:
        return await asyncio.wait_for(
            run_single(sequence, total, dashboard),
            timeout=CONFIG.per_account_timeout,
        )
    except asyncio.TimeoutError:
        stamp = f"[{sequence}/{total}]"
        log = Logger(stamp, thread_index=sequence).bind(dashboard)
        log.fail(f"Hard timeout ({CONFIG.per_account_timeout:.0f}s) — skipped")
        dashboard.advance(success=False)
        dashboard.clear_thread(sequence)
        return False, CONFIG.per_account_timeout


async def orchestrate(tasks: int) -> None:
    sem = asyncio.Semaphore(CONFIG.max_concurrency)

    # Bypass dashboard for single task to print direct logs to console
    if tasks == 1:
        class DummyDashboard:
            def advance(self, success: bool): pass
            def clear_thread(self, idx: int): pass
            def set_status(self, idx: int, kind: str, msg: str):
                print(f"[{kind.upper()}] {msg}")

        dash = DummyDashboard()
        results = [await run_single(1, 1, dash)]
    else:
        with Dashboard(total=tasks, threads=CONFIG.max_concurrency) as dash:
            async def bounded_run(idx: int) -> tuple[bool, float]:
                async with sem:
                    return await _safe_run(idx, tasks, dash)
            results = await asyncio.gather(*(bounded_run(i) for i in range(1, tasks + 1)))

    wins = sum(1 for ok, _ in results if ok)
    intervals = [elapsed for _, elapsed in results]

    cumulative = sum(intervals)
    average = cumulative / len(intervals) if intervals else 0

    print(f"\n{Fore.CYAN}{'=' * 50}")
    print(f"  SUMMARY — Success: {Fore.GREEN}{wins}/{tasks}")
    print(f"  Total runtime : {cumulative:.1f}s")
    if tasks > 1:
        print(f"  Mean time     : {average:.1f}s per run")
    if wins:
        print(f"  Output        : {Fore.YELLOW}{CONFIG.export_path}")
    print(f"{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}\n")

    sys.exit(0 if wins == tasks else 1)
