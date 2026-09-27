"""Figures for a non-technical audience (jury, ICRC) → docs/presentation/figures_public/ (PNG 300 dpi + PDF, 16:9).

    python scripts/make_public_figures.py

One figure = one message: the title states the conclusion, a short caption box inside the figure says what was
measured, on what, and how to read it. No model is run and no metric is recomputed: numbers are read from
docs/results/ALL_METRICS.csv, the timing / metrics files in docs/results/, and (read only, as in make_presentation.py)
the per-item scores in results/ for the uncertainty ranges of the ranking quality, the video ROC and the pre-filter curve.
Every number printed on a figure is recorded and checked against a fresh read of ALL_METRICS.csv (table in INDEX.md).
The older figures are kept; the presentation zip is rebuilt with this folder added.
"""

import csv
import json
import shutil
import textwrap
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from make_presentation import boot_auroc, jl  # noqa: E402  (same bootstrap: 2 000 resamples, seed 42)

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "docs" / "results"
RAW = ROOT / "results"
PRES = ROOT / "docs" / "presentation"
OUT = PRES / "figures_public"
BACKUP = Path("/dlabscratch1/gmikou/backups")

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
# same colour = same thing, in every figure
JUDGE = "#2a78d6"      # AI judge, full input (image + text / images + speech + on-screen text), first version
TEXT = "#86b6ef"       # AI judge reading text only (meme text / speech + on-screen text)
V3 = "#0d366b"         # improved version of the definition (indicative)
FILTER = "#eda100"     # fast pre-filter / two-step system
OTHER = "#a9a8a3"      # comparison baseline (original dataset labels, image + text pre-filter)
CELL = {"ok": ("#d4f0e3", "#0f6b49"), "err": ("#fde0d3", "#a8401a"), "work": ("#fbeccb", "#7a5200")}
W, H = 13.333, 7.5
MODELS = [("qwen3.5-9b", "qwen35-9b", "Qwen3.5-9B"), ("qwen3.5-4b", "qwen35-4b", "Qwen3.5-4B"),
          ("gemma-4-12b", "gemma4-12b", "Gemma 4 12B"), ("internvl3.5-8b", "internvl35-8b", "InternVL3.5-8B")]
WORD = {1: "one", 2: "two", 3: "three", 4: "four"}

plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "font.size": 15,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK, "ytick.color": INK2,
                     "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "xtick.labelsize": 15,
                     "ytick.labelsize": 14, "axes.labelsize": 15})

REC: list[dict] = []   # every number printed: figure, what, shown text, source spec
INDEX: list[dict] = []
FILES: list[Path] = []


# --- sources ---------------------------------------------------------------------------------------------------------
def metrics() -> list[dict]:
    return list(csv.DictReader(open(RES / "ALL_METRICS.csv", encoding="utf-8")))


def row(R, **kw) -> dict:
    out = [r for r in R if all(r[k] == v for k, v in kw.items())]
    assert len(out) == 1, (kw, len(out))
    return out[0]


def note(r, key) -> float:
    """Numeric field of the ALL_METRICS 'notes' column, e.g. sent=0.733 or time/img=1.508."""
    return float(r["notes"].split(f"{key}=")[1].split(";")[0].split("/")[0])


def J(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def rec(fig, what, shown, src, key=None, col=None, f=None):
    """src: 'csv' (key + column of ALL_METRICS.csv, optional transform f of the raw value) or a file description."""
    REC.append({"figure": fig, "what": what, "shown": shown, "src": src, "key": key, "col": col, "f": f})
    return shown


# --- layout ----------------------------------------------------------------------------------------------------------
def frame(title, subtitle, caption, legend_room=False):
    """16:9 figure: conclusion title, subtitle, caption box at the bottom; returns (fig, [left, bottom, width, height])."""
    fig = plt.figure(figsize=(W, H))
    t = textwrap.wrap(title, 58)
    fig.text(0.04, 0.955, "\n".join(t), fontsize=25, fontweight="bold", va="top", ha="left", linespacing=1.15)
    y = 0.955 - 0.068 * len(t) - 0.012
    fig.text(0.04, y, subtitle, fontsize=16, color=INK2, va="top", ha="left")
    c = textwrap.wrap(caption, 118)
    fig.text(0.04, 0.035, "\n".join(c), fontsize=13.5, va="bottom", ha="left", color=INK, linespacing=1.35,
             bbox={"boxstyle": "round,pad=0.7", "facecolor": "#f1f0ec", "edgecolor": GRID})
    bottom = 0.035 + 0.036 * len(c) + 0.13
    top = y - 0.075 - (0.05 if legend_room else 0)
    return fig, [0.10, bottom, 0.86, top - bottom]


def save(fig, name, title, message, slide):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        p = OUT / f"{name}.{ext}"
        fig.savefig(p, dpi=300)
        FILES.append(p)
    plt.close(fig)
    INDEX.append({"file": name, "title": title, "message": message, "slide": slide})


def bars(ax, figname, groups, series, ylabel, ymax=1.0, fmt="{:.3f}", unit="", legend=True):
    """Vertical bars; series = [(label, colour, values, ranges, specs)]; ranges[i] = [lo, hi] or None (no error bar);
    specs[i] = (src, key, col, f) for the check of the printed value."""
    n, x = len(series), np.arange(len(groups))
    w = 0.8 / n
    for k, (lab, col, vals, rng, specs) in enumerate(series):
        xs = x + (k - (n - 1) / 2) * w
        ax.bar(xs, vals, width=w * 0.88, color=col, label=lab, zorder=2)
        for xi, g, v, r, s in zip(xs, groups, vals, rng, specs):
            if r:
                ax.errorbar(xi, v, yerr=[[v - r[0]], [r[1] - v]], fmt="none", ecolor=INK, elinewidth=1.8, capsize=7,
                            zorder=3)
            shown = fmt.format(v) + unit
            ax.text(xi, (r[1] if r else v) + ymax * 0.015, shown, ha="center", va="bottom", fontsize=15,
                    fontweight="bold", color=INK)
            rec(figname, f"{g.replace(chr(10), ' ')} · {lab}", shown, *s)
    ax.set_xticks(x, groups)
    ax.set_ylim(0, ymax * 1.12)
    ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0] if ymax == 1.0 else None
    ax.set_yticks(ticks if ticks else [t for t in ax.get_yticks() if 0 <= t <= ymax])
    ax.spines["left"].set_bounds(0, ymax)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", length=0, pad=8)
    if legend and n > 1:
        ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=n, fontsize=15, handlelength=1.2)


