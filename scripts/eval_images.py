"""Image test of the judge on QCRI/MemeLens (open data, CC BY-NC 4.0), TEST split only.

    python scripts/eval_images.py sample               # stratified sample + NSFW quarantine → data/images/memelens/
    python scripts/eval_images.py smoke                # 5 memes: valid JSON, fields filled, triggered_layer
    python scripts/eval_images.py run                  # judge the sample → results/images/<ts>_qwen35-9b/predictions.jsonl
    python scripts/eval_images.py score <run_dir>      # metrics.json, confusion_*.csv/png (+ T5 if silver labels exist)

Images and data stay in data/ (git-ignored). Explicit images are quarantined before the judge (hash + reason):
never sent, never shown, counted. The judge never sees the dataset label, explanation or task description.
"""

import argparse
import glob
import hashlib
import io
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "images" / "memelens"
SAMPLE = DATA / "sample.jsonl"
QUARANTINE = DATA / "quarantine.jsonl"
SILVER = DATA / "silver_labels.jsonl"
RESULTS = ROOT / "results" / "images"
SEED = 42
NSFW_MODEL = "Falconsai/nsfw_image_detection"  # open source (Apache-2.0) ViT
NSFW_THRESHOLD = 0.7

# subset → (n per class, positive label, negative label, region, lang). Labels checked against the data (see report).
SUBSETS = {
    "violence_en__MAMI": (20, "violence", "not-violence", "global", "en"),
    "objectification_en__MAMI": (10, "objectification", "not-objectification", "global", "en"),
    "shaming_en__MAMI": (10, "shaming", "not-shaming", "global", "en"),
    "Hateful_en_FHM": (40, "hateful", "not-hateful", "global", "en"),
    "Hateful_en__MMHS": (20, "hateful", "not-hateful", "global", "en"),
    "toxic_ru__Toxic_Memes_Detection_Dataset": (20, "toxic", "not-toxic", "ru_ua", "ru"),
}
HATE_SUBSETS = ["Hateful_en_FHM", "Hateful_en__MMHS", "toxic_ru__Toxic_Memes_Detection_Dataset"]
MAMI = ["violence_en__MAMI", "objectification_en__MAMI", "shaming_en__MAMI"]
# Few-shot: 4 examples per region (memes described in text + one hate-without-SV hard negative).
SHOTS = {"global": ["G02", "G03", "G05", "G06"], "ru_ua": ["E08", "E12", "G02", "G05"]}


def _parquets(subset: str) -> list[str]:
    home = os.environ.get("HF_HOME", str(Path.home() / "hf_cache"))
    return sorted(glob.glob(f"{home}/hub/datasets--QCRI--MemeLens/snapshots/*/{subset}/test-*.parquet"))


def cmd_sample(args):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from PIL import Image
    from transformers import pipeline

    nsfw = pipeline("image-classification", model=NSFW_MODEL, device=0 if args.gpu else -1)
    DATA.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    rows, quarantine, seen = [], [], set()
    for subset, (n, pos, neg, region, lang) in SUBSETS.items():
        table = pa.concat_tables([pq.read_table(f, columns=["id", "image", "text", "label"]) for f in _parquets(subset)])
        labels = table.column("label").to_pylist()
        for gold, label in ((1, pos), (0, neg)):
            idx = [i for i, l in enumerate(labels) if l == label]
            rng.shuffle(idx)  # fixed seed; walk the shuffled list until the quota is filled with clean images
            taken = 0
            for i in idx:
                if taken == n:
                    break
                r = table.slice(i, 1).to_pylist()[0]
                raw = r["image"]["bytes"]
                h = hashlib.sha256(raw).hexdigest()
                if h in seen:  # MAMI subsets share memes: never twice in the sample
                    continue
                seen.add(h)
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                score = next(s["score"] for s in nsfw(img) if s["label"] == "nsfw")
                if score >= NSFW_THRESHOLD:
                    quarantine.append({"sha256": h, "subset": subset, "gold": gold,
                                       "reason": f"nsfw_classifier score {score:.2f} >= {NSFW_THRESHOLD}"})
                    continue
                img.thumbnail((768, 768))
                path = DATA / f"{r['id']}.jpg"
                img.save(path, "JPEG", quality=90)
                rows.append({"id": r["id"], "subset": subset, "gold": gold, "label": r["label"], "text": r["text"] or "",
                             "region": region, "lang": lang, "sha256": h, "nsfw_score": round(score, 3),
                             "image": str(path.relative_to(ROOT))})
                taken += 1
            print(f"{subset:<42} {label:<22} {taken}/{n}")
    SAMPLE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    QUARANTINE.write_text("".join(json.dumps(q) + "\n" for q in quarantine), encoding="utf-8")
    print(f"{len(rows)} sampled, {len(quarantine)} quarantined (NSFW) → {SAMPLE}")


