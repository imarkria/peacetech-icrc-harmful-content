"""Build docs/results/ALL_METRICS.csv|json and ALL_CONFUSIONS.json from the (git-ignored) result files, recompute
the metrics that were never written to a file (from existing predictions, no model is re-run), and copy the AGGREGATED
files (metrics, confusion CSV, matplotlib figures, leaderboards, summaries, timing) into docs/results/<experiment>/.

    python docs/results/build_all_metrics.py

Never copied: line-by-line predictions, images, raw data. Every PNG copied is checked to be a matplotlib figure.
"""

import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "results"
R = ROOT / "results"
FIELDS = ["experiment", "date", "modality", "dataset", "n_pos", "n_neg", "model", "prompt", "variant", "task", "TP", "FP",
          "FN", "TN", "precision", "recall", "f1", "accuracy", "specificity", "auroc", "throughput_items_per_min", "notes"]
ROWS: list[dict] = []
CONF: list[dict] = []
RECOMPUTED: list[str] = []


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def conf(pairs) -> dict:
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if not g and p)
    fn = sum(1 for g, p in pairs if g and not p)
    tn = sum(1 for g, p in pairs if not g and not p)
    d = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    pr, rc = d(tp, tp + fp), d(tp, tp + fn)
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": pr, "recall": rc,
            "f1": round(2 * pr * rc / (pr + rc), 3) if pr and rc else 0.0, "accuracy": d(tp + tn, len(pairs)),
            "specificity": d(tn, tn + fp)}


def add(experiment, date, modality, dataset, model, prompt, variant, task, m, auroc=None, throughput=None, notes="",
        labels=("positive", "negative")):
    row = {"experiment": experiment, "date": date, "modality": modality, "dataset": dataset,
           "n_pos": m["TP"] + m["FN"], "n_neg": m["FP"] + m["TN"], "model": model, "prompt": prompt, "variant": variant,
           "task": task, **{k: m.get(k) for k in ("TP", "FP", "FN", "TN", "precision", "recall", "f1", "accuracy",
                                                 "specificity")},
           "auroc": auroc, "throughput_items_per_min": throughput, "notes": notes}
    ROWS.append(row)
    CONF.append({"id": f"{experiment}|{model}|{prompt}|{variant}|{task}", "experiment": experiment, "model": model,
                 "prompt": prompt, "variant": variant, "task": task, "labels": {"positive": labels[0], "negative": labels[1]},
                 "matrix": {"rows": "reference", "cols": "prediction",
                            "values": [[m["TP"], m["FN"]], [m["FP"], m["TN"]]], "order": [["TP", "FN"], ["FP", "TN"]]}})


# --- a) first test: 240 memes (abandoned) --------------------------------------------------------------------------
def first_test():
    d = R / "images" / "20260926_1614_qwen35-9b"
    m = json.loads((d / "metrics.json").read_text())
    thr = (m.get("throughput") or {}).get("images_per_min") or (m.get("run_info") or {}).get("images_per_min")
    for task, groups in m["tasks"].items():
        for g, c in groups.items():
            add("first_test_240_memes", "2026-09-26", "image", f"MemeLens test · {g}", "qwen3.5-9b", "compact_v0",
                "image_text", task, c, throughput=thr if g in ("all", "flag") else None,
                notes="abandoned test; dataset labels ≠ policy definitions" + ("; T5 = Claude silver labels" if task == "T5_silver" else ""))


# --- b) benchmark sv_images_v1 ---------------------------------------------------------------------------------------
MODELS = {"qwen35-9b": "qwen3.5-9b", "qwen35-4b": "qwen3.5-4b", "gemma4-12b": "gemma-4-12b", "internvl35-8b": "internvl3.5-8b"}


def benchmark():
    for folder, prompt, note in ((R / "sv_benchmark", "v1", "official (prompt v1 frozen)"),
                                 (R / "sv_benchmark_v3", "v3", "indicative: prompt v3 tuned after analysing this set's errors")):
        for mdir, model in MODELS.items():
            for mode in ("image_text", "text_only"):
                p = folder / mdir / mode / "metrics.json"
                if not p.exists():
                    continue
                m = json.loads(p.read_text())
                thr = m["throughput"]["images_per_min"]
                lp = m.get("logprob", {})
                add("sv_images_v1", "2026-09-26", "image", "sv_images_v1 (60 pos / 60 neg)", model, prompt, mode,
                    "sexual", m["sexual"], (lp.get("sexual") or {}).get("auroc"), thr, note,
                    ("sexual character", "not sexual"))
                for task, key in (("hate", "hate_vs_reference"), ("misogyny", "misogyny_vs_reference")):
                    add("sv_images_v1", "2026-09-26", "image", "sv_images_v1 (reference hate / misogyny)", model, prompt,
                        mode, task, m[key], (lp.get(task) or {}).get("auroc"), thr, note + "; decision field")
                nk = m["positives_without_keyword"]
                ROWS[-3]["notes"] += f"; recall on positives without explicit keyword {nk['detected']}/{nk['n']}"
    pre = R / "sv_benchmark" / "_prefreeze_qwen35-9b" / "metrics.json"
    if pre.exists():
        m = json.loads(pre.read_text())
        add("sv_images_v1", "2026-09-26", "image", "sv_images_v1 (60 pos / 60 neg)", "qwen3.5-9b", "pre-freeze",
            "image_text", "sexual", m["sexual"], m["quantification"]["auroc"], m["throughput"]["images_per_min"],
            "run before the prompt was frozen (superseded by v1); AUROC on written scores, no logprobs")


