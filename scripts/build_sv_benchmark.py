"""Build the confirmed, balanced "sexual character" image benchmark (sv_images_v1) from QCRI/MemeLens (all splits).

    python scripts/build_sv_benchmark.py candidates     # keyword-targeted candidate pool, NSFW quarantine, minors excluded
    python scripts/build_sv_benchmark.py grids          # contact sheets for the human confirmation pass
    python scripts/build_sv_benchmark.py finalize       # annotations → data/benchmarks/sv_images_v1.jsonl + distribution

The dataset label only proposes candidates. Every retained item is confirmed by looking at image + text against the
definition (policy/ Axis 1 or sexual harassment); ambiguous items are excluded and counted. No tested model is used.
Explicit images are quarantined before anyone looks at them (hash + reason); items with a possible minor are excluded.
Everything stays in data/ (git-ignored).
"""

import argparse
import glob
import hashlib
import io
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "benchmarks"
CAND_DIR = OUT / "sv_images_v1_candidates"
CANDIDATES = OUT / "sv_images_v1_candidates.jsonl"
QUARANTINE = OUT / "sv_images_v1_quarantine.jsonl"
ANNOTATIONS = OUT / "sv_images_v1_annotations.jsonl"
BENCHMARK = OUT / "sv_images_v1.jsonl"
DISTRIBUTION = OUT / "sv_images_v1_distribution.json"
ABANDONED_SAMPLE = ROOT / "data" / "images" / "memelens" / "sample.jsonl"  # the abandoned 240-meme test: never reused
SEED = 42
NSFW_MODEL = "Falconsai/nsfw_image_detection"
NSFW_THRESHOLD = 0.3  # stricter than the first test: nudity must never reach annotation

MAMI = ["misogynous_en__MAMI", "violence_en__MAMI", "objectification_en__MAMI", "shaming_en__MAMI"]
RAPE = re.compile(r"\b(rap(e|ed|es|ist|ists|ing)|roofie\w*|molest\w*|consent\w*|grop(e|ed|ing)|sexual(ly)? assault\w*|"
                  r"sex offender|date rape)\b", re.I)
SLUR = re.compile(r"\b(slut\w*|whore\w*|hoes?|thots?|skank\w*|cum ?dump\w*|sluts?)\b", re.I)
SEXUAL = re.compile(r"\b(sex\w*|dick\w*|cock\w*|puss(y|ies)|tits?|titties|boobs?|blow ?jobs?|bj|suck\w*|"
                    r"horny|nudes?|naked|porn\w*|anal|orgasm\w*|virgin\w*|milf|booty|thicc|spread|swallow\w*|"
                    r"bang\w*|smash|hit it|make me a sandwich and)\b", re.I)
ANY_SEXUAL = [RAPE, SLUR, SEXUAL]

# candidate group → how many to draw (more than needed: confirmation drops ambiguous items)
QUOTAS = {
    "pos_rape_mami": 40, "pos_rape_fhm_mmhs": 25, "pos_slur_mami": 30, "pos_sexual_mami": 30,
    "pos_objectification_mami": 15, "pos_sexual_mmhs": 15,
    "trap_hate_fhm": 30, "trap_sexist_mami": 30,
    "neutral_mami": 25, "neutral_fhm": 25,
}


def _parquets(subset: str) -> list[str]:
    home = os.environ.get("HF_HOME", str(Path.home() / "hf_cache"))
    return sorted(glob.glob(f"{home}/hub/datasets--QCRI--MemeLens/snapshots/*/{subset}/*.parquet"))


def _rows(subset: str, columns=("id", "text", "label")) -> list[dict]:
    import pyarrow.parquet as pq

    out = []
    for f in _parquets(subset):
        split = Path(f).name.split("-")[0]
        for r in pq.read_table(f, columns=list(columns)).to_pylist():
            r["split"], r["subset"] = split, subset
            out.append(r)
    return out


def sexual_words(text: str) -> bool:
    return any(p.search(text or "") for p in ANY_SEXUAL)


