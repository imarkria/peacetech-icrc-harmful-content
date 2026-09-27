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

Demo accounts (created when `SEED_DEMO_DATA=true`, password `DEMO_PASSWORD`):

```text
reviewer@icrc.org  / reviewer     ICRC reviewer: queue, decisions, analysis
volunteer@icrc.org / reviewer     trained volunteer: structured reports only
```

Tests:

```bash
pip install -r requirements-dev.txt
pytest
```

## MVP API

| Method | Route | Auth |
| --- | --- | --- |
| GET | `/api/health` | Public |
| POST | `/api/auth/login` | Public |
| POST | `/api/auth/logout` | Signed in |
| GET | `/api/me` | Signed in |
| POST | `/api/reports` | Public, rate-limited per IP |
| POST | `/api/volunteer/reports` | Trained volunteer |
| POST | `/api/detections` | `X-Ingest-Token` header |
| GET | `/api/intake/screening` | `X-Ingest-Token` header |
| POST | `/api/intake/screening/{id}` | `X-Ingest-Token` header |
| GET | `/api/reviews/queue` | Reviewer |
| GET | `/api/reviews/{id}` | Reviewer |
| POST | `/api/reviews/{id}` | Reviewer |
| GET | `/api/analysis/summary` | Reviewer |

Login sets an HTTP-only `access_token` cookie (JWT signed with `JWT_SECRET`).

## Three lanes into one queue

Every queue item is a `detected_links` row with a `source` (lane) and a `priority` (`urgent`, `high`, `standard`, `none`):

| Source | Lane | Enters through | Status on arrival |
| --- | --- | --- | --- |
| `SCRAP` | Detection by harmwatch (Apify, Telegram collector) | `POST /api/detections` | `PENDING`, priority from the model |
| `PUBLIC` | Broader local community, anonymous (web form, extension, Telegram bot) | `POST /api/reports`, or harmwatch for the bot | `SCREENING` while `INGEST_TOKEN` is set, else `PENDING` |
| `VOLUNTEER` | Trained volunteers with an account | `POST /api/volunteer/reports` | `PENDING`, `high` or `urgent` |

Community reports in `SCREENING` wait for `python -m harmwatch.screen`, which fetches the post, judges it and answers with an outcome: `flagged` (queue, model priority), `not_flagged` (queue, priority `none`: human reports are never dropped), `unavailable` (queue, marked "not screened") or `restricted` (`RESTRICTED`: never listed or shown, notes erased). A report still waiting after `SCREENING_TIMEOUT_MINUTES` reaches the queue unscreened. A volunteer report of the same content ends the wait.

The queue lists `PENDING` items with the most urgent first, then the most copies, then the newest.

## Duplicates

Copies of the same content are one item with several `occurrences` (URL, platform, lane, note, date), reviewed once:

- harmwatch sends a `group_key` built from content fingerprints (same or nearly the same text, image or video), so a post and its reposts on other platforms share an item;
- reports of the same URL share an item: URLs are normalised (host aliases like twitter.com → x.com, no `www.`/`m.`, no tracking parameters such as `utm_*` or `fbclid`);
- a screened community report whose content is already queued is merged into that item.

Each copy can raise the item's priority. A copy of content already reviewed is attached to it and inherits the decision. Sending the same `external_id` twice to `POST /api/detections` changes nothing.

`POST /api/detections` and screening need `INGEST_TOKEN` in `.env`; they are disabled while it is empty.

## Reviews

A reviewer answers two core questions. The backend derives the final `decision`: `YES` only when both answers are true, otherwise `NO`.

```json
{
  "sexual_violence": true,
  "harmful_information": true,
  "evidence": {
    "basicTags": ["BT-SEXUAL-VIOLENCE", "BT-FORCED-SEXUAL-ACTION"],
    "targetedEthnicity": "",
    "targetedEthnicity2": "",
    "sexualElements": [],
    "coerciveCircumstances": [],
    "sexualForms": [],
    "harmfulTypes": [],
    "harmPathways": []
  }
}
```

Basic tags (`BT-MEN`, `BT-WOMEN`, `BT-CHILDREN`, `BT-SEXUAL-VIOLENCE`, `BT-FORCED-SEXUAL-ACTION`, plus two open "targeted ethnicity" fields) are charted over time by `/api/analysis/summary`. The advanced fields are optional.

## Database model

| Table | Holds |
| --- | --- |
| `users` | Accounts: `email`, `password_hash`, `role` (`REVIEWER` or `VOLUNTEER`; earlier `SPECIALIST` accounts are migrated to `VOLUNTEER` on startup) |
| `public_reports` | Every community report: `url`, `category`, `reason`, `source` |
| `detected_links` | One queue item per content group: `url`, `platform`, `predicted_category`, `confidence`, `source` (lane), `status` (`PENDING`, `REVIEWED`, `SCREENING`, `RESTRICTED`), `priority`, `group_key`, `normalized_url`, `occurrence_count`, `context` |
| `occurrences` | Every copy or report of an item: `url`, `platform`, `source`, `note`, `reporter_id` (trained volunteer), `external_id` (harmwatch sighting), `seen_at` |
| `reviews` | One per item: `decision` (`YES`/`NO`), `sexual_violence`, `harmful_information`, `evidence` (tags), `reviewer_id` |

## Accounts

```bash
python -m app.create_account analyst@icrc.org                      # reviewer; asks for the password
python -m app.create_account someone@example.org --role volunteer  # trained volunteer
```

Run it again to reset a password or change a role.

## Deploying outside localhost

Set `ENVIRONMENT` to anything other than `development` (for example `production`). The API then refuses to start unless:

- `JWT_SECRET` is a random value of at least 32 characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `COOKIE_SECURE=true`, so the API is served over HTTPS
- `SEED_DEMO_DATA=false`, or `DEMO_PASSWORD` is changed
- `INGEST_TOKEN`, if set, is at least 32 characters

Create real accounts with `app.create_account`. The community rate limit (`REPORT_RATE_LIMIT`) is kept in memory per API process: behind several workers or a proxy, put a shared limit in front. In the frontend, set `NEXT_PUBLIC_SHOW_DEMO_LOGIN=false` to hide the demo credentials.

## Docker

```bash
docker compose up --build
```

This starts PostgreSQL on port `5432` and the API on port `8000`.