def matrix(ax, figname, v, rows, cols, names, kinds, specs, big=50, small=16, xlabel="What the AI decided",
           ylabel="What a human decided", show_row_labels=True):
    """2 × 2 table of counts; green = right answer, orange = mistake, yellow = extra work (not a mistake)."""
    ax.set_xlim(0, 2)
    ax.set_ylim(2, 0)
    ax.axis("off")
    for i in range(2):
        for j in range(2):
            face, ink = CELL[kinds[i][j]]
            ax.add_patch(Rectangle((j + 0.03, i + 0.03), 0.94, 0.94, facecolor=face, edgecolor="none"))
            shown = str(v[i][j])
            ax.text(j + 0.5, i + 0.44, shown, ha="center", va="center", fontsize=big, fontweight="bold", color=ink)
            ax.text(j + 0.5, i + 0.80, names[i][j], ha="center", va="center", fontsize=small, color=ink)
            rec(figname, f"{rows[i]} / {cols[j]} ({names[i][j]})", shown, *specs[i][j])
    for j, c in enumerate(cols):
        ax.text(j + 0.5, -0.06, c, ha="center", va="bottom", fontsize=small, fontweight="bold")
    ax.text(1, -0.30, xlabel, ha="center", va="bottom", fontsize=small, color=INK2)
    if show_row_labels:
        for i, r in enumerate(rows):
            ax.text(-0.06, i + 0.5, r, ha="right", va="center", fontsize=small, fontweight="bold")
        ax.text(-0.06, -0.06, ylabel, ha="right", va="bottom", fontsize=small, color=INK2)


def cm_specs(key):
    return [[("csv", key, "TP"), ("csv", key, "FN")], [("csv", key, "FP"), ("csv", key, "TN")]]


def cm_values(r):
    return [[int(r["TP"]), int(r["FN"])], [int(r["FP"]), int(r["TN"])]]


# --- images ----------------------------------------------------------------------------------------------------------
IMG_SUB = "Four open-source AI models · 120 hand-checked memes"
IMG_BASE = ("We showed 120 memes, checked by hand (60 with sexual content, 60 without), to each AI model, which saw the "
            "image and the text written on it.")