def load_sample() -> list[dict]:
    return [json.loads(l) for l in SAMPLE.read_text(encoding="utf-8").splitlines() if l.strip()]


def assessors():
    from harmwatch.policy_loader import load_examples, load_policy
    from harmwatch.vision import ImageAssessor

    ex = {x["id"]: x for r in ("global", "ru_ua") for x in load_examples(r)}
    out = {}
    for region, shots in SHOTS.items():
        # global: every entry is still proposed → core-only (proposed entries are never loaded)
        policy = load_policy(region, "generic", allow_no_approved=(region == "global"))
        out[region] = ImageAssessor(policy, [ex[i] for i in shots])
    return out


def to_item(r: dict) -> dict:
    from PIL import Image

    return {"id": r["id"], "image": Image.open(ROOT / r["image"]), "text": r["text"], "lang": r["lang"],
            "modality": "meme" if r["text"].strip() else "image"}


def cmd_smoke(args):
    rows = [r for r in load_sample() if r["text"].strip()]
    rows = random.Random(SEED).sample(rows, 5)
    judges = assessors()
    ok = 0
    for r in rows:
        res = judges[r["region"]].assess(to_item(r))
        a = res["assessment"]
        good = a is not None and a.triggered_layer in ("image", "embedded_text", "meme") and (a.reason or a.route == "restricted_escalation")
        ok += bool(good)
        print(f"{r['id'][:10]} {r['subset'][:24]:<24} {res['seconds']:.1f}s "
              f"{'OK' if good else 'KO'} error={res['error']} "
              f"{a.model_dump(include={'modality', 'hateful', 'hi_types', 'sv_related', 'flag', 'route', 'triggered_layer', 'confidence'}) if a else ''}")
    print(f"smoke: {ok}/5 valid")


def cmd_run(args):
    rows = load_sample()
    judges = assessors()
    run_dir = RESULTS / f"{datetime.now().strftime('%Y%m%d_%H%M')}_qwen35-9b"
    run_dir.mkdir(parents=True, exist_ok=True)
    by_region = {}
    for r in rows:
        by_region.setdefault(r["region"], []).append(r)
    out = open(run_dir / "predictions.jsonl", "w", encoding="utf-8")
    start = time.time()
    done = 0
    for region, rs in by_region.items():
        def write(item, res, meta={r["id"]: r for r in rs}):
            nonlocal done
            m = meta[item["id"]]
            a = res["assessment"]
            out.write(json.dumps({"id": m["id"], "subset": m["subset"], "gold": m["gold"], "label": m["label"],
                                  "region": region, "prediction": a.model_dump() if a else None,
                                  "seconds": round(res["seconds"], 2), "usage": res["usage"], "error": res["error"],
                                  "raw_on_error": res["raw"] if res["error"] else None}, ensure_ascii=False) + "\n")
            out.flush()
            done += 1
            if done % 20 == 0:
                print(f"{done}/{len(rows)} in {time.time() - start:.0f}s", flush=True)
        judges[region].assess_many([to_item(r) for r in rs], workers=args.workers, on_result=write)
    total = time.time() - start
    out.close()
    (run_dir / "run_info.json").write_text(json.dumps({
        "model": "Qwen3.5-9B Q8_0 + mmproj-F16 (llama.cpp, V100)", "n_items": len(rows), "workers": args.workers,
        "total_seconds": round(total, 1), "images_per_min": round(60 * len(rows) / total, 1),
        "shots": SHOTS, "nsfw_model": NSFW_MODEL, "nsfw_threshold": NSFW_THRESHOLD, "seed": SEED,
        "profiles": {k: v.policy.profile_version for k, v in judges.items()}}, indent=2))
    print(f"done: {len(rows)} in {total:.0f}s → {60 * len(rows) / total:.1f} images/min · {run_dir}")


