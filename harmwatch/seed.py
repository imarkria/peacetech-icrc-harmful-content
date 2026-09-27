"""Run the synthetic sample posts through intake (duplicate groups + judge), like collected posts.

    python -m harmwatch.seed
"""

import json
from collections import Counter
from pathlib import Path

from harmwatch.detections import db_path
from harmwatch.intake import Post, ingest

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "sample_posts.json"


def load_samples() -> list[dict]:
    return json.loads(SAMPLES.read_text(encoding="utf-8"))["posts"]


def main():
    stats = Counter()
    for p in load_samples():
        post = Post(platform="sample", post_id=p["id"], text=p["text"], reach=p["views"],
                    url=f"https://example.org/samples/{p['id']}")
        result = ingest(post, source="sample")
        stats["new" if result.new else "already seen"] += 1
        if result.detection:
            stats[result.detection["route"]] += 1
    print(", ".join(f"{k} {v}" for k, v in stats.items()) + f". Database: {db_path()}")


if __name__ == "__main__":
    main()
