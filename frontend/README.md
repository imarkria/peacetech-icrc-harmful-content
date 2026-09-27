# PeaceTech Hackathon — ICRC Challenge

**Challenge:** How can we identify harmful content related to sexual violence?

Challenge given by the International Committee of the Red Cross (ICRC) for the PeaceTech Hackathon.

## Team

- _Add names here_

## Getting started

```bash
git clone https://github.com/imarkria/peacetech-icrc-harmful-content.git
cd peacetech-icrc-harmful-content
cd frontend
```

## Frontend MVP

The first working frontend is in the repository root and uses Next.js, TypeScript, and local browser storage as a temporary API mock. It implements the complete demo workflow before the FastAPI service is connected:

- Public user: `/` → `/report` → `/report/success`
- ICRC reviewer: `/login` → `/review` → `/review/:id`
- Reviewer demo account: `reviewer@icrc.org` / `reviewer`

Run it directly on the host:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

The review queue is seeded with safe placeholder metadata in `lib/review-data.ts`. Reviewer decisions are persisted in `localStorage` for the MVP, and public reports are kept separate from the review queue. Replace those helpers with the FastAPI client when the backend is ready.

An optional Docker setup is also available:

```bash
docker compose up --build
```

## Workflow

- Create a branch for your work: `git checkout -b your-name/feature`
- Open a pull request into `main` when ready.

## Data & ethics

This project deals with sensitive content. Do **not** commit raw datasets, personal data, or harmful media to this repository. Keep data out of git (see `.gitignore`) and share it only through the channels agreed with the ICRC.
