"""Presentation figures from docs/results/ALL_METRICS.csv and ALL_CONFUSIONS.json → docs/figures/*.png.

    python scripts/make_figures.py

Bar charts carry 95 % CIs only where they were already computed: F1 CIs from docs/results/sv_images_v1/significance.json,
AUROC CIs by the same bootstrap as scripts/make_presentation.py (2 000 resamples, seed 42) on the per-item scores in
results/ (read only). No CI → no error bar, and the figure says "CI not available".

No dataset image is ever read or drawn. Static PNGs for slides (light surface); colours: reference categorical order
(blue, orange, aqua, yellow) and a single-hue blue ramp for the confusion heatmaps. Values are printed on every mark
(identity and numbers never rely on colour alone).
"""

import csv
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from make_presentation import NO_CI, SHOWN, bars, boot_auroc, jl  # noqa: E402  (before rcParams below)

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "docs" / "results"
FIG = ROOT / "docs" / "figures"

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed categorical order, never cycled
BLUE_RAMP = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
MODEL_ORDER = ["qwen3.5-9b", "qwen3.5-4b", "gemma-4-12b", "internvl3.5-8b"]
MODEL_LABEL = {"qwen3.5-9b": "Qwen3.5-9B", "qwen3.5-4b": "Qwen3.5-4B", "gemma-4-12b": "Gemma 4 12B",
               "internvl3.5-8b": "InternVL3.5-8B"}

plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False})


def rows() -> list[dict]:
    out = []
    for r in csv.DictReader(open(RES / "ALL_METRICS.csv", encoding="utf-8")):
        for k in ("TP", "FP", "FN", "TN", "n_pos", "n_neg"):
            r[k] = int(r[k]) if r[k] not in ("", None) else None
        for k in ("precision", "recall", "f1", "accuracy", "specificity", "auroc", "throughput_items_per_min"):
            r[k] = float(r[k]) if r[k] not in ("", None, "None") else None
        out.append(r)
    return out


def pick(R, **kw):
    return [r for r in R if all(r.get(k) == v for k, v in kw.items())]


def save(fig, name, note=None, hires=False):
    """hires: PNG 300 dpi + PDF (bar charts); otherwise PNG 160 dpi (unchanged figures)."""
    if note:
        fig.text(0.01, -0.03, note, fontsize=7, color=INK2, ha="left", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=300 if hires else 160, bbox_inches="tight")
    print("wrote", FIG / name)
    if hires:
        fig.savefig(FIG / name.replace(".png", ".pdf"), bbox_inches="tight")
        print("wrote", FIG / name.replace(".png", ".pdf"))
    plt.close(fig)


def subtitle(fig, text, y=0.95):
    fig.text(0.01, y, text, fontsize=9, color=INK2, ha="left", va="bottom")


FOLDER = {"qwen3.5-9b": "qwen35-9b", "qwen3.5-4b": "qwen35-4b", "gemma-4-12b": "gemma4-12b", "internvl3.5-8b": "internvl35-8b"}


def f1_ci(model, variant):
    sig = json.loads((RES / "sv_images_v1" / "significance.json").read_text())
    return sig.get(FOLDER[model], {}).get(variant, {}).get("ci95")


def auroc_ci(model):
    """Same bootstrap as make_presentation.py (image + text, prompt v1); None if the per-item scores are absent."""
    f = ROOT / "results" / "sv_benchmark" / FOLDER[model] / "image_text" / "predictions.jsonl"
    if not f.exists():
        return None
    preds = [p for p in jl(f) if p["prediction"]]
    return boot_auroc([int(p["reference"]["sexual"]) for p in preds],
                      [1.0 if p["prediction"]["possible_minor"] else p["prediction"]["p_true"]["sexual"] for p in preds])


def fig_models(R):
    rs = {r["model"]: r for r in pick(R, experiment="sv_images_v1", prompt="v1", variant="image_text", task="sexual")}
    models = [m for m in MODEL_ORDER if m in rs]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    bars(ax, [MODEL_LABEL[m] for m in models],
         [("F1 · sexual character", SERIES[0], [rs[m]["f1"] for m in models], [f1_ci(m, "image_text") for m in models]),
          ("AUROC · P(sexual) from logprobs", SERIES[1], [rs[m]["auroc"] for m in models], [auroc_ci(m) for m in models])],
         "Four vision models on sv_images_v1 (60 / 60, prompt v1 frozen, image + text)", "models_f1_auroc")
    subtitle(fig, "F1 and AUROC per model with bootstrap 95 % CIs: the four models are within each other's intervals.")
    save(fig, "models_f1_auroc.png", "\n\nError bars: bootstrap 95 % CIs (2 000 resamples). Differences are not "
                                     "statistically significant (CIs overlap, McNemar p ≥ 0.6).", hires=True)


