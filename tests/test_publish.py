import json

from harmwatch import publish


def row(**overrides):
    data = dict(id=7, group_key="g-1", url="https://t.me/chan/1", source="telegram", route="priority_review",
                priority="high", category="threat_incitement", summary="Threat against a group.",
                sexual_violence=None, sexual_harassment=None, created_at="2026-09-27T10:00:00+00:00",
                full_result_json=json.dumps({"confidence": "high"}))
    return data | overrides


def test_payload():
    p = publish.to_detection(row())
    assert p["external_id"] == "s7" and p["group_key"] == "g-1" and p["priority"] == "high"
    assert p["confidence"] == 0.9 and p["source"] == "SCRAP"
    assert p["context"] == "Priority review (threat_incitement). Threat against a group."


def test_local_judge_probability_is_used_when_available():
    assert publish.to_detection(row(full_result_json=json.dumps({"p_sexual": 0.8731})))["confidence"] == 0.873


def test_community_sightings_are_public_reports():
    assert publish.to_detection(row(source="telegram_bot"))["source"] == "PUBLIC"


def test_explicit_media_warns_the_reviewer():
    p = publish.to_detection(row(route="explicit_alert", priority="urgent", summary=None, category=None))
    assert "Do not open the link without precautions" in p["context"]


def test_sightings_without_web_link_are_skipped():
    assert publish.to_detection(row(url=None)) is None
