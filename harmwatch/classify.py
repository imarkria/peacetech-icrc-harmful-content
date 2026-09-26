"""Classifiers: Claude (policy-following) and an offline keyword fallback.

CLASSIFIER=claude | keywords | auto (default: claude when ANTHROPIC_API_KEY is set).
"""

import os
import re
from pathlib import Path

from harmwatch.schema import Classification

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy.md"
DEFAULT_MODEL = "claude-opus-5"

SYSTEM_PROMPT = """You label public social media posts for ICRC analysts who monitor harmful content related to sexual violence in armed conflict. Your output is a proposal; a trained human reviews every post before any action.

Apply the policy below exactly. Posts may be in Russian, Ukrainian or English; answer in English. Judge only the text you are given.

<policy>
{policy}
</policy>"""


def backend_name() -> str:
    choice = os.getenv("CLASSIFIER", "auto")
    if choice == "auto":
        return "claude" if os.getenv("ANTHROPIC_API_KEY") else "keywords"
    return choice


def classify(text: str) -> tuple[Classification, str]:
    """Return (classification, backend label)."""
    if backend_name() == "claude":
        return classify_claude(text)
    return classify_keywords(text), "keywords"


# --- Claude -----------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def classify_claude(text: str) -> tuple[Classification, str]:
    model = os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
    response = _get_client().messages.parse(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT.format(policy=POLICY_PATH.read_text(encoding="utf-8")),
        messages=[{"role": "user", "content": f"<post>\n{text}\n</post>"}],
        output_format=Classification,
        # If a safety classifier declines, retry server-side on Anthropic's recommended fallback model.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return needs_human("The model declined or returned no label; review manually."), f"{model} (declined)"
    return response.parsed_output, model


def needs_human(reason: str) -> Classification:
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