# --- c) text baselines -----------------------------------------------------------------------------------------------
def baselines():
    from harmwatch.schema import FLAG_ROUTES

    p = ROOT / "data" / "results" / "examples_ru_ua.jsonl"  # last leave-one-out run (core v1.3, telegram.md hint)
    if p.exists():
        rows = [r for r in load(p) if r.get("assessment")]
        m = conf([(r["expected"]["flag"], r["assessment"]["route"] in FLAG_ROUTES) for r in rows])
        add("baseline_ru_ua_text", "2026-09-26", "text", "ru_ua examples E01-E16 (leave-one-out)", "qwen3.5-9b",
            "core v1.3 + ru_ua", "text", "flag", m,
            notes="technical non-regression only (region phase); recomputed from per-item file; "
                  f"route correct {sum(r['agree']['route'] for r in rows)}/{len(rows)}")
        RECOMPUTED.append("baseline ru_ua: flag confusion (from data/results/examples_ru_ua.jsonl)")
    for run, core in (("20260926_1937", "core v1.3"), ("20260926_1953", "core v1.4")):
        d = R / "baseline_general" / run
        if (d / "metrics.json").exists():
            m = json.loads((d / "metrics.json").read_text())
            for task in ("flag", "sexual"):
                add("baseline_general_core_only", "2026-09-26", "text", "22 general examples (leave-one-out)",
                    "qwen3.5-9b", core, "text", task, m[task],
                    notes="core + global profile only; examples written by the team (not a benchmark)")


# --- d) video racism ---------------------------------------------------------------------------------------------------
def video():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_auc_score, roc_curve

    d = R / "videos" / "racism_v1" / "qwen35-9b"
    m = json.loads((d / "metrics.json").read_text())
    cost = m["cost"]
    for v in ("B", "C"):
        vids = load(d / v / "predictions_videos.jsonl")
        per_min = round(60 * len(vids) / (sum(cost["per_stage_total_s"].values()) + m[v]["judge_seconds"]), 2)
        add("video_racism_v1", "2026-09-26", "video", "HateMM (15 racist / 15 non-racist)", "qwen3.5-9b", "racism_v1",
            v, "racism", m[v]["videos"], m[v]["auroc_max_p_racist"], per_min,
            ("B = frames + transcript + OCR" if v == "B" else "C = transcript + OCR only")
            + f"; localisation top-1 {m[v]['localisation']['top1_hits']}/15 (chance ≈ 0.85: HateMM snippets cover ~79% of videos)",
            ("racist video", "non-racist video"))
        # recomputed: ROC of the video score (max P(racist) over segments), never written before
        y = [int(x["reference"]["racist"]) for x in vids]
        s = [x["score"] or 0.0 for x in vids]
        fpr, tpr, _ = roc_curve(y, s)
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.plot(fpr, tpr, lw=2, label=f"AUROC {roc_auc_score(y, s):.3f}")
        ax.plot([0, 1], [0, 1], ls="--", lw=1, color="grey")
        ax.set_xlabel("false positive rate")
        ax.set_ylabel("true positive rate")
        ax.set_title(f"Video racism · variant {v} · video score = max P(racist)", fontsize=8)
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        (d / v / "roc.png").parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / v / "roc.png", dpi=120)
        plt.close(fig)
        RECOMPUTED.append(f"video racism {v}: roc.png (from predictions_videos.jsonl)")
    (d / "timing.json").write_text(json.dumps(cost, indent=2))
    RECOMPUTED.append("video racism: timing.json (extracted from metrics.json)")


