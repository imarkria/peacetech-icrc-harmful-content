from datetime import datetime, timedelta, timezone

from app import main
from app.database import SessionLocal
from app.intake import RateLimiter, normalize_url
from app.models import DetectedLink

from .conftest import TOKEN, login


def queue_ids(client, status="PENDING"):
    return [i["id"] for i in client.get(f"/api/reviews/queue?status={status}&page_size=100").json()["items"]]


def detection(external_id, url, group_key=None, priority="standard"):
    return {"external_id": external_id, "group_key": group_key, "url": url, "predicted_category": "sexual_violence",
            "confidence": 0.8, "priority": priority, "context": "Threat against a group."}


def test_normalize_url_groups_copies_of_the_same_post():
    assert normalize_url("https://www.Facebook.com/page/posts/1/?fbclid=x&utm_source=y#top") == \
        normalize_url("http://m.facebook.com/page/posts/1")
    assert normalize_url("https://twitter.com/a/status/1?s=20") == normalize_url("https://x.com/a/status/1")
    assert normalize_url("https://example.org/p?id=1") != normalize_url("https://example.org/p?id=2")


def test_community_report_waits_for_screening_then_joins_the_queue(client):
    r = client.post("/api/reports", json={"url": "https://t.me/chan/101", "category": "other", "reason": "threats"})
    assert r.status_code == 201
    link_id = "public-" + str(r.json()["id"])

    login(client, "reviewer@icrc.org")
    assert link_id not in queue_ids(client)
    assert client.get(f"/api/reviews/{link_id}").status_code == 404

    waiting = client.get("/api/intake/screening", headers=TOKEN).json()
    assert link_id in [i["id"] for i in waiting]
    r = client.post(f"/api/intake/screening/{link_id}", headers=TOKEN,
                    json={"outcome": "flagged", "priority": "high", "confidence": 0.9, "summary": "Threat."})
    assert r.json()["status"] == "PENDING"
    item = client.get(f"/api/reviews/{link_id}").json()
    assert item["priority"] == "high" and "Model screening: Threat." in item["context"]


def test_reports_of_the_same_post_are_one_item(client):
    first = client.post("/api/reports", json={"url": "https://t.me/chan/202?utm_source=a", "category": "other"}).json()
    client.post("/api/reports", json={"url": "https://t.me/chan/202/", "category": "other"})
    with SessionLocal() as db:
        link = db.get(DetectedLink, f"public-{first['id']}")
        assert link.occurrence_count == 2


def test_detections_group_by_content_and_are_idempotent(reviewer):
    a = reviewer.post("/api/detections", headers=TOKEN, json=detection("s1", "https://x.com/a/status/1", "g-abc"))
    b = reviewer.post("/api/detections", headers=TOKEN, json=detection("s2", "https://instagram.com/p/XYZ", "g-abc", "urgent"))
    again = reviewer.post("/api/detections", headers=TOKEN, json=detection("s2", "https://instagram.com/p/XYZ", "g-abc"))
    assert (a.status_code, b.status_code, again.status_code) == (201, 200, 200)
    item = reviewer.get(f"/api/reviews/{a.json()['id']}").json()
    assert item["occurrence_count"] == 2 and item["priority"] == "urgent"
    assert {o["platform"] for o in item["occurrences"]} == {"X", "Instagram"}
    assert queue_ids(reviewer)[0] == a.json()["id"]  # urgent first


def test_wrong_ingest_token_is_refused(client):
    r = client.post("/api/detections", headers={"X-Ingest-Token": "nope"}, json=detection("s9", "https://x.com/b/status/9"))
    assert r.status_code == 401


def test_a_copy_of_reviewed_content_inherits_the_decision(reviewer):
    link = reviewer.post("/api/detections", headers=TOKEN, json=detection("s3", "https://t.me/c/3", "g-rev")).json()
    reviewer.post(f"/api/reviews/{link['id']}", json={"sexual_violence": True, "harmful_information": True})
    reviewer.post("/api/detections", headers=TOKEN, json=detection("s4", "https://t.me/other/8", "g-rev"))
    item = reviewer.get(f"/api/reviews/{link['id']}").json()
    assert item["status"] == "REVIEWED" and item["occurrence_count"] == 2
    assert link["id"] not in queue_ids(reviewer)


def test_restricted_screening_hides_the_report_and_its_note(client):
    r = client.post("/api/reports", json={"url": "https://t.me/chan/303", "category": "other", "reason": "details"})
    link_id = f"public-{r.json()['id']}"
    client.post(f"/api/intake/screening/{link_id}", headers=TOKEN, json={"outcome": "restricted"})
    client.post("/api/reports", json={"url": "https://t.me/chan/303", "category": "other", "reason": "more details"})
    login(client, "reviewer@icrc.org")
    assert client.get(f"/api/reviews/{link_id}").status_code == 404
    with SessionLocal() as db:
        link = db.get(DetectedLink, link_id)
        assert link.status == "RESTRICTED" and all(o.note is None for o in link.occurrences)
    client.cookies.clear()


def test_screening_merges_a_report_into_the_same_content(reviewer):
    detected = reviewer.post("/api/detections", headers=TOKEN, json=detection("s5", "https://x.com/c/status/5", "g-merge")).json()
    report = reviewer.post("/api/reports", json={"url": "https://facebook.com/share/p/77", "category": "other"}).json()
    r = reviewer.post(f"/api/intake/screening/public-{report['id']}", headers=TOKEN,
                      json={"outcome": "flagged", "group_key": "g-merge"})
    assert r.json() == {"status": "merged", "link_id": detected["id"]}
    assert reviewer.get(f"/api/reviews/{detected['id']}").json()["occurrence_count"] == 2


def test_volunteer_lane(client):
    body = {"url": "https://tiktok.com/@a/video/1", "category": "sexual_violence", "harm_types": ["threat_incitement"],
            "urgency": "urgent", "context": "Seen in three local groups this morning."}
    client.cookies.clear()
    assert client.post("/api/volunteer/reports", json=body).status_code == 401
    login(client, "reviewer@icrc.org")
    assert client.post("/api/volunteer/reports", json=body).status_code == 403

    assert login(client, "volunteer@icrc.org")["role"] == "VOLUNTEER"
    assert client.get("/api/reviews/queue").status_code == 403
    r = client.post("/api/volunteer/reports", json=body)
    assert r.status_code == 201 and r.json()["duplicate"] is False

    login(client, "reviewer@icrc.org")
    item = client.get(f"/api/reviews/{r.json()['link_id']}").json()
    assert item["source"] == "VOLUNTEER" and item["priority"] == "urgent"
    client.cookies.clear()


def test_unscreened_reports_are_released_after_the_timeout(client):
    r = client.post("/api/reports", json={"url": "https://t.me/chan/404", "category": "other"})
    link_id = f"public-{r.json()['id']}"
    with SessionLocal() as db:
        link = db.get(DetectedLink, link_id)
        link.detected_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()
    login(client, "reviewer@icrc.org")
    assert link_id in queue_ids(client)
    assert "Not screened" in client.get(f"/api/reviews/{link_id}").json()["context"]
    client.cookies.clear()


def test_community_reports_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main, "report_limiter", RateLimiter(1, 600))
    assert client.post("/api/reports", json={"url": "https://t.me/chan/501", "category": "other"}).status_code == 201
    assert client.post("/api/reports", json={"url": "https://t.me/chan/502", "category": "other"}).status_code == 429