def pools() -> dict[str, list[dict]]:
    """Candidate pools (metadata only; images loaded later for the drawn ones)."""
    mami: dict[str, dict] = {}
    for sub in MAMI:  # the four MAMI tasks share memes: merge by text + split to get all labels per meme
        for r in _rows(sub):
            key = (r["split"], (r["text"] or "").strip().lower())
            m = mami.setdefault(key, {"text": r["text"] or "", "split": r["split"], "ids": {}, "labels": {}})
            m["ids"][sub] = r["id"]
            m["labels"][sub.split("_")[0]] = r["label"]
    mami_list = [dict(m, source="MAMI") for m in mami.values() if "misogynous_en__MAMI" in m["ids"]]
    pos = lambda m, k: m["labels"].get(k) == k  # noqa: E731
    fhm = [dict(r, source="FHM") for r in _rows("Hateful_en_FHM")]
    mmhs = [dict(r, source="MMHS") for r in _rows("Hateful_en__MMHS", ("id", "text", "label", "explanation"))]

    p = {
        "pos_rape_mami": [m for m in mami_list if pos(m, "misogynous") and RAPE.search(m["text"])],
        "pos_rape_fhm_mmhs": [r for r in fhm + mmhs if RAPE.search(r["text"] or "")],
        "pos_slur_mami": [m for m in mami_list if pos(m, "misogynous") and SLUR.search(m["text"]) and not RAPE.search(m["text"])],
        "pos_sexual_mami": [m for m in mami_list if pos(m, "misogynous") and SEXUAL.search(m["text"])
                            and not SLUR.search(m["text"]) and not RAPE.search(m["text"])],
        "pos_objectification_mami": [m for m in mami_list if pos(m, "objectification") and not sexual_words(m["text"])],
        "pos_sexual_mmhs": [r for r in mmhs if r["label"] == "hateful" and (SLUR.search(r["text"] or "") or SEXUAL.search(r["text"] or ""))
                            and re.search(r"sexis|women|woman|misogyn", r.get("explanation") or "", re.I)],
        "trap_hate_fhm": [r for r in fhm if r["label"] == "hateful" and not sexual_words(r["text"])],
        "trap_sexist_mami": [m for m in mami_list if pos(m, "misogynous") and not sexual_words(m["text"])
                             and m["labels"].get("objectification") != "objectification"],
        "neutral_mami": [m for m in mami_list if m["labels"].get("misogynous") == "not-misogynous" and not sexual_words(m["text"])],
        "neutral_fhm": [r for r in fhm if r["label"] == "not-hateful" and not sexual_words(r["text"])],
    }
    return p


def _image_bytes(source: str, cand: dict, index: dict) -> bytes:
    import pyarrow.parquet as pq

    sub, rid = (next(iter(cand["ids"].items())) if source == "MAMI" else (cand["subset"], cand["id"]))
    f = index[(sub, rid)]
    t = pq.read_table(f, columns=["id", "image"], filters=[("id", "=", rid)])
    return t.column("image").to_pylist()[0]["bytes"]


def cmd_candidates(args):
    import pyarrow.parquet as pq
    from PIL import Image
    from transformers import pipeline

    from harmwatch.lexicon import age_indicators

    nsfw = pipeline("image-classification", model=NSFW_MODEL, device=0 if args.gpu else -1)
    abandoned = {json.loads(l)["sha256"] for l in ABANDONED_SAMPLE.read_text().splitlines() if l.strip()} \
        if ABANDONED_SAMPLE.exists() else set()
    index = {}
    for sub in MAMI + ["Hateful_en_FHM", "Hateful_en__MMHS"]:
        for f in _parquets(sub):
            for rid in pq.read_table(f, columns=["id"]).column("id").to_pylist():
                index[(sub, rid)] = f
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    seen, rows, quarantine, excluded = set(abandoned), [], [], Counter()
    for group, pool in pools().items():
        rng.shuffle(pool)
        taken = 0
        for c in pool:
            if taken == QUOTAS[group]:
                break
            if age_indicators(c["text"] or ""):
                excluded["age_indicator_in_text"] += 1
                continue
            raw = _image_bytes(c["source"], c, index)
            h = hashlib.sha256(raw).hexdigest()
            if h in seen:
                excluded["duplicate_or_abandoned_test"] += 1
                continue
            seen.add(h)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            score = next(s["score"] for s in nsfw(img) if s["label"] == "nsfw")
            if score >= NSFW_THRESHOLD:
                quarantine.append({"sha256": h, "group": group, "reason": f"nsfw {score:.2f} >= {NSFW_THRESHOLD}"})
                continue
            img.thumbnail((768, 768))
            cid = f"c{len(rows):03d}"
            img.save(CAND_DIR / f"{cid}.jpg", "JPEG", quality=90)
            rid = next(iter(c["ids"].values())) if c["source"] == "MAMI" else c["id"]
            rows.append({"cid": cid, "id": rid, "group": group, "source": c["source"], "split": c["split"],
                         "text": c["text"] or "", "dataset_labels": c.get("labels") or {c["subset"]: c["label"]},
                         "sha256": h, "nsfw_score": round(score, 3), "image": str((CAND_DIR / f"{cid}.jpg").relative_to(ROOT))})
            taken += 1
        print(f"{group:<26} pool {len(pool):>6} → {taken}")
    CANDIDATES.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    QUARANTINE.write_text("".join(json.dumps(q) + "\n" for q in quarantine))
    print(f"{len(rows)} candidates · {len(quarantine)} quarantined (NSFW) · excluded {dict(excluded)}")