def images(R):
    sig = J(RES / "sv_images_v1" / "significance.json")
    key = lambda m, p="v1", v="image_text": dict(experiment="sv_images_v1", model=m, prompt=p, variant=v, task="sexual")  # noqa: E731
    rows, auroc_rng = [], {}
    for mid, folder, lab in MODELS:
        preds = [p for p in jl(RAW / "sv_benchmark" / folder / "image_text" / "predictions.jsonl") if p["prediction"]]
        auroc_rng[mid] = boot_auroc([int(p["reference"]["sexual"]) for p in preds],
                                    [1.0 if p["prediction"]["possible_minor"] else p["prediction"]["p_true"]["sexual"]
                                     for p in preds])
        rows.append((mid, folder, lab, row(R, **key(mid))))
    labs = [lab for _, _, lab, _ in rows]

    # 1. accuracy score
    name = "01_models_accuracy_score"
    title = "All four AI models recognise sexual content in memes equally well"
    fig, rect = frame(title, IMG_SUB, IMG_BASE + " Bars show the accuracy score (F1): the balance between catching "
                      "harmful memes and avoiding false alarms (1.0 = perfect). Black lines show the uncertainty range; "
                      "the ranges overlap, so the differences are not statistically significant.")
    bars(fig.add_axes(rect), name, labs,
         [("image + text", JUDGE, [float(r["f1"]) for *_, r in rows], [sig[f]["image_text"]["ci95"] for _, f, _, _ in rows],
           [("csv", key(m), "f1") for m, *_ in rows])], "Accuracy score (F1)\n1.0 = perfect")
    save(fig, name, title, "The four models score between 0.898 and 0.918; their uncertainty ranges overlap.",
         "Images · which AI model?")

    # 2. ranking quality
    name = "02_models_ranking_quality"
    title = "All four AI models' confidence separates harmful from harmless memes very well"
    fig, rect = frame(title, IMG_SUB, "Same 120 hand-checked memes. Besides its yes / no answer, each model gives a "
                      "confidence score. Bars show the ranking quality (AUROC): how well this confidence puts harmful "
                      "memes above harmless ones (1.0 = perfect, 0.5 = chance). Black lines show the uncertainty range.")
    bars(fig.add_axes(rect), name, labs,
         [("image + text", JUDGE, [float(r["auroc"]) for *_, r in rows], [auroc_rng[m] for m, *_ in rows],
           [("csv", key(m), "auroc") for m, *_ in rows])], "Ranking quality (AUROC)\n1.0 = perfect")
    save(fig, name, title, "Ranking quality from 0.948 to 0.975: the confidence score can be used to prioritise review.",
         "Images · which AI model?")

    # 3. four tables side by side
    name = "03_models_right_and_wrong_answers"
    acc = [float(r["accuracy"]) for *_, r in rows]
    title = "All four AI models classify about 9 out of 10 memes correctly"
    for (m, *_), a in zip(rows, acc):
        rec(name, f"title: about 9 out of 10 correct ({m} accuracy)", f"{a:.3f}", "csv", key(m), "accuracy")
    fig, rect = frame(title, IMG_SUB, "Each square counts memes out of the 120 hand-checked memes (60 harmful, 60 "
                      "harmless). Rows: what a human decided. Columns: what the AI decided. Green squares are right "
                      "answers; orange squares are mistakes (harmful memes missed, false alarms).")
    left, bottom, width, height = rect
    for k, (m, _, lab, r) in enumerate(rows):
        ax = fig.add_axes([0.15 + k * 0.212, bottom, 0.18, height * 0.80])
        matrix(ax, name, cm_values(r), ["Harmful (60)", "Harmless (60)"], ["AI: flagged", "AI: not flagged"],
               [["Correctly flagged", "Missed"], ["False alarm", "Correctly ignored"]], [["ok", "err"], ["err", "ok"]],
               cm_specs(key(m)), big=30, small=11, xlabel="", show_row_labels=(k == 0))
        ax.text(1, -0.30, lab, ha="center", va="bottom", fontsize=16, fontweight="bold")
    save(fig, name, title, "Each model gets 107 to 110 of the 120 memes right; errors are split between misses and false alarms.",
         "Images · which AI model?")

    # 4. one table per model
    for m, folder, lab, r in rows:
        name = f"04_right_and_wrong_answers_{folder}"
        title = f"{lab} catches {r['TP']} of 60 harmful memes and raises {r['FP']} false alarms"
        rec(name, "title: caught", r["TP"], "csv", key(m), "TP")
        rec(name, "title: false alarms", r["FP"], "csv", key(m), "FP")
        fig, rect = frame(title, IMG_SUB, IMG_BASE + " Rows: what a human decided. Columns: what the AI decided. "
                          "Green: right answers; orange: mistakes. Our definition, first version, frozen before the test.")
        left, bottom, width, height = rect
        matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(r), ["Harmful (60)", "Harmless (60)"],
               ["Flagged", "Not flagged"], [["Correctly flagged", "Missed"], ["False alarm", "Correctly ignored"]],
               [["ok", "err"], ["err", "ok"]], cm_specs(key(m)), big=46, small=16)
        save(fig, name, title, f"{lab}: {r['TP']} of 60 harmful memes caught, {r['FP']} of 60 harmless memes wrongly flagged.",
             "Images · detail per model (backup)")

    # 5. text only vs image + text
    name = "05_image_adds_little_to_text"
    title = "Seeing the image adds little: the text written on the meme does most of the work"
    fig, rect = frame(title, IMG_SUB, "Same 120 memes. Light blue: the model only read the text written on the meme. "
                      "Blue: it also saw the image. Bars show the accuracy score (F1, 1.0 = perfect); black lines show the "
                      "uncertainty range. 50 of the 60 harmful memes contain an explicit word, so this test mostly "
                      "measures reading the text.", legend_room=True)
    tx = [row(R, **key(m, v="text_only")) for m, *_ in rows]
    bars(fig.add_axes(rect), name, labs,
         [("text only", TEXT, [float(t["f1"]) for t in tx], [sig[f]["text_only"]["ci95"] for _, f, _, _ in rows],
           [("csv", key(m, v="text_only"), "f1") for m, *_ in rows]),
          ("image + text", JUDGE, [float(r["f1"]) for *_, r in rows], [sig[f]["image_text"]["ci95"] for _, f, _, _ in rows],
           [("csv", key(m), "f1") for m, *_ in rows])], "Accuracy score (F1)\n1.0 = perfect")
    save(fig, name, title, "Adding the image changes the score by at most 0.021 and the ranges overlap: the meme text "
         "carries most of the signal on this set.", "Images · what does the AI rely on?")

    # 6. first version vs improved version of the definition
    name = "06_improved_definition"
    title = "The improved definition scores slightly higher in most cases (indicative only)"
    groups, a, b, ra, sa, sb = [], [], [], [], [], []
    for mode, ml in (("image_text", "image + text"), ("text_only", "text only")):
        for col, cl in (("f1", "Accuracy score (F1)"), ("auroc", "Ranking quality (AUROC)")):
            groups.append(f"{cl}\n{ml}")
            a.append(float(row(R, **key("qwen3.5-9b", "v1", mode))[col]))
            b.append(float(row(R, **key("qwen3.5-9b", "v3", mode))[col]))
            ra.append(sig["qwen35-9b"][mode]["ci95"] if col == "f1" else auroc_rng["qwen3.5-9b"] if mode == "image_text" else None)
            sa.append(("csv", key("qwen3.5-9b", "v1", mode), col))
            sb.append(("csv", key("qwen3.5-9b", "v3", mode), col))
    fig, rect = frame(title, "Qwen3.5-9B · 120 hand-checked memes", "Our definition, first version (blue) against an "
                      "improved version (dark blue). Indicative only: the improved version was tuned after looking at the "
                      "mistakes on these same memes, so it is expected to do better here. Black lines: uncertainty range "
                      "(not available where there is no line). 1.0 = perfect.", legend_room=True)
    ax = fig.add_axes(rect)
    bars(ax, name, groups, [("first version", JUDGE, a, ra, sa), ("improved version (indicative)", V3, b, [None] * 4, sb)],
         "Score (1.0 = perfect)")
    ax.tick_params(axis="x", labelsize=13)
    save(fig, name, title, "The improved definition is higher on 3 of 4 scores, lower on the accuracy score with text "
         "only; indicative because it was tuned on these memes.", "Images · annex")


