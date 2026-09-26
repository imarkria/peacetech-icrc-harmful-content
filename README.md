# PeaceTech Hackathon — ICRC Challenge

**Challenge:** How can we identify harmful content related to sexual violence?

Challenge given by the International Committee of the Red Cross (ICRC) for the PeaceTech Hackathon.

## Team

- _Add names here_

## Getting started

```bash
git clone https://github.com/imarkria/peacetech-icrc-harmful-content.git
cd peacetech-icrc-harmful-content
```

## What's in the skeleton

A working end-to-end prototype, meant to be deepened in parallel:

```
Volunteers ── Telegram bot ──┐                     ┌── Web app (Streamlit) ── ICRC analysts
                             ▼                     │   review queue · blur · Yes/No/Not processed
Telegram channels ── collector ──► SQLite ◄────────┘   tracking · export
                                     │  ▲
                                     ▼  │
                          classifier (Claude + policy.md)
```

| File | Role |
|---|---|
| `policy.md` | The harm definitions the classifier applies. **Edit this first** (task M1). |
| `harmwatch/classify.py` | Claude classifier (structured output) + offline keyword fallback |
| `harmwatch/triage.py` | Rules that turn labels into Escalate / Harmful / Potentially harmful / Not harmful, plus a priority score |
| `harmwatch/db.py` | SQLite storage in `data/` (git-ignored) |
| `app.py` | Web app: landing page → report form (no login) → thank-you page; ICRC sign-in → control board (review queue, tracking, export) |
| `harmwatch/bot.py` | Telegram bot: volunteers forward a post, it joins the queue |
| `harmwatch/collector.py` | Reads public Telegram channels (text + views/forwards only, no media) |
| `harmwatch/evaluate.py` | Scores the classifier on the labelled samples |
| `samples/sample_posts.json` | 20 synthetic, non-graphic posts with expected labels (seed of the evaluation set, task M2) |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY to use Claude; without it the keyword fallback runs
python -m harmwatch.seed      # load and classify the sample posts
streamlit run app.py          # ICRC sign-in: accounts in ICRC_USERS (default reviewer / demo)
```

Other commands:

```bash
python -m harmwatch.evaluate                # precision/recall, false flags on safe posts, parity by side
python -m harmwatch.collector --limit 100   # needs TELEGRAM_API_ID/HASH + TELEGRAM_CHANNELS
python -m harmwatch.bot                     # needs TELEGRAM_BOT_TOKEN
```

## Workflow

- Create a branch for your work: `git checkout -b your-name/feature`
- Open a pull request into `main` when ready.

## Data & ethics

This project deals with sensitive content. Do **not** commit raw datasets, personal data, or harmful media to this repository. Keep data out of git (see `.gitignore`) and share it only through the channels agreed with the ICRC.