def fig_v1_v3(R):
    labels, a, b, ci = [], [], [], []
    for mode, mlab in (("image_text", "image + text"), ("text_only", "text only")):
        for metric, mname in (("f1", "F1"), ("auroc", "AUROC")):
            v1 = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v1", variant=mode, task="sexual")
            v3 = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v3", variant=mode, task="sexual")
            if v1 and v3:
                labels.append(f"{mname}\n{mlab}")
                a.append(v1[0][metric])
                b.append(v3[0][metric])
                ci.append(f1_ci("qwen3.5-9b", mode) if metric == "f1" else
                          auroc_ci("qwen3.5-9b") if mode == "image_text" else None)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bars(ax, labels, [("prompt v1 (official)", SERIES[0], a, ci),
                      ("prompt v3 (indicative) · CI not available", SERIES[1], b, [None] * len(b))],
         "Qwen3.5-9B · prompt v1 vs v3", "v1_vs_v3")
    subtitle(fig, "F1 and AUROC of the frozen prompt v1 and the tuned prompt v3, with and without the image.")
    save(fig, "v1_vs_v3.png", "\n\nError bars: bootstrap 95 % CIs; " + NO_CI + " (prompt v3; AUROC text only). "
         "v3 was tuned after analysing the errors on this same set: its score is indicative only.", hires=True)


def fig_image_vs_text(R):
    labels, a, b, ca, cb = [], [], [], [], []
    for m in MODEL_ORDER:
        it = pick(R, experiment="sv_images_v1", model=m, prompt="v1", variant="image_text", task="sexual")
        tx = pick(R, experiment="sv_images_v1", model=m, prompt="v1", variant="text_only", task="sexual")
        if it and tx:
            labels.append(MODEL_LABEL[m])
            a.append(tx[0]["f1"])
            b.append(it[0]["f1"])
            ca.append(f1_ci(m, "text_only"))
            cb.append(f1_ci(m, "image_text"))
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bars(ax, labels, [("text only (embedded text)", SERIES[0], a, ca), ("image + text", SERIES[1], b, cb)],
         "F1 · what the image adds (prompt v1) [95 % CI]", "image_text_vs_text_only")
    subtitle(fig, "F1 per model when the judge reads only the embedded text vs when it also sees the image.")
    save(fig, "image_text_vs_text_only.png", "\n\nError bars: bootstrap 95 % CIs. 50 of 60 positives contain an "
         "explicit keyword: the benchmark mostly measures reading the embedded text.", hires=True)


def fig_video(R):
    rs = {r["variant"]: r for r in pick(R, experiment="video_racism_v1", task="racism")}
    if not rs:
        return
    metrics = ["precision", "recall", "f1", "specificity", "auroc"]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    x = range(len(metrics))
    for k, (v, lab) in enumerate((("B", "B · frames + transcript + OCR"), ("C", "C · transcript + OCR only"))):
        if v not in rs:
            continue
        vals = [rs[v][m] for m in metrics]
        xs = [i + (k - 0.5) * 0.28 for i in x]
        ax.bar(xs, vals, width=0.26, color=SERIES[k], label=lab, edgecolor=SURFACE, linewidth=2)
        for xi, val in zip(xs, vals):
            ax.text(xi, val + 0.015, f"{val:.2f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(list(x), ["precision", "recall", "F1", "specificity", "AUROC"])
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_title("Video racism test (HateMM, 15 racist / 15 non-racist) · video level")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, fontsize=8)
    ax.grid(axis="x", visible=False)
    save(fig, "video_B_vs_C.png", "\n\nLocalisation not demonstrated: HateMM snippets cover ~79% of each video "
                                  "(a random segment hits them 85% of the time).")


