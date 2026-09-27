"""Detection-phase text baseline: core + generic profile + the GENERAL examples only (no region profile).

    python scripts/baseline_general.py [--workers 8]

Each example of policy/regions/global_examples.jsonl is judged with all the others as few-shot (leave-one-out):
(a) flag / route with the CRSV text judge (INSTRUCTIONS), (b) sexual with the sexual-character scores judge
(SV_SCORE_INSTRUCTIONS, the live v2 instructions; memes are given as their text description).
Writes results/baseline_general/<timestamp>/ (per_item.jsonl, metrics.json, confusion_flag.*, confusion_sexual.*).
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harmwatch.crsv import Assessor  # noqa: E402
from harmwatch.policy_loader import format_item, load_policy  # noqa: E402
from harmwatch.schema import FLAG_ROUTES  # noqa: E402
from harmwatch.sv_scores import SVScorer  # noqa: E402
from scripts.eval_sv_benchmark import confusion, save_matrix  # noqa: E402

JUDGE_NOTE = "\nJudge the item above (a meme is given as the description of its image and its embedded text)."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--model", default="qwen3.5-9b")
    args = ap.parse_args()
    policy = load_policy("global", "generic", allow_no_approved=True)  # global entries proposed → core only
    xs = policy.examples
    out = ROOT / "results" / "baseline_general" / datetime.now().strftime("%Y%m%d_%H%M")
    out.mkdir(parents=True, exist_ok=True)

    # (a) flag / route, leave-one-out
    assessor = Assessor(policy, model=args.model)
    systems = [policy.system_prompt([e for e in xs if e["id"] != x["id"]]) for x in xs]
    flag_res = assessor.assess_many(xs, workers=args.workers, systems=systems)

    # (b) sexual, leave-one-out (examples with sv_scores only)
    def sexual(x):
        scorer = SVScorer(policy, [e for e in xs if e["id"] != x["id"] and e.get("sv_scores")], model=args.model,
                          with_image=False)
        return scorer.assess(x, user_text=format_item(x, policy.platform) + JUDGE_NOTE)
    with ThreadPoolExecutor(args.workers) as pool:
        sex_res = list(pool.map(sexual, xs))

    rows = []
    for x, fr, sr in zip(xs, flag_res, sex_res):
        a, s = fr["assessment"], sr["assessment"]
        rows.append({"id": x["id"], "expected_flag": x["expected"]["flag"], "expected_route": x["expected"]["route"],
                     "expected_sexual": x["sv_scores"]["sexual"],
                     "flag": a.route in FLAG_ROUTES if a else None, "route": a.route if a else None,
                     "primary_relation": a.primary_relation if a else None,
                     "sexual": s.sexual if s else None, "p_sexual": (s.p_true or {}).get("sexual") if s else None,
                     "category": s.category if s else None, "expected_category": x["sv_scores"]["category"],
                     "errors": [e for e in (fr["error"], sr["error"]) if e]})
    ok_f = [r for r in rows if r["flag"] is not None]
    ok_s = [r for r in rows if r["sexual"] is not None]
    m = {"n": len(rows), "profile": policy.profile_version, "model": args.model,
         "flag": confusion([(r["expected_flag"], r["flag"]) for r in ok_f]),
         "route_correct": sum(r["route"] == r["expected_route"] for r in ok_f),
         "sexual": confusion([(r["expected_sexual"], r["sexual"]) for r in ok_s]),
         "category_correct_on_positives": sum(r["category"] == r["expected_category"] for r in ok_s if r["expected_sexual"]),
         "errors": {r["id"]: r["errors"] for r in rows if r["errors"]}}
    save_matrix(out / "confusion_flag", m["flag"], "general examples · flag (core only)")
    save_matrix(out / "confusion_sexual", m["sexual"], "general examples · sexual (core only)")
    (out / "per_item.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (out / "metrics.json").write_text(json.dumps(m, indent=2))
    for r in rows:
        miss = [k for k in ("flag", "route", "sexual") if r[k] != r[f"expected_{k}"]]
        print(f"{r['id']}  flag {r['expected_flag']!s:<5}→{r['flag']!s:<5} route {r['route'] or '-':<16} "
              f"sexual {r['expected_sexual']!s:<5}→{r['sexual']!s:<5} p={r['p_sexual'] if r['p_sexual'] is not None else '-':<9} "
              f"cat {r['category'] or '-':<27} {'OK' if not miss else 'MISS ' + ','.join(miss)}")
    print(json.dumps({k: m[k] for k in ("flag", "route_correct", "sexual", "category_correct_on_positives", "errors")}))
    print(out)


if __name__ == "__main__":
    main()
