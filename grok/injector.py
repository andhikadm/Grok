import json
import sqlite3
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path

from .settings import CONFIG

def inject_to_9router(email: str, access_token: str, refresh_token: str, expires_at: str) -> tuple[bool, str]:
    """Inject registered Grok account into 9Router SQLite database."""
    db_path = Path(CONFIG.ninerouter_db_path)
    if not db_path.is_file():
        return False, "DB_NOT_FOUND"

    try:
        # Hubungkan ke database sqlite 9Router
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Cek apakah akun sudah terdaftar
        cur.execute(
            "SELECT id FROM providerConnections WHERE provider = 'grok-cli' AND (email = ? OR name = ?) LIMIT 1",
            (email, email)
        )
        row = cur.fetchone()

        if row:
            conn.close()
            return False, "ALREADY_EXISTS"

        # Tulis timestamp saat ini format ISO
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn_id = str(uuid.uuid4())

        data = {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at,
            "testStatus": "active",
            "errorCode": None,
            "lastRefreshAt": now,
            "clientId": "b1a00492-073a-47ea-816f-4c329264a828"
        }

        cur.execute(
            """INSERT INTO providerConnections
            (id, provider, name, email, data, isActive, createdAt, updatedAt, authType)
            VALUES (?, 'grok-cli', ?, ?, ?, 1, ?, ?, 'oauth2')""",
            (conn_id, email, email, json.dumps(data), now, now)
        )

        conn.commit()
        conn.close()
        return True, "SUCCESS"

    except Exception as exc:
        return False, str(exc)
