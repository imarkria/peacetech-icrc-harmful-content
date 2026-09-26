"""Hard rules of policy/core.md and children.md, checked without any model.

Age-indicator tests use neutral text only (CH-5): no sexual content is ever combined with them here.
"""

import pytest

from harmwatch.lexicon import age_indicators, normalize
from harmwatch.policy_loader import ProfileNotApproved, load_policy
from harmwatch.schema import CRSVModelOutput, finalize, to_classification
from harmwatch.triage import ESCALATE, HARMFUL, NOT_HARMFUL, triage


def output(**overrides) -> CRSVModelOutput:
    """A flaggable SV-REL-2 threat by default; override fields per test."""
    base = dict(
        risk_flags={"possible_minor": False, "identifiable_person": False, "possible_manipulated_media": False},
        exclusion=None, forwarded_original=None,
        features={"source_attributed": False, "stance": "endorses", "target": "group", "general": True, "modal": "future", "cta": "implied",
                  "frame": True, "speaker": "unknown"},
        elements={k: {"value": "likely", "confidence": 0.9, "reason": "r"} for k in "ABC"},
        primary_relation="SV-REL-2", secondary_relations=[], content_type=3, named_acts=["SV-FORM-01"],
        hi_types=[{"id": "HI-TYPE-04", "possible": False}], harm_pathways=[{"id": "HP-01", "possible": False}],
        affiliation="AFF-1", conf_ids=["CONF-3"], age=["adult"], triggered_layer="TG-L1",
        lexicon_hits=["RG-SVTERM-010"], cited_ids=["SV-REL-2", "HP-01"], route="standard_review",
        priority="standard", lead=False, reviewer_summary="A threat against a group.",
        media_needed_to_decide=False, notes="",
    )
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return CRSVModelOutput(**base)


def run(o, **kw):
    return finalize(o, item_id="t", region="test", profile_version="0", **kw)


def test_possible_minor_blanks_content_even_if_model_filled_it():
    a = run(output(risk_flags={"possible_minor": True}))
    assert a.route == "restricted_escalation"
    assert a.reviewer_summary == "" and a.named_acts == [] and a.lexicon_hits == [] and a.notes == ""
    assert a.primary_relation is None and all(getattr(a.elements, k).reason == "" for k in "ABC")
    assert triage(to_classification(a)) == ESCALATE
    assert to_classification(a).summary == ""


def test_age_indicator_plus_sexual_element_raises_possible_minor():
    a = run(output(), age_indicator=True)
    assert a.route == "restricted_escalation" and a.risk_flags.possible_minor
    assert "raised by rule" in a.rule_notes[0]


def test_age_indicator_without_sexual_element_is_not_restricted():  # CH-1b stays reviewable
    o = output(primary_relation=None, named_acts=[], elements={"A": {"value": "unlikely", "confidence": 0.9,
                                                                     "reason": "r"}})
    assert run(o, age_indicator=True).route == "not_flagged"


def test_minor_in_model_age_list_with_sexual_element_is_restricted():
    assert run(output(age=["minor"])).route == "restricted_escalation"


def test_flag_requires_axis1():  # hate without sexual violence = hard negative
    a = run(output(primary_relation=None, route="standard_review"))
    assert a.route == "not_flagged" and not a.in_scope


def test_flag_requires_axis2_and_affiliation():
    assert run(output(harm_pathways=[])).route == "not_flagged"
    assert run(output(affiliation="AFF-4")).route == "not_flagged"


def test_b2_exclusion_is_never_flagged():
    a = run(output(exclusion="B2-3"))
    assert a.route == "not_flagged" and a.lead


@pytest.mark.parametrize("stance", ["reports", "quotes_to_condemn"])
def test_stance_override_gives_lead(stance):
    a = run(output(features={"stance": stance, "source_attributed": True}), quote_present=True)
    assert a.route == "not_flagged" and a.lead
    assert triage(to_classification(a)) == NOT_HARMFUL


def test_unsourced_report_is_not_an_override():  # core v1.1: rumour = unclear, still assessed
    a = run(output(features={"stance": "reports", "source_attributed": False}))
    assert a.features.stance == "unclear" and a.route == "priority_review" and not a.lead


def test_condemning_without_quote_is_not_an_override():
    a = run(output(features={"stance": "quotes_to_condemn"}), quote_present=False)
    assert a.features.stance == "unclear" and a.route == "priority_review"


def test_testimony_is_not_a_lead():  # core v1.1, B6-3
    a = run(output(exclusion="B2-1", features={"stance": "reports"}, lead=True))
    assert a.route == "not_flagged" and not a.lead


def test_restricted_reason():
    assert run(output(risk_flags={"possible_minor": True})).restricted_reason == "model"
    assert run(output(), age_indicator=True).restricted_reason == "rule_age"
    assert run(output()).restricted_reason is None


def test_prevention_is_not_a_lead():
    a = run(output(exclusion="B2-2", features={"stance": "reports", "source_attributed": True}, lead=True))
    assert a.route == "not_flagged" and not a.lead


def test_threat_future_is_urgent_priority_review():
    a = run(output())
    assert a.priority == "urgent" and a.route == "priority_review"
    assert triage(to_classification(a)) == HARMFUL