def cmd_grids(args):
    from PIL import Image, ImageDraw

    rows = [json.loads(l) for l in CANDIDATES.read_text().splitlines() if l.strip()]
    grid_dir = OUT / "sv_images_v1_grids"
    grid_dir.mkdir(exist_ok=True)
    for g in range(0, len(rows), 6):
        canvas = Image.new("RGB", (1050, 760), "white")
        d = ImageDraw.Draw(canvas)
        for k, r in enumerate(rows[g:g + 6]):
            im = Image.open(ROOT / r["image"])
            im.thumbnail((340, 345))
            x, y = (k % 3) * 350 + 5, (k // 3) * 380 + 22
            canvas.paste(im, (x, y))
            d.text((x, y - 16), r["cid"], fill="red")
        canvas.save(grid_dir / f"g{g // 6:03d}.jpg", quality=85)
    print(f"{(len(rows) + 5) // 6} grids in {grid_dir}")


def stratified(items: list[dict], key: str, n: int, rng: random.Random) -> list[dict]:
    """Round-robin over the values of `key` (shuffled with the seed) so that rare categories are all kept."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it[key], []).append(it)
    for g in groups.values():
        rng.shuffle(g)
    out: list[dict] = []
    while len(out) < min(n, len(items)):
        for g in sorted(groups, key=lambda k: len(groups[k])):
            if groups[g] and len(out) < n:
                out.append(groups[g].pop())
    return out


def cmd_finalize(args):
    cands = {json.loads(l)["cid"]: json.loads(l) for l in CANDIDATES.read_text().splitlines() if l.strip()}
    notes = [json.loads(l) for l in ANNOTATIONS.read_text().splitlines() if l.strip()]
    keep = [a for a in notes if a["decision"] == "keep"]
    pos = [a for a in keep if a["sexual"]]
    neg_neutral = [a for a in keep if not a["sexual"] and a["neg_type"] == "neutral"]
    neg_trap = [a for a in keep if not a["sexual"] and a["neg_type"] == "trap"]
    rng = random.Random(SEED)
    chosen = stratified(pos, "category", 60, rng) + rng.sample(neg_neutral, min(30, len(neg_neutral))) + \
        stratified(neg_trap, "category", 30, rng)
    bench = []
    for a in sorted(chosen, key=lambda a: a["cid"]):
        c = cands[a["cid"]]
        bench.append({"item_id": f"sv1-{a['cid']}", "dataset_id": c["id"], "source": c["source"], "split": c["split"],
                      "dataset_labels": c["dataset_labels"], "candidate_group": c["group"], "text": c["text"],
                      "image": c["image"], "sha256": c["sha256"],
                      "reference": {k: a[k] for k in ("sexual", "category", "hate", "misogyny", "other_harm", "reason")},
                      "neg_type": a.get("neg_type")})
    BENCHMARK.write_text("\n".join(json.dumps(b, ensure_ascii=False) for b in bench) + "\n", encoding="utf-8")
    dist = {
        "n": len(bench), "positives": sum(b["reference"]["sexual"] for b in bench),
        "negatives_neutral": sum(b["neg_type"] == "neutral" for b in bench),
        "negatives_trap": sum(b["neg_type"] == "trap" for b in bench),
        "categories": Counter(b["reference"]["category"] for b in bench),
        "sources": Counter(f"{b['source']}/{'pos' if b['reference']['sexual'] else b['neg_type']}" for b in bench),
        "reference_hate": sum(b["reference"]["hate"] for b in bench),
        "reference_misogyny": sum(b["reference"]["misogyny"] for b in bench),
        "reviewed_candidates": len(notes),
        "excluded": Counter(a["decision"] for a in notes if a["decision"] != "keep"),
        "confirmed_available": {"pos": len(pos), "neutral": len(neg_neutral), "trap": len(neg_trap)},
        "nsfw_quarantined_before_review": sum(1 for l in QUARANTINE.read_text().splitlines() if l.strip()),
    }
    DISTRIBUTION.write_text(json.dumps(dist, indent=2, ensure_ascii=False))
    print(json.dumps(dist, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--gpu", action="store_true")
    sub.add_parser("grids")
    sub.add_parser("finalize")
    args = ap.parse_args()
    {"candidates": cmd_candidates, "grids": cmd_grids, "finalize": cmd_finalize}[args.cmd](args)


if __name__ == "__main__":
    main()
