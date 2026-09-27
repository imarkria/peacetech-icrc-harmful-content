"""Classify every stored post that has no classification yet.

    python -m harmwatch.pipeline
"""

from harmwatch import db
from harmwatch.classify import classify_full
from harmwatch.triage import priority, triage


def classify_post(conn, post) -> str:
    result, backend, assessment = classify_full(post["text"])
    bucket = triage(result)
    db.save_classification(conn, post["id"], backend, result, bucket, priority(result, post["views"]))
    if assessment is not None:
        db.save_assessment(conn, post["id"], assessment)
    return bucket


def classify_pending(conn) -> int:
    pending = db.unclassified(conn)
    for post in pending:
        classify_post(conn, post)
    return len(pending)


if __name__ == "__main__":
    with db.connect() as conn:
        print(f"Classified {classify_pending(conn)} posts.")
