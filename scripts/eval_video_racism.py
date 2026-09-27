"""Video pipeline test by segments with the RACISM topic layer on HateMM (Zenodo 7799469, CC BY 4.0).

    python scripts/eval_video_racism.py freeze                  # fingerprint of the racism prompt (pinned below)
    python scripts/eval_video_racism.py download                # HateMM csv + zips → data/videos/hatemm/ (disk checked)
    python scripts/eval_video_racism.py candidates              # seed 42, <= 4 min, candidate pools
    python scripts/eval_video_racism.py prepare [--ids ...]     # segments, frames, safety, Whisper, OCR (no judge)
    python scripts/eval_video_racism.py review                  # review sheets (frames + transcript) for the human check
    python scripts/eval_video_racism.py reference               # data/videos/racism_v1/reference_notes.jsonl → reference
    python scripts/eval_video_racism.py run --variant B|C       # judge every segment (B: frames + text; C: text only)
    python scripts/eval_video_racism.py score                   # metrics, confusion, localisation, timelines

This test changes nothing in the sexual-violence core: the prompt is modalities.md + policy/topics/racism.md + examples.
Nothing under data/ or results/ is versioned.
"""

import argparse
import csv
import json
import random
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harmwatch.video_segments import (OCR, Segment, SegmentJudge, TopicPrompt, Transcriber, aggregate, attach,  # noqa: E402
                                      grab_frames, offset, overlaps, scene_cuts, segment_bounds, video_duration)

# Frozen before any test video was looked at (racism v1: TOPIC_INSTRUCTIONS + modalities.md + racism.md + 6 examples).
FROZEN_PROMPT_SHA256 = "4396e156f031109269240ba38ee216c18f0c6c949a28403687d93d94fb17a52d"
DATA = ROOT / "data" / "videos"
HATEMM = DATA / "hatemm"
WORK = DATA / "racism_v1"
RESULTS = ROOT / "results" / "videos" / "racism_v1" / "qwen35-9b"
ZENODO = "https://zenodo.org/records/7799469/files/{}?download=1"
FILES = ["HateMM_annotation.csv", "hate_videos.zip", "non_hate_videos.zip"]
SEED = 42
MAX_SECONDS = 240
N_PER_CLASS = 15
RACIAL_TARGETS = re.compile(r"black|african|asian|hispanic|latin|mexican|arab|indian|white|immigrant|refugee", re.I)


def check_prompt() -> TopicPrompt:
    p = TopicPrompt("racism")
    if FROZEN_PROMPT_SHA256 and p.fingerprint() != FROZEN_PROMPT_SHA256:
        sys.exit("Racism prompt differs from the frozen fingerprint: refusing to run.")
    return p


def cmd_freeze(args):
    p = TopicPrompt("racism")
    out = ROOT / "results" / "videos" / "racism_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "prompt_racism_v1_system.txt").write_text(p.system, encoding="utf-8")
    print(p.fingerprint())


def cmd_download(args):
    import urllib.request

    HATEMM.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(HATEMM).free / 1e9
    print(f"free disk: {free:.0f} GB")
    if free < 30:
        sys.exit("Less than 30 GB free: not downloading.")
    for name in FILES:
        dest = HATEMM / name
        if not dest.exists():
            print("downloading", name, flush=True)
            urllib.request.urlretrieve(ZENODO.format(name), dest)
        if name.endswith(".zip") and not (HATEMM / name[:-4]).exists():
            with zipfile.ZipFile(dest) as z:
                z.extractall(HATEMM / name[:-4])
    print("ok")


def find_video(name: str) -> Path | None:
    hits = list(HATEMM.rglob(name))
    return hits[0] if hits else None


def parse_snippet(s: str) -> list[tuple[float, float]]:
    """HateMM hate_snippet → [(start_s, end_s)] (accepts 'hh:mm:ss' or 'mm:ss' pairs)."""
    def sec(t):
        parts = [float(x) for x in t.split(":")]
        return sum(v * 60 ** i for i, v in enumerate(reversed(parts)))
    times = re.findall(r"\d{1,2}:\d{2}(?::\d{2})?", s or "")
    return [(sec(a), sec(b)) for a, b in zip(times[::2], times[1::2])]


