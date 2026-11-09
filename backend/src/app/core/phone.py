import re

_NON_DIGITS = re.compile(r"\D")


def normalize_phone(raw: str, country: str = "RU") -> str | None:
    """Return E.164 or None. RU/KZ (+7) numbers get full rules; other countries accept explicit +E.164."""
    digits = _NON_DIGITS.sub("", raw)
    if country in {"RU", "KZ"}:
        if len(digits) == 11 and digits[0] in "78":
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        else:
            return None
        # Mobile (9xx) and geographic (3xx, 4xx, 8xx) ranges; 7 7xx is Kazakhstan.
        return "+" + digits if digits[1] in "3456789" else None
    if raw.strip().startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    return None
