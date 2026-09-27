"""analyze(): one test per modality, checking the row written in `detections` (fake judge, no GPU, no server)."""

from PIL import Image

from harmwatch.analyze import Analyzer
from tests.analyze_fakes import FakeJudge, FakePrefilter, FakeSafety, FakeVideo, video_script


def analyzer(tmp_path, **kw):
    parts = {"judge": FakeJudge(), "safety": FakeSafety(), "prefilter": FakePrefilter(), "db": tmp_path / "h.db"}
    return Analyzer(**(parts | kw))


def test_text_row(tmp_path):
    a = analyzer(tmp_path)
    row = a.analyze({"modality": "text", "text": "a synthetic threat", "url": "https://t.me/x/1", "source": "test"})
    assert row["id"] == 1 and row["modality"] == "text" and row["url"] == "https://t.me/x/1"
    assert row["sexual"] == 1 and row["sexual_violence"] == 70 and row["misogyny"] == 30
    assert row["primary_relation"] == "SV-REL-2" and row["category"] == "threat_incitement"
    assert (row["route"], row["priority"]) == ("priority_review", "high")
    assert row["filter_score"] is None and row["filter_passed"] is None  # no pre-filter for text
    assert row["restricted"] == 0 and row["summary"].startswith("Threat")
    assert row["model"] == "fake-qwen" and row["prompt_version"] == "sv_prompt_v3" and row["region"] == "global"
    assert len(row["media_hash"]) == 64 and "synthetic threat" not in row["full_result_json"]  # raw text not stored
    assert a.judge.calls[0]["image"] is None


def test_image_meme_row(tmp_path):
    p = tmp_path / "meme.png"
    Image.new("RGB", (64, 64), "white").save(p)
    a = analyzer(tmp_path)
    row = a.analyze({"modality": "image", "path": str(p), "text": "embedded words"})
    assert row["modality"] == "meme"  # image + embedded text
    assert row["filter_score"] == 0.8 and row["filter_passed"] == 1
    assert row["sexual"] == 1 and row["explicit_alert"] == 0 and row["possible_minor"] == 0
    assert a.judge.calls[0]["image"] is not None and a.judge.calls[0]["text"] == "embedded words"


def test_video_row_worst_segment(tmp_path):
    v = tmp_path / "clip.mp4"
    v.write_bytes(b"not a real video: segments come from the fake")
    a = analyzer(tmp_path, judge=FakeJudge(video_script), video=FakeVideo())
    row = a.analyze({"modality": "video", "path": str(v)})
    assert row["modality"] == "video" and row["sexual"] == 1
    assert (row["flagged_start_s"], row["flagged_end_s"]) == (10.0, 25.0)  # the harmful segment
    assert row["route"] == "priority_review" and len(a.judge.calls) == 2
