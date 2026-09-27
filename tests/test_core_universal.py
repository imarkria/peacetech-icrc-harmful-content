"""The core is universal (core v1.3): core.md, children.md, modalities.md and the general judge instructions contain no
country, place, local actor, platform layer or non-Latin script. Everything local belongs in policy/regions/<code>.*.
"""

import re
import unicodedata
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policy"

PLATFORM_NAMES = ["Telegram", "WhatsApp", "VKontakte", "Facebook", "Instagram", "TikTok", "YouTube", "Twitter", "Signal"]
GENERIC_CAPITALISED = {"LGBTIQ", "POWs", "Grey", "Zone", "Corps", "SIZO"}  # capitalised but not local on their own


def universal_texts() -> dict[str, str]:
    from harmwatch.policy_loader import INSTRUCTIONS
    from harmwatch.sv_scores import SV_SCORE_INSTRUCTIONS
    from harmwatch.vision import IMAGE_INSTRUCTIONS

    texts = {f: (POLICY / f).read_text(encoding="utf-8") for f in ("core.md", "children.md", "modalities.md")}
    texts.update(INSTRUCTIONS=INSTRUCTIONS, SV_SCORE_INSTRUCTIONS=SV_SCORE_INSTRUCTIONS,
                 IMAGE_INSTRUCTIONS=IMAGE_INSTRUCTIONS)
    return texts


def local_names() -> set[str]:
    """Country names + proper nouns of every region profile except the generic one (places, actors, groups...)."""
    names = {l.strip() for l in (ROOT / "tests" / "fixtures" / "country_names.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")}
    for path in (POLICY / "regions").glob("*.yaml"):
        if path.stem == "global" or path.stem.endswith("_filter"):
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        names |= set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", doc.get("name") or ""))
        for e in doc.get("entries", []):
            if e["type"] in ("RG-PLACE", "RG-ACTOR", "RG-GROUP", "RG-NARRATIVE", "RG-CONTEXT"):
                names |= set(re.findall(r"\b[A-Z][a-zA-Z]{2,}(?:-[A-Z][a-zA-Z]+)?\b", e["value"]))
    return names - GENERIC_CAPITALISED - {"War"}


def non_latin_letters(text: str) -> list[str]:
    return sorted({ch for ch in text if ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN")})


@pytest.mark.parametrize("name", ["core.md", "children.md", "modalities.md", "INSTRUCTIONS", "SV_SCORE_INSTRUCTIONS",
                                  "IMAGE_INSTRUCTIONS"])
def test_core_has_no_local_content(name):
    text = universal_texts()[name]
    assert not non_latin_letters(text), f"{name}: non-Latin script {non_latin_letters(text)[:10]}"
    found = sorted(n for n in local_names() if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text))
    assert not found, f"{name}: local names {found}"
    platforms = [p for p in PLATFORM_NAMES if re.search(rf"\b{p}\b", text)] + re.findall(r"\bTG-L\d\b", text)
    assert not platforms, f"{name}: platform-specific references {platforms}"


def test_the_check_catches_local_content():
    assert non_latin_letters("говорят")
    assert "Bucha" in local_names() and "Ukraine" in local_names()


def test_local_content_lives_in_the_region_profile():
    doc = yaml.safe_load((POLICY / "regions" / "ru_ua.yaml").read_text(encoding="utf-8"))
    assert {"ru", "uk"} <= set(doc["age_terms"])
    ids = {e["id"] for e in doc["entries"]}
    assert {"RG-CONTEXT-001", "RG-STANCE-001", "RG-STANCE-002"} <= ids  # former CH-3 and rumour markers
    assert "en" in yaml.safe_load((POLICY / "regions" / "global.yaml").read_text(encoding="utf-8"))["age_terms"]


def general_examples() -> list[dict]:
    import json

    path = POLICY / "regions" / "global_examples.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_general_examples_are_universal_and_cite_only_core_ids():
    """Detection phase: examples are general (no country, place, real actor, non-Latin script) and their 'why' cites
    only IDs of the universal layers (no RG-*: no region profile is loaded in this phase)."""
    from scripts.check_policy_ids import CITED

    core_ids = set()
    for f in ("core.md", "children.md", "modalities.md", "platforms/generic.md"):
        core_ids |= set(CITED.findall((POLICY / f).read_text(encoding="utf-8")))
    names = local_names()
    for x in general_examples():
        text = " ".join([x.get("text", ""), x.get("image_description", ""), x["why"]])
        assert not non_latin_letters(text), (x["id"], non_latin_letters(text))
        assert not [n for n in names if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)], x["id"]
        cited = set(CITED.findall(x["why"] + json_dump(x["expected"])))
        assert not [i for i in cited if i.startswith("RG-")], (x["id"], cited)
        assert cited <= core_ids, (x["id"], cited - core_ids)


def test_general_examples_cover_the_boundary():
    xs = general_examples()
    cats = {x["sv_scores"]["category"] for x in xs if x["sv_scores"]["sexual"]}
    rels = {x["sv_scores"]["primary_relation"] for x in xs if x["sv_scores"]["sexual"]}
    assert {"SV-REL-1", "SV-REL-2", "SV-REL-3", "SV-REL-4", "SV-REL-5"} <= rels
    assert {"sexualised_insult", "degrading_sexualisation", "humiliating_objectification"} <= cats
    assert {x["expected"].get("exclusion") for x in xs} >= {"B2-1", "B2-2", "B2-3", "B2-4", "B2-5"}
    assert all(not x["sv_scores"]["sexual"] for x in xs if x["expected"].get("exclusion"))
    for x in xs:  # sv_scores complete and consistent
        s = x["sv_scores"]
        assert set(s["scores"]) == {"sexual_violence", "sexual_harassment", "hate", "misogyny", "other_violence"}
        assert (s["category"] == "none") == (not s["sexual"])
        assert "flag" in x["expected"] and "route" in x["expected"]


def json_dump(obj) -> str:
    import json

    return json.dumps(obj)
