#!/usr/bin/env python3
"""
grok_login.py — Login OAuth 2.0 PKCE untuk AKUN GROK MILIKMU SENDIRI.

Cara kerja (RFC 8252 - Authorization Code + PKCE untuk native/CLI app):
  1. Skrip membuat code_verifier + code_challenge (PKCE).
  2. Skrip membuka browser ke halaman login RESMI auth.x.ai.
  3. KAMU login sendiri dengan email + password kamu di halaman itu
     (dan selesaikan 2FA / verifikasi apa pun kalau diminta).
  4. Server meredirect ?code=... ke http://127.0.0.1:<PORT>/callback.
  5. Skrip menangkap code, memvalidasi 'state', lalu menukarnya jadi token.
  6. Token disimpan ke tokens.json (access_token, refresh_token, expires_at).

Jalankan di MESIN LOKAL kamu (bukan server headless):
    python grok_login.py
"""

import base64
import hashlib
import http.server
import json
import secrets
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone

# ─────────────────────────── KONFIGURASI ───────────────────────────
# client_id publik grok-cli (public client OAuth memang tidak punya secret).
CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
AUTH_URL = "https://auth.x.ai/oauth2/authorize"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
# Port loopback harus cocok dengan redirect_uri yang terdaftar di client.
REDIRECT_PORT = 56121
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
# offline_access WAJIB ada agar server mengembalikan refresh_token.
SCOPE = "openid profile email offline_access grok-cli:access api:access"
LOGIN_TIMEOUT = 300  # detik menunggu kamu menyelesaikan login di browser
OUTPUT_FILE = "tokens.json"
# ────────────────────────────────────────────────────────────────────


def make_pkce_pair():
    """Buat (code_verifier, code_challenge) sesuai RFC 7636 (metode S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def build_authorize_url(challenge, state, nonce):
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "nonce": nonce,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}  # diisi: {"code": ...} atau {"error": ...} + {"state": ...}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result = {k: v[0] for k, v in qs.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = ("<h3>Login selesai.</h3><p>Kamu boleh menutup tab ini "
               "dan kembali ke terminal.</p>")
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, *args):
        pass  # jangan cetak log HTTP


def wait_for_callback(timeout):
    """Jalankan listener localhost sekali-tangkap, kembalikan dict query."""
    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _CallbackHandler)
    server.timeout = timeout
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    deadline = time.time() + timeout
    while t.is_alive() and time.time() < deadline:
        time.sleep(0.2)
    server.server_close()
    return _CallbackHandler.result


def exchange_code_for_tokens(code, verifier):
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL, data=form, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if not port_is_free(REDIRECT_PORT):
        print(f"[!] Port {REDIRECT_PORT} sedang dipakai. Tutup aplikasi yang "
              f"memakainya (mis. grok-cli) lalu coba lagi.")
        sys.exit(1)

    verifier, challenge = make_pkce_pair()
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_hex(16)
    url = build_authorize_url(challenge, state, nonce)

    print("[*] Membuka browser untuk login...")
    print(f"    Kalau tidak terbuka otomatis, buka URL ini manual:\n    {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print(f"[*] Menunggu kamu login (timeout {LOGIN_TIMEOUT}s)...")
    result = wait_for_callback(LOGIN_TIMEOUT)

    if not result:
        print("[!] Timeout — tidak ada callback diterima.")
        sys.exit(1)
    if "error" in result:
        print(f"[!] Server menolak: {result.get('error')} "
              f"— {result.get('error_description', '')}")
        sys.exit(1)
    if result.get("state") != state:
        print("[!] 'state' tidak cocok — kemungkinan CSRF. Dibatalkan.")
        sys.exit(1)
    if "code" not in result:
        print(f"[!] Tidak ada 'code' di callback: {result}")
        sys.exit(1)

    print("[*] Code diterima. Menukar jadi token...")
    try:
        tok = exchange_code_for_tokens(result["code"], verifier)
    except urllib.error.HTTPError as e:
        print(f"[!] Token exchange gagal ({e.code}): {e.read().decode(errors='ignore')}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Token exchange error: {e!r}")
        sys.exit(1)

    access = tok.get("access_token", "")
    refresh = tok.get("refresh_token", "")
    expires_in = int(tok.get("expires_in", 0) or 0)
    expires_at = (datetime.fromtimestamp(time.time() + expires_in, timezone.utc)
                  .isoformat().replace("+00:00", "Z")) if expires_in else ""

    out = {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": expires_in,
        "expires_at": expires_at,
        "token_type": tok.get("token_type", "Bearer"),
        "scope": tok.get("scope", SCOPE),
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("\n[OK] Berhasil!")
    print(f"     access_token  : {access[:24]}... ({len(access)} char)")
    print(f"     refresh_token : {refresh[:24]}... ({len(refresh)} char)"
          if refresh else "     refresh_token : (KOSONG — cek scope offline_access)")
    print(f"     expires_at    : {expires_at}")
    print(f"     Tersimpan ke  : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
