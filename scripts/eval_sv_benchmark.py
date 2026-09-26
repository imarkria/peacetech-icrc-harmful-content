"""Run and score one model on the frozen sexual-character benchmark (sv_images_v1) with the frozen prompt (sv_prompt_v1).

    python scripts/eval_sv_benchmark.py freeze                              # once: records the prompt fingerprint
    python scripts/eval_sv_benchmark.py run   --model qwen35-9b --mode image_text|text_only|ambiguous [--api-model ...]
    python scripts/eval_sv_benchmark.py score --model qwen35-9b --mode image_text|text_only|ambiguous

Modes: image_text = image + embedded text (main); text_only = embedded text alone (what the image adds);
ambiguous = the 57 excluded ambiguous candidates (score distributions only, no reference, no F1).
The model is served behind an OpenAI-compatible endpoint (LOCAL_LLM_URL, default llama-server on :8080).
Outputs: results/sv_benchmark/<model>/<mode>/ (predictions.jsonl, metrics.json, confusion*, roc.png, calibration.png).
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BENCH_DIR = ROOT / "data" / "benchmarks"
BENCH = BENCH_DIR / "sv_images_v1.jsonl"
DIST = BENCH_DIR / "sv_images_v1_distribution.json"
PROMPT_FREEZE = BENCH_DIR / "sv_prompt_v1.json"
# Frozen 2026-09-26 (core v1.2, SH-DEF, shots G03 G05 G06 G09). Never changed after results were seen.
FROZEN_PROMPT_SHA256 = "ecaefeee7cb18e9883f09e417e5fc20dbb115014b138dd62d26bd506b6445101"
RESULTS = ROOT / "results" / "sv_benchmark"
SHOTS = ["G03", "G05", "G06", "G09"]  # synthetic, described in text; never benchmark images
THRESHOLD = 50
MODES = ("image_text", "text_only", "ambiguous")


def load_bench() -> list[dict]:
    text = BENCH.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest() != json.loads(DIST.read_text())["frozen"]["sha256_jsonl"]:
        sys.exit("Benchmark file differs from the frozen v1 hash.")
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def load_ambiguous() -> list[dict]:
    cands = {json.loads(l)["cid"]: json.loads(l) for l in (BENCH_DIR / "sv_images_v1_candidates.jsonl").read_text().splitlines() if l.strip()}
    notes = [json.loads(l) for l in (BENCH_DIR / "sv_images_v1_annotations.jsonl").read_text().splitlines() if l.strip()]
    return [{"item_id": f"amb-{a['cid']}", "image": cands[a["cid"]]["image"], "text": cands[a["cid"]]["text"],
             "source": cands[a["cid"]]["source"], "neg_type": None, "reference": None, "why_ambiguous": a["reason"]}
            for a in notes if a["decision"] == "ambiguous"]


def make_scorer(api_model: str, with_image: bool):
    from harmwatch.policy_loader import load_examples, load_policy
    from harmwatch.sv_scores import SVScorer

    policy = load_policy("global", "generic", allow_no_approved=True)  # global entries still proposed → core only
    ex = {x["id"]: x for x in load_examples("global")}
    return SVScorer(policy, [ex[i] for i in SHOTS], model=api_model, with_image=with_image), policy


def cmd_freeze(args):
    if PROMPT_FREEZE.exists():
        sys.exit(f"Already frozen: {json.loads(PROMPT_FREEZE.read_text())['sha256']}")
    scorer, policy = make_scorer("any", True)
    fp = scorer.fingerprint()
    (BENCH_DIR / "sv_prompt_v1_system.txt").write_text(scorer.system, encoding="utf-8")
    PROMPT_FREEZE.write_text(json.dumps({"version": "sv_prompt_v1", "date": date.today().isoformat(), "sha256": fp,
                                         "profile": policy.profile_version, "shots": SHOTS}, indent=2))
    print(fp)


def check_prompt(scorer):
    frozen = FROZEN_PROMPT_SHA256 or json.loads(PROMPT_FREEZE.read_text())["sha256"]
    if scorer.fingerprint() != frozen:
        sys.exit("Prompt differs from the frozen sv_prompt_v1 fingerprint: refusing to run.")


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

    scorer, policy = make_scorer(args.api_model, with_image=args.mode != "text_only")
    check_prompt(scorer)
    scorer.logprobs = not args.no_logprobs
    rows = load_ambiguous() if args.mode == "ambiguous" else load_bench()
    out_dir = RESULTS / args.model / args.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    items = [{"id": b["item_id"], "image": Image.open(ROOT / b["image"]), "text": b["text"], "lang": "en",
              "modality": "meme" if b["text"].strip() else "image"} for b in rows]
    ref = {b["item_id"]: b for b in rows}
    f = open(out_dir / "predictions.jsonl", "w", encoding="utf-8")
    lock = threading.Lock()

    def write(item, res):
        b, a = ref[item["id"]], res["assessment"]
        with lock:
            f.write(json.dumps({"item_id": b["item_id"], "source": b["source"], "neg_type": b["neg_type"],
                                "reference": b["reference"], "text": b["text"], "why_ambiguous": b.get("why_ambiguous"),
                                "prediction": a.model_dump() if a else None, "seconds": round(res["seconds"], 2),
                                "usage": res["usage"], "error": res["error"],
                                "raw_on_error": res["raw"] if res["error"] else None}, ensure_ascii=False) + "\n")
            f.flush()

    vram = VramMonitor()
    vram.start()
    start = time.time()
    scorer.assess_many(items, workers=args.workers, on_result=write)
    total = time.time() - start
    vram.stop = True
    f.close()
    info = {"model": args.model, "api_model": args.api_model, "backend": args.backend, "mode": args.mode,
            "n_items": len(items), "workers": args.workers, "total_seconds": round(total, 1),
            "images_per_min": round(60 * len(items) / total, 1), "vram_peak_mib": vram.peak,
            "prompt_sha256": scorer.fingerprint(), "profile": policy.profile_version, "threshold": THRESHOLD}
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


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def save_matrix(path: Path, m: dict, title: str):
    plt = _plt()
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


def calibration(y: list[int], p: list[float], bins: int = 10) -> dict:
    """Reliability table, ECE and Brier score for probabilities p against labels y."""
    table, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, v in enumerate(p) if lo <= v < hi or (b == bins - 1 and v == 1.0)]
        if idx:
            conf = sum(p[i] for i in idx) / len(idx)
            acc = sum(y[i] for i in idx) / len(idx)
            ece += len(idx) / len(p) * abs(acc - conf)
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(idx), "mean_p": round(conf, 3), "frac_pos": round(acc, 3)})
    brier = sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(p)
    return {"ece": round(ece, 3), "brier": round(brier, 3), "table": table}


def keyword_explicit(text: str) -> bool:
    from scripts.build_sv_benchmark import ANY_SEXUAL

    return any(r.search(text or "") for r in ANY_SEXUAL)


def cmd_score(args):
    from sklearn.metrics import roc_auc_score, roc_curve

    from harmwatch.sv_scores import CATEGORY_REL, DIMENSIONS

    out_dir = RESULTS / args.model / args.mode
    preds = [json.loads(l) for l in (out_dir / "predictions.jsonl").read_text().splitlines() if l.strip()]
    ok = [p for p in preds if p["prediction"]]
    err = [p for p in preds if not p["prediction"]]
    info = json.loads((out_dir / "run_info.json").read_text())
    m: dict = {"model": args.model, "mode": args.mode}
    m["counts"] = {"n": len(preds), "valid": len(ok),
                   "invalid_json": sum(p["error"].startswith("invalid_json") for p in err),
                   "timeouts": sum(p["error"].startswith("timeout") for p in err),
                   "server_errors": sum(p["error"].startswith("server_error") for p in err),
                   "refusals": sum(1 for p in ok if not p["prediction"]["reason"] and not p["prediction"]["possible_minor"]),
                   "restricted_possible_minor": sum(p["prediction"]["possible_minor"] for p in ok),
                   "logprobs_missing": sum(1 for p in ok if not p["prediction"]["possible_minor"]
                                           and (p["prediction"].get("p_true") or {}).get("sexual") is None)}
    m["throughput"] = {**{k: info[k] for k in ("total_seconds", "images_per_min", "vram_peak_mib", "workers")},
                       "mean_latency_s": round(sum(p["seconds"] for p in preds) / len(preds), 2)}
    scored = [p for p in ok if p["prediction"]["scores"] is not None]

    def p_sexual(p):  # restricted items (B1-1 escalation, scores blanked) count as 1
        a = p["prediction"]
        return 1.0 if a["possible_minor"] else (a.get("p_true") or {}).get("sexual")

    if args.mode == "ambiguous":
        plt = _plt()
        m["ambiguous"] = {"pct_sexual_pred": round(100 * sum(p["prediction"]["sexual"] for p in ok) / max(len(ok), 1), 1)}
        for d in DIMENSIONS:
            vals = [p["prediction"]["scores"][d] for p in scored]
            m["ambiguous"][d] = {"mean": round(sum(vals) / max(len(vals), 1), 1),
                                 "pct_ge50": round(100 * sum(v >= THRESHOLD for v in vals) / max(len(vals), 1), 1),
                                 "hist_0_25_50_75_100": [sum(lo <= v < hi for v in vals) for lo, hi in
                                                         ((0, 25), (25, 50), (50, 75), (75, 101))]}
        ps = [p_sexual(p) for p in ok if p_sexual(p) is not None]
        m["ambiguous"]["p_sexual_hist_deciles"] = [sum(b / 10 <= v < (b + 1) / 10 or (b == 9 and v == 1) for v in ps) for b in range(10)]
        m["ambiguous"]["p_sexual_between_0.2_0.8"] = sum(0.2 <= v <= 0.8 for v in ps)
        fig, ax = plt.subplots(figsize=(4.5, 3))
        ax.hist(ps, bins=10, range=(0, 1))
        ax.set_xlabel("P(sexual = true) from logprobs")
        ax.set_ylabel("items")
        ax.set_title(f"{args.model} · 57 ambiguous items", fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "ambiguous_p_sexual.png", dpi=120)
        plt.close(fig)
        (out_dir / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))
        print(json.dumps(m, indent=1))
        return

    main = confusion([(p["reference"]["sexual"], p["prediction"]["sexual"]) for p in ok])
    m["sexual"] = main
    save_matrix(out_dir / "confusion", main, f"{args.model} · {args.mode} · sexual")

    # Positives without an explicit sexual keyword in the embedded text (the hard, image- or context-dependent ones)
    no_kw = [p for p in ok if p["reference"]["sexual"] and not keyword_explicit(p["text"])]
    m["positives_without_keyword"] = {"n": len(no_kw), "detected": sum(p["prediction"]["sexual"] for p in no_kw),
                                      "recall": round(sum(p["prediction"]["sexual"] for p in no_kw) / max(len(no_kw), 1), 3)}
    kw_neg = [p for p in ok if not p["reference"]["sexual"] and keyword_explicit(p["text"])]
    m["negatives_with_keyword"] = {"n": len(kw_neg), "false_positives": sum(p["prediction"]["sexual"] for p in kw_neg)}

    # Quantification 1: written scores, max(sexual_violence, sexual_harassment); restricted → 100
    y = [int(p["reference"]["sexual"]) for p in ok]
    written = [100 if p["prediction"]["scores"] is None else max(p["prediction"]["scores"]["sexual_violence"],
                                                                  p["prediction"]["scores"]["sexual_harassment"]) for p in ok]
    m["written_scores"] = {"auroc": round(roc_auc_score(y, written), 3),
                           "distinct_values": len(set(written))}
    # Quantification 2: logprob P(sexual = true)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.plot([0, 1], [0, 1], ls="--", lw=1, color="grey")
    m["logprob"] = {}
    lp_rows = [(yi, p_sexual(p)) for yi, p in zip(y, ok) if p_sexual(p) is not None]
    if lp_rows and len({r[0] for r in lp_rows}) == 2:
        yy, pp = [r[0] for r in lp_rows], [r[1] for r in lp_rows]
        auroc = roc_auc_score(yy, pp)
        fpr, tpr, thr = roc_curve(yy, pp)
        best = max(range(len(thr)), key=lambda i: tpr[i] - fpr[i])
        m["logprob"]["sexual"] = {"n": len(yy), "auroc": round(auroc, 3), "best_threshold": round(float(min(thr[best], 1.0)), 4),
                                  "tpr_at_best": round(float(tpr[best]), 3), "fpr_at_best": round(float(fpr[best]), 3),
                                  "calibration": calibration(yy, pp)}
        ax.plot(fpr, tpr, lw=2, label=f"P(sexual) logprob · AUROC {auroc:.3f}")
    fpr_w, tpr_w, _ = roc_curve(y, written)
    ax.plot(fpr_w, tpr_w, lw=1.5, label=f"written score · AUROC {m['written_scores']['auroc']:.3f}")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title(f"{args.model} · {args.mode}", fontsize=8)
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "roc.png", dpi=120)
    plt.close(fig)
    for dim, key in (("hate", "hateful"), ("misogyny", "misogynous")):
        rows = [(int(p["reference"][dim]), (p["prediction"].get("p_true") or {}).get(key)) for p in scored]
        rows = [r for r in rows if r[1] is not None]
        if rows and len({r[0] for r in rows}) == 2:
            m["logprob"][dim] = {"n": len(rows), "auroc": round(roc_auc_score([r[0] for r in rows], [r[1] for r in rows]), 3),
                                 "calibration": calibration([r[0] for r in rows], [r[1] for r in rows])}
    if "sexual" in m["logprob"]:
        t = m["logprob"]["sexual"]["calibration"]["table"]
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.plot([0, 1], [0, 1], ls="--", lw=1, color="grey")
        ax.plot([r["mean_p"] for r in t], [r["frac_pos"] for r in t], marker="o")
        for r in t:
            ax.annotate(str(r["n"]), (r["mean_p"], r["frac_pos"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel("mean P(sexual) in bin")
        ax.set_ylabel("fraction confirmed sexual")
        ax.set_title(f"{args.model} · {args.mode} · ECE {m['logprob']['sexual']['calibration']['ece']}", fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "calibration.png", dpi=120)
        plt.close(fig)

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
    for dim, key in (("hate", "hateful"), ("misogyny", "misogynous")):
        c = confusion([(p["reference"][dim], p["prediction"][key]) for p in scored])
        m[f"{dim}_vs_reference"] = c
        m[f"{dim}_score_vs_reference"] = confusion([(p["reference"][dim], p["prediction"]["scores"][dim] >= THRESHOLD) for p in scored])
        save_matrix(out_dir / f"confusion_{dim}", c, f"{args.model} · {args.mode} · {dim}")

    tps = [p for p in ok if p["reference"]["sexual"] and p["prediction"]["sexual"] and p["prediction"]["scores"] is not None]
    cat_ok = [p for p in tps if p["prediction"]["category"] == p["reference"]["category"]
              or (CATEGORY_REL.get(p["reference"]["category"]) is not None
                  and p["prediction"]["primary_relation"] == CATEGORY_REL[p["reference"]["category"]])]
    m["tp_category_or_relation_correct"] = {"n_tp": len(tps), "correct": len(cat_ok),
                                            "pct": round(100 * len(cat_ok) / max(len(tps), 1), 1)}
    m["by_category_recall"] = {}
    for p in ok:
        if p["reference"]["sexual"]:
            c = m["by_category_recall"].setdefault(p["reference"]["category"], {"n": 0, "detected": 0})
            c["n"] += 1
            c["detected"] += p["prediction"]["sexual"]
    m["errors"] = {"FP": [p["item_id"] for p in ok if p["prediction"]["sexual"] and not p["reference"]["sexual"]],
                   "FN": [p["item_id"] for p in ok if not p["prediction"]["sexual"] and p["reference"]["sexual"]]}
    (out_dir / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))
    show = ("sexual", "positives_without_keyword", "written_scores", "counts", "throughput", "tp_category_or_relation_correct")
    print(json.dumps({k: m[k] for k in show}, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "calibration"} | {"ece": v["calibration"]["ece"], "brier": v["calibration"]["brier"]}
                      for k, v in m["logprob"].items()}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    r = sub.add_parser("run")
    r.add_argument("--model", required=True, help="name of the results folder")
    r.add_argument("--mode", choices=MODES, default="image_text")
    r.add_argument("--api-model", default="qwen3.5-9b")
    r.add_argument("--backend", default="llama.cpp")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--no-logprobs", action="store_true")
    s = sub.add_parser("score")
    s.add_argument("--model", required=True)
    s.add_argument("--mode", choices=MODES, default="image_text")
    args = ap.parse_args()
    {"freeze": cmd_freeze, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
