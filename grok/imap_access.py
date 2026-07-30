import asyncio
import email
import imaplib
import random
import string
import time
from typing import Any

from .settings import CONFIG

_VOWELS = "aeiou"
_CONSONANTS = "bcdfghjklmnpqrstvwxyz"


def generate_imap_address() -> str:
    """Generate random address for catch-all domain."""
    length = random.randint(5, 8)
    buf = []
    for idx in range(length):
        buf.append(random.choice(_CONSONANTS) if idx % 2 == 0 else random.choice(_VOWELS))
    prefix = "".join(buf)
    # Tambahkan angka acak untuk menghindari tabrakan
    rand_num = random.randint(10, 99)
    return f"{prefix}{rand_num}@{CONFIG.imap_domain}"


def _get_email_body(msg) -> str:
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in cdisp:
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return ""


def _check_imap_inbox(target_address: str) -> str | None:
    """
    Connect to IMAP server, search for the confirmation email for target_address,
    and extract confirmation code.
    """
    # Menggunakan SSL
    try:
        mail = imaplib.IMAP4_SSL(CONFIG.imap_host, CONFIG.imap_port)
        mail.login(CONFIG.imap_user, CONFIG.imap_pass)
    except Exception as exc:
        raise ConnectionError(f"IMAP connection/auth failed: {exc}")

    try:
        status, _ = mail.select(CONFIG.imap_folder)
        if status != "OK":
            raise ValueError(f"Could not select IMAP folder: {CONFIG.imap_folder}")

        # Cari email ke target_address
        # Format SEARCH: TO "target_address"
        # Kita juga bisa batasi untuk SpaceXAI/x.ai email
        search_query = f'(TO "{target_address}")'
        status, data = mail.search(None, search_query)

        if status != "OK" or not data or not data[0]:
            return None

        # Ambil list email ID, urutkan dari yang terbaru
        email_ids = data[0].split()
        for email_id in reversed(email_ids):
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extract body
            body = _get_email_body(msg)

            # Cek confirmation code pakai regex token_matcher dari settings
            match = CONFIG.token_matcher.search(body)
            if not match:
                # Cek juga subject
                subject = str(msg.get("subject", ""))
                match = CONFIG.token_matcher.search(subject)

            if match:
                # Tandai email sebagai dibaca/hapus agar tidak terbaca lagi jika perlu
                # mail.store(email_id, '+FLAGS', '\\Seen')
                return match.group(1)

        return None
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


async def poll_imap_code(target_address: str, timeout: float, gap: float, logger: Any) -> str | None:
    """Poll IMAP server in separate thread until token appears or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        await asyncio.sleep(gap)
        elapsed = timeout - (deadline - time.time())
        logger.progress(f"Checking IMAP inbox... ({int(elapsed)}s)")
        try:
            code = await asyncio.to_thread(_check_imap_inbox, target_address)
            if code:
                return code
        except Exception as exc:
            logger.alert(f"IMAP error: {exc!r}")
            # Tunggu sebentar sebelum retry jika ada error koneksi
            await asyncio.sleep(2)
    return None
