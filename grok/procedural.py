import asyncio
import sys
import time
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


class _Abort(Exception):
    """Raised inside run_single to break out to the common failure path."""


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

            if positive:
                log.confirm(f"Account registered ({elapsed:.1f}s)")
                await persist_account(inbox, secret)
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
