import pytest

from harmwatch import dedup, detect, publish
from harmwatch.intake import Post, ingest

THREAT = "When we get to their villages, their women will learn what it means to resist us."


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("HARMWATCH_DB", str(tmp_path / "hw.db"))
    monkeypatch.setenv("CLASSIFIER", "keywords")
    return tmp_path / "hw.db"


def test_copies_are_judged_once_and_published_as_one_group(db, monkeypatch):
    calls = []
    real = detect.detect_post
    monkeypatch.setattr(detect, "detect_post", lambda *a, **k: calls.append(1) or real(*a, **k))

    first = ingest(Post("telegram", THREAT, "https://t.me/a/1", "a/1"), source="telegram")
    copy = ingest(Post("x", THREAT + " 🔥", "https://x.com/b/status/2", "2"), source="apify:x")
    again = ingest(Post("telegram", THREAT, "https://t.me/a/1", "a/1"), source="telegram")

    assert len(calls) == 1
    assert first.group_key == copy.group_key and copy.duplicate and not first.duplicate
    assert again.new is False and again.sighting_id == first.sighting_id
    assert first.detection["route"] == "priority_review"

    conn = dedup.connect(db)
    rows = dedup.unpublished(conn, publish.PUBLISH_ROUTES)
    assert [r["url"] for r in rows] == ["https://t.me/a/1", "https://x.com/b/status/2"]
    payloads = [publish.to_detection(r) for r in rows]
    assert {p["group_key"] for p in payloads} == {first.group_key}
    assert THREAT not in payloads[0]["context"]  # never the post text


def test_harmless_posts_are_not_published(db):
    ingest(Post("telegram", "Community meeting about the new water well on Saturday at noon.", "https://t.me/a/3", "a/3"),
           source="telegram")
    assert dedup.unpublished(dedup.connect(db), publish.PUBLISH_ROUTES) == []


def test_restricted_groups_are_never_published(db):
    result = ingest(Post("telegram", "Those children deserved it, well done.", "https://t.me/a/4", "a/4"),
                    source="telegram")
    assert result.detection["restricted"] == 1 and result.detection["summary"] is None
    assert dedup.unpublished(dedup.connect(db), publish.PUBLISH_ROUTES) == []


def test_media_is_only_downloaded_for_the_local_judge(db):
    def fail(*args):
        raise AssertionError("no download without the local judge")

    ingest(Post("x", THREAT, "https://x.com/c/status/5", "5", media_urls=[("image", "https://pbs.twimg.com/a.jpg")]),
           source="apify:x", download=fail)