def cmd_candidates(args):
    rows = list(csv.DictReader(open(HATEMM / "HateMM_annotation.csv", encoding="utf-8")))
    rng = random.Random(SEED)
    pos = [r for r in rows if r["label"].strip().lower() == "hate" and RACIAL_TARGETS.search(r.get("target") or "")
           and parse_snippet(r.get("hate_snippet"))]
    neg = [r for r in rows if r["label"].strip().lower() in ("non hate", "non_hate", "nonhate")]
    rng.shuffle(pos)
    rng.shuffle(neg)
    out = []
    for pool, cls, want in ((pos, "pos", args.pool), (neg, "neg", args.pool)):
        taken = 0
        for r in pool:
            if taken == want:
                break
            path = find_video(r["video_file_name"])
            if not path:
                continue
            d = video_duration(path)
            if not 0 < d <= MAX_SECONDS:
                continue
            out.append({"video": r["video_file_name"], "class": cls, "label": r["label"], "target": r.get("target"),
                        "hate_snippet": parse_snippet(r.get("hate_snippet")), "duration": round(d, 1),
                        "path": str(path.relative_to(ROOT))})
            taken += 1
        print(cls, f"pool {len(pool)} → {taken}")
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "candidates.jsonl").write_text("\n".join(json.dumps(c) for c in out) + "\n")


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_prepare(args):
    """Segments, frames, explicit-image safety on every frame, transcript, OCR. No judge."""
    from harmwatch.safety import ImageSafety

    cands = load(WORK / "candidates.jsonl")
    if args.ids:
        cands = [c for c in cands if c["video"] in args.ids]
    safety, whisper, ocr = ImageSafety(), Transcriber(), OCR()
    (WORK / "segments").mkdir(parents=True, exist_ok=True)
    (WORK / "frames").mkdir(parents=True, exist_ok=True)
    for c in cands:
        out = WORK / "segments" / f"{Path(c['video']).stem}.json"
        if out.exists():
            continue
        path, t = ROOT / c["path"], {}
        s0 = time.time()
        bounds = segment_bounds(c["duration"], scene_cuts(path))
        t["segmentation"] = time.time() - s0
        s0 = time.time()
        frames = [grab_frames(path, [s + 0.3, (s + e) / 2, max(s, e - 0.3)]) for s, e in bounds]
        quarantined = []
        for i, fs in enumerate(frames):
            for f in fs:
                d = safety.check(f)
                if d.quarantine:
                    quarantined.append({"segment": i + 1, "reasons": d.reasons})
        t["frames_and_safety"] = time.time() - s0
        s0 = time.time()
        phrases = whisper.phrases(path)
        t["whisper"] = time.time() - s0
        s0 = time.time()
        ocr_text = [" / ".join(dict.fromkeys(l for f in fs for l in ocr.lines(f))) for fs in frames]
        t["ocr"] = time.time() - s0
        speech = attach(phrases, bounds)
        segs = []
        for i, ((s, e), fs) in enumerate(zip(bounds, frames)):
            names = []
            if not quarantined:  # frames of a quarantined video are never stored nor shown
                for j, f in enumerate(fs):
                    name = f"{Path(c['video']).stem}_{i + 1:03d}_{j}.jpg"
                    f.save(WORK / "frames" / name, quality=85)
                    names.append(name)
            segs.append({"video": c["video"], "index": i + 1, "n": len(bounds), "start": s, "end": e,
                         "speech": speech[i], "on_screen_text": ocr_text[i], "frames": names})
        out.write_text(json.dumps({"video": c["video"], "duration": c["duration"], "segments": segs,
                                   "phrases": phrases, "quarantined": quarantined,
                                   "timing": {k: round(v, 2) for k, v in t.items()}}, ensure_ascii=False))
        print(c["video"], len(bounds), "segments", {k: round(v, 1) for k, v in t.items()},
              "QUARANTINED" if quarantined else "", flush=True)


def cmd_review(args):
    """Contact sheets (3 frames per segment, max 12 segments per sheet) + transcript, for the human check."""
    from PIL import Image, ImageDraw

    sheets = WORK / "review"
    sheets.mkdir(exist_ok=True)
    for c in load(WORK / "candidates.jsonl"):
        p = WORK / "segments" / f"{Path(c['video']).stem}.json"
        if not p.exists():
            continue
        doc = json.loads(p.read_text())
        if doc["quarantined"]:
            continue
        segs = doc["segments"][:12]
        sheet = Image.new("RGB", (3 * 220, len(segs) * 140 + 10), "white")
        d = ImageDraw.Draw(sheet)
        for i, s in enumerate(segs):
            for j, name in enumerate(s["frames"][:3]):
                im = Image.open(WORK / "frames" / name)
                im.thumbnail((215, 120))
                sheet.paste(im, (j * 220, i * 140 + 15))
            d.text((2, i * 140 + 2), f"#{s['index']} {s['start']:.0f}-{s['end']:.0f}s", fill="red")
        sheet.save(sheets / f"{Path(c['video']).stem}.jpg", quality=80)
        (sheets / f"{Path(c['video']).stem}.txt").write_text(
            "\n".join(f"#{s['index']} {s['start']:.0f}-{s['end']:.0f}s | speech: {s['speech']} | ocr: {s['on_screen_text']}"
                      for s in doc["segments"]), encoding="utf-8")
    print(sheets)