# --- video -----------------------------------------------------------------------------------------------------------
VID_SUB = "Qwen3.5-9B · 30 public videos (15 racist, 15 not)"
VID_WHY = "The video test uses racism because no open video dataset on sexual violence exists."


def video(R):
    from sklearn.metrics import roc_auc_score, roc_curve

    key = lambda v: dict(experiment="video_racism_v1", model="qwen3.5-9b", prompt="racism_v1", variant=v, task="racism")  # noqa: E731
    B, C = row(R, **key("B")), row(R, **key("C"))
    names = [["Correctly flagged", "Missed"], ["False alarm", "Correctly ignored"]]
    rows_ = ["Racist (15)", "Not racist (15)"]
    for r, v, name, how, title in (
            (B, "B", "07_video_images_speech_text", "images from each scene, the speech and the on-screen text",
             f"The AI finds all {B['TP']} racist videos and makes {WORD[int(B['FP'])]} false alarm"
             + ("s" if int(B["FP"]) > 1 else "")),
            (C, "C", "08_video_speech_text_only", "only the speech and the on-screen text (no images)",
             f"Without the images, the AI still finds all {C['TP']} racist videos but makes {WORD[int(C['FP'])]} false alarms")):
        rec(name, "title: racist videos found", r["TP"], "csv", key(v), "TP")
        rec(name, "title: false alarms", str(int(r["FP"])), "csv", key(v), "FP")
        sub = "images + speech + on-screen text" if v == "B" else "speech + on-screen text only"
        fig, rect = frame(title, f"{VID_SUB} · {sub}", f"Short public videos, up to 4 minutes long. The AI used {how}. "
                          f"{VID_WHY} With only 30 videos, each mistake moves the scores a lot.")
        left, bottom, width, height = rect
        matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(r), rows_, ["Flagged", "Not flagged"],
               names, [["ok", "err"], ["err", "ok"]], cm_specs(key(v)), big=46, small=16)
        save(fig, name, title, f"{sub}: {r['TP']}/15 racist videos found, {r['FP']}/15 harmless videos flagged.",
             "Video · does it work on video?")

    # 9. ROC
    name = "09_video_confidence_ranking"
    title = "The AI's confidence separates racist from non-racist videos perfectly"
    fig, rect = frame(title, VID_SUB, "Each video gets a confidence score (its most suspicious scene). Lowering the alert "
                      "threshold moves along the curve: up = more racist videos caught, right = more harmless videos "
                      "flagged. A curve through the top-left corner is perfect (ranking quality 1.0); the dashed line is "
                      f"chance. Both setups give the same curve. {VID_WHY}")
    left, bottom, width, height = rect
    ax = fig.add_axes([0.12, bottom, height * H / W, height])
    for v, col, lw, lab in (("B", JUDGE, 9, "images + speech + on-screen text"), ("C", TEXT, 3.5, "speech + on-screen text only")):
        vids = jl(RAW / "videos" / "racism_v1" / "qwen35-9b" / v / "predictions_videos.jsonl")
        y, s = [int(x["reference"]["racist"]) for x in vids], [x["score"] or 0.0 for x in vids]
        fpr, tpr, _ = roc_curve(y, s)
        au = roc_auc_score(y, s)
        shown = f"{au:.1f}"
        rec(name, f"ranking quality · {lab}", shown, "csv", key(v), "auroc")
        ax.plot(fpr, tpr, lw=lw, color=col, drawstyle="steps-post", label=f"{lab} · ranking quality {shown}",
                zorder=2 if v == "B" else 3, solid_capstyle="round")
    ax.plot([0, 1], [0, 1], ls="--", lw=1.5, color=INK2)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("share of harmless videos flagged (false alarms)")
    ax.set_ylabel("share of racist videos caught")
    ax.legend(loc="center left", bbox_to_anchor=(1.04, 0.5), fontsize=14)
    save(fig, name, title, "Ranking quality 1.0 with and without the images: every racist video scores above every "
         "harmless one (only 30 videos).", "Video · does it work on video?")

    # 10. which part of the video carried the racist content
    vm = J(RES / "video_racism_v1" / "qwen35-9b" / "metrics.json")
    tl = vm["B"]["triggered_layer"]
    name = "10_video_what_carries_racism"
    title = "In these videos, racism was mostly spoken, rarely shown in the images"
    fig, rect = frame(title, f"{VID_SUB} · images + speech + on-screen text", "Scenes the AI judged racist, counted by "
                      "the part of the video that carried the racist content. The videos were cut into scenes (about 6 "
                      f"per video). {VID_WHY}")
    vals = [tl["speech"], tl["on_screen_text"], tl["visuals"]]
    src = "docs/results/video_racism_v1/qwen35-9b/metrics.json (triggered_layer, B)"
    bars(fig.add_axes(rect), name, ["speech", "on-screen text", "images"],
         [("racist scenes", JUDGE, vals, [None] * 3, [(src,)] * 3)], "number of scenes judged racist",
         ymax=max(vals), fmt="{:d}")
    save(fig, name, title, "89 racist scenes were carried by speech, 24 by on-screen text, 1 by the images: "
         "speech-to-text is essential.", "Video · what does the AI rely on?")


