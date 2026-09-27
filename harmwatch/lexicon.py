"""Deterministic lexicon checks: normalisation, age indicators (children.md CH-2), region term hits.

Nothing here is country-specific: age indicators come from the `age_terms` of the loaded region profiles and
terms from the approved entries of the selected region profile.
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


_UK_ONLY = re.compile(r"[іїєґ]", re.IGNORECASE)
_RU_ONLY = re.compile(r"[ыэъё]", re.IGNORECASE)


def guess_lang(text: str) -> str:
    """ru / uk / en / other from letters that exist in only one of the two alphabets."""
    uk, ru = len(_UK_ONLY.findall(text)), len(_RU_ONLY.findall(text))
    if uk or ru:
        return "uk" if uk > ru else "ru"
    if _CYRILLIC.search(text):
        return "ru"
    return "en" if re.search(r"[a-z]", text, re.IGNORECASE) else "other"


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
# children.md CH-2 only describes the TYPES of indicators; the words for each language are in the `age_terms` of
# the region profiles (policy/regions/*.yaml). Nothing language-specific is hard-coded here.

# Latin transliteration of Cyrillic (URLs, evasion: "shkolnica"). Soft/hard signs are dropped on both sides before
# age-term matching, since transliterations usually omit them.
_TRANSLIT_MULTI = [("shch", "щ"), ("sch", "щ"), ("zh", "ж"), ("kh", "х"), ("ch", "ч"), ("sh", "ш"), ("ts", "ц"),
                   ("yu", "ю"), ("ya", "я"), ("ye", "е"), ("yo", "е"), ("ju", "ю"), ("ja", "я")]
_TRANSLIT_ONE = str.maketrans("abvgdezijklmnoprstufhcwx", "абвгдезийклмнопрстуфхцвк")


def _translit(text: str) -> str:
    def word(w: str) -> str:
        for a, b in _TRANSLIT_MULTI:
            w = w.replace(a, b)
        w = re.sub(r"(?<=[аеиоуяюэ])y", "й", w)
        return w.replace("y", "ы").translate(_TRANSLIT_ONE)
    return re.sub(r"[a-z]+", lambda m: word(m.group()), text)


def _unit(u: str) -> str:
    r"""'years old' → years[\s-]+old ; 'летн*' → летн\w* ; spaces and hyphens are interchangeable."""
    parts = [re.escape(p[:-1]) + r"\w*" if p.endswith("*") else re.escape(p) for p in u.lower().split()]
    return r"[\s-]+".join(parts)


def _alt(items) -> str:
    return "|".join(sorted(items, key=len, reverse=True))


class AgeMatcher:
    """Compiled CH-2 indicators for the `age_terms` of the loaded profiles ({lang: {words, age_units, ...}})."""

    def __init__(self, age_terms: dict):
        self.term_patterns: list[re.Pattern] = []
        self.numeric: list[tuple[str, re.Pattern]] = []
        for lang, t in age_terms.items():
            if not isinstance(t, dict):
                continue  # "note"
            for w in list(t.get("words", [])) + list(t.get("institutions", [])):
                self.term_patterns.append(re.compile(_term_pattern(w).replace("ь", "").replace("ъ", "")))
            words = {k.lower(): v for k, v in (t.get("number_words") or {}).items()}
            minor_words = [re.escape(k) for k, v in words.items() if v < 18]
            any_words = [re.escape(k) for k in words]
            # a number that is not part of a bigger number or a decimal ("13," is fine, "1.13" or "113" is not)
            minor = r"(?:(?<!\d)(?<!\d[.,])(?:[1-9]|1[0-7])(?!\d)(?![.,]\d)" + (f"|\\b(?:{_alt(minor_words)})" if minor_words else "") + ")"
            anynum = r"(?:(?<!\d)(?<!\d[.,])\d{1,3}(?!\d)(?![.,]\d)" + (f"|\\b(?:{_alt(any_words)})" if any_words else "") + ")"
            stop = t.get("not_followed_by") or []
            not_after = (r"(?!\s*-?\s*(?:" + _alt([_unit(x) for x in stop]) + r")(?!\w))") if stop else ""
            if t.get("age_units"):
                self.numeric.append(("stated_age", re.compile(
                    minor + r"\s*[\s-]?\s*(?:" + _alt(_unit(u) for u in t["age_units"]) + r")(?!\w)")))
            if t.get("infant_units"):
                self.numeric.append(("infant_age", re.compile(
                    anynum + r"\s*[\s-]?\s*(?:" + _alt(_unit(u) for u in t["infant_units"]) + r")(?!\w)")))
            for ph in t.get("stated_age_phrases") or []:
                before, _, after = ph.lower().partition("{n}")
                self.numeric.append(("stated_age", re.compile(
                    r"(?<!\w)" + re.escape(before) + minor + re.escape(after) + r"(?!\w)" + not_after)))
            grade = r"(?<!\d)(?:[1-9]|1[0-2])(?!\d)"
            for gp in t.get("grade_patterns") or []:
                before, _, after = gp.lower().partition("{n}")
                self.numeric.append(("school_grade", re.compile(
                    r"(?<!\w)" + (_unit(before) + r"[\s-]*" if before.strip() else "") + grade
                    + (r"[\s-]*" + _unit(after) if after.strip() else "") + r"(?!\w)")))

    def hits(self, text: str) -> list[str]:
        lower = text.lower().replace("ё", "е").replace("’", "'")  # digits must not go through the homoglyph map
        norm = normalize(text).replace("ь", "").replace("ъ", "")
        norm += "\n" + _translit(lower).replace("ь", "").replace("ъ", "")
        found = []
        for label, p in self.numeric:
            if label not in found and p.search(lower):
                found.append(label)
        if any(p.search(norm) for p in self.term_patterns):
            found.append("age_term")
        return found


_DEFAULT: AgeMatcher | None = None


def default_age_terms() -> dict:
    """The generic profile's age terms (policy/regions/global.yaml): used when no profile is given."""
    import yaml

    doc = yaml.safe_load((POLICY_DIR / "regions" / "global.yaml").read_text(encoding="utf-8"))
    return doc.get("age_terms") or {}


def age_indicators(text: str, matcher: AgeMatcher | None = None) -> list[str]:
    """Which CH-2 indicator types occur (labels only, never the matched span). `matcher` comes from the loaded
    policy (Policy.age_matcher); without one, the generic profile's terms are used."""
    global _DEFAULT
    if matcher is None:
        if _DEFAULT is None:
            _DEFAULT = AgeMatcher(default_age_terms())
        matcher = _DEFAULT
    return matcher.hits(text)


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
