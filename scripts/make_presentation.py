"""Presentation pack → docs/presentation/ (figures PNG 300 dpi + PDF, TABLES.md, RESULTS_FOR_SLIDES.md, zip).

    python scripts/make_presentation.py

No model is run. Inputs: docs/results/ALL_METRICS.csv, ALL_CONFUSIONS.json and the versioned timing / metrics files
in docs/results/. Three things need per-item scores that only exist in results/ (git-ignored) and are READ, never
modified: bootstrap CIs of the image AUROC, the video ROC curves and the student recall curve (+ one timeline excerpt).
Nothing line-by-line is written. A number that was not measured is written "not measured / non mesuré".
"""

import csv
import json
import shutil
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "docs" / "results"
RAW = ROOT / "results"
OUT = ROOT / "docs" / "presentation"
FIG = OUT / "figures"
BACKUP = Path("/dlabscratch1/gmikou/backups")
HW = "1× NVIDIA V100 32 GB"

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
SER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
CMAP = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
MODELS = [("qwen3.5-9b", "qwen35-9b", "Qwen3.5-9B"), ("qwen3.5-4b", "qwen35-4b", "Qwen3.5-4B"),
          ("gemma-4-12b", "gemma4-12b", "Gemma 4 12B"), ("internvl3.5-8b", "internvl35-8b", "InternVL3.5-8B")]
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "font.size": 11,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True})
CREATED: list[Path] = []