# --- Scoring -----------------------------------------------------------------------

def confusion(pairs: list[tuple[int, int]]) -> dict:
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if not g and p)
    fn = sum(1 for g, p in pairs if g and not p)
    tn = sum(1 for g, p in pairs if not g and not p)
    div = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    prec, rec = div(tp, tp + fp), div(tp, tp + fn)
    f1 = round(2 * prec * rec / (prec + rec), 3) if prec and rec else 0.0
    return {"n": len(pairs), "TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": prec, "recall": rec, "f1": f1,
            "accuracy": div(tp + tn, len(pairs)), "specificity": div(tn, tn + fp)}


def save_matrix(run_dir: Path, name: str, m: dict, title: str):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    (run_dir / f"confusion_{name}.csv").write_text(
        "gold\\pred,positive,negative\n"
        f"positive,{m['TP']},{m['FN']}\nnegative,{m['FP']},{m['TN']}\n"
        f"\nn,{m['n']}\nprecision,{m['precision']}\nrecall,{m['recall']}\nf1,{m['f1']}\n"
        f"accuracy,{m['accuracy']}\nspecificity,{m['specificity']}\n")
    grid = [[m["TP"], m["FN"]], [m["FP"], m["TN"]]]
    tags = [["TP", "FN"], ["FP", "TN"]]
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.imshow([[1, 0], [0, 1]], cmap="Blues", vmin=-0.6, vmax=1.6)  # diagonal = correct
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{tags[i][j]}\n{grid[i][j]}", ha="center", va="center", fontsize=12)
    ax.set_xticks([0, 1], ["pred +", "pred −"])
    ax.set_yticks([0, 1], ["gold +", "gold −"])
    ax.set_title(f"{title}\nP={m['precision']} R={m['recall']} F1={m['f1']}", fontsize=8)
    fig.tight_layout()
    fig.savefig(run_dir / f"confusion_{name}.png", dpi=120)
    plt.close(fig)


