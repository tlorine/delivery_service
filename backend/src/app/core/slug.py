import re

_RU = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str = "item") -> str:
    """URL slug from a Russian or Latin name: 'Шаурма с сыром' -> 'shaurma-s-syrom'."""
    latin = "".join(_RU.get(ch, ch) for ch in text.lower())
    slug = _NON_SLUG.sub("-", latin).strip("-")[:90]
    return slug or fallback