def test_region_can_raise_priority_never_lower():
    o = output(primary_relation="SV-REL-4", features={"modal": "past", "cta": "none"}, priority="high")
    assert run(o).priority == "high"
    o = output(priority="standard")  # rule says urgent, model says standard → urgent
    assert run(o).priority == "urgent"


def test_exposure_of_identifiable_person_is_urgent():
    o = output(primary_relation="SV-REL-5", features={"modal": "past", "cta": "none", "target": "individual"},
               harm_pathways=[{"id": "HP-03", "possible": False}],
               risk_flags={"identifiable_person": True})
    a = run(o)
    assert a.priority == "urgent" and a.route == "priority_review"


def test_invalid_cited_ids_are_reported():
    a = run(output(cited_ids=["SV-REL-2", "XX-99"]), valid_ids={"SV-REL-2"})
    assert a.invalid_ids == ["XX-99"]


def test_age_indicators_on_neutral_text():
    assert age_indicators("Ученица 9 класса победила в олимпиаде")
    assert age_indicators("Дітей евакуювали з Херсона")
    assert age_indicators("Він має 14 років")
    assert not age_indicators("Девушки из волонтёрского штаба привезли воду")  # девушка is not an indicator
    assert not age_indicators("Мне было 34 года")
    assert not age_indicators("A kidnapped journalist; minority rights")
    assert age_indicators("A 15-year-old boy won the regional chess cup")
    assert age_indicators("The 14 yr old student gave a speech")
    assert age_indicators("news/2021/shkolnica-vyigrala-olimpiadu")  # Latin transliteration in a URL


def test_normalize_evasion():
    assert normalize("изн@силование") == "изнасилование"
    assert normalize("н@силие") == "насилие"


def test_loader_refuses_without_approved_entries(tmp_path, monkeypatch):
    import harmwatch.policy_loader as pl

    (tmp_path / "regions").mkdir()
    (tmp_path / "regions" / "xx.yaml").write_text("version: '0'\nentries:\n- {id: RG-SLUR-001, status: proposed}\n")
    monkeypatch.setattr(pl, "POLICY_DIR", tmp_path)
    with pytest.raises(ProfileNotApproved):
        load_policy("xx")


def test_export_excludes_restricted(tmp_path, monkeypatch):
    from harmwatch import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    a = run(output(risk_flags={"possible_minor": True}))
    c = to_classification(a)
    with db.connect() as conn:
        pid = db.add_post(conn, source="sample", text="placeholder", url="x://1")
        db.save_classification(conn, pid, "test", c, triage(c), 0)
        db.save_decision(conn, pid, "yes", "", "t")
        assert db.export_decisions(conn) == []


# --- Modalities and the compact image judge ------------------------------------------

def compact(**overrides):
    from harmwatch.vision import CompactModelOutput

    base = dict(risk_flags={"possible_minor": False, "identifiable_person": False, "possible_manipulated_media": False},
                exclusion=None, stance="endorses", source_attributed=False, primary_relation="SV-REL-3",
                hi_types=["HI-TYPE-04"], harm_pathways=["HP-04"], affiliation="AFF-1", triggered_layer="meme",
                confidence=0.8, reason="r")
    return CompactModelOutput(**{**base, **overrides})


def fin(o, text=""):
    from harmwatch.vision import finalize_compact

    return finalize_compact(o, item_id="t", modality="meme", embedded_text=text)


def test_compact_hate_without_sv_is_hateful_not_flagged():
    a = fin(compact(primary_relation=None))
    assert a.hateful and not a.sv_related and not a.flag and a.route == "not_flagged"


def test_compact_flag_rule_and_route():
    assert fin(compact()).route == "standard_review"
    assert fin(compact(primary_relation="SV-REL-2")).route == "priority_review"
    assert not fin(compact(affiliation="AFF-4")).flag
    assert not fin(compact(harm_pathways=[])).flag
    a = fin(compact(exclusion="B2-3"))
    assert not a.flag and a.lead


def test_compact_unsourced_report_is_not_an_override():
    a = fin(compact(stance="reports", source_attributed=False))
    assert a.stance == "unclear" and a.flag


def test_compact_possible_minor_blanks_everything():
    a = fin(compact(risk_flags={"possible_minor": True, "identifiable_person": False,
                                "possible_manipulated_media": False}))
    assert a.route == "restricted_escalation" and a.reason == "" and a.hi_types == [] and a.restricted_reason == "model"
    assert fin(compact(), text="Ученица 9 класса").restricted_reason == "rule_age"  # neutral text (CH-5)


def test_assessment_has_modality_and_loader_has_modalities_layer():
    assert run(output()).modality == "text"
    p = load_policy("ru_ua")
    assert "<modalities_policy>" in p.system_prompt([]) and "MOD-MEME" in p.valid_ids


def test_generic_platform_and_global_profile_never_load_proposed():
    p = load_policy("global", "generic", allow_no_approved=True)
    assert p.entries == [] or all(e["status"] == "approved" for e in p.entries)
    assert "platform: generic" in p.system_prompt(p.examples[:2])
