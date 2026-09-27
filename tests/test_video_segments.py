"""Video pipeline by segments and the separate racism topic layer (no video or image needed)."""

import json
import re
from pathlib import Path

from harmwatch.video_segments import (TopicPrompt, aggregate, attach, format_segment, offset, overlaps,
                                      segment_bounds)

POLICY = Path(__file__).resolve().parent.parent / "policy"


def test_segments_are_between_5_and_20_seconds():
    b = segment_bounds(100.0, [2.0, 3.0, 30.0, 31.0, 80.0])
    assert b[0][0] == 0.0 and b[-1][1] == 100.0
    assert all(5.0 <= e - s <= 20.0 for s, e in b), b
    assert all(b[i][1] == b[i + 1][0] for i in range(len(b) - 1))  # contiguous, no gap


def test_no_scene_cut_gives_fixed_15s_windows():
    b = segment_bounds(47.0, [])
    assert [round(e - s) for s, e in b] == [15, 15, 17]  # short tail merged backwards
    assert segment_bounds(0.0, []) == []


def test_short_video_is_one_segment():
    assert segment_bounds(4.0, []) == [(0.0, 4.0)]


def test_transcript_phrases_attach_to_every_overlapping_segment():
    texts = attach([{"start": 0, "end": 4, "text": "a"}, {"start": 9, "end": 12, "text": "b"}],
                   [(0, 10), (10, 20)])
    assert texts == ["a b", "b"]


def test_aggregate_is_max_over_segments():
    segs = [{"index": 1, "start": 0, "end": 10, "p_racist": 0.1, "racist": False, "category": "none",
             "triggered_layer": "speech", "scores": {"racism": 5}},
            {"index": 2, "start": 10, "end": 20, "p_racist": 0.9, "racist": True, "category": "RAC-1",
             "triggered_layer": "speech", "scores": {"racism": 80}},
            {"index": 3, "start": 20, "end": 30, "p_racist": None, "racist": None}]
    v = aggregate("v", segs)
    assert v["score"] == 0.9 and v["racist"] and v["flagged"][0]["index"] == 2 and v["n_errors"] == 1


def test_localisation_helpers():
    assert overlaps((10, 20), (15, 30)) and not overlaps((0, 5), (10, 20))
    assert offset((0, 5), (10, 20)) == 5 and offset((10, 20), (15, 30)) == 0


def test_topic_prompt_never_loads_the_sexual_violence_core():
    p = TopicPrompt("racism")
    assert "RAC-DEF" in p.system and "MOD-VID" in p.system  # topic + modalities (read as is)
    assert "<core_policy>" not in p.system and "SV-REL-1" not in p.system and "CH-1a" not in p.system
    assert p.fingerprint() == TopicPrompt("racism").fingerprint()


def test_racism_examples_cite_only_topic_ids():
    xs = [json.loads(l) for l in (POLICY / "topics" / "racism_examples.jsonl").read_text().splitlines() if l.strip()]
    assert len(xs) == 6 and sum(x["expected"]["racist"] for x in xs) == 3
    ids = set(re.findall(r"\bRAC-(?:DEF|EX-\d|\d)\b", (POLICY / "topics" / "racism.md").read_text()))
    for x in xs:
        cited = set(re.findall(r"\b[A-Z]{2,5}-(?:[A-Z]{2,3}-)?\d+\b|\bRAC-DEF\b", x["why"] + json.dumps(x["expected"])))
        assert cited <= ids, (x["id"], cited - ids)
        assert (x["expected"]["category"] == "none") == (not x["expected"]["racist"])


def test_segment_message_says_when_frames_are_missing():
    seg = {"start": 0.0, "end": 10.0, "speech": "", "on_screen_text": ""}
    assert "NOT provided" in format_segment(seg, with_frames=False)
    assert "frames of the segment follow" in format_segment(seg, with_frames=True)
