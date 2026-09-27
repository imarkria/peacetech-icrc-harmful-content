# SignalSafe backend

FastAPI MVP service for the SignalSafe harmful-content reporting and review workflow.

## Run locally

From this directory:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

The default development database is SQLite at `backend/data/local.db`. The same app uses PostgreSQL when `DATABASE_URL` is set to a PostgreSQL connection string.

Open the interactive API documentation at http://localhost:8000/docs.

Demo reviewer:

```text
reviewer@icrc.org / reviewer
```

## MVP API

| Method | Route | Auth |
| --- | --- | --- |
| GET | `/api/health` | Public |
| POST | `/api/auth/login` | Public |
| POST | `/api/auth/logout` | Reviewer |
| GET | `/api/me` | Reviewer |
| POST | `/api/reports` | Public |
| GET | `/api/reviews/queue` | Reviewer |
| GET | `/api/reviews/{id}` | Reviewer |
| POST | `/api/reviews/{id}` | Reviewer |

Public reports are stored in `public_reports` and never enter the reviewer queue. Seeded detected links simulate the crawler/model output until that integration is added.

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL on port `5432` and the API on port `8000`.
