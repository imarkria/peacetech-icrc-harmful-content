# SignalSafe — PeaceTech Hackathon, ICRC Challenge

**Challenge:** How can we identify harmful content related to sexual violence?

Challenge given by the International Committee of the Red Cross (ICRC) for the PeaceTech Hackathon.

SignalSafe finds and collects links to harmful content related to conflict-related sexual violence, and gives ICRC reviewers a safe place to label them. `harmwatch` is the name of its detection package.

> **Detection part (safety filter → fast pre-filter → AI judge → SQLite table `detections`):** start with
> [`docs/platform/README.md`](docs/platform/README.md): pipeline, who does what, quick start, how to read the table.
> The definitions the AI judge applies are in [`policy/README.md`](policy/README.md).

## Team

- Carlos Rafael Gonzalez Soffnee
- Davide Hoxhaj
- Gayet Nino
- Ghita Mikou
- Ismael MARKRIA
- Julius Schmitz
- Théo Goyette
- Xiru Wang

## Architecture

Content reaches ICRC reviewers through three lanes. Every copy of the same content (a repost, the same image on another platform, the same link reported twice) becomes one queue item, reviewed once.

```
 DETECTION LANE                     COMMUNITY LANE (anonymous)          TRAINED VOLUNTEER LANE (accounts)
 Apify: Facebook, Instagram,        web form /report, browser           /volunteer/report: structured
   TikTok, X  (harmwatch.social)    extension, Telegram bot             report, urgency, context
 Telegram channels (collector)      rate-limited                        no model screening
          │                                 │                                     │
          ▼                                 ▼                                     │
 ┌──────── harmwatch.intake ────────────────────────────┐                         │
 │ fingerprint → duplicate group → judge once per group │ ◄── harmwatch.screen    │
 │ (analyze(): safety filter, pre-filter, Qwen judge;   │     fetches and judges  │
 │  or the text classifier without a GPU)               │     community reports   │
 │ media: temp download, deleted after judging          │                         │
 └───────────────┬──────────────────────────────────────┘                         │
                 │ harmwatch.publish (POST /api/detections, group key)            │
                 ▼                                                                ▼
 backend/  FastAPI ─── one item per content group: occurrences, priority, lane ───────
                 │     restricted (possible minor) → never listed
                 ▼
 frontend/ Next.js ─── review queue (urgent first, most copies first), review form, analysis
```

| Lane | Who | How it enters | Before reviewers see it |
|---|---|---|---|
| Detection | `harmwatch.social` (Apify), `harmwatch.collector` (Telegram) | `POST /api/detections` | Judged by the model; only items routed for review are sent |
| Community | Anyone: web form, extension, Telegram bot | `POST /api/reports`, or the bot through intake | Rate-limited, grouped with copies, screened by the model (`harmwatch.screen`); never dropped, only ranked lower |
| Trained volunteer | Volunteers with an account | `POST /api/volunteer/reports` | Nothing: straight to the queue, `high` or `urgent` |

| Path | Role |
|---|---|
| `frontend/` | Next.js app: public report (`/report`), sign-in, reviewer queue and review form (`/review`), analysis (`/analysis`), volunteer report (`/volunteer/report`). The Chrome/Edge extension is in `frontend/browser-extension/`. See [frontend/README.md](frontend/README.md). |
| `backend/` | FastAPI service: accounts, the three lanes, duplicate grouping, screening, review queue, decisions, analysis. See [backend/README.md](backend/README.md). |
| `policy/` | The layered policy the local model applies: universal core, children rules, modalities, platform and region profiles. See [policy/README.md](policy/README.md). |
| `harmwatch/social.py` | Apify collector for Facebook, Instagram, TikTok and X (search, or one post by URL) |
| `harmwatch/collector.py`, `bot.py` | Telegram channel reader (text only), and the anonymous community bot |
| `harmwatch/intake.py`, `dedup.py` | One path for every source: fingerprints, duplicate groups, judge once per group |
| `harmwatch/detect.py` | Picks the judge: `analyze()` with the local model, or the text classifier |
| `harmwatch/analyze.py`, `detections.py` | Safety filter, pre-filter and AI judge for text, images, memes and video; the `detections` table. See [docs/platform/README.md](docs/platform/README.md). |
| `harmwatch/publish.py`, `screen.py` | Send flagged content groups to the queue; screen community reports |
| `harmwatch/classify.py`, `triage.py` | Classifier switch (our Qwen model, or the keyword baseline) and the triage buckets |
| `harmwatch/crsv.py`, `schema.py`, `policy_loader.py`, `lexicon.py` | Full text assessment against `policy/core.md`, prompt assembly, age-indicator checks |
| `harmwatch/vision.py`, `sv_scores.py`, `safety.py`, `cascade.py`, `prefilter.py`, `video_segments.py` | Image, meme and video judging, explicit-image quarantine, trained pre-filter |
| `harmwatch/db.py`, `pipeline.py`, `evaluate.py` | Older text-only tables and the classifier evaluation on the samples |
| `scripts/` | Data preparation, region approval, benchmarks and evaluation, figures |
| `tests/`, `backend/tests/` | Detection tests (policy rules, safety, duplicates, intake, Apify parsing); API tests (lanes, grouping, screening) |
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

