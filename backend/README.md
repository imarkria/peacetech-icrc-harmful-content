# SignalSafe backend

FastAPI MVP service for the SignalSafe harmful-content reporting and review workflow.

## Run locally

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

The default development database is SQLite at `backend/data/local.db`. The same app uses PostgreSQL when `DATABASE_URL` is set to a PostgreSQL connection string. Tables are created on startup.

Open the interactive API documentation at http://localhost:8000/docs.

Demo reviewer (created when `SEED_DEMO_DATA=true`):

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
| GET | `/api/analysis/summary` | Reviewer |

Login sets an HTTP-only `access_token` cookie (JWT signed with `JWT_SECRET`).

## Where queue items come from

Every item in the queue is a `detected_links` row with a `source`:

- `PUBLIC`: a report sent through `POST /api/reports` (web form or browser extension). The report is also kept in `public_reports`.
- `SCRAP`: a link found by detection. For now these are demo links seeded by `app/seed.py`. The `harmwatch` pipeline at the repository root is not connected yet.

A link can be reviewed once. The decision and the structured evidence are stored in `reviews` and feed `/api/analysis/summary`.

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL on port `5432` and the API on port `8000`.