# --- pre-filter and two-step system ------------------------------------------------------------------------------------
PF_WHAT = ("Two-step system: a fast pre-filter looks at each image first and passes only suspicious memes to the AI "
           "judge (Qwen3.5-9B).")


def prefilter(R):
    k10 = dict(experiment="cascade_filter_test", model="filter I_logreg", variant="filter_95_10pct")
    k50 = dict(experiment="cascade_filter_test", model="filter I_logreg", variant="filter_95_50pct")
    f10, f50 = row(R, **k10), row(R, **k50)
    cols = ["Passed to the AI judge", "Set aside"]
    names = [["Passed on", "Missed"], ["Extra work for the judge", "Correctly set aside"]]
    kinds = [["ok", "err"], ["work", "ok"]]

    name = "11_prefilter_halves_the_work"
    title = f"A fast pre-filter halves the work of the AI judge, missing {f10['FN']} of 60 harmful memes"
    rec(name, "title: missed", f10["FN"], "csv", k10, "FN")
    sent = f"{note(f10, 'sent') * 100:.0f} %"
    rec(name, "caption: share passed on", sent, "csv", k10, "notes", ("note_pct", "sent"))
    share = f"{int(f10['n_pos']) / (int(f10['n_pos']) + int(f10['n_neg'])) * 100:.0f} %"
    rec(name, "caption: share of harmful content in the feed", share, "csv", k10, "n_pos", ("prevalence",))
    fig, rect = frame(title, "Simulated feed · 579 memes · share of harmful content in the feed: " + share,
                      f"{PF_WHAT} Feed: the 120 hand-checked memes plus 459 harmless ones, so {share} is harmful. "
                      f"The pre-filter passed {sent} of the memes on. The 459 extra memes were labelled by the AI judge, "
                      "not checked by hand: this is an estimate.")
    left, bottom, width, height = rect
    matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(f10),
           [f"Harmful ({int(f10['TP']) + int(f10['FN'])})", f"Harmless ({int(f10['FP']) + int(f10['TN'])})"], cols, names,
           kinds, cm_specs(k10), big=44, small=15, xlabel="What the pre-filter decided")
    save(fig, name, title, f"In a feed with {share} harmful content, the judge only sees {sent} of the memes and 58 of "
         "60 harmful memes still reach it.", "Speed · two-step system")

    name = "12_prefilter_balanced_set"
    s50 = f"{note(f50, 'sent') * 100:.0f} %"
    title = "When half of the memes are harmful, the pre-filter saves only about a quarter of the work"
    rec(name, "title: about a quarter saved (1 - share passed on)", f"{(1 - note(f50, 'sent')) * 100:.0f} %", "csv", k50,
        "notes", ("note_pct_saved", "sent"))
    rec(name, "caption: share passed on", s50, "csv", k50, "notes", ("note_pct", "sent"))
    fig, rect = frame(title, "120 hand-checked memes · share of harmful content: 50 %",
                      f"{PF_WHAT} On the 120 hand-checked memes (half harmful), it passed {s50} of them on and missed "
                      f"{f50['FN']} harmful memes. Real feeds contain far less harmful content, so the saving is larger "
                      "there (see the 10 % feed).")
    rec(name, "caption: missed", f50["FN"], "csv", k50, "FN")
    left, bottom, width, height = rect
    matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(f50), ["Harmful (60)", "Harmless (60)"],
           cols, names, kinds, cm_specs(k50), big=46, small=15, xlabel="What the pre-filter decided")
    save(fig, name, title, f"On a set that is half harmful, {s50} of memes must still go to the judge.",
         "Speed · two-step system (backup)")

    kj = dict(experiment="cascade_images", model="qwen3.5-9b", prompt="v3", variant="judge_alone")
    kc = dict(experiment="cascade_images", model="cascade I_logreg -> qwen3.5-9b", prompt="v3", variant="cascade_95")
    ja, c95 = row(R, **kj), row(R, **kc)
    names = [["Correctly flagged", "Missed"], ["False alarm", "Correctly ignored"]]
    ok = [["ok", "err"], ["err", "ok"]]
    name = "13_judge_alone"
    title = f"The AI judge alone catches {ja['TP']} of 60 harmful memes, with {ja['FP']} false alarms"
    rec(name, "title: caught", ja["TP"], "csv", kj, "TP")
    rec(name, "title: false alarms", ja["FP"], "csv", kj, "FP")
    fig, rect = frame(title, "Qwen3.5-9B · 120 hand-checked memes · reference for the two-step system",
                      "The AI judge checks every meme, with the improved version of our definition (indicative only: it "
                      "was tuned on these memes). Rows: what a human decided; columns: what the AI decided. Green: right "
                      "answers; orange: mistakes.")
    left, bottom, width, height = rect
    matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(ja), ["Harmful (60)", "Harmless (60)"],
           ["Flagged", "Not flagged"], names, ok, cm_specs(kj), big=46, small=16)
    save(fig, name, title, "Reference: the judge alone, checking all 120 memes.", "Speed · two-step system")

    name = "14_two_step_system"
    s = f"{note(c95, 'sent') * 100:.0f} %"
    title = f"The two-step system catches {c95['TP']} of 60 harmful memes while the AI judge sees only {s} of them"
    rec(name, "title: caught", c95["TP"], "csv", kc, "TP")
    rec(name, "title: share seen by the judge", s, "csv", kc, "notes", ("note_pct", "sent"))
    lost = int(note(c95, "lost"))
    rec(name, "caption: set aside by the pre-filter", str(lost), "csv", kc, "notes", ("note_int", "lost"))
    rec(name, "caption: missed by the judge", str(int(c95["FN"]) - lost), "csv", kc, "FN", ("minus_lost",))
    rec(name, "caption: false alarms", c95["FP"], "csv", kc, "FP")
    fig, rect = frame(title, "Two-step system: fast pre-filter, then AI judge · 120 hand-checked memes",
                      f"{PF_WHAT} The pre-filter set aside {lost} harmful memes and the judge missed "
                      f"{int(c95['FN']) - lost} others; false alarms stay at {c95['FP']}. The judge uses the improved "
                      "version of our definition (indicative only: tuned on these memes).")
    left, bottom, width, height = rect
    matrix(fig.add_axes([0.36, bottom, 0.40, height * 0.86]), name, cm_values(c95), ["Harmful (60)", "Harmless (60)"],
           ["Flagged", "Not flagged"], names, ok, cm_specs(kc), big=46, small=16, xlabel="What the two-step system decided")
    save(fig, name, title, f"Two harmful memes are lost by the pre-filter; in exchange the judge sees only {s} of the memes.",
         "Speed · two-step system")

    # 15. curve
    cm = J(RAW / "cascade" / "metrics.json")  # per-item pre-filter scores (read only)
    ref = {b["item_id"]: b["reference"]["sexual"] for b in jl(ROOT / "data" / "benchmarks" / "sv_images_v1.jsonl")}
    name = "15_prefilter_curve"
    title = "Pre-filters that look at the image catch harmful memes sooner than one that reads only the text"
    fig, rect = frame(title, "Three fast pre-filters · 120 hand-checked memes (half harmful)",
                      "Each line is a fast pre-filter. Moving right, it passes more of the memes to the AI judge; moving "
                      "up, more harmful memes get through to the judge. Higher and further left is better. The dotted "
                      "line marks half of the memes. The image-only pre-filter is the one used in the two-step system.")
    left, bottom, width, height = rect
    ax = fig.add_axes([0.14, bottom, 0.50, height])
    for st, col, lab in (("T_logreg", TEXT, "reads the text only"), ("IT_logreg", OTHER, "image + text"),
                         ("I_logreg", FILTER, "looks at the image only (used)")):
        sc = cm["students"][st]["scores"]
        ids = list(sc)
        s_, y = np.array([sc[i] for i in ids]), np.array([ref[i] for i in ids])
        ts = np.sort(s_)[::-1]
        ax.plot([(s_ >= t).mean() for t in ts], [(y & (s_ >= t)).sum() / y.sum() for t in ts], lw=4, color=col, label=lab)
    ax.axvline(0.5, ls=":", color=INK2, lw=1.5)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.03)
    ax.set_xlabel("share of memes passed to the AI judge")
    ax.set_ylabel("share of harmful memes passed on")
    ax.legend(loc="center left", bbox_to_anchor=(1.04, 0.5), fontsize=15)
    save(fig, name, title, "At equal workload, the image-based pre-filters let more harmful memes through to the judge "
         "than the text-only one.", "Speed · two-step system (backup)")

    # 16. learned from the judge vs from the original labels
    name = "16_prefilter_learns_from_judge"
    title = "The pre-filter learns much better from the AI judge than from the original dataset labels"
    ks = lambda n: dict(experiment="cascade_images", model=f"student {n}", variant="student_95")  # noqa: E731
    groups = ["reads the text only", "looks at the image only\n(used)", "image + text"]
    st = ["T_logreg", "I_logreg", "IT_logreg"]
    fig, rect = frame(title, "Three fast pre-filters · tested on the 120 hand-checked memes",
                      "Each pre-filter learned from other memes (never these 120), labelled either by the original dataset "
                      "(grey) or by the AI judge (yellow). Bars show the ranking quality (AUROC): how well its score puts "
                      "harmful memes above harmless ones (1.0 = perfect, 0.5 = chance). No uncertainty range available.",
                      legend_room=True)
    bars(fig.add_axes(rect), name, groups,
         [("learned from the original labels", OTHER, [float(row(R, **ks(n + "_datasetlabels"))["auroc"]) for n in st],
           [None] * 3, [("csv", ks(n + "_datasetlabels"), "auroc") for n in st]),
          ("learned from the AI judge", FILTER, [float(row(R, **ks(n))["auroc"]) for n in st], [None] * 3,
           [("csv", ks(n), "auroc") for n in st])], "Ranking quality (AUROC)\n1.0 = perfect")
    save(fig, name, title, "Learning from the AI judge raises the pre-filter's ranking quality from 0.710-0.789 to "
         "0.895-0.965.", "Speed · two-step system")
    return f10, f50, ja


