# SignalSafe — PeaceTech Hackathon, ICRC Challenge

**Challenge:** How can we identify harmful content related to sexual violence?

Challenge given by the International Committee of the Red Cross (ICRC) for the PeaceTech Hackathon.

SignalSafe finds and collects links to harmful content related to conflict-related sexual violence, and gives ICRC reviewers a safe place to label them. `harmwatch` is the name of its detection package.

## Team

- Ismaël Markria — platform skeleton, integration
- SheEagle — web app, backend, browser extension
- gmikou — detection pipeline, policy layers, evaluation

## Architecture

```
 PLATFORM                                                DETECTION  (harmwatch)

 Public user ── web form (/report) ──┐                   Telegram channels ── collector ──┐
 Browser extension ──────────────────┤                   Volunteers ── Telegram bot ──────┤
                                     ▼                                                    ▼
 frontend/  Next.js ◄──── REST ────► backend/  FastAPI   harmwatch/  classifier ──► data/harmwatch.db
            reviewer queue,          PostgreSQL | SQLite     (Claude, local Qwen3.5-9B or keywords)
            review form, analysis          ▲                 applies policy/ (layered, per region)
                                           │                                              │
                                           └──── POST /api/detections ◄── harmwatch.publish
```

- **Platform** (`frontend/`, `backend/`): the public report flow, the ICRC reviewer workspace and the analysis dashboard. Reviewers see links and context, never media.
- **Detection** (`harmwatch/`, `policy/`, `scripts/`): collects posts and classifies them against the policy. This part also holds the evaluation work on text, images, memes and video.

| Path | Role |
|---|---|
| `frontend/` | Next.js app: public report (`/report`), reviewer sign-in, queue and review form (`/review`), analysis (`/analysis`). The Chrome/Edge extension is in `frontend/browser-extension/`. See [frontend/README.md](frontend/README.md). |
| `backend/` | FastAPI service: auth, public reports, review queue, decisions, analysis. See [backend/README.md](backend/README.md). |
| `policy/` | The layered policy the local model applies: universal core, children rules, modalities, platform and region profiles. See [policy/README.md](policy/README.md). |
| `policy.md` | The short v0 policy, still used by the Claude and keyword backends. |
| `harmwatch/classify.py` | Backend switch: `claude`, `local` (llama-server + `policy/`), `keywords` |
| `harmwatch/crsv.py`, `schema.py` | Text assessment with the local model; the hard rules of `policy/core.md` applied in code |
| `harmwatch/policy_loader.py`, `lexicon.py` | Build the prompt from the policy layers; deterministic age-indicator and term checks |
| `harmwatch/vision.py`, `sv_scores.py`, `safety.py`, `cascade.py` | Image and meme judging, explicit-image quarantine, fast student → judge cascade |
| `harmwatch/video_segments.py` | Video judged segment by segment (tested on the separate racism topic layer) |
| `harmwatch/triage.py` | Turns labels into Escalate / Harmful / Potentially harmful / Not harmful, plus a priority score |
| `harmwatch/db.py` | SQLite storage for the detection side, in `data/` (git-ignored) |
| `harmwatch/collector.py`, `bot.py` | Telegram channel reader (text only) and volunteer bot |
| `harmwatch/publish.py` | Sends Harmful and Potentially harmful posts to the backend's review queue |
| `scripts/` | Data preparation, region approval, benchmarks and evaluation, figures |
| `tests/` | Tests for the policy rules, safety filters, cascade and video segments |
| `docs/` | Results ([images](docs/FINAL_IMAGES.md), [cascade](docs/RESULTS_CASCADE.md)), frozen prompts, metrics, presentation pack |
| `samples/sample_posts.json` | 20 synthetic, non-graphic posts with expected labels |
| `DATASETS.md` | Candidate public datasets |
| `TODO_SECURITE.md` | Open safety decisions (age indicators, explicit-image filter, childlike appearance), in French |

## Run the platform

Backend, from `backend/`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend, from `frontend/` in another terminal:

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Reviewer demo account: `reviewer@icrc.org` / `reviewer`. The API docs are at http://localhost:8000/docs.

Before running it anywhere other than your machine, see [Deploying outside localhost](backend/README.md#deploying-outside-localhost).

## Run the detection pipeline

From the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m harmwatch.seed      # load and classify the sample posts
pytest                        # tests
```

Pick the classifier with `CLASSIFIER` in `.env`:

- `keywords`: offline baseline, no setup. `auto` falls back to it when no API key is set.
- `claude`: needs `ANTHROPIC_API_KEY`. Applies `policy.md`.
- `local`: needs a llama-server running Qwen3.5-9B (`scripts/serve_llm.sh`, written for one V100 32 GB). Applies `policy/` for `REGION` and `PLATFORM`.

### Send detections to the review queue

Generate a token and put the same value in `backend/.env` (`INGEST_TOKEN`) and in the root `.env` (`SIGNALSAFE_INGEST_TOKEN`). Restart the backend after you change `backend/.env`.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```bash
python -m harmwatch.seed        # classify the sample posts
python -m harmwatch.publish     # send the flagged ones to the queue
```

The collector and the bot send new flagged posts on their own when the token is set. Only the neutral summary and the labels are sent, never the post text. Posts flagged as possibly involving a minor (Escalate) are never sent: the platform has no restricted handling for them yet.

Local databases seeded before this change still have `sample://` links, which the backend rejects. Delete `data/harmwatch.db` and seed again.

### Other commands

```bash
python -m harmwatch.evaluate                # precision/recall, false flags on safe posts, parity by side
python -m harmwatch.collector --limit 100   # needs TELEGRAM_API_ID/HASH + TELEGRAM_CHANNELS
python -m harmwatch.bot                     # needs TELEGRAM_BOT_TOKEN
python scripts/check_policy_ids.py          # every policy ID is defined, nothing cites an unknown one
python scripts/approve_region.py ru_ua --list
```

The image, cascade and video scripts download public datasets into `data/` and need a GPU for the judge. The video pipeline has extra dependencies, listed at the top of `harmwatch/video_segments.py`.

## Workflow

- Create a branch for your work: `git checkout -b your-name/feature`
- Open a pull request into `main` when ready.

## Data & ethics

This project deals with sensitive content. Do **not** commit raw datasets, personal data, or harmful media to this repository. Keep data out of git (see `.gitignore`) and share it only through the channels agreed with the ICRC.

Content that may involve a minor and a sexual element is never shown, described or exported. The detection pipeline routes it to `restricted_escalation`, leaves it out of exports and never sends it to the review queue.
