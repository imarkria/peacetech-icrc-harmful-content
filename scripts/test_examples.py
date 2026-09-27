"""Phase 1 check: the region examples, leave-one-out (each example judged with the other k-1 as few-shot).

    python scripts/test_examples.py --region ru_ua [--allow-no-approved] [--bench]

Writes data/results/examples_<region>.jsonl and prints per-example agreement, hard-rule invariants,
and (with --bench) throughput with the fixed full few-shot prefix.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harmwatch.crsv import Assessor  # noqa: E402
from harmwatch.policy_loader import load_policy  # noqa: E402
from harmwatch.schema import FLAG_ROUTES, PRIORITY_RANK, flag_rule  # noqa: E402


def invariants(a) -> list[str]:
    """Hard rules that must hold on every final assessment."""
    broken = []
    if a.risk_flags.possible_minor != (a.route == "restricted_escalation"):
        broken.append("possible_minor <=> restricted")
    if a.route == "restricted_escalation" and (a.reviewer_summary or a.named_acts or a.lexicon_hits or a.notes
                                               or any(getattr(a.elements, k).reason for k in "ABC")):
        broken.append("restricted content not blanked")
    if a.route in FLAG_ROUTES and not flag_rule(a):
        broken.append("flagged without 3 axes / with exclusion")
    if a.route in FLAG_ROUTES and a.features.stance in ("reports", "quotes_to_condemn"):
        broken.append("reporting/condemning flagged")
    if a.route in FLAG_ROUTES and PRIORITY_RANK[a.priority] < PRIORITY_RANK.get(a.model_priority, 0):
        broken.append("priority lowered")
    return broken


def compare(expected: dict, a) -> dict[str, bool]:
    """Field-by-field agreement on the fields the example specifies."""
    got_flag = a.route in FLAG_ROUTES
    r = {"flag": got_flag == expected["flag"], "route": a.route == expected["route"]}
    for key in ("primary_relation", "exclusion", "affiliation", "content_type", "triggered_layer", "priority", "lead"):
        if key in expected:
            r[key] = getattr(a, key) == expected[key]
    for key, attr in (("named_acts", "named_acts"), ("hi_types", "hi_types"), ("harm_pathways", "harm_pathways")):
        if key in expected:
            got = {x if isinstance(x, str) else x.id for x in getattr(a, attr)}
            r[key] = set(expected[key]) <= got
    for k, v in (expected.get("features") or {}).items():
        r[f"FT-{k}"] = getattr(a.features, k) == v
    for k, v in (expected.get("risk_flags") or {}).items():
        r[k] = getattr(a.risk_flags, k) == v
    for k, v in (expected.get("elements") or {}).items():
        r[f"element_{k}"] = getattr(a.elements, k).value == v
    if expected.get("low_confidence"):
        r["low_confidence"] = min(a.elements.A.confidence, a.elements.B.confidence) < 0.7
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="ru_ua")
    ap.add_argument("--allow-no-approved", action="store_true",
                    help="dev: run core-only while no region entry is approved (never loads proposed ones)")
    ap.add_argument("--platform", default=None, help="platform profile (default: PLATFORM env or telegram)")
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    policy = load_policy(args.region, args.platform, allow_no_approved=args.allow_no_approved)
    examples = policy.examples
    assessor = Assessor(policy)
    systems = [policy.system_prompt([e for e in examples if e["id"] != x["id"]]) for x in examples]

    start = time.time()
    results = assessor.assess_many(examples, workers=args.workers, systems=systems)
    elapsed = time.time() - start

    out_dir = ROOT / "data" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, n_ok, n_crit, n_inv = [], 0, 0, 0
    print(f"Profile {policy.region} v{policy.profile_version} · {len(policy.entries)} approved entries · "
          f"leave-one-out on {len(examples)} examples\n")
    for x, res in zip(examples, results):
        a = res["assessment"]
        if a is None:
            print(f"{x['id']}  ERROR {res['error']}")
            rows.append({"id": x["id"], "error": res["error"]})
            continue
        agree = compare(x["expected"], a)
        broken = invariants(a)
        n_ok += 1
        n_crit += agree["flag"] and agree["route"]
        n_inv += not broken
        misses = [k for k, v in agree.items() if not v]
        print(f"{x['id']}  exp {x['expected']['route']:<22} got {a.route:<22} prio {a.priority:<8} "
              f"rel {a.primary_relation or '-':<9} {'OK ' if not misses else 'MISS ' + ','.join(misses)}"
              f"{'  INVARIANT BROKEN: ' + ';'.join(broken) if broken else ''}"
              f"{'  invalid_ids=' + ','.join(a.invalid_ids) if a.invalid_ids else ''}")
        rows.append({"id": x["id"], "expected": x["expected"], "agree": agree, "invariants_broken": broken,
                     "assessment": a.model_dump(), "usage": res["usage"], "seconds": res["seconds"]})

    fields = {}
    for row in rows:
        for k, v in (row.get("agree") or {}).items():
            fields.setdefault(k, []).append(v)
    print(f"\nRestricted: " + str({r["id"]: r["assessment"]["restricted_reason"] for r in rows if r.get("assessment") and r["assessment"]["restricted_reason"]}))
    print(f"Valid JSON: {n_ok}/{len(examples)}   Hard-rule invariants: {n_inv}/{n_ok}   "
          f"Flag + route correct: {n_crit}/{len(examples)}")
    print("Field agreement: " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in fields.items()))
    print(f"Wall time {elapsed:.1f}s for {len(examples)} items (distinct prefixes: no cache reuse)")
    (out_dir / f"examples_{args.region}.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    if args.bench:
        bench(assessor, examples, args.workers)


def bench(assessor: Assessor, examples: list[dict], workers: int):
    """Throughput with the fixed full prefix: the 16 examples + the 20 synthetic sample posts."""
    samples = json.loads((ROOT / "samples" / "sample_posts.json").read_text(encoding="utf-8"))["posts"]
    items = [{"id": x["id"], "text": x["text"], "fwd_from": x.get("fwd_from")} for x in examples] + \
            [{"id": s["id"], "text": s["text"], "views": s["views"], "forwards": s["forwards"]} for s in samples]
    for w in (1, workers):
        start = time.time()
        res = assessor.assess_many(items, workers=w)
        t = time.time() - start
        prompt = sum(r["usage"].get("prompt_tokens", 0) for r in res)
        cached = sum((r["usage"].get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0 for r in res)
        completion = sum(r["usage"].get("completion_tokens", 0) for r in res)
        errors = sum(r["assessment"] is None for r in res)
        print(f"workers={w}: {len(items)} items in {t:.0f}s → {3600 * len(items) / t:.0f} items/h · "
              f"prompt {prompt / len(items):.0f} tok/item (cached {cached / max(prompt, 1):.0%}) · "
              f"output {completion / len(items):.0f} tok/item · errors {errors}")


if __name__ == "__main__":
    main()
