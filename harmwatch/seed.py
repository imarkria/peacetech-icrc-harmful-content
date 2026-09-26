"""Load the synthetic sample posts into the database and classify them.

    python -m harmwatch.seed
"""

import json
from pathlib import Path

from harmwatch import db
from harmwatch.pipeline import classify_pending

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "sample_posts.json"


def load_samples() -> list[dict]:
    return json.loads(SAMPLES.read_text(encoding="utf-8"))["posts"]


def main():
    with db.connect() as conn:
        added = 0
        for p in load_samples():
            post_id = db.add_post(
                conn, source="sample", text=p["text"], channel=p["channel"], side=p["side"],
                url=f"sample://{p['id']}", views=p["views"], forwards=p["forwards"],
            )
            added += post_id is not None
        print(f"Added {added} sample posts. Classifying…")
        print(f"Classified {classify_pending(conn)} posts. Database: {db.DB_PATH}")


if __name__ == "__main__":
    main()
