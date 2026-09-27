# SignalSafe frontend

Next.js (App Router, TypeScript) app for public reporting and ICRC review. It talks to the FastAPI service in `../backend` through `lib/api.ts`.

| Route | Who | What |
| --- | --- | --- |
| `/` → `/report` → `/report/success` | Public, no account | Submit a link and an optional reason (reviewers set the category). Returns a reference such as `SS-000012`. |
| `/reviewer/login` (`/login` redirects) | Reviewers and trained volunteers | Sign in, then go to the queue or the volunteer form by role. The session is an HTTP-only cookie set by the backend. |
| `/volunteer/report` | Trained volunteer | Structured report: link, category, harm types, urgency, context. Goes to the priority lane. |
| `/review` | Reviewer | Queue from the three lanes (detection, trained volunteers, community), urgent and most-copied first |
| `/review/:id` | Reviewer | Review form: decision plus structured evidence. Lists every copy of the content; the decision covers them all. |
| `/analysis` | Reviewer | Charts over reviewed items: by source, decision, platform, evidence, over time |

Demo accounts: `reviewer@icrc.org` and `volunteer@icrc.org`, password `reviewer` (seeded by the backend). The sign-in page shows them unless `NEXT_PUBLIC_SHOW_DEMO_LOGIN=false`.

The header asks `GET /api/me` on each navigation to know who is signed in and shows the links for that role. Reviewer pages redirect to sign-in when the API answers 401.

## Run locally

Start the backend first (see `../backend/README.md`), then:

```bash
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL, defaults to http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000.

With Docker:

```bash
docker compose up --build
```

This runs the dev server only. Start the backend separately.

## Browser extension

`browser-extension/` is a Chrome/Edge extension that reports the current tab. It posts to `http://localhost:8000` by default; the address can be changed in the popup. See [browser-extension/README.md](browser-extension/README.md).
