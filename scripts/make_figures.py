"""Presentation figures from docs/results/ALL_METRICS.csv and ALL_CONFUSIONS.json ONLY → docs/figures/*.png.

    python scripts/make_figures.py

No dataset image is ever read or drawn. Static PNGs for slides (light surface); colours: reference categorical order
(blue, orange, aqua, yellow) and a single-hue blue ramp for the confusion heatmaps. Values are printed on every mark
(identity and numbers never rely on colour alone).
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

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


def save(fig, name, note=None):
    if note:
        fig.text(0.01, -0.03, note, fontsize=7, color=INK2, ha="left", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / name)


def dot_panel(ax, labels, values, title, xlim, colors):
    """Cleveland dot plot: one row per entity, value printed next to each dot (no truncated bar)."""
    y = list(range(len(labels)))[::-1]
    for yi, v, c in zip(y, values, colors):
        ax.hlines(yi, xlim[0], v, color=GRID, lw=2, zorder=1)
        ax.scatter([v], [yi], s=80, color=c, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(v + (xlim[1] - xlim[0]) * 0.015, yi, f"{v:.3f}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, labels)
    ax.set_xlim(*xlim)
    ax.set_title(title)
    ax.grid(axis="y", visible=False)


def fig_models(R):
    rs = {r["model"]: r for r in pick(R, experiment="sv_images_v1", prompt="v1", variant="image_text", task="sexual")}
    models = [m for m in MODEL_ORDER if m in rs]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    colors = [SERIES[MODEL_ORDER.index(m)] for m in models]
    dot_panel(axes[0], [MODEL_LABEL[m] for m in models], [rs[m]["f1"] for m in models],
              "F1 · sexual character", (0.85, 1.0), colors)
    dot_panel(axes[1], [MODEL_LABEL[m] for m in models], [rs[m]["auroc"] for m in models],
              "AUROC · P(sexual) from logprobs", (0.85, 1.0), colors)
    fig.suptitle("Four vision models on sv_images_v1 (60 / 60, prompt v1 frozen, image + text)", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", y=1.04)
    save(fig, "models_f1_auroc.png", "Axes start at 0.85. Differences are not statistically significant "
                                     "(bootstrap 95% CIs overlap, McNemar p ≥ 0.6).")


def dumbbell(ax, labels, a, b, la, lb, title, xlim):
    y = list(range(len(labels)))[::-1]
    for yi, va, vb in zip(y, a, b):
        ax.plot([va, vb], [yi, yi], color=GRID, lw=3, zorder=1, solid_capstyle="round")
        ax.scatter([va], [yi], s=80, color=SERIES[0], edgecolor=SURFACE, linewidth=2, zorder=3,
                   label=la if yi == y[0] else None)
        ax.scatter([vb], [yi], s=80, color=SERIES[1], edgecolor=SURFACE, linewidth=2, zorder=3,
                   label=lb if yi == y[0] else None)
        lo, hi = sorted([(va, "a"), (vb, "b")])
        off = (xlim[1] - xlim[0]) * 0.02
        ax.text(lo[0] - off, yi, f"{lo[0]:.3f}", ha="right", va="center", fontsize=8, color=INK2)
        ax.text(hi[0] + off, yi, f"{hi[0]:.3f}", ha="left", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, labels)
    ax.set_xlim(*xlim)
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.14), ncol=2, fontsize=8)


def fig_v1_v3(R):
    labels, a, b = [], [], []
    for mode, mlab in (("image_text", "image + text"), ("text_only", "text only")):
        for metric, mname in (("f1", "F1"), ("auroc", "AUROC")):
            v1 = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v1", variant=mode, task="sexual")
            v3 = pick(R, experiment="sv_images_v1", model="qwen3.5-9b", prompt="v3", variant=mode, task="sexual")
            if v1 and v3:
                labels.append(f"{mname} · {mlab}")
                a.append(v1[0][metric])
                b.append(v3[0][metric])
    fig, ax = plt.subplots(figsize=(7, 3))
    dumbbell(ax, labels, a, b, "prompt v1 (official)", "prompt v3 (indicative)", "Qwen3.5-9B · prompt v1 vs v3", (0.84, 1.0))
    save(fig, "v1_vs_v3.png", "\n\nv3 was tuned after analysing the errors on this same set: its score is indicative only.")


def fig_image_vs_text(R):
    labels, a, b = [], [], []
    for m in MODEL_ORDER:
        it = pick(R, experiment="sv_images_v1", model=m, prompt="v1", variant="image_text", task="sexual")
        tx = pick(R, experiment="sv_images_v1", model=m, prompt="v1", variant="text_only", task="sexual")
        if it and tx:
            labels.append(MODEL_LABEL[m])
            a.append(tx[0]["f1"])
            b.append(it[0]["f1"])
    fig, ax = plt.subplots(figsize=(7, 3))
    dumbbell(ax, labels, a, b, "text only (embedded text)", "image + text", "F1 · what the image adds (prompt v1)", (0.84, 1.0))
    save(fig, "image_text_vs_text_only.png",
         "\n\n50 of 60 positives contain an explicit keyword: the benchmark mostly measures reading the embedded text.")


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
    rs = pick(R, experiment="cascade")
    if not rs:
        print("skip cascade: no cascade rows in ALL_METRICS.csv (students not trained yet)")
        return
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
    for k, kind in enumerate(sorted({r["variant"].split("_")[0] for r in rs})):
        sub = sorted((r for r in rs if r["variant"].startswith(kind)), key=lambda r: r["notes"])
        xs = [float(r["notes"].split("sent=")[1].split(";")[0]) for r in sub]
        axes[0].plot(xs, [r["recall"] for r in sub], marker="o", ms=8, lw=2, color=SERIES[k % 4], label=kind)
    axes[0].set_xlabel("share of images sent to the judge")
    axes[0].set_ylabel("recall")
    axes[0].set_title("Cascade · recall vs share sent to Qwen")
    axes[0].legend(fontsize=8)
    save(fig, "cascade.png")


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
        save(fig, name.replace(" ", "").replace(".", "").replace("≥", "") + ".png")


def main():
    R = rows()
    fig_models(R)
    fig_v1_v3(R)
    fig_image_vs_text(R)
    fig_video(R)
    fig_cascade(R)
    fig_confusions()


if __name__ == "__main__":
    main()