def J(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def metrics() -> list[dict]:
    rows = list(csv.DictReader(open(RES / "ALL_METRICS.csv", encoding="utf-8")))
    for r in rows:
        for k in ("TP", "FP", "FN", "TN"):
            r[k] = int(r[k])
        for k in ("precision", "recall", "f1", "accuracy", "specificity", "auroc", "throughput_items_per_min"):
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
    return rows


def pick(R, **kw):
    out = [r for r in R if all(r[k] == v for k, v in kw.items())]
    return out[0] if len(out) == 1 else out


def save(fig, name: str, note: str | None = None):
    if note:
        fig.text(0.01, -0.02, note, fontsize=8, color=INK2, ha="left", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        p = FIG / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        CREATED.append(p)
    plt.close(fig)


def heat(ax, v, title, pos="sexual", neg="not sexual", vmax=None, cols=("pred +", "pred −")):
    vmax = vmax or max(max(r) for r in v)
    ax.imshow(v, cmap=CMAP, vmin=0, vmax=vmax)
    ax.grid(False)
    for i, (row, tags) in enumerate(zip(v, (("TP", "FN"), ("FP", "TN")))):
        for j, (val, tag) in enumerate(zip(row, tags)):
            ax.text(j, i, f"{tag}\n{val}", ha="center", va="center", fontsize=15, fontweight="bold",
                    color="#ffffff" if val > 0.55 * vmax else INK)
    ax.set_xticks([0, 1], list(cols), fontsize=9)
    ax.set_yticks([0, 1], [f"ref: {pos}", f"ref: {neg}"], fontsize=9, rotation=90, va="center")
    ax.set_title(title, fontsize=11)
    for s in ax.spines.values():
        s.set_visible(False)


def boot_auroc(y, s, n=2000, seed=42):
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(seed)
    y, s = np.asarray(y), np.asarray(s)
    vals = []
    for _ in range(n):
        b = rng.integers(0, len(y), len(y))
        if len(set(y[b])) == 2:
            vals.append(roc_auc_score(y[b], s[b]))
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


# ---------------------------------------------------------------------------------------------------------------------
def part_images(R, T):
    sig = J(RES / "sv_images_v1" / "significance.json")
    lb = {r["model"]: r for r in csv.DictReader(open(RES / "sv_images_v1" / "leaderboard.csv"))}
    rows = []
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    for ax, (mid, folder, label) in zip(axes, MODELS):
        r = pick(R, experiment="sv_images_v1", model=mid, prompt="v1", variant="image_text", task="sexual")
        heat(ax, [[r["TP"], r["FN"]], [r["FP"], r["TN"]]], f"{label}\nF1 {r['f1']:.3f}", vmax=60)
        preds = jl(RAW / "sv_benchmark" / folder / "image_text" / "predictions.jsonl")
        y = [int(p["reference"]["sexual"]) for p in preds if p["prediction"]]
        s = [1.0 if p["prediction"]["possible_minor"] else p["prediction"]["p_true"]["sexual"] for p in preds if p["prediction"]]
        rows.append({"label": label, "folder": folder, **r, "f1_ci": sig[folder]["image_text"]["ci95"],
                     "auroc_ci": boot_auroc(y, s), "vram_gb": round(int(lb[folder]["vram_peak_mib"]) / 1000, 1),
                     "mcnemar": sig[folder]["image_text"]["mcnemar_vs_qwen9b"]})
    save(fig, "images_4models_confusions", "sv_images_v1 (60 sexual / 60 not sexual, hand-validated), prompt v1 frozen, "
         "image + text. Same colour scale (0-60) in all four panels.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
    yy = list(range(len(rows)))[::-1]
    for ax, key, ci, title in ((axes[0], "f1", "f1_ci", "F1 · sexual character [95 % CI]"),
                               (axes[1], "auroc", "auroc_ci", "AUROC · P(sexual) from logprobs [95 % CI]")):
        for y, r, c in zip(yy, rows, SER):
            ax.plot(r[ci], [y, y], color=c, lw=3, solid_capstyle="round", alpha=0.55)
            ax.scatter([r[key]], [y], s=110, color=c, edgecolor=SURF, linewidth=2, zorder=3)
            ax.text(r[ci][1] + 0.004, y, f"{r[key]:.3f}", va="center", fontsize=10)
        ax.set_yticks(yy, [r["label"] for r in rows])
        ax.set_xlim(0.8, 1.02)
        ax.set_title(title)
        ax.grid(axis="y", visible=False)
    save(fig, "images_4models_f1_auroc_ci", "Bootstrap 95 % CIs (2 000 resamples of the 120 images). Axes start at 0.80. "
         "McNemar vs Qwen3.5-9B: p ≥ 0.6 for all → no significant difference.")

    # annex: v1 vs v3, image+text vs text only
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.6))
    items = []
    for mode, ml in (("image_text", "image + text"), ("text_only", "text only")):
        for key, kl in (("f1", "F1"), ("auroc", "AUROC")):
            a = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v1", variant=mode, task="sexual")[key]
            b = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v3", variant=mode, task="sexual")[key]
            items.append((f"{kl} · {ml}", a, b))
    dumbbell(axes[0], items, "prompt v1 (official)", "prompt v3 (indicative)", "Qwen3.5-9B · prompt v1 vs v3")
    items = [(lab, pick(R, experiment="sv_images_v1", model=mid, prompt="v1", variant="text_only", task="sexual")["f1"],
              pick(R, experiment="sv_images_v1", model=mid, prompt="v1", variant="image_text", task="sexual")["f1"])
             for mid, _, lab in MODELS]
    dumbbell(axes[1], items, "text only", "image + text", "F1 · what the image adds (prompt v1)")
    fig.subplots_adjust(wspace=0.55)
    save(fig, "annex_images_v1_v3_and_text_only", "\n\n\nv3 was tuned after analysing this set's errors: indicative only. "
         "50 of 60 positives contain an explicit keyword: the benchmark mostly measures reading the embedded text.")

    T.append("## 1. Images: four models, definition v1 (sv_images_v1, 60 / 60, prompt v1 frozen, image + text)\n")
    T.append("| model | TP | FP | FN | TN | precision | recall | F1 [95 % CI] | AUROC [95 % CI] | images/min | VRAM peak | McNemar vs Qwen3.5-9B |")
    T.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        mc = r["mcnemar"]
        mct = "reference" if r["folder"] == "qwen35-9b" else f"{mc['ref_right_other_wrong']} / {mc['ref_wrong_other_right']} discordant, p = {mc['p']}"
        T.append(f"| {r['label']} | {r['TP']} | {r['FP']} | {r['FN']} | {r['TN']} | {r['precision']:.3f} | {r['recall']:.3f} | "
                 f"{r['f1']:.3f} [{r['f1_ci'][0]:.3f}-{r['f1_ci'][1]:.3f}] | {r['auroc']:.3f} [{r['auroc_ci'][0]:.3f}-{r['auroc_ci'][1]:.3f}] | "
                 f"{r['throughput_items_per_min']:.1f} | {r['vram_gb']} GB{'*' if r['folder'] == 'qwen35-9b' else ''} | {mct} |")
    T.append("\n**Significance:** no significant difference between the four models (bootstrap CIs overlap; McNemar p ≥ 0.6). "
             "*Qwen3.5-9B ran with a 163 840-token context (others 98 304): its VRAM is overestimated.\n")
    return rows


def dumbbell(ax, items, la, lb, title):
    yy = list(range(len(items)))[::-1]
    for y, (lab, a, b) in zip(yy, items):
        ax.plot([a, b], [y, y], color=GRID, lw=4, zorder=1, solid_capstyle="round")
        ax.scatter([a], [y], s=100, color=SER[0], edgecolor=SURF, linewidth=2, zorder=3, label=la if y == yy[0] else None)
        ax.scatter([b], [y], s=100, color=SER[1], edgecolor=SURF, linewidth=2, zorder=3, label=lb if y == yy[0] else None)
        lo, hi = sorted([a, b])
        ax.text(lo - 0.004, y, f"{lo:.3f}", ha="right", va="center", fontsize=9, color=INK2)
        ax.text(hi + 0.004, y, f"{hi:.3f}", ha="left", va="center", fontsize=9, color=INK2)
    ax.set_yticks(yy, [i[0] for i in items])
    ax.set_xlim(0.84, 1.01)
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.14), ncol=2, fontsize=9)


