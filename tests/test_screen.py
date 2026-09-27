import pytest

from harmwatch import dedup, publish, screen
from harmwatch.intake import Post

THREAT = "When we get to their villages, their women will learn what it means to resist us."


@pytest.fixture
def backend(tmp_path, monkeypatch):
    monkeypatch.setenv("HARMWATCH_DB", str(tmp_path / "hw.db"))
    monkeypatch.setenv("CLASSIFIER", "keywords")
    sent = {}
    waiting = [{"id": "public-1", "url": "https://t.me/a/1"}, {"id": "public-2", "url": "https://example.org/x"},
               {"id": "public-3", "url": "https://t.me/a/3"}]

    def post_json(path, payload=None, method="POST"):
        if method == "GET":
            return waiting
        sent[path.rsplit("/", 1)[1]] = payload

    monkeypatch.setattr(publish, "post_json", post_json)
    return sent


def test_community_reports_get_a_model_outcome(backend, tmp_path):
    posts = {"https://t.me/a/1": Post("telegram", THREAT, "https://t.me/a/1", "a/1"),
             "https://t.me/a/3": Post("telegram", "Weather is sunny in the valley today, markets open at nine as usual.",
                                      "https://t.me/a/3", "a/3")}
    stats = screen.screen_pending(fetch=posts.get)
    assert stats == {"flagged": 1, "unavailable": 1, "not_flagged": 1}
    assert backend["public-1"]["priority"] == "high" and backend["public-1"]["group_key"].startswith("g-")
    assert backend["public-2"] == {"outcome": "unavailable"}
    assert backend["public-3"]["outcome"] == "not_flagged"
    # the report already carries these sightings: publish.py must not send them a second time
    assert dedup.unpublished(dedup.connect(tmp_path / "hw.db"), publish.PUBLISH_ROUTES) == []
