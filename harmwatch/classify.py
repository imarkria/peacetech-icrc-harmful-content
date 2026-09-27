"""Text classifiers: our Qwen model (the classifier) and an offline keyword baseline.

CLASSIFIER=local (default) | keywords
local    = our Qwen model on llama-server (OpenAI-compatible, LOCAL_LLM_URL, LOCAL_LLM_MODEL), applying the policy/
           layers for REGION. Needs scripts/serve_llm.sh on a GPU.
keywords = crude keyword matching, for tests and demos without a GPU. Not a classifier to rely on.
"""

import os
import re

from harmwatch.schema import Classification

BACKENDS = ("local", "keywords")


def backend_name() -> str:
    choice = os.getenv("CLASSIFIER", "local")
    if choice not in BACKENDS:
        raise ValueError(f"CLASSIFIER must be one of {BACKENDS}, got {choice!r}")
    return choice


def classify(text: str) -> tuple[Classification, str]:
    """Return (classification, backend label)."""
    classification, backend, _ = classify_full(text)
    return classification, backend


def classify_full(text: str):
    """Return (classification, backend label, CRSVAssessment or None)."""
    if backend_name() == "local":
        return classify_local(text)
    return classify_keywords(text), "keywords", None


# --- Local open model ---------------------------------------------------------------

def classify_local(text: str):
    from harmwatch.crsv import assess_text
    from harmwatch.schema import to_classification

    label = f"local:{os.getenv('LOCAL_LLM_MODEL', 'qwen3.5-9b')}"
    assessment = assess_text(text)
    if assessment is None:
        return _needs_human("The local model returned no valid assessment; review manually."), f"{label} (failed)", None
    return to_classification(assessment), label, assessment


def _needs_human(reason: str) -> Classification:
    return Classification(
        harm_types=[],
        tone="other",
        claim_status="no_claim",
        victims=["unidentifiable"],
        harm_potential=1,
        confidence="low",
        summary="Not classified automatically.",
        rationale=reason,
    )


# --- Keyword fallback ---------------------------------------------------------
# Crude on purpose: it lets the demo run offline and gives the evaluation a baseline to beat.

KEYWORDS: dict[str, list[str]] = {
    "threat_incitement": [r"will (pay|learn|find out)", r"their women", r"when we (get|come)", r"do the same to"],
    "glorification": [r"deserved it", r"\breward", r"well done", r"trophy", r"proud of our"],
    "mockery_dark_humor": [r"😂|🤣|lol|lmao", r"\bjoke\b"],
    "victim_identification": [r"her name is", r"lives (on|at|in)", r"who is she", r"find her", r"address"],
    "stigmatization": [r"spoiled", r"asked for it", r"shame on (her|them)", r"no one will marry"],
    "sexually_explicit": [r"\bnude\b|\bnaked\b", r"explicit"],
    "denial_or_disinformation": [r"\bstaged\b", r"\bfake\b", r"so-called", r"crisis actors?"],
    "unverified_sv_claim": [r"heard (that|from)", r"rumou?r", r"unconfirmed", r"people are saying"],
}
SAFE_TONE = {
    "reporting": [r"\breport(s|ed)?\b", r"commission", r"documented", r"\bUN\b|OHCHR|NGO"],
    "testimony": [r"\bI was\b", r"\bhappened to me\b", r"\bmy (sister|mother|daughter|story)\b"],
    "awareness": [r"hotline", r"support (service|line)", r"you are not alone", r"help is available"],
}
VICTIMS = {
    "child": [r"\bchild(ren)?\b", r"\bgirl of \d", r"\bminor", r"\bkids?\b"],
    "woman": [r"\bwom[ae]n\b", r"\bgirls?\b", r"\bher\b", r"\bwives\b"],
    "man": [r"\bmen\b", r"\bprisoners?\b", r"\bPOWs?\b"],
}


def _hits(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_keywords(text: str) -> Classification:
    harms = [h for h, pats in KEYWORDS.items() if _hits(pats, text)]
    tone = next((t for t, pats in SAFE_TONE.items() if _hits(pats, text)), None)
    if tone and set(harms) <= {"unverified_sv_claim", "mockery_dark_humor"}:
        harms = []  # reporting / testimony / awareness vocabulary wins over weak signals
    if "mockery_dark_humor" in harms:
        tone = "humorous_ironic"
    victims = [v for v, pats in VICTIMS.items() if _hits(pats, text)] or ["unidentifiable"]
    severe = {"threat_incitement", "victim_identification", "glorification"}
    potential = 3 if severe & set(harms) and len(harms) > 1 else 2 if severe & set(harms) else 1 if harms else 0
    return Classification(
        harm_types=harms,
        tone=tone or "serious",
        claim_status="unverified_allegation" if "unverified_sv_claim" in harms else "no_claim",
        victims=victims,
        harm_potential=potential,
        confidence="low" if harms and potential < 2 else "medium",
        summary="Keyword match only (offline mode); no summary available.",
        rationale=f"Matched keyword groups: {', '.join(harms) or 'none'}.",
    )
