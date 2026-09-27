import os
import tempfile

import pytest

# Settings and the engine are read at import time: configure them before importing the app.
_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    INGEST_TOKEN="test-ingest-token-0123456789abcdef",
    REPORT_RATE_LIMIT="1000/60",
    SEED_DEMO_DATA="true",
    ENVIRONMENT="development",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TOKEN = {"X-Ingest-Token": os.environ["INGEST_TOKEN"]}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email):
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"email": email, "password": "reviewer"})
    assert r.status_code == 200, r.text
    return r.json()["user"]


@pytest.fixture
def reviewer(client):
    login(client, "reviewer@icrc.org")
    yield client
    client.cookies.clear()


@pytest.fixture
def volunteer(client):
    login(client, "volunteer@icrc.org")
    yield client
    client.cookies.clear()