# --- time ------------------------------------------------------------------------------------------------------------
def times(R, f10, f50, ja):
    name = "17_time_per_meme_models"
    key = lambda m: dict(experiment="sv_images_v1", model=m, prompt="v1", variant="image_text", task="sexual")  # noqa: E731
    vals = [60 / float(row(R, **key(m))["throughput_items_per_min"]) for m, *_ in MODELS]
    title = f"The four AI models need between {min(vals):.1f} and {max(vals):.1f} seconds per meme"
    rec(name, "title: fastest", f"{min(vals):.1f}", "csv", key(MODELS[int(np.argmin(vals))][0]),
        "throughput_items_per_min", ("per_item_s",))
    rec(name, "title: slowest", f"{max(vals):.1f}", "csv", key(MODELS[int(np.argmax(vals))][0]),
        "throughput_items_per_min", ("per_item_s",))
    fig, rect = frame(title, "Four open-source AI models · one graphics card (NVIDIA V100 32 GB)",
                      "Time to check one meme (image + text), measured on the 120 hand-checked memes with 8 memes "
                      "processed in parallel. Lower is faster.")
    bars(fig.add_axes(rect), name, [lab for *_, lab in MODELS],
         [("seconds per meme", JUDGE, vals, [None] * 4,
           [("csv", key(m), "throughput_items_per_min", ("per_item_s",)) for m, *_ in MODELS])],
         "seconds per meme", ymax=max(vals), fmt="{:.2f}", unit=" s")
    save(fig, name, title, "Qwen3.5-4B is the fastest (1.30 s per meme), Gemma 4 12B the slowest (2.74 s).",
         "Speed · cost of the AI judge")

    name = "18_time_two_step_system"
    kj = dict(experiment="cascade_images", model="qwen3.5-9b", prompt="v3", variant="judge_alone")
    k10 = dict(experiment="cascade_filter_test", model="filter I_logreg", variant="filter_95_10pct")
    k50 = dict(experiment="cascade_filter_test", model="filter I_logreg", variant="filter_95_50pct")
    sp = note(f10, "speedup")
    title = "In a realistic feed, the two-step system checks memes " + ("twice as fast" if round(sp) == 2 else f"{sp:.0f} times faster")
    rec(name, "title: 'twice as fast' (speed-up, rounded)", f"{sp:.0f}", "csv", k10, "notes", ("note", "speedup"))
    ft = J(RES / "cascade" / "filter_test_10pct.json")
    fs = f"{ft['filter_seconds_per_image']:.2f}"
    rec(name, "caption: pre-filter time per meme", fs, "docs/results/cascade/filter_test_10pct.json (filter_seconds_per_image)")
    fig, rect = frame(title, "Seconds per meme · one graphics card (NVIDIA V100 32 GB)",
                      f"AI judge alone (Qwen3.5-9B): measured. Two-step system: pre-filter time (measured, {fs} s per "
                      "meme) plus the judge's time on the memes passed on, computed from measured times, not a separate "
                      "run. The rarer harmful content is in the feed, the larger the gain.")
    bars(fig.add_axes(rect), name, ["AI judge alone", "two-step system\nhalf harmful", "two-step system\n10 % harmful (realistic)"],
         [("seconds per meme", None, [note(ja, "time/img"), note(f50, "time/img"), note(f10, "time/img")], [None] * 3,
           [("csv", kj, "notes", ("note", "time/img")), ("csv", k50, "notes", ("note", "time/img")),
            ("csv", k10, "notes", ("note", "time/img"))])],
         "seconds per meme", ymax=note(ja, "time/img"), fmt="{:.2f}", unit=" s")
    ax = fig.axes[-1]
    for p, c in zip(ax.patches, (JUDGE, FILTER, FILTER)):
        p.set_facecolor(c)
    save(fig, name, title, "Judge alone 1.51 s per meme; with the pre-filter 1.13 s on a half-harmful set and 0.75 s in a "
         "realistic feed.", "Speed · two-step system")

    name = "19_time_video"
    tim = J(RES / "video_racism_v1" / "qwen35-9b" / "timing.json")
    vm = J(RES / "video_racism_v1" / "qwen35-9b" / "metrics.json")
    vid_min = tim["total_video_seconds"] / 60
    prep = sum(tim["per_stage_total_s"].values())
    pB, pC = (prep + vm["B"]["judge_seconds"]) / vid_min, (prep + vm["C"]["judge_seconds"]) / vid_min
    ten = 10 * pB
    title = f"Checking a 10-minute video takes about {ten / 60:.0f} minutes (estimate)"
    tsrc = "docs/results/video_racism_v1/qwen35-9b/timing.json + metrics.json (judge_seconds)"
    rec(name, "title: minutes for 10 min of video (estimate)", f"{ten / 60:.0f}", tsrc)
    rec(name, "caption: seconds for 10 min of video (estimate)", f"{ten:.0f}", tsrc)
    rec(name, "caption: times faster than real time", f"{60 / pB:.1f}", tsrc)
    rec(name, "caption: minutes of video measured", f"{vid_min:.0f}", tsrc)
    fig, rect = frame(title, VID_SUB + " · one graphics card (NVIDIA V100 32 GB)",
                      f"Computing time per minute of video, measured on 30 videos ({vid_min:.0f} minutes in total), "
                      f"including cutting into scenes, speech-to-text, reading on-screen text and the AI judge. With the "
                      f"images, this is {60 / pB:.1f} times faster than real time. A 10-minute video would take about "
                      f"{ten:.0f} s: an estimate, since test videos were at most 4 minutes long.")
    bars(fig.add_axes(rect), name, ["images + speech + on-screen text", "speech + on-screen text only"],
         [("seconds per minute of video", None, [pB, pC], [None] * 2, [(tsrc,), (tsrc,)])],
         "seconds of computing\nper minute of video", ymax=pB, fmt="{:.1f}", unit=" s")
    ax = fig.axes[-1]
    for p, c in zip(ax.patches, (JUDGE, TEXT)):
        p.set_facecolor(c)
    save(fig, name, title, f"About {pB:.1f} s of computing per minute of video, so roughly 2 minutes for a 10-minute "
         "video (estimate).", "Video · cost")


