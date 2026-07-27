# GroK

Account registration tool using Camoufox browser automation.

> Educational / research only. Demonstrates browser automation, API interaction, and challenge solving.
> Use at your own risk. No liability assumed for misuse or account bans.

## Structure

```
main.py
grok/
├── cli.py               # CLI prompt / entry
├── settings.py          # Configuration with env overrides
├── output.py            # Logging helpers
├── builder.py           # Identity generation
├── mail_access.py       # Temporary email operations
├── navigator.py         # Camoufox session manager
├── requester_dispatch.py# In-browser fetch calls
├── captcha_bypasser.py  # Turnstile token gathering
├── procedural.py       # Registration workflow orchestration
└── archiver.py          # Credential persistence
```

## Requirements

- Python 3.10+
- Camoufox

## Setup

```bash
pip install -r requirements.txt
camoufox fetch
```

## Usage

```bash
python main.py
# Prompts: How many registrations?

python main.py 3
# Non-interactive, three registrations
```

## Configuration

Env vars override defaults:

| Variable | Default |
|----------|---------|
| `MAIL_ORIGIN` | `https://mail.cskh-group.com` |
| `MAILBOX_DOMAIN` | `vin-groupvn.com` |
| `EXPORT_PATH` | `accounts.txt` |
| `SHOW_BROWSER` | `False` |
| `CAPTCHA_KEY` | `0x4AAAAAAAhr9JGVDZbrZOo0` |
| `POLL_MAX` | `60` |
| `CAPTCHA_WINDOW` | `25` |

## Output

Credentials appended to `accounts.txt`:

```
email@example.com|PasswordHere1!
```
