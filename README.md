# SignalSafe

SignalSafe is a web platform for reporting, reviewing, and analysing harmful content related to sexual violence in armed conflicts.

The platform separates the public reporting experience from the authenticated reviewer workspace. Public users can submit a link without an account. ICRC specialists can submit links after signing in, and their submissions go directly to the review queue. Reviewers assess links detected by the crawler/model as well as links submitted by specialists and public users that pass the mock AI potential-harm gate.

## Product workflows

### Public user

Public users do not need an account.

1. Open the landing page.
2. Open **Report a link**.
3. Enter a URL and explain why the content may be harmful.
4. Submit the report.
5. The report is always stored in `public_reports`.
6. The mock AI gate decides whether the report is potentially harmful. Only a positive result is added to the reviewer queue.

Public submissions are not visible in the reviewer queue when the mock AI result is negative. They remain available as future research and training data.

### ICRC specialist

Specialists use the same staff sign-in page as reviewers, but have a different role and permission set.

1. Open **Staff sign in**.
2. Sign in with a specialist account.
3. Submit a link using the specialist report form.
4. The submission is stored and added directly to the reviewer queue.

Specialists cannot access the reviewer queue or analysis dashboard.

### ICRC reviewer

Reviewers use the shared staff sign-in page and are redirected to the reviewer workspace.

1. Open the pending review queue.
2. Open a link for review.
3. Answer the two core questions:
   - Is the content sexual in nature?
   - Are coercive circumstances present or indicated?
4. Add basic tags. Basic tags are stored with the review.
5. Optionally add advanced tags.
6. Save the review.

The final decision is derived from the two core questions: it is `YES` only when both answers are `YES`; otherwise it is `NO`. The final decision is stored for analysis, but is not displayed as a separate editable field in the review form.

## Review tags

### Basic tags

Basic tags are available directly in the review form:

1. Men
2. Women
3. Children
4. Sexual violence
5. Forced sexual action
6. Targeted ethnicity 1 (open text)
7. Targeted ethnicity 2 (open text)

### Advanced tags

Advanced tags are optional and are selected from dropdown controls. They are saved together with the review evidence and can be extended as the policy taxonomy evolves.

## Roles and permissions

| Role | Authentication | Submit report | Reviewer queue | Review items | Analysis |
| --- | --- | --- | --- | --- | --- |
| Public user | Not required | Yes; AI gate applies | No | No | No |
| ICRC specialist | Required | Yes; direct queue entry | No | No | No |
| ICRC reviewer | Required | No | Yes | Yes | Yes |

All staff roles use the same login route: `/login`. The application redirects the user according to the role returned by the API:

- `REVIEWER` → `/reviewer`
- `SPECIALIST` → `/specialist/report`

## Technology stack

- Frontend: Next.js 14, React, TypeScript, Tailwind CSS, Recharts
- Backend: FastAPI, SQLAlchemy, Pydantic, JWT authentication
- Database: SQLite for local development, PostgreSQL for Docker/deployment
- Browser extension: Manifest V3 extension under `frontend/browser-extension`
- Containerisation: Docker Compose for the backend and PostgreSQL

The frontend can be started directly with `npm run dev`. Docker is provided for the backend and database environment.

## Repository structure

```text
.
├── frontend/
│   ├── app/                  Next.js routes and pages
│   ├── components/           Shared UI components and app shell
│   ├── lib/                  API client, auth state, review data and types
│   └── browser-extension/    Manifest V3 browser extension
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI routes and application logic
│   │   ├── database.py        SQLAlchemy engine, models and local migrations
│   │   ├── models.py          Database models
│   │   ├── schemas.py         Request and response schemas
│   │   ├── auth.py            Password hashing and JWT helpers
│   │   └── config.py          Environment configuration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
└── README.md
```

## Database model

The MVP uses four main tables.

### `users`

Stores authenticated staff accounts.

- `email`
- `password_hash`
- `role`: `REVIEWER` or `SPECIALIST`
- `created_at`

### `public_reports`

Stores every public report, regardless of the mock AI result.

- `url`
- `reason`
- `source`: `PUBLIC`
- `ai_potential`: whether the mock AI considered the report potentially harmful
- `created_at`

### `detected_links`

Stores items that are available for reviewer assessment.

- `url`
- `predicted_category`
- `confidence`
- `source`: `SCRAP`, `PUBLIC`, or `SPECIALIST`
- `status`: `PENDING` or `REVIEWED`
- `created_at`

### `reviews`

Stores the reviewer decision and review evidence.

- `detected_link_id`
- `reviewer_id`
- `decision`: `YES` or `NO`
- `sexual_violence`: the first core answer
- `harmful_information`: the second core answer
- `evidence`: JSON containing basic tags and optional advanced tags
- `created_at`

The analysis dashboard reads reviewed items and aggregates their decision and basic-tag data over time.

## API endpoints

The backend exposes the following MVP endpoints.

### Public and specialist submissions

```http
POST /api/reports
```

Public request example:

