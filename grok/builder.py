import secrets
import random
import string

_VOWEL_POOL = "aeiou"
_CONSONANT_POOL = "bcdfghjklmnpqrstvwxyz"
_CHAR_BANK = string.ascii_letters + string.digits + "!@#$%^&*"
_SYMBOL_SET = "!@#$%^&*"


def _generate_name(lo: int = 4, hi: int = 7) -> str:
    length = random.randint(lo, hi)
    buf = [random.choice(string.ascii_uppercase)]
    for _ in range(1, length):
        prev = buf[-1].lower()
        buf.append(random.choice(_CONSONANT_POOL) if prev in _VOWEL_POOL else random.choice(_VOWEL_POOL))
    return "".join(buf)


def _generate_secret(size: int = 14) -> str:
    while True:
        candidate = "".join(secrets.choice(_CHAR_BANK) for _ in range(size))
        if (any(ch.isupper() for ch in candidate)
                and any(ch.islower() for ch in candidate)
                and any(ch.isdigit() for ch in candidate)
                and any(ch in _SYMBOL_SET for ch in candidate)):
            return candidate


def compose_identity() -> tuple[str, str, str]:
    """Returns (first_name, last_name, secret)."""
    return _generate_name(4, 7), _generate_name(5, 8), _generate_secret(14)