def cmd_score(args):
    run_dir = Path(args.run_dir)
    preds = [json.loads(l) for l in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [p for p in preds if p["prediction"]]
    errors = [p for p in preds if not p["prediction"]]
    metrics: dict = {"tasks": {}}

    def task(tname: str, subsets: list[str], pred_fn, per_subset=True, overall=True, gold_fn=None):
        gold_fn = gold_fn or (lambda p: p["gold"])
        groups = ([(s, [s]) for s in subsets] if per_subset else []) + ([("all", subsets)] if overall and len(subsets) > 1 else [])
        for gname, ss in groups:
            pairs = [(gold_fn(p), int(pred_fn(p["prediction"]))) for p in ok if p["subset"] in ss]
            m = confusion(pairs)
            metrics["tasks"].setdefault(tname, {})[gname] = m
            save_matrix(run_dir, f"{tname}_{gname}", m, f"{tname} · {gname}")

    task("T1_hate", HATE_SUBSETS, lambda a: a["hateful"])
    task("T2_misogyny", MAMI, lambda a: a["hateful"] or a["sv_related"])
    task("T3_sv_related", ["violence_en__MAMI", "objectification_en__MAMI"], lambda a: a["sv_related"])
    task("T4_flag", list(SUBSETS), lambda a: a["flag"])
    # Sensitivity: restricted items have hateful blanked (B1-1), so they count as FN in T1; also score T1 without them.
    pairs = [(p["gold"], int(p["prediction"]["hateful"])) for p in ok
             if p["subset"] in HATE_SUBSETS and p["prediction"]["route"] != "restricted_escalation"]
    metrics["T1_hate_excluding_restricted"] = confusion(pairs)

    if SILVER.exists():  # T5: Qwen vs my annotation under policy/ (silver labels)
        silver = {s["id"]: s for s in (json.loads(l) for l in SILVER.read_text().splitlines() if l.strip())}
        sub = [p for p in ok if p["id"] in silver]
        for key in ("hateful", "sv_related", "flag"):
            m = confusion([(int(silver[p["id"]][key]), int(p["prediction"][key])) for p in sub])
            metrics["tasks"].setdefault("T5_silver", {})[key] = m
            save_matrix(run_dir, f"T5_silver_{key}", m, f"T5 vs silver · {key}")
        metrics["silver_ids"] = sorted(silver)
        metrics["silver_missing_prediction"] = sorted(set(silver) - {p["id"] for p in sub})
        # dataset gold vs my silver labels, to see where the policy and the dataset disagree
        metrics["silver_vs_dataset"] = {
            k: confusion([(p["gold"], int(silver[p["id"]][k])) for p in sub]) for k in ("hateful", "flag")}

    info = json.loads((run_dir / "run_info.json").read_text()) if (run_dir / "run_info.json").exists() else {}
    quarantined = [json.loads(l) for l in QUARANTINE.read_text().splitlines() if l.strip()] if QUARANTINE.exists() else []
    secs = [p["seconds"] for p in preds]
    metrics["counts"] = {
        "n_items": len(preds), "valid": len(ok),
        "invalid_json": sum(1 for p in errors if p["error"].startswith("invalid_json")),
        "timeouts": sum(1 for p in errors if p["error"].startswith("timeout")),
        "server_errors": sum(1 for p in errors if p["error"].startswith("server_error")),
        "refusals": sum(1 for p in ok if not p["prediction"]["reason"] and p["prediction"]["route"] != "restricted_escalation"),
        "restricted_escalation": sum(1 for p in ok if p["prediction"]["route"] == "restricted_escalation"),
        "nsfw_quarantined": len(quarantined),
        "nsfw_quarantined_by_subset": {s: sum(1 for q in quarantined if q["subset"] == s) for s in SUBSETS},
        "errors_by_subset": {s: sum(1 for p in errors if p["subset"] == s) for s in SUBSETS},
    }
    metrics["throughput"] = {
        **{k: info.get(k) for k in ("total_seconds", "images_per_min", "workers")},
        "images_per_10_min": round(10 * info["images_per_min"]) if info.get("images_per_min") else None,
        "mean_latency_s": round(sum(secs) / len(secs), 2), "max_latency_s": round(max(secs), 2),
        "prompt_tokens_mean": round(sum(p["usage"].get("prompt_tokens", 0) for p in ok) / max(len(ok), 1)),
        "completion_tokens_mean": round(sum(p["usage"].get("completion_tokens", 0) for p in ok) / max(len(ok), 1)),
    }
    metrics["triggered_layer"] = {}
    for p in ok:
        k = p["prediction"]["triggered_layer"]
        metrics["triggered_layer"][k] = metrics["triggered_layer"].get(k, 0) + 1
    metrics["run_info"] = info
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    for t, groups in metrics["tasks"].items():
        for g, m in groups.items():
            print(f"{t:<14} {g:<42} n={m['n']:<4} TP={m['TP']:<3} FP={m['FP']:<3} FN={m['FN']:<3} TN={m['TN']:<3} "
                  f"P={m['precision']} R={m['recall']} F1={m['f1']} Acc={m['accuracy']} Spec={m['specificity']}")
    print(json.dumps(metrics["counts"]), json.dumps(metrics["throughput"]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--gpu", action="store_true")
    sub.add_parser("smoke")
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=8)
    sc = sub.add_parser("score")
    sc.add_argument("run_dir")
    args = ap.parse_args()
    {"sample": cmd_sample, "smoke": cmd_smoke, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
