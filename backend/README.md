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
| POST | `/api/detections` | `X-Ingest-Token` header |

Login sets an HTTP-only `access_token` cookie (JWT signed with `JWT_SECRET`).

## Where queue items come from

Every item in the queue is a `detected_links` row with a `source`:

- `PUBLIC`: a report sent through `POST /api/reports` (web form or browser extension). The report is also kept in `public_reports`.
- `SCRAP`: a link found by detection, sent by `python -m harmwatch.publish` to `POST /api/detections` (ids `hw-<post id>`), plus the demo links seeded by `app/seed.py`. Posts forwarded by volunteers through the Telegram bot arrive as `PUBLIC`.

`POST /api/detections` needs `INGEST_TOKEN` in `.env`. It is disabled while the token is empty. Sending the same post twice changes nothing.

A link can be reviewed once. The decision and the structured evidence are stored in `reviews` and feed `/api/analysis/summary`.

## Reviewer accounts

```bash
python -m app.create_reviewer analyst@icrc.org      # asks for the password; run it again to reset it
```

## Deploying outside localhost

Set `ENVIRONMENT` to anything other than `development` (for example `production`). The API then refuses to start unless:

- `JWT_SECRET` is a random value of at least 32 characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `COOKIE_SECURE=true`, so the API is served over HTTPS
- `SEED_DEMO_DATA=false`, or `DEMO_REVIEWER_PASSWORD` is changed
- `INGEST_TOKEN`, if set, is at least 32 characters

Create real reviewer accounts with `app.create_reviewer`. In the frontend, set `NEXT_PUBLIC_SHOW_DEMO_LOGIN=false` to hide the demo credentials.

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL on port `5432` and the API on port `8000`.
