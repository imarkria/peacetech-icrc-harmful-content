"""Classify every stored post that has no classification yet.

    python -m harmwatch.pipeline
"""

import json

from harmwatch import db
from harmwatch.classify import classify, needs_human
from harmwatch.triage import ESCALATE, priority, triage


def classify_post(conn, post) -> str:
    if post["text"].strip():
        result, backend = classify(post["text"])
    else:
        result, backend = needs_human("Link only, no text provided. Open the link to review."), "none"
    bucket = triage(result)
    targets = json.loads(post["targets"]) if post["targets"] else []
    if "child" in targets:  # a reporter's child flag always escalates, whatever the model says
        bucket = ESCALATE
    db.save_classification(conn, post["id"], backend, result, bucket, priority(result, post["views"], bucket))
    return bucket


def classify_pending(conn) -> int:
    pending = db.unclassified(conn)
    for post in pending:
        classify_post(conn, post)
    return len(pending)


if __name__ == "__main__":
    with db.connect() as conn:
        print(f"Classified {classify_pending(conn)} posts.")
