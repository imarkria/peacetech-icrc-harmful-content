"""Score the classifier against the labelled samples.

    python -m harmwatch.evaluate

Reports per-label precision/recall, bucket accuracy, how often non-harmful posts
(testimony, reporting, help) get flagged, and the flag rate per side.
"""

from collections import Counter, defaultdict

from harmwatch.classify import classify
from harmwatch.seed import load_samples
from harmwatch.triage import NOT_HARMFUL, triage


def main():
    samples = load_samples()
    tp, fp, fn = Counter(), Counter(), Counter()
    bucket_ok = 0
    false_flags = []
    flagged_by_side = defaultdict(lambda: [0, 0])  # side -> [flagged, harmful expected]
    backend = "?"

    for s in samples:
        result, backend = classify(s["text"])
        predicted, expected = set(result.harm_types), set(s["expected"]["harm_types"])
        for label in predicted & expected:
            tp[label] += 1
        for label in predicted - expected:
            fp[label] += 1
        for label in expected - predicted:
            fn[label] += 1

        bucket = triage(result)
        bucket_ok += bucket == s["expected"]["bucket"]
        if s["expected"]["bucket"] == NOT_HARMFUL and bucket != NOT_HARMFUL:
            false_flags.append(s["id"])
        if expected:
            flagged_by_side[s["side"]][0] += bucket != NOT_HARMFUL
            flagged_by_side[s["side"]][1] += 1

    print(f"Backend: {backend}   Samples: {len(samples)}\n")
    print(f"{'label':28} {'precision':>9} {'recall':>7}")
    for label in sorted(set(tp) | set(fp) | set(fn)):
        p = tp[label] / (tp[label] + fp[label]) if tp[label] + fp[label] else 0
        r = tp[label] / (tp[label] + fn[label]) if tp[label] + fn[label] else 0
        print(f"{label:28} {p:9.2f} {r:7.2f}")

    safe = [s for s in samples if s["expected"]["bucket"] == NOT_HARMFUL]
    print(f"\nBucket accuracy: {bucket_ok}/{len(samples)}")
    print(f"Non-harmful posts wrongly flagged: {len(false_flags)}/{len(safe)} {false_flags}")
    print("Harmful posts caught, by side:")
    for side, (flagged, total) in sorted(flagged_by_side.items()):
        print(f"  side {side}: {flagged}/{total}")


if __name__ == "__main__":
    main()