def cmd_reference(args):
    """reference_notes.jsonl (written by hand BEFORE any judge call) → reference.jsonl with 15 + 15 videos."""
    notes = load(WORK / "reference_notes.jsonl")
    cands = {c["video"]: c for c in load(WORK / "candidates.jsonl")}
    keep = [n for n in notes if n["decision"] == "keep"]
    pos = [n for n in keep if n["racist"]][:N_PER_CLASS]
    neg = [n for n in keep if not n["racist"]][:N_PER_CLASS]
    ref = [{**cands[n["video"]], "reference": {k: n[k] for k in ("racist", "category", "reason")}} for n in pos + neg]
    (WORK / "reference.jsonl").write_text("\n".join(json.dumps(r) for r in ref) + "\n")
    replaced = [n for n in notes if n["decision"] != "keep"]
    print(f"{len(pos)} positives, {len(neg)} negatives; {len(replaced)} candidates not used:",
          {n["video"]: n["decision"] for n in replaced})


def segments_of(video: str) -> list[Segment]:
    from PIL import Image

    doc = json.loads((WORK / "segments" / f"{Path(video).stem}.json").read_text())
    return [Segment(video=s["video"], index=s["index"], n=s["n"], start=s["start"], end=s["end"], speech=s["speech"],
                    on_screen_text=s["on_screen_text"], frames=[Image.open(WORK / "frames" / f) for f in s["frames"]])
            for s in doc["segments"]]