```json
{
  "url": "https://t.me/example/123",
  "category": "sexual_violence",
  "reason": "The post may contain harmful content related to sexual violence in an armed conflict."
}
```

```http
POST /api/specialist/reports
```

This endpoint requires a specialist session and sends the new item directly to the reviewer queue.

### Authentication

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/me
```

The login response sets an HTTP cookie used by authenticated API requests.

### Reviewer workspace

```http
GET  /api/reviews/queue
GET  /api/reviews/{link_id}
POST /api/reviews/{link_id}
```

Review submission example:

```json
{
  "sexual_violence": true,
  "harmful_information": true,
  "evidence": {
    "basicTags": [
      "BT-SEXUAL-VIOLENCE",
      "BT-FORCED-SEXUAL-ACTION"
    ],
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

The advanced fields inside `evidence` are optional. The final `decision` is calculated by the backend from the two core answers; clients do not submit a separate final-decision field.

### Analysis and health

```http
GET /api/analysis/summary
GET /api/health
```

The analysis response includes review counts, decision distribution, source distribution, basic-tag distribution, and time-series data for the line plot.

## Local development

### Option A: SQLite backend and direct frontend

This is the fastest setup for frontend and API development.

#### 1. Start the backend

PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The local `.env` uses SQLite by default and creates the database at `backend/data/local.db`.

Backend URLs:

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

#### 2. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Frontend URL: <http://localhost:3000>

The default frontend API URL is:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

If the API runs on another host or port, update `frontend/.env.local` and restart the Next.js development server.

### Option B: Docker PostgreSQL backend and direct frontend

Use this setup when you want to test against PostgreSQL.

```powershell
cd backend
docker compose up --build
```

This starts:

- PostgreSQL on port `5432`
- FastAPI on port `8000`

Then start the frontend directly in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Docker Compose uses the database URL configured in `backend/docker-compose.yml`:

```text
postgresql+psycopg://signalsafe:signalsafe@db:5432/signalsafe
```

The backend container seeds development data when `SEED_DEMO_DATA=true`.

To stop the backend and database:

```powershell
cd backend
docker compose down
```

To remove the PostgreSQL volume as well, use this only when local database data can be discarded:

```powershell
docker compose down -v
```

## Local development accounts

When demo seeding is enabled, the backend creates these local-only accounts:

```text
Reviewer:
  Email: reviewer@icrc.org
  Password: reviewer

Specialist:
  Email: specialist@icrc.org
  Password: specialist
```

These credentials are for local development only. Replace the seed accounts and configure a real identity provider before deployment.

## Browser extension

The browser extension lets a user submit the current browser tab without copying the URL manually.

1. Start the backend and frontend.
2. Open Chrome or Edge and navigate to the extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Enable **Developer mode**.
4. Select **Load unpacked**.
5. Choose the `frontend/browser-extension` directory.
6. Open a page, click the extension, review the captured URL, and submit it.

The extension calls the public report endpoint and therefore does not require a login.

## Mock AI gate

The crawler and production ML service are not connected in the MVP. Public reports use a deterministic mock gate in `backend/app/main.py`.

The mock gate checks the submitted URL, reason, and category text for configured harmful-content keywords. A positive result creates a `detected_links` record; a negative result keeps the report only in `public_reports`.

The integration point is the `mock_ai_potential` function. It can later be replaced by a real model service without changing the public submission workflow.

Seeded scraped links use `source=SCRAP`. Specialist submissions use `source=SPECIALIST`, and public submissions that pass the AI gate use `source=PUBLIC`.

## Verification commands

Backend syntax check:

```powershell
cd backend
.venv\Scripts\python.exe -m compileall -q app
```

Frontend type check:

```powershell
cd frontend
npm.cmd exec tsc -- --noEmit
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## Data protection and safety

This platform is intended for sensitive humanitarian information. During development and deployment:

- Do not commit raw harmful media, personal information, or sensitive source material.
- Do not copy or share sensitive content outside authorised systems.
- Use HTTPS and secure cookie settings outside local development.
- Replace the local JWT secret before deployment.
- Replace seeded passwords with managed accounts or an approved identity provider.
- Restrict reviewer and specialist access according to operational need.
- Treat URLs and submitted explanations as untrusted user input.

## Current MVP limitations

The current MVP intentionally keeps the operational model small:

- The AI classifier is mocked.
- The crawler is represented by seeded `SCRAP` records.
- There is no assignment locking or concurrent-review workflow.
- There is no SSO/OIDC integration yet.
- There is no production queue worker or scheduled crawler.
- There is no object storage for media.
- SQLite is suitable for local development only; use PostgreSQL for shared environments.

## Suggested next steps

1. Replace the mock AI gate with the model service API.
2. Connect the Telegram crawler and add an ingestion job.
3. Add OIDC/SSO for staff authentication.
4. Add reviewer assignment and locking if multiple reviewers work concurrently.
5. Add audit logging and retention rules for sensitive reports.
6. Add automated backend and frontend tests for each role and workflow.