Open http://localhost:3000. Demo accounts: `reviewer@icrc.org` and `volunteer@icrc.org`, both with the password `reviewer`. The API docs are at http://localhost:8000/docs.

Before running it anywhere other than your machine, see [Deploying outside localhost](backend/README.md#deploying-outside-localhost).

## Run the detection pipeline

From the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # add requirements-detection.txt for the local judge (GPU)
cp .env.example .env
scripts/serve_llm.sh &                     # our Qwen model, on a GPU (see below)
python -m harmwatch.seed                   # run the sample posts through intake
pytest                                     # tests (no GPU needed)
```

Without a GPU, set `CLASSIFIER=keywords` to try the pipeline end to end with the keyword baseline.

### The classifier

The classifier is our own model, served on our own GPU: nothing is sent to an outside AI service.

- **AI judge:** Qwen3.5-9B (open weights, text and vision) on llama.cpp (`scripts/serve_llm.sh`), instructed with our policy layers (`policy/`) and our annotated examples through the frozen prompt v3, which the code checks at load. It reads text, images, memes and video segments. To use another checkpoint, such as a fine-tuned one, point `MODEL` in `scripts/serve_llm.sh` and `LOCAL_LLM_MODEL` at it.
- **Fast pre-filter:** a small model trained on our data (`models/`, distilled from the judge's labels on our meme pool). It skips the judge for clearly harmless images.
- Measured results and limits: [docs/platform/README.md](docs/platform/README.md#5-measured-performance-and-limits).

`CLASSIFIER` in `.env`:

- `local` (default): the full pipeline above. Only this mode downloads and judges media.
- `keywords`: crude keyword matching on text only, for tests and demos on a machine without a GPU. Not a classifier to rely on.

### Connect to the review queue

Generate a token and put the same value in `backend/.env` (`INGEST_TOKEN`) and in the root `.env` (`SIGNALSAFE_INGEST_TOKEN`). Restart the backend after you change `backend/.env`.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```bash
python -m harmwatch.publish                # send flagged content groups to the queue
python -m harmwatch.screen --every 60      # screen community reports as they arrive
```

With the token set, the collectors and the bot publish on their own. Without it, community reports skip screening and go straight to the queue. Only the neutral summary and the labels are sent, never the post text. Content that may involve a minor is never sent: the platform has no restricted channel yet.

### Collect from social media

```bash
python -m harmwatch.social --query "keyword" --platform facebook instagram tiktok x --max-items 20
python -m harmwatch.collector --limit 100  # Telegram: TELEGRAM_API_ID/HASH + TELEGRAM_CHANNELS
python -m harmwatch.bot                    # community bot: TELEGRAM_BOT_TOKEN
```

`harmwatch.social` needs `APIFY_TOKEN`. Each Apify run costs money, so `--max-items` caps every run, and `--dataset-id` re-reads a finished run for free. Media is downloaded only for the local judge, only from the platform's own servers, and deleted right after judging; the database keeps hashes and URLs.

### Duplicates

Copies are grouped by fingerprints, never by storing the content: the same text (at least 5 words), nearly the same text (SimHash, at least 8 words), the same file, or nearly the same image (perceptual hash). The model judges a group once, and reviewers see one item listing every copy. The backend also groups reports of the same URL. Limits are in `harmwatch/dedup.py`.

### Other commands

```bash
python -m harmwatch.evaluate                # precision/recall on the samples (CLASSIFIER=keywords for the baseline)
python -m harmwatch.analyze text "..."      # one item through the local pipeline
python scripts/check_policy_ids.py          # every policy ID is defined, nothing cites an unknown one
python scripts/approve_region.py ru_ua --list
```

The image, cascade and video scripts download public datasets into `data/` and need a GPU for the judge. The video pipeline has extra dependencies, listed at the top of `harmwatch/video_segments.py`.

## Workflow

- Create a branch for your work: `git checkout -b your-name/feature`
- Open a pull request into `main` when ready.

## Data & ethics

This project deals with sensitive content. Do **not** commit raw datasets, personal data, or harmful media to this repository. Keep data out of git (see `.gitignore`) and share it only through the channels agreed with the ICRC.

Content that may involve a minor and a sexual element is never shown, described or exported. The detection pipeline routes it to `restricted_escalation` and never sends it to the review queue; a community report screened as such is hidden (`RESTRICTED`) and its note erased. A restricted escalation channel is still to be built.