def cmd_run(args):
    prompt = check_prompt()
    judge = SegmentJudge(prompt, with_frames=args.variant == "B")
    ref = load(WORK / "reference.jsonl")
    out = RESULTS / args.variant
    out.mkdir(parents=True, exist_ok=True)
    segs = [s for r in ref for s in segments_of(r["video"])]
    t0 = time.time()
    res = judge.judge_many(segs, workers=args.workers)
    total = time.time() - t0
    (out / "predictions_segments.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in res) + "\n")
    by_video = {}
    for r in res:
        by_video.setdefault(r["video"], []).append(r)
    vids = [{**aggregate(v["video"], by_video.get(v["video"], [])), "reference": v["reference"],
             "hate_snippet": v["hate_snippet"], "duration": v["duration"]} for v in ref]
    (out / "predictions_videos.jsonl").write_text("\n".join(json.dumps(v) for v in vids) + "\n")
    (out / "run_info.json").write_text(json.dumps({"variant": args.variant, "prompt_sha256": prompt.fingerprint(),
                                                   "n_segments": len(segs), "judge_seconds": round(total, 1),
                                                   "workers": args.workers}, indent=2))
    print(f"{args.variant}: {len(segs)} segments judged in {total:.0f}s")


def cmd_score(args):
    from sklearn.metrics import roc_auc_score

    from scripts.eval_sv_benchmark import confusion, save_matrix

    metrics = {}
    for variant in ("B", "C"):
        out = RESULTS / variant
        if not (out / "predictions_videos.jsonl").exists():
            continue
        vids, segs = load(out / "predictions_videos.jsonl"), load(out / "predictions_segments.jsonl")
        m = {"videos": confusion([(v["reference"]["racist"], v["racist"]) for v in vids])}
        y = [int(v["reference"]["racist"]) for v in vids]
        sc = [v["score"] if v["score"] is not None else 0.0 for v in vids]
        m["auroc_max_p_racist"] = round(roc_auc_score(y, sc), 3) if len(set(y)) == 2 else None
        save_matrix(out / "confusion", m["videos"], f"racism · videos · variant {variant}")
        tps = [v for v in vids if v["reference"]["racist"] and v["racist"] and v["hate_snippet"]]
        loc = {"n_true_positives_with_snippet": len(tps), "top1_hits": 0, "top3_hits": 0, "offsets_top1_s": []}
        for v in tps:
            flagged = [(f["start"], f["end"]) for f in v["flagged"]]
            snippets = [tuple(s) for s in v["hate_snippet"]]
            if flagged and any(overlaps(flagged[0], s) for s in snippets):
                loc["top1_hits"] += 1
            if any(overlaps(f, s) for f in flagged[:3] for s in snippets):
                loc["top3_hits"] += 1
            if flagged:
                loc["offsets_top1_s"].append(min(offset(flagged[0], s) for s in snippets))
        n = max(len(tps), 1)
        loc["top1_rate"], loc["top3_rate"] = round(loc["top1_hits"] / n, 3), round(loc["top3_hits"] / n, 3)
        loc["mean_offset_top1_s"] = round(sum(loc["offsets_top1_s"]) / n, 1) if tps else None
        m["localisation"] = loc
        racist_segs = [s for s in segs if s.get("racist")]
        m["triggered_layer"] = {k: sum(s["triggered_layer"] == k for s in racist_segs) for k in ("speech", "on_screen_text", "visuals")}
        m["segments"] = {"n": len(segs), "errors": sum(s["error"] is not None for s in segs),
                         "racist": len(racist_segs),
                         "invalid_json": sum(1 for s in segs if (s["error"] or "").startswith("invalid_json")),
                         "timeouts": sum(1 for s in segs if (s["error"] or "").startswith("timeout"))}
        info = json.loads((out / "run_info.json").read_text())
        m["judge_seconds"] = info["judge_seconds"]
        metrics[variant] = m
    prep = [json.loads((WORK / "segments" / f"{Path(v['video']).stem}.json").read_text()) for v in load(WORK / "reference.jsonl")]
    cost = {k: round(sum(p["timing"][k] for p in prep), 1) for k in ("segmentation", "frames_and_safety", "whisper", "ocr")}
    metrics["cost"] = {"per_stage_total_s": cost, "videos": len(prep),
                       "total_video_seconds": round(sum(p["duration"] for p in prep), 1),
                       "segments_per_video": round(sum(len(p["segments"]) for p in prep) / len(prep), 1),
                       "prep_seconds_per_video": round(sum(cost.values()) / len(prep), 1)}
    for variant in metrics:
        if variant in ("B", "C"):
            metrics["cost"][f"judge_seconds_per_video_{variant}"] = round(metrics[variant]["judge_seconds"] / len(prep), 1)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    # timelines for positive videos (variant B), no graphic description
    if (RESULTS / "B" / "predictions_segments.jsonl").exists():
        segs = load(RESULTS / "B" / "predictions_segments.jsonl")
        lines = []
        for v in load(RESULTS / "B" / "predictions_videos.jsonl"):
            if not v["reference"]["racist"]:
                continue
            snip = ", ".join(f"{a:.0f}-{b:.0f}s" for a, b in v["hate_snippet"])
            top = v["flagged"][0] if v["flagged"] else None
            lines.append(f"\n{v['video']} · {v['duration']:.0f}s · video racist={v['racist']} (max P={v['score']}) · "
                         f"HateMM snippet {snip} · flagged {top['start']:.0f}-{top['end']:.0f}s" if top else "")
            for s in sorted((s for s in segs if s["video"] == v["video"]), key=lambda s: s["index"]):
                mark = " ◀ flagged" if top and s["index"] == top["index"] else ""
                in_snip = " [snippet]" if any(overlaps((s["start"], s["end"]), tuple(x)) for x in v["hate_snippet"]) else ""
                p = s.get("p_racist")
                lines.append(f"  #{s['index']:>2} {s['start']:6.1f}-{s['end']:6.1f}s  P={p if p is None else round(p, 3)!s:<6} "
                             f"racism={(s.get('scores') or {}).get('racism', '-')!s:<3} {s.get('category') or '-':<5} "
                             f"{s.get('triggered_layer') or '-':<14}{in_snip}{mark}")
        (RESULTS / "timelines.txt").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(metrics, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("freeze", "download", "review", "reference", "score"):
        sub.add_parser(name)
    c = sub.add_parser("candidates")
    c.add_argument("--pool", type=int, default=25, help="candidates drawn per class before the human check")
    p = sub.add_parser("prepare")
    p.add_argument("--ids", nargs="*")
    r = sub.add_parser("run")
    r.add_argument("--variant", choices=("B", "C"), required=True)
    r.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    {"freeze": cmd_freeze, "download": cmd_download, "candidates": cmd_candidates, "prepare": cmd_prepare,
     "review": cmd_review, "reference": cmd_reference, "run": cmd_run, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