# ---------------------------------------------------------------------------------------------------------------------
def part_video(R, T):
    from sklearn.metrics import roc_auc_score, roc_curve

    vm = J(RES / "video_racism_v1" / "qwen35-9b" / "metrics.json")
    loc = J(RES / "video_racism_v1" / "qwen35-9b" / "localisation_vs_chance.json")
    rows = {v: pick(R, experiment="video_racism_v1", variant=v, task="racism") for v in ("B", "C")}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), gridspec_kw={"width_ratios": [1, 1, 1.15]})
    for ax, v, lab in ((axes[0], "B", "B · frames + transcript + OCR"), (axes[1], "C", "C · transcript + OCR only")):
        r = rows[v]
        heat(ax, [[r["TP"], r["FN"]], [r["FP"], r["TN"]]], f"{lab}\nF1 {r['f1']:.3f}", "racist video", "non-racist", vmax=15)
    ax = axes[2]
    for k, v in enumerate(("B", "C")):
        vids = jl(RAW / "videos" / "racism_v1" / "qwen35-9b" / v / "predictions_videos.jsonl")
        y = [int(x["reference"]["racist"]) for x in vids]
        s = [x["score"] or 0.0 for x in vids]
        fpr, tpr, _ = roc_curve(y, s)
        ax.plot(fpr, tpr, lw=7 if v == "B" else 2.5, color=SER[k], drawstyle="steps-post", zorder=2 if v == "B" else 3,
                label=f"{v} · AUROC {roc_auc_score(y, s):.2f}" + (" (under C: identical curve)" if v == "B" else ""))
    ax.plot([0, 1], [0, 1], ls="--", lw=1, color=INK2)
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("ROC · video score = max P(racist)")
    ax.legend(loc="lower right", fontsize=10)
    fig.subplots_adjust(wspace=0.45)
    save(fig, "video_racism_confusions_roc", "HateMM, 15 racist / 15 non-racist videos, ≤ 4 min, prompt racism_v1 frozen "
         "before any test video. 30 videos only: each error = ~7 points.")

    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    layers = ["speech", "on_screen_text", "visuals"]
    x = np.arange(len(layers))
    for k, v in enumerate(("B", "C")):
        vals = [vm[v]["triggered_layer"][l] for l in layers]
        bars = ax.bar(x + (k - 0.5) * 0.36, vals, width=0.34, color=SER[k], edgecolor=SURF, linewidth=2,
                      label=f"variant {v}")
        for b, val in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, val + 1.5, str(val), ha="center", fontsize=10)
    ax.set_xticks(x, ["speech", "on-screen text", "visuals"])
    ax.set_ylabel("racist segments")
    ax.set_title("Which layer carries the racist content")
    ax.legend(fontsize=10)
    ax.grid(axis="x", visible=False)
    save(fig, "video_triggered_layer")

    T.append("## 2. Video: racism test (HateMM, 15 / 15, method B by segments)\n")
    T.append("| variant | TP | FP | FN | TN | precision | recall | F1 | AUROC | top-1 / top-3 localisation | mean offset |")
    T.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for v in ("B", "C"):
        r, l = rows[v], vm[v]["localisation"]
        T.append(f"| {v} | {r['TP']} | {r['FP']} | {r['FN']} | {r['TN']} | {r['precision']:.3f} | {r['recall']:.3f} | "
                 f"{r['f1']:.3f} | {r['auroc']:.3f} | {l['top1_hits']}/15 · {l['top3_hits']}/15 | {l['mean_offset_top1_s']} s |")
    T.append(f"\n**Localisation not demonstrated:** HateMM snippets cover on average {int(loc['B']['snippet_coverage_mean'] * 100)} % of "
             f"each video, so a random segment hits them {int(loc['B']['all_chance_top1'] * 100)} % of the time; only one video "
             f"has a short snippet (found top-1, chance {loc['B']['chance_top1']}).\n")
    T.append(f"Triggered layer (racist segments, B): speech {vm['B']['triggered_layer']['speech']}, on-screen text "
             f"{vm['B']['triggered_layer']['on_screen_text']}, visuals {vm['B']['triggered_layer']['visuals']}.\n")
    tl = (RAW / "videos" / "racism_v1" / "qwen35-9b" / "timelines.txt").read_text(encoding="utf-8")
    block = [b for b in tl.split("\n\n") if "hate_video_287" in b]
    if block:
        T.append("Example timeline (hate_video_287, the only video with a short annotated snippet; segment scores only):\n")
        T.append("```\n" + block[0].strip() + "\n```\n")
    return rows, vm


