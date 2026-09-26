"""Run and score one model on the frozen sexual-character benchmark (data/benchmarks/sv_images_v1.jsonl).

    python scripts/eval_sv_benchmark.py run   --model qwen35-9b [--api-model qwen3.5-9b] [--workers 8]
    python scripts/eval_sv_benchmark.py score --model qwen35-9b

The model is served behind an OpenAI-compatible endpoint (LOCAL_LLM_URL, default llama-server on :8080).
Outputs in results/sv_benchmark/<model>/: predictions.jsonl, metrics.json, confusion.csv/png, roc.png,
hate/misogyny confusion, run_info.json. summary.md is written by hand from metrics.json + predictions.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BENCH = ROOT / "data" / "benchmarks" / "sv_images_v1.jsonl"
DIST = ROOT / "data" / "benchmarks" / "sv_images_v1_distribution.json"
RESULTS = ROOT / "results" / "sv_benchmark"
SHOTS = ["G03", "G05", "G06", "G09"]  # synthetic, described in text; never benchmark images
THRESHOLD = 50


def load_bench() -> list[dict]:
    text = BENCH.read_text(encoding="utf-8")
    frozen = json.loads(DIST.read_text())["frozen"]["sha256_jsonl"]
    if hashlib.sha256(text.encode()).hexdigest() != frozen:
        sys.exit("Benchmark file differs from the frozen v1 hash.")
    return [json.loads(l) for l in text.splitlines() if l.strip()]


class VramMonitor(threading.Thread):
    """Peak GPU memory used (MiB) while the run lasts."""

    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.stop = 0, False

    def run(self):
        while not self.stop:
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=10).stdout
                self.peak = max(self.peak, max(int(x) for x in out.split()))
            except Exception:
                pass
            time.sleep(2)


def cmd_run(args):
    from PIL import Image

    from harmwatch.policy_loader import load_examples, load_policy
    from harmwatch.sv_scores import SVScorer

    bench = load_bench()
    policy = load_policy("global", "generic", allow_no_approved=True)  # global entries still proposed → core only
    ex = {x["id"]: x for x in load_examples("global")}
    scorer = SVScorer(policy, [ex[i] for i in SHOTS], model=args.api_model)
    out_dir = RESULTS / args.model
    out_dir.mkdir(parents=True, exist_ok=True)
    items = [{"id": b["item_id"], "image": Image.open(ROOT / b["image"]), "text": b["text"], "lang": "en",
              "modality": "meme" if b["text"].strip() else "image"} for b in bench]
    ref = {b["item_id"]: b for b in bench}
    f = open(out_dir / "predictions.jsonl", "w", encoding="utf-8")
    lock = threading.Lock()

    def write(item, res):
        b, a = ref[item["id"]], res["assessment"]
        with lock:
            f.write(json.dumps({"item_id": b["item_id"], "source": b["source"], "neg_type": b["neg_type"],
                                "reference": b["reference"], "prediction": a.model_dump() if a else None,
                                "seconds": round(res["seconds"], 2), "usage": res["usage"], "error": res["error"],
                                "raw_on_error": res["raw"] if res["error"] else None}, ensure_ascii=False) + "\n")
            f.flush()

    vram = VramMonitor()
    vram.start()
    start = time.time()
    scorer.assess_many(items, workers=args.workers, on_result=write)
    total = time.time() - start
    vram.stop = True
    f.close()
    info = {"model": args.model, "api_model": args.api_model, "backend": args.backend, "n_items": len(items),
            "workers": args.workers, "total_seconds": round(total, 1), "images_per_min": round(60 * len(items) / total, 1),
            "vram_peak_mib": vram.peak, "shots": SHOTS, "profile": policy.profile_version, "threshold": THRESHOLD}
    (out_dir / "run_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info))


# --- scoring -----------------------------------------------------------------------

def confusion(pairs):
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if not g and p)
    fn = sum(1 for g, p in pairs if g and not p)
    tn = sum(1 for g, p in pairs if not g and not p)
    div = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    prec, rec = div(tp, tp + fp), div(tp, tp + fn)
    f1 = round(2 * prec * rec / (prec + rec), 3) if prec and rec else 0.0
    return {"n": len(pairs), "TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": prec, "recall": rec, "f1": f1,
            "accuracy": div(tp + tn, len(pairs)), "specificity": div(tn, tn + fp)}


def save_matrix(path: Path, m: dict, title: str):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.with_suffix(".csv").write_text(
        f"gold\\pred,positive,negative\npositive,{m['TP']},{m['FN']}\nnegative,{m['FP']},{m['TN']}\n\n"
        + "".join(f"{k},{m[k]}\n" for k in ("n", "precision", "recall", "f1", "accuracy", "specificity")))
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.imshow([[1, 0], [0, 1]], cmap="Blues", vmin=-0.6, vmax=1.6)
    for i, row in enumerate([[("TP", m["TP"]), ("FN", m["FN"])], [("FP", m["FP"]), ("TN", m["TN"])]]):
        for j, (tag, v) in enumerate(row):
            ax.text(j, i, f"{tag}\n{v}", ha="center", va="center", fontsize=12)
    ax.set_xticks([0, 1], ["pred +", "pred −"])
    ax.set_yticks([0, 1], ["ref +", "ref −"])
    ax.set_title(f"{title}\nP={m['precision']} R={m['recall']} F1={m['f1']}", fontsize=8)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=120)
    plt.close(fig)


def cmd_score(args):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_auc_score, roc_curve

    from harmwatch.sv_scores import CATEGORY_REL, DIMENSIONS

    out_dir = RESULTS / args.model
    preds = [json.loads(l) for l in (out_dir / "predictions.jsonl").read_text().splitlines() if l.strip()]
    ok = [p for p in preds if p["prediction"]]
    err = [p for p in preds if not p["prediction"]]
    info = json.loads((out_dir / "run_info.json").read_text())
    m: dict = {"model": args.model}

    main = confusion([(p["reference"]["sexual"], p["prediction"]["sexual"]) for p in ok])
    m["sexual"] = main
    save_matrix(out_dir / "confusion", main, f"{args.model} · sexual")

    # Quantification: max(sexual_violence, sexual_harassment); restricted items (scores blanked) count as 100.
    def sx(p):
        s = p["prediction"]["scores"]
        return 100 if s is None else max(s["sexual_violence"], s["sexual_harassment"])
    y = [int(p["reference"]["sexual"]) for p in ok]
    score = [sx(p) for p in ok]
    auroc = roc_auc_score(y, score)
    fpr, tpr, thr = roc_curve(y, score)
    best = max(range(len(thr)), key=lambda i: tpr[i] - fpr[i])  # Youden J
    m["quantification"] = {"auroc": round(auroc, 3), "best_threshold": float(thr[best]),
                           "tpr_at_best": round(float(tpr[best]), 3), "fpr_at_best": round(float(fpr[best]), 3),
                           "at_50": confusion([(g, s >= THRESHOLD) for g, s in zip(y, score)])}
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.plot(fpr, tpr, lw=2, label=f"AUROC {auroc:.3f}")
    ax.plot([0, 1], [0, 1], ls="--", lw=1, color="grey")
    ax.scatter([fpr[best]], [tpr[best]], zorder=3, label=f"best threshold {thr[best]:.0f}")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title(f"{args.model} · max(sexual_violence, sexual_harassment)", fontsize=8)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "roc.png", dpi=120)
    plt.close(fig)

    # Percentages by reference class
    def pct(group):
        g = [p for p in group if p["prediction"]["scores"] is not None]
        out = {"n": len(group), "n_scored": len(g)}
        for d in DIMENSIONS:
            vals = [p["prediction"]["scores"][d] for p in g]
            out[f"pct_{d}_ge50"] = round(100 * sum(v >= THRESHOLD for v in vals) / max(len(vals), 1), 1)
            out[f"mean_{d}"] = round(sum(vals) / max(len(vals), 1), 1)
        out["pct_sexual_pred"] = round(100 * sum(p["prediction"]["sexual"] for p in group) / max(len(group), 1), 1)
        return out
    m["by_reference_class"] = {
        "positives": pct([p for p in ok if p["reference"]["sexual"]]),
        "negatives": pct([p for p in ok if not p["reference"]["sexual"]]),
        "negatives_trap": pct([p for p in ok if p["neg_type"] == "trap"]),
        "negatives_neutral": pct([p for p in ok if p["neg_type"] == "neutral"]),
    }
    scored = [p for p in ok if p["prediction"]["scores"] is not None]
    for dim in ("hate", "misogyny"):
        c = confusion([(p["reference"][dim], p["prediction"]["scores"][dim] >= THRESHOLD) for p in scored])
        m[f"{dim}_vs_reference"] = c
        save_matrix(out_dir / f"confusion_{dim}", c, f"{args.model} · {dim} (score ≥ 50)")

    tps = [p for p in ok if p["reference"]["sexual"] and p["prediction"]["sexual"] and p["prediction"]["scores"] is not None]
    cat_ok = [p for p in tps if p["prediction"]["category"] == p["reference"]["category"]
              or (CATEGORY_REL.get(p["reference"]["category"]) is not None
                  and p["prediction"]["primary_relation"] == CATEGORY_REL[p["reference"]["category"]])]
    m["tp_category_or_relation_correct"] = {"n_tp": len(tps), "correct": len(cat_ok),
                                            "pct": round(100 * len(cat_ok) / max(len(tps), 1), 1)}
    m["counts"] = {"n": len(preds), "valid": len(ok),
                   "invalid_json": sum(p["error"].startswith("invalid_json") for p in err),
                   "timeouts": sum(p["error"].startswith("timeout") for p in err),
                   "server_errors": sum(p["error"].startswith("server_error") for p in err),
                   "refusals": sum(1 for p in ok if not p["prediction"]["reason"] and not p["prediction"]["possible_minor"]),
                   "restricted_possible_minor": sum(p["prediction"]["possible_minor"] for p in ok)}
    m["throughput"] = {**{k: info[k] for k in ("total_seconds", "images_per_min", "vram_peak_mib", "workers")},
                       "mean_latency_s": round(sum(p["seconds"] for p in preds) / len(preds), 2)}
    m["by_category_recall"] = {}
    for p in ok:
        if p["reference"]["sexual"]:
            c = m["by_category_recall"].setdefault(p["reference"]["category"], {"n": 0, "detected": 0})
            c["n"] += 1
            c["detected"] += p["prediction"]["sexual"]
    (out_dir / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))
    print(json.dumps({k: m[k] for k in ("sexual", "quantification", "counts", "throughput", "tp_category_or_relation_correct")}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True, help="name of the results folder")
    r.add_argument("--api-model", default="qwen3.5-9b")
    r.add_argument("--backend", default="llama.cpp")
    r.add_argument("--workers", type=int, default=8)
    s = sub.add_parser("score")
    s.add_argument("--model", required=True)
    args = ap.parse_args()
    {"run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
