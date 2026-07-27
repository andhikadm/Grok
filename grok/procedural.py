import asyncio
import sys
import time
from colorama import Fore, Style

from .settings import CONFIG
from .output import Logger, emit_banner
from .builder import compose_identity
from .mail_access import create_temp_address, retrieve_inbox, harvest_code
from .navigator import ManagedSession
from .requester_dispatch import in_page_post
from .captcha_bypasser import bypass_challenge
from .archiver import persist_account


async def run_single(sequence: int, total: int) -> tuple[bool, float]:
    """Execute one full registration cycle.  Returns (succeeded, elapsed)."""
    stamp = f"[{sequence}/{total}]"
    log = Logger(stamp)
    started = time.time()

    # Build persona
    first, last, secret = compose_identity()
    log.plain(f"Full Name: {first} {last}")

    # Acquire mailbox
    log.progress("Securing temporary mailbox...")
    inbox_raw = create_temp_address()
    if not inbox_raw or "email" not in inbox_raw:
        log.fail("Could not obtain mailbox")
        return False, time.time() - started
    inbox = inbox_raw["email"]
    log.confirm(f"Mailbox: {inbox}")

    # Launch browser & execute sign-up sequence
    async with ManagedSession() as driver:
        tab = await driver.new_page()

        log.progress("Loading target platform...")
        await tab.goto(CONFIG.target_login, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        log.progress("Dispatching verification request...")
        dispatch = await in_page_post(tab, CONFIG.dispatch_code, {"email": inbox})
        if not dispatch or dispatch.get("status") != 200:
            log.fail(f"Dispatch rejected: {dispatch}")
            return False, time.time() - started
        log.confirm("Verification dispatched")

        log.progress("Awaiting confirmation token...")
        secret_token, consumed = None, 0.0
        while consumed < CONFIG.poll_deadline:
            await asyncio.sleep(CONFIG.poll_delay)
            consumed += CONFIG.poll_delay
            log.raw(f"  [{int(consumed)}s] Scanning inbox...")
            mail = retrieve_inbox(inbox)
            secret_token = harvest_code(mail)
            if secret_token:
                log.confirm(f"Token captured: {secret_token} ({int(consumed)}s)")
                break

        if not secret_token:
            log.fail("Token never arrived")
            return False, time.time() - started

        log.progress("Confirming email address...")
        confirm = await in_page_post(tab, CONFIG.confirm_email, {"email": inbox, "code": secret_token})
        if not confirm or confirm.get("status") != 200:
            log.fail(f"Confirmation failed: {confirm}")
            return False, time.time() - started
        log.confirm("Email confirmed")

        log.progress("Solving browser challenge...")
        challenge_token = await bypass_challenge(tab, log)
        if not challenge_token:
            log.fail("Challenge unsolved")
            return False, time.time() - started

        log.progress("Registering account...")
        registration = await in_page_post(tab, CONFIG.finish_signup, {
            "email": inbox,
            "password": secret,
            "givenName": first,
            "familyName": last,
            "emailValidationCode": secret_token,
            "turnstileToken": challenge_token,
        })

        elapsed = time.time() - started
        positive = bool(registration and registration.get("status") == 200)

        if positive:
            print(f"  Account registered successfully")
            print(f"  Wall clock: {elapsed:.1f}s")
            await persist_account(inbox, secret)
            print(f"  Saved to {CONFIG.export_path}")
        else:
            code = registration.get("status") if registration else "?"
            print(f"  Registration rejected (code {code})")
            print(f"  Wall clock: {elapsed:.1f}s")

        return positive, elapsed


async def orchestrate(tasks: int) -> None:
    emit_banner()
    print(f"\n>> Initiating {tasks} registration(s)...\n")

    wins = 0
    intervals = []

    for idx in range(1, tasks + 1):
        ok, elapsed = await run_single(idx, tasks)
        intervals.append(elapsed)
        if ok:
            wins += 1
        if idx < tasks:
            print()

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