# ---------------------------------------------------------------------------------------------------------------------
def part_cascade(R, T):
    ft = J(RES / "cascade" / "filter_test_10pct.json")
    cm = J(RAW / "cascade" / "metrics.json")  # per-item student scores (read only)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    for ax, key, title in zip(axes, ("benchmark_only", "mix"),
                              ("120 benchmark images · 50 % positive", "579 images · 10.4 % positive")):
        m = ft[key]
        v = [[m["positives_passed_TP"], m["positives_blocked_FN"]], [m["negatives_passed_FP"], m["negatives_blocked_TN"]]]
        vmax = max(max(r) for r in v)
        ax.imshow(np.log1p(v), cmap=CMAP, vmin=0, vmax=np.log1p(vmax))
        ax.grid(False)
        for i, row in enumerate(v):
            for j, val in enumerate(row):
                ax.text(j, i, f"{'passed' if j == 0 else 'blocked'}\n{val}", ha="center", va="center", fontsize=14,
                        fontweight="bold", color="#ffffff" if np.log1p(val) > 0.6 * np.log1p(vmax) else INK)
        ax.set_xticks([0, 1], ["sent to Qwen", "blocked by filter"], fontsize=9)
        ax.set_yticks([0, 1], ["sexual (60)", f"not sexual ({m['n'] - 60})"], fontsize=9, rotation=90, va="center")
        ax.set_title(f"{title}\nrecall {m['recall']:.3f} · sent {m['sent_fraction'] * 100:.0f} % · time ÷{m['speedup']}", fontsize=11)
        for s in ax.spines.values():
            s.set_visible(False)
    save(fig, "cascade_filter_50_vs_10pct", "Filter I_logreg (SigLIP2 image embedding + logistic regression), threshold "
         "frozen on DEV (recall 95 %). Colour = log count. The 459 extra negatives are DEV items labelled by Qwen.")

    best = cm["best_student"]
    c95 = cm["students"][best]["cascade"]["v3"]["95"]
    ja = cm["judge_alone"]["v3"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    heat(axes[0], [[ja["TP"], ja["FN"]], [ja["FP"], ja["TN"]]], f"Qwen3.5-9B alone (v3)\nF1 {ja['f1']:.3f}", vmax=60)
    heat(axes[1], [[c95["TP"], c95["FN"]], [c95["FP"], c95["TN"]]],
         f"Cascade {best} → Qwen v3 (95 %)\nF1 {c95['f1']:.3f} · {c95['sent_fraction'] * 100:.0f} % sent", vmax=60)
    save(fig, "cascade_qwen_alone_vs_cascade", "Benchmark sv_images_v1 (60 / 60). Qwen v3 predictions reused (no new run).")

    ref = {b["item_id"]: b["reference"]["sexual"] for b in jl(ROOT / "data" / "benchmarks" / "sv_images_v1.jsonl")}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    for k, name in enumerate(("T_logreg", "I_logreg", "IT_logreg")):
        sc = cm["students"][name]["scores"]
        ids = list(sc)
        s, y = np.array([sc[i] for i in ids]), np.array([ref[i] for i in ids])
        ts = np.sort(s)[::-1]
        ax.plot([(s >= t).mean() for t in ts], [(y & (s >= t)).sum() / y.sum() for t in ts], lw=2.5, color=SER[k],
                label={"T": "T (text)", "I": "I (image) · selected", "IT": "I + T"}[name.split("_")[0]])
    ax.axvline(0.5, ls=":", color=INK2, lw=1)
    ax.axhline(0.95, ls="--", color=GRID, lw=1)
    ax.set_xlabel("share of benchmark images sent to Qwen")
    ax.set_ylabel("recall of confirmed sexual images")
    ax.set_title("Student filter: recall vs share sent")
    ax.legend(loc="lower right", fontsize=10)
    ax = axes[1]
    pairs = [("T", "T_logreg", "T_logreg_datasetlabels"), ("I", "I_logreg", "I_logreg_datasetlabels"),
             ("I + T", "IT_logreg", "IT_logreg_datasetlabels")]
    yy = list(range(len(pairs)))[::-1]
    for y, (lab, a, b) in zip(yy, pairs):
        va, vb = cm["students"][a]["auroc_vs_reference"], cm["students"][b]["auroc_vs_reference"]
        ax.plot([vb, va], [y, y], color=GRID, lw=4, zorder=1)
        ax.scatter([vb], [y], s=100, color=SER[3], edgecolor=SURF, linewidth=2, zorder=3,
                   label="trained on dataset labels" if y == yy[0] else None)
        ax.scatter([va], [y], s=100, color=SER[0], edgecolor=SURF, linewidth=2, zorder=3,
                   label="distilled from Qwen (teacher)" if y == yy[0] else None)
        ax.text(vb - 0.01, y, f"{vb:.2f}", ha="right", va="center", fontsize=10)
        ax.text(va + 0.01, y, f"{va:.2f}", ha="left", va="center", fontsize=10)
    ax.set_yticks(yy, [p[0] for p in pairs])
    ax.set_xlim(0.6, 1.02)
    ax.set_title("Student AUROC on the benchmark")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=1, fontsize=9)
    fig.subplots_adjust(wspace=0.35)
    save(fig, "cascade_recall_curve_and_distillation")

    T.append("## 3. Fast filter / cascade (images)\n")
    T.append("| set | positives passed / blocked | negatives passed / blocked | recall [95 % CI] | false passes | sent to Qwen | time / image | gain |")
    T.append("|---|---|---|---|---|---|---|---|")
    for key, lab in (("benchmark_only", "120 benchmark images (50 %)"), ("mix", "579 images (10.4 %)")):
        m = ft[key]
        T.append(f"| {lab} | {m['positives_passed_TP']} / {m['positives_blocked_FN']} | {m['negatives_passed_FP']} / "
                 f"{m['negatives_blocked_TN']} | {m['recall']:.3f} [{m['recall_ci95'][0]:.3f}-{m['recall_ci95'][1]:.3f}] | "
                 f"{m['false_pass_rate']:.2f} | {m['sent_fraction'] * 100:.1f} % | {m['time_per_image_cascade_s']:.2f} s | ÷{m['speedup']} |")
    T.append(f"\nCascade {best} → Qwen v3 at 95 % on the benchmark: F1 {c95['f1']:.3f} vs {ja['f1']:.3f} for Qwen alone; "
             f"{c95['reference_positives_lost_by_filter']}/60 positives lost by the filter.\n")
    T.append("Student AUROC on the benchmark: distilled from Qwen " + ", ".join(
        f"{n} {cm['students'][n]['auroc_vs_reference']:.3f}" for n in ("T_logreg", "I_logreg", "IT_logreg", "I_mlp", "IT_mlp"))
        + " · trained on dataset labels " + ", ".join(
        f"{n.split('_')[0]} {cm['students'][n]['auroc_vs_reference']:.3f}" for n in
        ("T_logreg_datasetlabels", "I_logreg_datasetlabels", "IT_logreg_datasetlabels")) + ".\n")
    return ft, cm, c95, ja