def fig_cascade(R):
    """Cascade: recall vs share sent to Qwen (v3 judge) and time per image, from the cascade rows only."""
    rs = pick(R, experiment="cascade_images", prompt="v3")
    casc = sorted((r for r in rs if r["variant"].startswith("cascade_")), key=lambda r: r["variant"])
    judge = [r for r in rs if r["variant"] == "judge_alone"]
    if not casc or not judge:
        print("skip cascade: no cascade rows in ALL_METRICS.csv")
        return
    field = lambda r, k: float(r["notes"].split(f"{k}=")[1].split(";")[0].split("/")[0])  # noqa: E731
    labels = ["Qwen v3 on\nevery image"] + [f"cascade\n{r['variant'].replace('cascade_', '')} %" for r in casc]
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"wspace": 0.25})
    bars(axes[0], labels,
         [("recall (benchmark)", SERIES[0], [judge[0]["recall"]] + [r["recall"] for r in casc], [None] * (len(casc) + 1)),
          ("share of images sent to Qwen", SERIES[1], [1.0] + [field(r, "sent") for r in casc], [None] * (len(casc) + 1))],
         "Cascade · recall vs share sent", "cascade", legend_cols=1)
    ax = axes[1]
    vals = [float(judge[0]["notes"].split("time/img=")[1])] + [field(r, "time/img") for r in casc]
    for xi, v, c in zip(range(len(vals)), vals, [SERIES[0]] + [SERIES[1]] * len(casc)):
        ax.bar(xi, v, color=c, width=0.55, edgecolor=SURFACE, linewidth=2)
        ax.text(xi, v + 0.02, f"{v:.2f} s", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(range(len(vals)), labels)
    ax.set_ylim(0, max(vals) * 1.2)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("seconds per image")
    ax.set_title("Time per image")
    subtitle(fig, "Student filter (DEV recall 95 / 97 / 99 %) in front of Qwen v3: recall kept, share of images sent "
             "and time per image.")
    save(fig, "cascade.png", "\n\n\n\nLeft: " + NO_CI + ". Qwen v3 alone sends 100 % of the images by definition. "
         "sv_images_v1 is 50 % positive: the filter must pass at least half of the images, which caps the speed-up.",
         hires=True)


def fig_confusions():
    C = json.loads((RES / "ALL_CONFUSIONS.json").read_text())
    key = {
        "sv_images_v1|qwen3.5-9b|v1|image_text|sexual": "Qwen3.5-9B · prompt v1 · image+text · sexual",
        "sv_images_v1|qwen3.5-9b|v3|image_text|sexual": "Qwen3.5-9B · prompt v3 (indicative) · image+text · sexual",
        "sv_images_v1|gemma-4-12b|v1|image_text|sexual": "Gemma 4 12B · prompt v1 · image+text · sexual",
        "video_racism_v1|qwen3.5-9b|racism_v1|B|racism": "Video racism · variant B (frames + text)",
        "video_racism_v1|qwen3.5-9b|racism_v1|C|racism": "Video racism · variant C (text only)",
        "baseline_general_core_only|qwen3.5-9b|core v1.4|text|sexual": "General examples · core only · sexual",
        "safety_explicit_filter|OR(CLIP≥0.9, AdamCodd≥0.7, Falconsai≥0.3)|-|default|explicit_image":
            "Explicit-image filter · retained default",
        "cascade_images|cascade I_logreg -> qwen3.5-9b|v3|cascade_95|sexual": "Cascade I_logreg → Qwen v3 (DEV recall 95 %)",
        "cascade_filter_test|filter I_logreg|-|filter_95_10pct|sexual_sent_to_judge": "Filter alone · 579 images, 10.4 % positive",
    }
    for c in C:
        if c["id"] not in key:
            continue
        v = c["matrix"]["values"]
        fig, ax = plt.subplots(figsize=(3.8, 3.4))
        ax.imshow(v, cmap=BLUE_RAMP, vmin=0, vmax=max(max(r) for r in v))
        ax.grid(False)
        for i, (row, tags) in enumerate(zip(v, (("TP", "FN"), ("FP", "TN")))):
            for j, (val, tag) in enumerate(zip(row, tags)):
                dark = val > 0.55 * max(max(r) for r in v)
                ax.text(j, i, f"{tag}\n{val}", ha="center", va="center", fontsize=13,
                        color="#ffffff" if dark else INK, fontweight="bold")
        pos, neg = c["labels"]["positive"], c["labels"]["negative"]
        ax.set_xticks([0, 1], [f"pred: {pos}", f"pred: {neg}"], fontsize=7)
        ax.set_yticks([0, 1], [f"ref: {pos}", f"ref: {neg}"], fontsize=7, rotation=90, va="center")
        ax.set_title(key[c["id"]], fontsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
        slug = c["id"].split("|")
        name = "confusion_" + "_".join(x for x in (slug[0], slug[1].split("(")[0], slug[2], slug[3], slug[4]) if x and x != "-")
        import re
        save(fig, re.sub(r"[^A-Za-z0-9_-]", "", name.replace("->", "_to_").replace(" ", "")) + ".png")


def main():
    R = rows()
    fig_models(R)
    fig_v1_v3(R)
    fig_image_vs_text(R)
    fig_video(R)
    fig_cascade(R)
    fig_confusions()
    if os.environ.get("SHOWN_JSON"):  # optional: values printed on the bar charts, for the check against ALL_METRICS.csv
        Path(os.environ["SHOWN_JSON"]).write_text(json.dumps(SHOWN, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
