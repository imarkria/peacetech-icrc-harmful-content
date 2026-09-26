"""Deterministic lexicon checks: normalisation, age indicators (children.md CH-2), region term hits.

Nothing here is country-specific: age indicators are read from policy/children.md and terms
from the approved entries of the selected region profile.
"""

import re
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"

# Evasion: symbols and Latin look-alikes used inside Cyrillic words (platform profile, "Evasion").
_HOMOGLYPHS = str.maketrans({
    "@": "а", "0": "о", "3": "з", "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у",
    "k": "к", "m": "м", "t": "т", "b": "в", "h": "н", "ё": "е",
})
_CYRILLIC = re.compile(r"[а-яіїєґё]", re.IGNORECASE)
# Irregular or stem-changing forms of short words (regex alternations).
_IRREGULAR = {"child": "children", "дети": "детей|детям|детьми|детях", "діти": "дітей|дітям|дітьми|дітях",
              "kid": "kids"}


def normalize(text: str) -> str:
    """Lower-case; inside words that contain Cyrillic, map look-alike symbols to Cyrillic letters."""
    text = text.lower().replace("ё", "е")
    return re.sub(r"\S+", lambda m: m.group().translate(_HOMOGLYPHS) if _CYRILLIC.search(m.group()) else m.group(), text)


def _term_pattern(term: str) -> str:
    """'несовершеннолетн*' → prefix match; multi-word phrases match word by word with stems."""
    words = []
    for w in term.split():
        if w.endswith("*"):
            words.append(re.escape(normalize(w[:-1])) + r"\w*")
        elif len(w) <= 5:  # short words: whole word (+ plural), so "kid" ≠ "kidnap", "minor" ≠ "minority"
            w = normalize(w)
            words.append(f"(?:{re.escape(w)}(?:s|es|а|у|ом|е|и)?|{_IRREGULAR.get(w, re.escape(w))})(?!\\w)")
        else:
            w = normalize(w)
            words.append(re.escape(w[: max(5, len(w) - 2)]) + r"\w*")
    return r"(?<!\w)" + r"\s+".join(words)


# --- Age indicators (CH-2) -------------------------------------------------------

_AGE_NUMBER = re.compile(
    r"(?<!\d)(?:[1-9]|1[0-7])\s*(?:-?\s*(?:лет|года|год|летн\w*|років|рік|роки|річн\w*|y\.?\s?o\.?|yo|years?\s+old))(?!\w)")
_GRADE = re.compile(r"(?<!\d)(?:[1-9]|1[01])\s*(?:-?\s*(?:й|ий|го)\s*)?(?:класс\w*|клас\w*|grade)(?!\w)")


def _children_terms() -> list[str]:
    """Word lists from the CH-2 bullet lines of children.md (ru:/uk:/en: and orphanage terms)."""
    text = (POLICY_DIR / "children.md").read_text(encoding="utf-8")
    terms: list[str] = []
    for line in text.splitlines():
        m = re.match(r"\s*-\s*(ru|uk|en):\s*(.+?);?\s*$", line)
        if m:
            terms += [t.strip(" ;.") for t in m.group(2).split(",")]
    m = re.search(r"orphanage \(([^)]+)\)", text)
    if m:
        terms += [t.strip() for t in m.group(1).split(",")]
    return [t for t in terms if t]


_AGE_TERMS: list[re.Pattern] | None = None


def age_indicators(text: str) -> list[str]:
    """Which CH-2 indicators occur (labels only, never the matched span)."""
    global _AGE_TERMS
    if _AGE_TERMS is None:
        _AGE_TERMS = [re.compile(_term_pattern(t)) for t in _children_terms()]
    lower = text.lower().replace("ё", "е")  # digits must not go through the homoglyph map
    norm = normalize(text)
    hits = []
    if _AGE_NUMBER.search(lower):
        hits.append("stated_age")
    if _GRADE.search(lower):
        hits.append("school_grade")
    if any(p.search(norm) for p in _AGE_TERMS):
        hits.append("age_term")
    return hits


# --- Region terms ---------------------------------------------------------------

def _variants(value: str) -> list[str]:
    """'трофей / трофеи (applied to women…)' → ['трофей', 'трофеи']."""
    value = re.sub(r"\([^)]*\)", "", value)
    value = value.replace("«", "").replace("»", "").replace('"', "")
    return [v.strip() for v in value.split("/") if v.strip()]


class RegionLexicon:
    """Matcher over approved region entries of the given types (e.g. RG-SVTERM, RG-SLUR)."""

    def __init__(self, entries: list[dict], types: tuple[str, ...] = ("RG-SVTERM", "RG-SLUR")):
        self.patterns: list[tuple[str, re.Pattern]] = []
        for e in entries:
            if e["type"] in types and e.get("language") != "multi":
                for v in _variants(e["value"]):
                    self.patterns.append((e["id"], re.compile(_term_pattern(v))))

    def hits(self, text: str) -> list[str]:
        norm = normalize(text)
        return sorted({eid for eid, p in self.patterns if p.search(norm)})