# ---------------------------------------------------------------------------------------------------------------------
def part_time(R, T, rows_img, vm, ft):
    tim = J(RES / "video_racism_v1" / "qwen35-9b" / "timing.json")
    tm = J(RES / "cascade" / "train_metrics.json")
    lbl = J(RES / "cascade" / "label_stats.json")
    n_vid, vid_min = tim["videos"], tim["total_video_seconds"] / 60
    st = tim["per_stage_total_s"]
    stages = [("segmentation (PySceneDetect)", st["segmentation"]), ("frames + safety filter", st["frames_and_safety"]),
              ("Whisper large-v3-turbo", st["whisper"]), ("OCR (RapidOCR, CPU)", st["ocr"]),
              ("judge B (frames + text)", vm["B"]["judge_seconds"]), ("judge C (text only)", vm["C"]["judge_seconds"])]
    prep = sum(st.values())
    totB, totC = prep + vm["B"]["judge_seconds"], prep + vm["C"]["judge_seconds"]
    per_min_B, per_min_C = totB / vid_min, totC / vid_min
    fixed = (st["segmentation"] + st["frames_and_safety"] + st["whisper"]) / vid_min
    ocr_m, jb_m = st["ocr"] / vid_min, vm["B"]["judge_seconds"] / vid_min
    seg_per_min = tim["segments_per_video"] * n_vid / vid_min
    filt_min = seg_per_min * 3 * ft["filter_seconds_per_image"]  # hypothesis: image filter on 3 frames per segment
    hyp = {f: fixed + filt_min + f * (ocr_m + jb_m) for f in (0.2, 0.5)}

    img = [(r["label"] + " (judge, prompt v1)", 60 / r["throughput_items_per_min"]) for r in rows_img]
    v3 = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v3", variant="image_text", task="sexual")
    img.append(("Qwen3.5-9B (judge, prompt v3)", 60 / v3["throughput_items_per_min"]))
    img += [("filter only (SigLIP2 + logistic)", ft["filter_seconds_per_image"]),
            ("cascade · 50 % positive (benchmark)", ft["benchmark_only"]["time_per_image_cascade_s"]),
            ("cascade · 10.4 % positive", ft["mix"]["time_per_image_cascade_s"])]

    fig, axes = plt.subplots(1, 2, figsize=(15, 4.6), gridspec_kw={"width_ratios": [1, 1.05]})
    ax = axes[0]
    yy = list(range(len(img)))[::-1]
    cols = [SER[0]] * 5 + [SER[2], SER[1], SER[1]]
    for y, (lab, v), c in zip(yy, img, cols):
        ax.barh(y, v, color=c, height=0.6, edgecolor=SURF, linewidth=2)
        ax.text(v + 0.03, y, f"{v:.3f} s" if v < 0.1 else f"{v:.2f} s", va="center", fontsize=10)
    ax.set_yticks(yy, [i[0] for i in img], fontsize=10)
    ax.set_xlim(0, max(v for _, v in img) * 1.22)
    ax.set_xlabel("seconds per image (8 parallel judge requests)")
    ax.set_title("Images · time per image")
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    labs = [s[0] for s in stages[:4]] + ["judge B (frames + text)"]
    vals = [s[1] / vid_min for s in stages[:4]] + [vm["B"]["judge_seconds"] / vid_min]
    yy = list(range(len(labs)))[::-1]
    for y, lab, v in zip(yy, labs, vals):
        ax.barh(y, v, color=SER[0] if "judge" in lab else SER[2], height=0.6, edgecolor=SURF, linewidth=2)
        ax.text(v + 0.08, y, f"{v:.2f} s", va="center", fontsize=10)
    ax.set_yticks(yy, labs, fontsize=10)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_xlabel("seconds per minute of video")
    ax.set_title(f"Video (method B) · {per_min_B:.1f} s per minute of video")
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(wspace=0.75)
    save(fig, "compute_time_images_and_video", f"Hardware: {HW}. Image cascade times = filter + share sent × 1.51 s "
         "(Qwen v3, measured). Video: 30 HateMM videos, 45 min in total.")

    L = ["## 4. Compute time (hardware: " + HW + ", llama.cpp, Qwen3.5-9B Q8_0 + mmproj F16)\n",
         "### a) Images\n", "| system | seconds / image | images / min | gain vs Qwen3.5-9B v3 alone | source |", "|---|---|---|---|---|"]
    J3 = 60 / v3["throughput_items_per_min"]
    for lab, v in img:
        gain = "—" if "judge" in lab else f"÷{J3 / v:.2f}" if "cascade" in lab else f"÷{J3 / v:.0f}"
        src = "measured (benchmark run)" if "judge" in lab else ("measured (1 000 images)" if lab.startswith("filter")
                                                                  else "estimated: filter time + share sent × 1.51 s")
        L.append(f"| {lab} | {v:.3f} | {60 / v:.1f} | {gain} | {src} |")
    L += ["\n### b) Video (method B, 30 HateMM videos = " + f"{vid_min:.1f} min of video, {tim['segments_per_video']} segments / video)\n",
          "| stage | total (s) | seconds / video | seconds / minute of video |", "|---|---|---|---|"]
    for lab, v in stages:
        L.append(f"| {lab} | {v:.1f} | {v / n_vid:.1f} | {v / vid_min:.2f} |")
    L += [f"| **total B** (all stages + judge B) | {totB:.1f} | {totB / n_vid:.1f} | **{per_min_B:.1f}** |",
          f"| total C (all stages + judge C) | {totC:.1f} | {totC / n_vid:.1f} | {per_min_C:.1f} |",
          f"\n- **Speed vs real time:** method B processes video **{60 / per_min_B:.1f}× faster than real time** "
          f"(C: {60 / per_min_C:.1f}×).",
          f"- **For a 10-minute video (ESTIMATE, linear scaling of the measured per-minute rates):** method B ≈ "
          f"**{10 * per_min_B:.0f} s ({10 * per_min_B / 60:.1f} min)** for the full processing. The decision and the flagged "
          f"passage are available at the same time, since every segment must be judged before the maximum is taken "
          "(time to decision ≈ full processing time; not measured separately). Measured videos were ≤ 4 min: longer videos not measured.",
          "- **Video cascade: not measured (video cascade not executed).** HYPOTHESIS only (not measured): if the image "
          f"filter were applied to the 3 frames of every segment (+{filt_min:.2f} s / min, using the measured image-filter "
          f"rate) and only 20 % / 50 % of segments were sent to OCR + judge, the rate would be "
          f"**{hyp[0.2]:.1f} s / min (20 %)** and **{hyp[0.5]:.1f} s / min (50 %)** instead of {per_min_B:.1f} s / min, i.e. "
          f"÷{per_min_B / hyp[0.2]:.1f} and ÷{per_min_B / hyp[0.5]:.1f}; segmentation, frames and Whisper stay on the whole video.",
          "\n### c) Building the data and the students\n", "| step | time | source |", "|---|---|---|",
          f"| teacher labelling of the pool (Qwen3.5-9B v3, 3 000 images) | 72.1 min (41.6 images / min) | measured |",
          "| pool construction (sampling, pHash anti-leakage, safety filter) | not measured | — |",
          "| embeddings of the pool (text + image, 3 000) | 94.8 s | measured |",
          f"| student training ({len(tm['candidates'])} candidates, 5-fold CV on train) | {sum(c['fit_seconds'] for c in tm['candidates'].values()):.0f} s | measured |",
          "| students on dataset labels (bonus) | not measured | — |",
          f"| benchmark runs (120 images, 4 models × image + text) | " + ", ".join(
              f"{r['label']} {120 / r['throughput_items_per_min']:.1f} min" for r in rows_img) + " | measured |",
          f"| video preparation (30 videos: segments, frames, Whisper, OCR) | {prep:.0f} s | measured |",
          "| benchmark construction and hand confirmation (265 candidates) | not measured | — |",
          f"\nPool usable after exclusions: {lbl['labelled_usable']} images (train {lbl['teacher_sexual_by_part']['train']['n']}, "
          f"DEV {lbl['teacher_sexual_by_part']['dev']['n']}).\n"]
    T.extend(L)
    return {"per_min_B": per_min_B, "per_min_C": per_min_C, "rt_B": 60 / per_min_B, "ten_min_B": 10 * per_min_B,
            "hyp": hyp, "img": img, "J3": J3}


