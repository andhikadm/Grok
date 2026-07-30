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
cp .env.example .env   # fill in your values
```

## Usage

```bash
python main.py
# Prompts: How many registrations? How many threads?

python main.py 3 2
# Non-interactive, three registrations with 2 threads
```

## Configuration

Copy `.env.example` to `.env` and fill in the **required** values:

| Variable | Required | Default |
|----------|----------|---------|
| `MAIL_ORIGIN` | **Yes** | — |
| `MAILBOX_DOMAIN` | **Yes** | — |
| `CAPTCHA_KEY` | **Yes** | — |
| `EXPORT_PATH` | No | `accounts.txt` |
| `SHOW_BROWSER` | No | `False` |
| `CONCURRENCY` | No | `3` |
| `POLL_MAX` | No | `60` |
| `CAPTCHA_WINDOW` | No | `25` |

## Output

Credentials appended to `accounts.txt`:

```
email@example.com|PasswordHere1!
```