# --- check and index -----------------------------------------------------------------------------------------------
def check() -> tuple[list[str], int]:
    """Re-read ALL_METRICS.csv from disk and compare each printed number with it (at the printed precision)."""
    R = metrics()
    lines, bad = [], 0
    for r in REC:
        shown = str(r["shown"]).replace(" s", "").replace(" %", "")
        if r["src"] != "csv":
            lines.append(f"| {r['figure']} | {r['what']} | {r['shown']} | {r['src']} | not in ALL_METRICS.csv | — |")
            continue
        x = row(R, **r["key"])
        f = r["f"] or ("raw",)
        if f[0] == "raw":
            exp = float(x[r["col"]])
        elif f[0] == "note":
            exp = note(x, f[1])
        elif f[0] == "note_pct":
            exp = note(x, f[1]) * 100
        elif f[0] == "note_pct_saved":
            exp = (1 - note(x, f[1])) * 100
        elif f[0] == "note_int":
            exp = note(x, f[1])
        elif f[0] == "minus_lost":
            exp = float(x["FN"]) - note(x, "lost")
        elif f[0] == "prevalence":
            exp = int(x["n_pos"]) / (int(x["n_pos"]) + int(x["n_neg"])) * 100
        elif f[0] == "per_item_s":
            exp = 60 / float(x["throughput_items_per_min"])
        dec = len(shown.split(".")[1]) if "." in shown else 0
        ok = abs(float(shown) - exp) <= 0.5 * 10 ** -dec + 1e-9
        bad += not ok
        k = r["key"]
        src = " · ".join(str(k[c]) for c in ("experiment", "model", "prompt", "variant") if c in k) + f" · {r['col']}"
        lines.append(f"| {r['figure']} | {r['what']} | {r['shown']} | {src} | {exp:g} | {'OK' if ok else 'DIFF'} |")
    return lines, bad