# --- f) safety filters (TODO_SECURITE.md) ------------------------------------------------------------------------------
def safety():
    from harmwatch.safety import THRESHOLDS, decide

    p = ROOT / "data" / "benchmarks" / "safety_scores_sv_v1_candidates.json"
    s = json.loads(p.read_text())
    truth = [v["explicit_at_review"] for v in s.values()]
    add("safety_explicit_filter", "2026-09-26", "image", "sv_images_v1 candidates (10 explicit at review / 255 not)",
        "Falconsai ViT", "-", "threshold 0.3", "explicit_image",
        conf([(t, v["falconsai"] >= 0.3) for t, v in zip(truth, s.values())]),
        notes="recomputed from precomputed scores; the 10 explicit images are the ones Falconsai had missed (selection bias)",
        labels=("explicit at review", "not explicit"))
    add("safety_explicit_filter", "2026-09-26", "image", "sv_images_v1 candidates (10 explicit at review / 255 not)",
        "OR(CLIP≥0.9, AdamCodd≥0.7, Falconsai≥0.3)", "-", "default", "explicit_image",
        conf([(t, decide(v).quarantine) for t, v in zip(truth, s.values())]),
        notes="retained default; thresholds chosen on these 10 cases (optimistic); 26 of the blocked non-explicit are benchmark positives",
        labels=("explicit at review", "not explicit"))
    minor = [v["possible_minor_at_review"] for v in s.values()]
    add("safety_child_visual", "2026-09-26", "image", "sv_images_v1 candidates (25 possible minors at review)",
        "CLIP ViT-L/14 zero-shot", "-", f"threshold {THRESHOLDS['clip_child']}", "childlike_appearance",
        conf([(t, v["clip_child"] >= THRESHOLDS["clip_child"]) for t, v in zip(minor, s.values())]),
        notes="recomputed from precomputed scores; signal not wired anywhere (decision 2026-09-26)",
        labels=("possible minor at review", "adult / no person"))
    RECOMPUTED.append("safety: explicit-filter and childlike-appearance confusions (from safety_scores_sv_v1_candidates.json)")
    # judge possible_minor (prompt v3): counts documented in TODO_SECURITE.md; per-item predictions were never saved
    add("safety_judge_possible_minor", "2026-09-26", "image", "18 minor + sexual element / 8 minor without sexual element",
        "qwen3.5-9b", "v3", "image_text", "possible_minor",
        conf([(1, 1)] * 9 + [(1, 0)] * 9 + [(0, 1)] * 5 + [(0, 0)] * 3),
        notes="from counts documented in TODO_SECURITE.md (per-item predictions not saved: not recomputable)",
        labels=("minor + sexual element", "minor without sexual element"))


# --- e) cascade images ------------------------------------------------------------------------------------------------
def cascade():
    p = R / "cascade" / "metrics.json"
    if not p.exists():
        return
    m = json.loads(p.read_text())
    best = m["best_student"]
    ds = "sv_images_v1 (60 pos / 60 neg)"
    lab = ("sexual character", "not sexual")
    for pv, c in m["judge_alone"].items():
        add("cascade_images", "2026-09-27", "image", ds, "qwen3.5-9b", pv, "judge_alone", "sexual", c,
            throughput=round(60 / c["seconds_per_image"], 1), notes=f"reference for the cascade; time/img={c['seconds_per_image']}", labels=lab)
    for name, st in m["students"].items():
        tgt = "teacher-distilled" if st["target"] == "teacher" else "dataset labels"
        research = "" if name.startswith("T_") else "; image features: research experiment (B5-4)"
        for k, c in st["alone"].items():
            add("cascade_images", "2026-09-27", "image", ds, f"student {name}", "-", f"student_{k}", "sexual", c,
                st["auroc_vs_reference"], round(60 * st["images_per_second"], 1),
                f"{tgt}; threshold for DEV recall {k} % vs teacher{research}" + ("; SELECTED ON DEV" if name == best else ""),
                labels=lab)
        if name != best:
            continue
        for pv, ks in st["cascade"].items():
            for k, c in ks.items():
                add("cascade_images", "2026-09-27", "image", ds, f"cascade {name} -> qwen3.5-9b", pv, f"cascade_{k}",
                    "sexual", c, None, round(60 * 120 / c["estimated_seconds"], 1),
                    f"sent={c['sent_fraction']}; lost={c['reference_positives_lost_by_filter']}/60; "
                    f"speedup={c['speedup']}; time/img={round(c['estimated_seconds'] / 120, 3)}{research}", labels=lab)
    RECOMPUTED.append("cascade: rows from results/cascade/metrics.json (judge alone, students alone, cascade v1/v3)")
    ft = R / "cascade" / "filter_test_10pct.json"
    if ft.exists():
        f = json.loads(ft.read_text())
        for key, ds in (("mix", "sv_images_v1 (60 pos) + 459 DEV negatives (teacher labels) · 10.4 % positive"),
                        ("benchmark_only", "sv_images_v1 (60 pos / 60 neg)")):
            mm = f[key]
            add("cascade_filter_test", "2026-09-27", "image", ds, f"filter {f['student']}", "-",
                "filter_95_" + ("10pct" if key == "mix" else "50pct"), "sexual_sent_to_judge",
                mm["confusion"], None, round(60 / f["filter_seconds_per_image"], 1),
                f"sent={mm['sent_fraction']}; false_pass={mm['false_pass_rate']}; speedup={mm['speedup']}; "
                f"time/img={mm['time_per_image_cascade_s']}; DEV negatives labelled by Qwen (not checked by hand); "
                "threshold chosen on DEV (false-pass rate possibly optimistic); image features: research experiment (B5-4)",
                labels=("sexual", "not sexual"))
        RECOMPUTED.append("cascade: filter test at 10 % prevalence (from filter_test_10pct.json)")


