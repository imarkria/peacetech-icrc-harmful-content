from harmwatch import db, publish
from harmwatch.schema import Classification
from harmwatch.triage import ESCALATE, HARMFUL, NOT_HARMFUL, POTENTIAL


def _classification(**overrides) -> Classification:
    data = dict(harm_types=["threat_incitement"], tone="serious", claim_status="no_claim", victims=["group"],
                harm_potential=3, confidence="high", summary="Threat against a group.", rationale="Future tense.")
    return Classification(**(data | overrides))


def _item(**overrides) -> dict:
    data = dict(id=7, url="https://t.me/chan/1", source="telegram", bucket=HARMFUL,
                classified_at="2026-09-27T10:00:00+00:00", result=_classification(), text="raw post text")
    return data | overrides


def test_payload_carries_summary_not_post_text():
    payload = publish.to_detection(_item())
    assert payload["external_id"] == "7"
    assert payload["predicted_category"] == "sexual_violence"
    assert payload["confidence"] == 0.9
    assert payload["source"] == "SCRAP"
    assert "Threat against a group." in payload["context"]
    assert "raw post text" not in payload["context"]


def test_volunteer_posts_are_public_reports():
    assert publish.to_detection(_item(source="volunteer"))["source"] == "PUBLIC"


def test_posts_without_web_link_are_skipped():
    assert publish.to_detection(_item(url=None)) is None
    assert publish.to_detection(_item(url="sample://s01")) is None


def test_escalated_and_not_harmful_posts_are_never_published(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "hw.db")
    conn = db.connect()
    for n, bucket in enumerate([HARMFUL, POTENTIAL, ESCALATE, NOT_HARMFUL]):
        post_id = db.add_post(conn, source="telegram", text=f"post {n}", channel="c", url=f"https://t.me/c/{n}")
        db.save_classification(conn, post_id, "keywords", _classification(), bucket, 1.0)
    assert {i["bucket"] for i in db.unpublished(conn, publish.PUBLISHED_BUCKETS)} == {HARMFUL, POTENTIAL}

    first = db.unpublished(conn, publish.PUBLISHED_BUCKETS)[0]
    db.mark_published(conn, first["id"], "hw-1")
    assert len(db.unpublished(conn, publish.PUBLISHED_BUCKETS)) == 1
