"""analyze(): CH-5 restriction, pre-filter short-cut, explicit alert, table constraints, schema file, frozen judge."""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from harmwatch import detections
from harmwatch.analyze import V3_SHA256, Analyzer
from tests.analyze_fakes import FakeJudge, FakePrefilter, FakeSafety, judge_output

ROOT = Path(__file__).resolve().parent.parent


def image(tmp_path):
    p = tmp_path / "img.png"
    Image.new("RGB", (64, 64), "white").save(p)
    return str(p)


def test_possible_minor_empties_content(tmp_path):
    judge = FakeJudge(lambda item: judge_output(minor=True))
    row = Analyzer(judge=judge, db=tmp_path / "h.db").analyze({"modality": "text", "text": "synthetic"})
    assert row["possible_minor"] == 1 and row["restricted"] == 1 and row["route"] == "restricted_escalation"
    for k in detections.CONTENT_FIELDS:
        assert row[k] is None, k
    full = json.loads(row["full_result_json"])
    assert "judge" not in full and "scores" not in json.dumps(full)


def test_childlike_signal_raises_minor(tmp_path):
    """CH-2 (images): childlike appearance + sexual element → restricted, via the existing finalize_scores rule."""
    a = Analyzer(judge=FakeJudge(), safety=FakeSafety(child_visual=True), prefilter=FakePrefilter(), db=tmp_path / "h.db")
    row = a.analyze({"modality": "image", "path": image(tmp_path), "text": ""})
    assert row["restricted"] == 1 and row["sexual_violence"] is None and row["summary"] is None


def test_filtered_out_without_judge(tmp_path):
    judge = FakeJudge()
    a = Analyzer(judge=judge, safety=FakeSafety(), prefilter=FakePrefilter(score=0.1), db=tmp_path / "h.db")
    row = a.analyze({"modality": "image", "path": image(tmp_path), "text": ""})
    assert judge.calls == []
    assert row["route"] == "filtered_out" and row["filter_score"] == 0.1 and row["filter_passed"] == 0
    assert row["sexual"] is None and row["priority"] == "none"


def test_explicit_alert_never_dropped_nor_judged(tmp_path):
    judge = FakeJudge()
    a = Analyzer(judge=judge, safety=FakeSafety(quarantine=True), prefilter=FakePrefilter(score=0.0), db=tmp_path / "h.db")
    row = a.analyze({"modality": "image", "path": image(tmp_path), "text": ""})
    assert judge.calls == [] and row["explicit_alert"] == 1
    assert (row["route"], row["priority"]) == ("explicit_alert", "urgent")


def test_table_rejects_content_on_restricted_rows(tmp_path):
    """Second barrier: even SQL that bypasses insert_detection cannot store content for a restricted row."""
    conn = detections.connect(tmp_path / "h.db")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO detections (created_at, modality, media_hash, route, priority, region, possible_minor,"
                     " restricted, summary) VALUES ('t', 'text', 'h', 'x', 'urgent', 'global', 1, 1, 'content')")
    with pytest.raises(sqlite3.IntegrityError):  # possible_minor without restricted
        conn.execute("INSERT INTO detections (created_at, modality, media_hash, route, priority, region, possible_minor,"
                     " restricted) VALUES ('t', 'text', 'h', 'x', 'urgent', 'global', 1, 0)")


def test_schema_file_matches_code():
    assert (ROOT / "docs" / "platform" / "schema.sql").read_text(encoding="utf-8") == detections.SCHEMA


def test_unknown_region_refused(tmp_path):
    with pytest.raises(ValueError):
        Analyzer(judge=FakeJudge(), db=tmp_path / "h.db").analyze({"modality": "text", "text": "x"}, region="nowhere")


def test_prefilter_loads_from_models():
    from harmwatch.prefilter import Prefilter

    pf = Prefilter.load()
    assert pf.meta["embedding_model"] == "google/siglip2-so400m-patch14-384" and pf.meta["embedding_dim"] == 1152
    assert abs(pf.threshold - 0.1823) < 1e-3 and "research experiment" in pf.meta["status"]
    s = pf.score_embeddings(np.zeros((2, 1152)))
    assert len(s) == 2 and all(0 <= x <= 1 for x in s)


def test_prefilter_file_holds_weights_only():
    """Scaler statistics, coefficients and intercept of 1152-d features: no stored image or embedding matrix."""
    import joblib

    pipe = joblib.load(ROOT / "models" / "prefilter_image_logreg.joblib")
    arrays = {f"{name}.{k}": v.shape for name, step in pipe.named_steps.items() for k, v in vars(step).items()
              if isinstance(v, np.ndarray)}
    assert arrays == {"scale.mean_": (1152,), "scale.var_": (1152,), "scale.scale_": (1152,),
                      "clf.classes_": (2,), "clf.coef_": (1, 1152), "clf.intercept_": (1,), "clf.n_iter_": (1,)}


def test_judge_uses_frozen_v3_prompt():
    from harmwatch.analyze import Judge

    j = Judge(model="any")  # no server call at construction
    assert j.with_image.fingerprint() == V3_SHA256 == j.text_only.fingerprint()
