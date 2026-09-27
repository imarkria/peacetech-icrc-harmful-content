# SignalSafe frontend

Next.js (App Router, TypeScript) app for public reporting and ICRC review. It talks to the FastAPI service in `../backend` through `lib/api.ts`.

| Route | Who | What |
| --- | --- | --- |
| `/` → `/report` → `/report/success` | Public, no account | Submit a link and an optional reason (reviewers set the category). Returns a reference such as `SS-000012`. |
| `/reviewer/login` (`/login` redirects) | ICRC reviewer | Sign in. The session is an HTTP-only cookie set by the backend. |
| `/review` | Reviewer | Queue of detected and publicly reported links, with status filter and search |
| `/review/:id` | Reviewer | Review form: decision plus structured evidence (sexual elements, forms, harm types, pathways) |
| `/analysis` | Reviewer | Charts over reviewed items: by source, decision, platform, evidence, over time |

Demo reviewer: `reviewer@icrc.org` / `reviewer` (seeded by the backend). The sign-in page shows it unless `NEXT_PUBLIC_SHOW_DEMO_LOGIN=false`.

The header asks `GET /api/me` on each navigation to know whether a reviewer is signed in. Reviewer pages redirect to sign-in when the API answers 401.

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