# --- copy aggregated files ---------------------------------------------------------------------------------------------
AGGREGATED = ("metrics.json", "run_info.json", "summary.md", "leaderboard.md", "leaderboard.csv", "significance.json",
              "error_consensus.json", "localisation_vs_chance.json", "timing.json", "FINAL_IMAGES.md", "label_stats.json",
              "train_metrics.json", "prevalence_projection.json", "filter_test_10pct.json")


def is_matplotlib_png(p: Path) -> bool:
    from PIL import Image

    return "matplotlib" in str(Image.open(p).info.get("Software", "")).lower()


def copy_aggregated():
    copied, refused = 0, []
    plan = {"first_test_240_memes": R / "images" / "20260926_1614_qwen35-9b",
            "sv_images_v1": R / "sv_benchmark", "sv_images_v1_prompt_v3": R / "sv_benchmark_v3",
            "baseline_general_core_only": R / "baseline_general", "video_racism_v1": R / "videos" / "racism_v1",
            "cascade": R / "cascade"}
    for name, src in plan.items():
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            ok = f.name in AGGREGATED or (f.suffix == ".csv" and f.name.startswith("confusion")) or f.suffix == ".png"
            if not ok or "predictions" in f.name or f.suffix in (".jpg", ".jpeg") or "per_item" in f.name:
                continue
            if f.suffix == ".png" and not is_matplotlib_png(f):
                refused.append(str(f))
                continue
            dst = OUT / name / f.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            copied += 1
    # per-item student scores are line-by-line predictions: removed from the versioned copy (kept in results/)
    cm = OUT / "cascade" / "metrics.json"
    if cm.exists():
        d = json.loads(cm.read_text())
        for st in d.get("students", {}).values():
            st.pop("scores", None)
        cm.write_text(json.dumps(d, indent=2))
    # Telegram extraction: counts only (no ground truth, no text)
    tg = OUT / "telegram_extraction"
    tg.mkdir(parents=True, exist_ok=True)
    totals = ROOT / "data" / "processed" / "corpus_totals.json"
    if totals.exists():
        from collections import Counter

        hits, strength, n = Counter(), Counter(), 0
        for line in (ROOT / "data" / "processed" / "sv_regex_hits.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            n += 1
            strength[r.get("filter_strength")] += 1
            hits.update(r.get("filter_hits", []))
        t = json.loads(totals.read_text())
        (tg / "extraction_counts.json").write_text(json.dumps({
            "stage": "regex candidates only (stage a); embeddings stage abandoned; no ground truth → no confusion matrix",
            "corpus_messages_by_side": t["by_side"], "corpus_messages_total": sum(t["by_side"].values()),
            "regex_candidates": n, "by_strength": dict(strength), "by_pattern": dict(hits.most_common())}, indent=2))
        RECOMPUTED.append("telegram extraction: aggregated counts (from corpus_totals.json + sv_regex_hits.jsonl)")
        copied += 1
    return copied, refused


def main():
    first_test()
    benchmark()
    baselines()
    video()
    safety()
    cascade()
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "ALL_METRICS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ROWS)
    (OUT / "ALL_METRICS.json").write_text(json.dumps(ROWS, indent=1, ensure_ascii=False))
    (OUT / "ALL_CONFUSIONS.json").write_text(json.dumps(CONF, indent=1, ensure_ascii=False))
    copied, refused = copy_aggregated()
    (OUT / "RECOMPUTED.json").write_text(json.dumps(RECOMPUTED, indent=1))
    print(f"{len(ROWS)} metric rows · {len(CONF)} confusion matrices · {copied} aggregated files copied · "
          f"{len(refused)} non-matplotlib PNG refused: {refused}")


if __name__ == "__main__":
    main()
