"""Accent-insensitive text normalisation used by matching and sitemap indexing."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    {
        "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "com", "para",
        "por", "sem", "um", "uma", "no", "na", "nos", "nas", "ao", "tipo", "tp",
    }
)  # fmt: skip

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBER_UNIT = re.compile(r"(\d)([a-z])")
_UNIT_NUMBER = re.compile(r"([a-z])(\d)")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str | None) -> str:
    """Lowercase, remove accents and punctuation, separate numbers from letters.

    ``"Café 3 Corações 250g"`` -> ``"cafe 3 coracoes 250 g"``.
    """
    if not text:
        return ""
    value = strip_accents(text).lower().replace("º", "").replace("ª", "")
    value = _NON_ALNUM.sub(" ", value)
    value = _NUMBER_UNIT.sub(r"\1 \2", value)
    value = _UNIT_NUMBER.sub(r"\1 \2", value)
    return " ".join(value.split())


def stem(token: str) -> str:
    """Very small plural folding for Portuguese: ``ovos`` -> ``ovo``, ``maçãs`` -> ``maca``."""
    if len(token) > 3 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 3 and token.endswith("aes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("is") and not token.endswith("ais"):
        return token[:-1]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text: str | None, drop_stopwords: bool = True) -> list[str]:
    result = []
    for token in normalize(text).split():
        if drop_stopwords and token in STOPWORDS:
            continue
        result.append(stem(token))
    return result


def phrase_in(phrase: str, normalized_text: str) -> bool:
    """Whole-word phrase containment on already-normalised text (with stemming)."""
    phrase_tokens = [stem(t) for t in normalize(phrase).split()]
    if not phrase_tokens:
        return False
    text_tokens = [stem(t) for t in normalized_text.split()]
    width = len(phrase_tokens)
    return any(
        text_tokens[i : i + width] == phrase_tokens for i in range(len(text_tokens) - width + 1)
    )


def slugify(text: str) -> str:
    return "-".join(normalize(text).split())