def write_index(lines, bad):
    n_csv = sum(1 for r in REC if r["src"] == "csv")
    L = ["# Figures for a non-technical audience", "",
         "Generated by `scripts/make_public_figures.py` (PNG 300 dpi + PDF, 16:9). No model was run and no metric was "
         "recomputed: every number is read from `docs/results/ALL_METRICS.csv`, the timing and metrics files in "
         "`docs/results/`, and (for uncertainty ranges and curves) the per-item scores already stored in `results/`.", "",
         "Colours: blue = AI judge (full input) · light blue = AI judge reading text only · dark blue = improved "
         "definition (indicative) · yellow = fast pre-filter / two-step system · grey = comparison baseline · "
         "green squares = right answers · orange squares = mistakes.", "",
         "## Figures", "", "| file (.png / .pdf) | title | message | suggested slide |", "|---|---|---|---|"]
    L += [f"| `{i['file']}` | {i['title']} | {i['message']} | {i['slide']} |" for i in INDEX]
    L += ["", "## Check: numbers on the figures vs ALL_METRICS.csv", "",
          f"{n_csv} numbers come from `ALL_METRICS.csv`: **{bad} difference(s)** (each printed number compared with the "
          f"value read again from the file, at the printed precision). {len(REC) - n_csv} other printed items come from "
          "the timing / metrics files and are listed with their source.", "",
          "| figure | what | shown | source | value in source | check |", "|---|---|---|---|---|---|"] + lines
    p = OUT / "INDEX.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    FILES.append(p)


def rebuild_zip():
    zp = PRES / "presentation_pack.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:  # same content rule as make_presentation.py
        for p in sorted(PRES.rglob("*")):
            if p.is_file() and p != zp:
                z.write(p, p.relative_to(ROOT))
        for p in (RES / "ALL_METRICS.csv", RES / "ALL_CONFUSIONS.json"):
            z.write(p, p.relative_to(ROOT))
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zp, BACKUP / "presentation_pack_2026-09-27.zip")
    return zp


def main():
    R = metrics()
    images(R)
    video(R)
    f10, f50, ja = prefilter(R)
    times(R, f10, f50, ja)
    lines, bad = check()
    write_index(lines, bad)
    zp = rebuild_zip()
    for p in FILES:
        print(p.relative_to(ROOT))
    print(f"{len(INDEX)} figures · {sum(1 for r in REC if r['src'] == 'csv')} numbers checked against ALL_METRICS.csv · "
          f"{bad} difference(s)")
    print("zip:", zp.relative_to(ROOT), "· backup:", BACKUP / "presentation_pack_2026-09-27.zip")


if __name__ == "__main__":
    main()
