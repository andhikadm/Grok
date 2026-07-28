import secrets
import string

_VOWEL_POOL = "aeiou"
_CONSONANT_POOL = "bcdfghjklmnpqrstvwxyz"
_SYMBOL_SET = "!@#$%^&*?+=-"


def _generate_name(lo: int = 4, hi: int = 7) -> str:
    length = secrets.randbelow(hi - lo + 1) + lo
    buf = [secrets.choice(string.ascii_uppercase)]
    for _ in range(1, length):
        prev = buf[-1].lower()
        buf.append(secrets.choice(_CONSONANT_POOL) if prev in _VOWEL_POOL else secrets.choice(_VOWEL_POOL))
    return "".join(buf)


def _generate_secret() -> str:
    """
    Generates a password matching the pattern:
    - 3 letters (1 uppercase, 2 lowercase)
    - 3 digits
    - 2 lowercase letters
    - 2 digits
    - 2 symbols
    Example: Fbr787pp48!!, Gup819xj91?+
    """
    p1 = secrets.choice(string.ascii_uppercase) + "".join(secrets.choice(string.ascii_lowercase) for _ in range(2))
    p2 = "".join(secrets.choice(string.digits) for _ in range(3))
    p3 = "".join(secrets.choice(string.ascii_lowercase) for _ in range(2))
    p4 = "".join(secrets.choice(string.digits) for _ in range(2))
    p5 = "".join(secrets.choice(_SYMBOL_SET) for _ in range(2))
    return f"{p1}{p2}{p3}{p4}{p5}"


def compose_identity() -> tuple[str, str, str]:
    """Returns (first_name, last_name, secret)."""
    return _generate_name(4, 7), _generate_name(5, 8), _generate_secret()
