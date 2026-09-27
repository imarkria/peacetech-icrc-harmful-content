"""harmwatch.safety: explicit-image quarantine and childlike-appearance signal (no image is ever stored in the repo)."""

import json
from pathlib import Path

import pytest

from harmwatch.safety import THRESHOLDS, decide

SCORES = Path(__file__).resolve().parent.parent / "data" / "benchmarks" / "safety_scores_sv_v1_candidates.json"


def test_decide_is_an_or_of_the_three_classifiers():
    low = {"falconsai": 0.0, "adamcodd": 0.0, "clip_explicit": 0.1, "clip_child": 0.0}
    assert not decide(low).quarantine
    for key in ("falconsai", "adamcodd", "clip_explicit"):
        d = decide({**low, key: THRESHOLDS[key]})
        assert d.quarantine and d.reasons and key in d.reasons[0]


def test_child_signal_never_quarantines_on_its_own():
    d = decide({"falconsai": 0.0, "adamcodd": 0.0, "clip_explicit": 0.0, "clip_child": 0.99})
    assert d.child_visual and not d.quarantine


def test_childlike_appearance_plus_sexual_element_raises_possible_minor():
    from tests.test_rules import sv_out
    from harmwatch.sv_scores import finalize_scores

    a = finalize_scores(sv_out(), item_id="t", child_visual=True)
    assert a.possible_minor and a.restricted_reason == "rule_visual" and a.scores is None
    o = sv_out(sexual=False, primary_relation=None, category="none",
               scores={"sexual_violence": 0, "sexual_harassment": 0, "hate": 0, "misogyny": 0, "other_violence": 0})
    assert finalize_scores(o, item_id="t", child_visual=True).restricted_reason is None  # CH-1b: no sexual element


@pytest.mark.skipif(not SCORES.exists(), reason="precomputed scores live in data/ (not versioned)")
def test_measured_recall_on_the_explicit_images_missed_by_falconsai():
    """Regression guard on the 10 explicit images found at review (scores precomputed, images never loaded here)."""
    s = json.loads(SCORES.read_text())
    missed = [v for v in s.values() if v["explicit_at_review"]]
    assert len(missed) == 10
    assert sum(decide(v).quarantine for v in missed) >= 8
    assert not any(v["falconsai"] >= THRESHOLDS["falconsai"] for v in missed)  # why a 2nd classifier is needed