# ---------------------------------------------------------------------------------------------------------------------
def slides(rows_img, vid_rows, vm, ft, cm, c95, ja, tt):
    best = cm["best_student"]
    f1s = [r["f1"] for r in rows_img]
    au = [r["auroc"] for r in rows_img]
    B, C = vid_rows["B"], vid_rows["C"]
    mix, bo = ft["mix"], ft["benchmark_only"]
    dist = [cm["students"][n]["auroc_vs_reference"] for n in ("T_logreg", "I_logreg", "IT_logreg", "I_mlp", "IT_mlp")]
    dsl = [cm["students"][n]["auroc_vs_reference"] for n in ("T_logreg_datasetlabels", "I_logreg_datasetlabels", "IT_logreg_datasetlabels")]
    L = ["# Results for the slides / Résultats pour les slides", "",
         f"All numbers come from `docs/results/ALL_METRICS.csv` and the timing files; hardware {HW}. "
         "Figures: `docs/presentation/figures/<name>.png` (300 dpi) and `.pdf`.", "",
         "## 1. Images — the method works whatever the model", "",
         f"- **EN:** With the same frozen definition (prompt v1), four open vision models detect the sexual character of memes "
         f"with F1 {min(f1s):.2f}–{max(f1s):.2f} and AUROC {min(au):.2f}–{max(au):.2f} on 120 hand-validated images; "
         "no difference between them is statistically significant.",
         f"- **FR :** Avec la même définition figée (prompt v1), quatre modèles de vision ouverts détectent le caractère sexuel "
         f"des mèmes avec un F1 de {min(f1s):.2f} à {max(f1s):.2f} et une AUROC de {min(au):.2f} à {max(au):.2f} sur 120 images "
         "validées à la main ; aucune différence entre eux n'est significative.",
         f"- **EN:** The definition, not the model, drives the result: all four make the same main error (sexist but non-sexual memes read as sexual).",
         f"- **FR :** C'est la définition, pas le modèle, qui fait le résultat : les quatre font la même erreur principale (mèmes sexistes non sexuels lus comme sexuels).",
         "- **Numbers:** " + "; ".join(f"{r['label']} F1 {r['f1']:.3f} [{r['f1_ci'][0]:.2f}-{r['f1_ci'][1]:.2f}], AUROC {r['auroc']:.3f}, "
                                       f"{r['throughput_items_per_min']:.0f} img/min" for r in rows_img) + ".",
         "- **Figures:** `images_4models_confusions`, `images_4models_f1_auroc_ci`; annex `annex_images_v1_v3_and_text_only`.",
         "- **Limit:** 120 clear cases selected by keywords, reference annotated by Claude (20 checked by the team); public datasets (possible contamination).", "",
         "## 2. Video — segment-by-segment method (racism test)", "",
         f"- **EN:** Cutting a video into segments and judging each one (frames + transcript + on-screen text) flags racist "
         f"videos with F1 {B['f1']:.2f} ({B['TP']}/15 found, {B['FP']} false alarm) and AUROC {B['auroc']:.2f}; without the frames, F1 {C['f1']:.2f}.",
         f"- **FR :** En découpant la vidéo en segments jugés un par un (captures + transcription + texte à l'écran), on repère "
         f"les vidéos racistes avec un F1 de {B['f1']:.2f} ({B['TP']}/15 trouvées, {B['FP']} fausse alerte) et une AUROC de {B['auroc']:.2f} ; sans les captures, F1 {C['f1']:.2f}.",
         f"- **EN:** It runs {tt['rt_B']:.1f}× faster than real time on one V100 (≈ {tt['ten_min_B'] / 60:.1f} min for a 10-min video, estimate).",
         f"- **FR :** Elle tourne {tt['rt_B']:.1f} fois plus vite que le temps réel sur un V100 (≈ {tt['ten_min_B'] / 60:.1f} min pour une vidéo de 10 min, estimation).",
         f"- **Numbers:** B TP {B['TP']} FP {B['FP']} FN {B['FN']} TN {B['TN']}; C TP {C['TP']} FP {C['FP']} FN {C['FN']} TN {C['TN']}; "
         f"layer: speech {vm['B']['triggered_layer']['speech']}, on-screen text {vm['B']['triggered_layer']['on_screen_text']}, visuals {vm['B']['triggered_layer']['visuals']}; "
         f"localisation top-1 {vm['B']['localisation']['top1_hits']}/15, top-3 {vm['B']['localisation']['top3_hits']}/15.",
         "- **Figures:** `video_racism_confusions_roc`, `video_triggered_layer`.",
         "- **Limit:** racism ≠ sexual violence (the test validates the method); 30 videos; localisation NOT demonstrated (annotated passages cover 79 % of each video).", "",
         "## 3. Fast filter + judge (cascade, images)", "",
         f"- **EN:** A small filter distilled from Qwen reads {1 / ft['filter_seconds_per_image']:.0f} images/s; at 10 % prevalence it sends "
         f"{mix['sent_fraction'] * 100:.0f} % of images to the full judge, loses {mix['positives_blocked_FN']}/60 positives and halves the compute time (÷{mix['speedup']}).",
         f"- **FR :** Un petit filtre distillé de Qwen lit {1 / ft['filter_seconds_per_image']:.0f} images/s ; à 10 % de prévalence, il n'envoie que "
         f"{mix['sent_fraction'] * 100:.0f} % des images au juge complet, perd {mix['positives_blocked_FN']} positifs sur 60 et divise le temps de calcul par {mix['speedup']}.",
         f"- **EN:** Distillation matters: students trained on Qwen's labels reach AUROC {min(dist):.2f}–{max(dist):.2f}, vs {min(dsl):.2f}–{max(dsl):.2f} with the datasets' own labels.",
         f"- **FR :** La distillation compte : entraînés sur les étiquettes de Qwen, les étudiants atteignent une AUROC de {min(dist):.2f} à {max(dist):.2f}, contre {min(dsl):.2f} à {max(dsl):.2f} avec les labels des datasets.",
         f"- **Numbers:** cascade F1 {c95['f1']:.3f} vs {ja['f1']:.3f} Qwen alone (benchmark, 50 %: {bo['sent_fraction'] * 100:.0f} % sent, ÷{bo['speedup']}); "
         f"10.4 %: recall {mix['recall']:.3f} [{mix['recall_ci95'][0]:.2f}-{mix['recall_ci95'][1]:.2f}], false passes {mix['false_pass_rate']:.2f}.",
         "- **Figures:** `cascade_filter_50_vs_10pct`, `cascade_qwen_alone_vs_cascade`, `cascade_recall_curve_and_distillation`.",
         "- **Limit:** training labels = Qwen, not humans; the selected filter uses image features (research experiment, B5: never train on media); the 459 extra negatives are Qwen-labelled and the threshold was set on the same DEV.", "",
         "## 4. Compute time (1× V100 32 GB)", "",
         f"- **EN:** One image takes {tt['J3']:.2f} s with the full judge and {ft['filter_seconds_per_image']:.3f} s with the filter; the cascade brings it to "
         f"{mix['time_per_image_cascade_s']:.2f} s at 10 % prevalence (estimate). Video: {tt['per_min_B']:.1f} s of compute per minute of video.",
         f"- **FR :** Une image prend {tt['J3']:.2f} s avec le juge complet et {ft['filter_seconds_per_image']:.3f} s avec le filtre ; la cascade la ramène à "
         f"{mix['time_per_image_cascade_s']:.2f} s à 10 % de prévalence (estimation). Vidéo : {tt['per_min_B']:.1f} s de calcul par minute de vidéo.",
         "- **EN:** Video cascade not measured (not executed); hypothesis only: "
         f"{tt['hyp'][0.2]:.1f} s/min if 20 % of segments reach the judge, {tt['hyp'][0.5]:.1f} s/min if 50 %.",
         "- **FR :** Cascade vidéo non mesurée (non exécutée) ; hypothèse seulement : "
         f"{tt['hyp'][0.2]:.1f} s/min si 20 % des segments vont au juge, {tt['hyp'][0.5]:.1f} s/min si 50 %.",
         "- **Figure:** `compute_time_images_and_video`. Full table: `TABLES.md` section 4.",
         "- **Limit:** judge times with 8 parallel requests on one GPU; cascade times are estimates (filter + share sent × measured judge time); videos ≤ 4 min."]
    (OUT / "RESULTS_FOR_SLIDES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    CREATED.append(OUT / "RESULTS_FOR_SLIDES.md")


def main():
    R = metrics()
    OUT.mkdir(parents=True, exist_ok=True)
    T = ["# Tables for the presentation", "", f"Generated by `scripts/make_presentation.py` from `docs/results/`. Hardware: {HW}. "
         "\"not measured\" = the number does not exist; estimates and hypotheses are labelled as such.", ""]
    rows_img = part_images(R, T)
    vid_rows, vm = part_video(R, T)
    ft, cm, c95, ja = part_cascade(R, T)
    tt = part_time(R, T, rows_img, vm, ft)
    (OUT / "TABLES.md").write_text("\n".join(T) + "\n", encoding="utf-8")
    CREATED.append(OUT / "TABLES.md")
    slides(rows_img, vid_rows, vm, ft, cm, c95, ja, tt)
    zp = OUT / "presentation_pack.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and p != zp:
                z.write(p, p.relative_to(ROOT))
        for p in (RES / "ALL_METRICS.csv", RES / "ALL_CONFUSIONS.json"):
            z.write(p, p.relative_to(ROOT))
    CREATED.append(zp)
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zp, BACKUP / "presentation_pack_2026-09-27.zip")
    for p in CREATED:
        print(p.relative_to(ROOT))
    print("backup:", BACKUP / "presentation_pack_2026-09-27.zip")


if __name__ == "__main__":
    main()
