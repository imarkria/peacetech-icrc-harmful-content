"""Cascade test: distil the judge (Qwen3.5-9B, prompt v3 frozen) into fast students, then simulate student → judge.

    python scripts/eval_cascade.py pool          # ~3000 MemeLens memes, anti-leakage vs the benchmark, safety, minors
    python scripts/eval_cascade.py label         # teacher labels (resumable): sexual, P(sexual), P(hate), P(misogyny)
    python scripts/eval_cascade.py embed         # text (Qwen3-Embedding-0.6B) + image (SigLIP2) embeddings, then
                                                 # the pool images are DELETED (only embeddings, hashes, labels kept)
    python scripts/eval_cascade.py train         # students T / I / IT (+ MLP), thresholds on DEV for recall 95/97/99 %
    python scripts/eval_cascade.py evaluate      # benchmark sv_images_v1 (never used for training or thresholds)

The benchmark (120 images) and its 57 ambiguous candidates are excluded from the pool with all their near-copies
(pHash distance <= 8). Data in data/cascade/, results in results/cascade/ (both git-ignored).
"""

import argparse
import hashlib
import io
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harmwatch.cascade import dedupe_within, near_duplicates, phash  # noqa: E402

DATA = ROOT / "data" / "cascade"
IMAGES = DATA / "pool_images"
POOL = DATA / "pool.jsonl"
EXCLUDED = DATA / "pool_excluded.jsonl"
TEACHER_RAW = DATA / "teacher_raw.jsonl"
RESULTS = ROOT / "results" / "cascade"
BENCH = ROOT / "data" / "benchmarks"
SEED = 42
# stratum → number of memes wanted in the pool (positives and negatives of every label)
QUOTAS = {"mami_violence_pos": 150, "mami_objectification_pos": 250, "mami_shaming_pos": 200,
          "mami_misogynous_other_pos": 150, "mami_neg": 750,
          "fhm_pos": 375, "fhm_neg": 375, "mmhs_pos": 375, "mmhs_neg": 375}
OVERSAMPLE = 1.7  # candidates drawn per stratum before exclusions


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def benchmark_hashes() -> tuple[dict[str, int], set[str]]:
    """pHash + sha256 of the 120 benchmark images and of the 57 ambiguous candidates (the test set and its neighbours)."""
    from PIL import Image

    cands = {c["cid"]: c for c in load(BENCH / "sv_images_v1_candidates.jsonl")}
    bench = {b["item_id"][4:] for b in load(BENCH / "sv_images_v1.jsonl")}
    amb = {a["cid"] for a in load(BENCH / "sv_images_v1_annotations.jsonl") if a["decision"] == "ambiguous"}
    ids = sorted(bench | amb)
    return ({cid: phash(Image.open(ROOT / cands[cid]["image"])) for cid in ids}, {cands[cid]["sha256"] for cid in ids})


def strata() -> dict[str, list[tuple[str, str, int]]]:
    """stratum → [(subset, parquet file, row)] for every eligible meme (MAMI merged over its four tasks)."""
    import pyarrow.parquet as pq

    from scripts.build_sv_benchmark import _parquets

    labels: dict[tuple, dict] = {}
    for sub in ("violence_en__MAMI", "objectification_en__MAMI", "shaming_en__MAMI"):
        for f in _parquets(sub):
            split = Path(f).name.split("-")[0]
            t = pq.read_table(f, columns=["text", "label"]).to_pylist()
            for r in t:
                labels.setdefault((split, (r["text"] or "").strip().lower()), {})[sub.split("_")[0]] = r["label"]
    out: dict[str, list] = {k: [] for k in QUOTAS}
    for f in _parquets("misogynous_en__MAMI"):
        split = Path(f).name.split("-")[0]
        for i, r in enumerate(pq.read_table(f, columns=["text", "label"]).to_pylist()):
            lab = labels.get((split, (r["text"] or "").strip().lower()), {})
            if r["label"] == "misogynous":
                key = ("mami_violence_pos" if lab.get("violence") == "violence" else
                       "mami_objectification_pos" if lab.get("objectification") == "objectification" else
                       "mami_shaming_pos" if lab.get("shaming") == "shaming" else "mami_misogynous_other_pos")
            else:
                key = "mami_neg"
            out[key].append(("misogynous_en__MAMI", f, i))
    for sub, prefix in (("Hateful_en_FHM", "fhm"), ("Hateful_en__MMHS", "mmhs")):
        for f in _parquets(sub):
            for i, lab in enumerate(pq.read_table(f, columns=["label"]).column("label").to_pylist()):
                out[f"{prefix}_{'pos' if lab == 'hateful' else 'neg'}"].append((sub, f, i))
    return out


def cmd_pool(args):
    import pyarrow.parquet as pq
    from PIL import Image

    from harmwatch.lexicon import age_indicators
    from harmwatch.safety import ImageSafety

    IMAGES.mkdir(parents=True, exist_ok=True)
    ref_hash, ref_sha = benchmark_hashes()
    rng = random.Random(SEED)
    drawn = {}
    for key, rows in strata().items():
        rng.shuffle(rows)
        drawn[key] = rows[:int(QUOTAS[key] * OVERSAMPLE)]
        print(f"{key:<28} eligible {len(rows):>6} → drawn {len(drawn[key])}", flush=True)
    by_file: dict[str, list] = {}
    for key, rows in drawn.items():
        for order, (sub, f, i) in enumerate(rows):
            by_file.setdefault(f, []).append((key, order, sub, i))
    items = {}
    for f, wanted in by_file.items():  # one pass per parquet file (images loaded once)
        t = pq.read_table(f, columns=["id", "image", "text", "label"])
        for key, order, sub, i in wanted:
            r = t.slice(i, 1).to_pylist()[0]
            items[(key, order)] = {"subset": sub, "dataset_id": r["id"], "text": r["text"] or "",
                                   "dataset_label": r["label"], "bytes": r["image"]["bytes"]}
        del t
    safety = ImageSafety()
    kept, excluded, pool_hashes = [], [], {}
    for key in QUOTAS:
        n = 0
        for order in range(len(drawn[key])):
            if n == QUOTAS[key]:
                break
            it = items[(key, order)]
            raw = it.pop("bytes")
            sha = hashlib.sha256(raw).hexdigest()
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            h = phash(img)
            pid = f"p{len(kept) + len(excluded):05d}"
            rec = {"pid": pid, "stratum": key, **it, "sha256": sha, "phash": f"{h:016x}"}
            reason = None
            if sha in ref_sha or near_duplicates({pid: h}, ref_hash):
                reason = "benchmark_near_copy"
            elif near_duplicates({pid: h}, pool_hashes):
                reason = "pool_near_duplicate"
            elif age_indicators(it["text"]):
                reason = "age_indicator_in_text"
            else:
                d = safety.check(img)
                if d.quarantine:
                    reason = "explicit_quarantine: " + "; ".join(d.reasons)
            if reason:
                excluded.append({"pid": pid, "stratum": key, "sha256": sha, "phash": rec["phash"], "reason": reason})
                continue
            img.thumbnail((768, 768))
            img.save(IMAGES / f"{pid}.jpg", "JPEG", quality=90)
            pool_hashes[pid] = h
            kept.append(rec)
            n += 1
        print(f"{key:<28} kept {n}/{QUOTAS[key]}", flush=True)
    rng2 = random.Random(SEED)
    for key in QUOTAS:  # 80 % train / 20 % dev, stratified
        ks = [k for k in kept if k["stratum"] == key]
        rng2.shuffle(ks)
        for j, k in enumerate(ks):
            k["part"] = "dev" if j < round(0.2 * len(ks)) else "train"
    POOL.write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kept) + "\n")
    EXCLUDED.write_text("\n".join(json.dumps(e) for e in excluded) + "\n")
    from collections import Counter
    print(f"pool {len(kept)} · excluded {len(excluded)}:", dict(Counter(e["reason"].split(":")[0] for e in excluded)))


def cmd_label(args):
    """Teacher = Qwen3.5-9B with sv_prompt_v3 (frozen), image + text. Resumable: already labelled pids are skipped."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image

    from scripts.eval_sv_benchmark import check_prompt, make_scorer

    scorer, _ = make_scorer(args.api_model, True, "v3")
    check_prompt(scorer, "v3")
    done = {r["pid"] for r in load(TEACHER_RAW)}
    todo = [p for p in load(POOL) if p["pid"] not in done]
    print(f"{len(done)} already labelled, {len(todo)} to go", flush=True)
    lock, f = threading.Lock(), open(TEACHER_RAW, "a", encoding="utf-8")
    t0, n = time.time(), [0]

    def one(p):
        item = {"id": p["pid"], "image": Image.open(IMAGES / f"{p['pid']}.jpg"), "text": p["text"], "lang": "en",
                "modality": "meme" if p["text"].strip() else "image"}
        res = scorer.assess(item)
        a = res["assessment"]
        rec = {"pid": p["pid"], "error": res["error"], "seconds": round(res["seconds"], 2)}
        if a:
            rec.update(sexual=a.sexual, possible_minor=a.possible_minor, restricted_reason=a.restricted_reason,
                       p_sexual=(a.p_true or {}).get("sexual"), p_hateful=(a.p_true or {}).get("hateful"),
                       p_misogynous=(a.p_true or {}).get("misogynous"), hateful=a.hateful, misogynous=a.misogynous,
                       category=a.category, primary_relation=a.primary_relation,
                       scores=a.scores.model_dump() if a.scores else None)
        with lock:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            n[0] += 1
            if n[0] % 100 == 0:
                el = time.time() - t0
                print(f"{n[0]}/{len(todo)} · {60 * n[0] / el:.1f} img/min", flush=True)
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, todo))
    f.close()
    print(f"done in {(time.time() - t0) / 60:.1f} min")


def cmd_label_report(args):
    """teacher_labels.jsonl (no image) + label statistics for checkpoint 1."""
    from collections import Counter

    pool = {p["pid"]: p for p in load(POOL)}
    raw = {r["pid"]: r for r in load(TEACHER_RAW)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid, p in pool.items():
        r = raw.get(pid, {})
        excluded = "teacher_possible_minor" if r.get("possible_minor") else ("teacher_error" if r.get("error") or not r else None)
        rows.append({"pid": pid, "source": p["subset"], "stratum": p["stratum"], "part": p["part"],
                     "dataset_label": p["dataset_label"], "sha256": p["sha256"], "phash": p["phash"],
                     "teacher": None if excluded else {k: r.get(k) for k in ("sexual", "p_sexual", "p_hateful",
                                                                             "p_misogynous", "hateful", "misogynous",
                                                                             "category", "primary_relation")},
                     "excluded_from_training": excluded})
    (RESULTS / "teacher_labels.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    ok = [r for r in rows if r["teacher"]]
    stats = {"pool": len(rows), "labelled_usable": len(ok),
             "excluded_from_training": dict(Counter(r["excluded_from_training"] for r in rows if r["excluded_from_training"])),
             "teacher_sexual_by_part": {part: {"n": sum(r["part"] == part for r in ok),
                                               "sexual": sum(r["part"] == part and r["teacher"]["sexual"] for r in ok)}
                                        for part in ("train", "dev")},
             "teacher_sexual_by_stratum": {s: f"{sum(r['teacher']['sexual'] for r in ok if r['stratum'] == s)}/"
                                              f"{sum(r['stratum'] == s for r in ok)}" for s in QUOTAS},
             "teacher_seconds_mean": round(sum(r["seconds"] for r in raw.values()) / max(len(raw), 1), 2),
             "p_sexual_missing": sum(r["teacher"]["p_sexual"] is None for r in ok)}
    excl = load(EXCLUDED)
    stats["pool_construction_exclusions"] = dict(Counter(e["reason"].split(":")[0] for e in excl))
    (RESULTS / "label_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=1))


EMB = DATA / "embeddings.npz"
STUDENTS = RESULTS / "students"
TARGETS = (0.95, 0.97, 0.99)
KINDS = ("T", "I", "IT")
# dataset labels counted as "harmful" for the bonus student (d): what a student learns WITHOUT the teacher
DATASET_POSITIVE = {"misogynous", "hateful"}


def bench_items() -> list[dict]:
    b = load(BENCH / "sv_images_v1.jsonl")
    return [{"id": x["item_id"], "image": ROOT / x["image"], "text": x["text"], "reference": x["reference"]} for x in b]


def cmd_embed(args):
    """Embeddings of the pool (then the pool images are deleted) and of the benchmark (images stay where they are)."""
    import numpy as np
    from PIL import Image

    from harmwatch.cascade import ImageEmbedder, TextEmbedder

    pool = load(POOL)
    te, ie = TextEmbedder(), ImageEmbedder()
    t0 = time.time()
    pt = te([p["text"] for p in pool])
    pi = np.concatenate([ie([Image.open(IMAGES / f"{p['pid']}.jpg") for p in pool[i:i + 256]])
                         for i in range(0, len(pool), 256)])
    pool_s = time.time() - t0
    bench = bench_items()
    t0 = time.time()
    bt = te([b["text"] for b in bench])
    bi = ie([Image.open(b["image"]) for b in bench])
    bench_s = time.time() - t0
    np.savez(EMB, pool_ids=np.array([p["pid"] for p in pool]), pool_text=pt, pool_image=pi,
             bench_ids=np.array([b["id"] for b in bench]), bench_text=bt, bench_image=bi)
    (DATA / "embed_timing.json").write_text(json.dumps({"pool_seconds": round(pool_s, 1), "pool_n": len(pool),
                                                        "bench_seconds": round(bench_s, 1), "bench_n": len(bench)}))
    if not args.keep_images:  # B5: only embeddings, hashes and labels are kept
        n = sum(1 for f in IMAGES.glob("*.jpg") if not f.unlink())
        IMAGES.rmdir()
        print(f"deleted {n} pool images")
    print(f"embeddings: pool {len(pool)} in {pool_s:.0f}s, benchmark {len(bench)} in {bench_s:.1f}s")


def training_table():
    """(features by kind, teacher y, dataset y, part, pids) for pool rows usable for training."""
    import numpy as np

    E = np.load(EMB)
    idx = {pid: i for i, pid in enumerate(E["pool_ids"])}
    rows = [r for r in load(RESULTS / "teacher_labels.jsonl") if r["teacher"] and r["pid"] in idx]
    ii = np.array([idx[r["pid"]] for r in rows])
    feats = {k: {"T": E["pool_text"], "I": E["pool_image"],
                 "IT": np.concatenate([E["pool_image"], E["pool_text"]], 1)}[k][ii] for k in KINDS}
    y = np.array([bool(r["teacher"]["sexual"]) for r in rows])
    yd = np.array([r["dataset_label"] in DATASET_POSITIVE for r in rows])
    part = np.array([r["part"] for r in rows])
    return feats, y, yd, part, [r["pid"] for r in rows]


def cmd_train(args):
    import joblib
    import numpy as np
    from sklearn.metrics import roc_auc_score

    from harmwatch.cascade import threshold_for_recall, train_student

    feats, y, yd, part, _ = training_table()
    tr, dv = part == "train", part == "dev"
    STUDENTS.mkdir(parents=True, exist_ok=True)
    out = {"n_train": int(tr.sum()), "n_dev": int(dv.sum()), "teacher_positive_rate_train": round(float(y[tr].mean()), 3),
           "students": {}}
    for kind in KINDS:
        for model in ("logreg", "mlp"):
            for target_name, target in (("teacher", y), ("dataset", yd)):
                if target_name == "dataset" and model == "mlp":
                    continue
                name = f"{kind}_{model}" + ("" if target_name == "teacher" else "_datasetlabels")
                t0 = time.time()
                clf = train_student(feats[kind][tr], target[tr], model)
                fit_s = time.time() - t0
                s = clf.predict_proba(feats[kind][dv])[:, 1]
                # thresholds always chosen against the TEACHER on DEV (the cascade must keep the judge's positives)
                th = {f"{int(t * 100)}": threshold_for_recall(s, y[dv], t) for t in TARGETS}
                out["students"][name] = {
                    "kind": kind, "model": model, "target": target_name, "fit_seconds": round(fit_s, 1),
                    "dev_auroc_vs_teacher": round(roc_auc_score(y[dv], s), 3),
                    "thresholds": th,
                    "dev_sent_fraction": {k: round(float((s >= v).mean()), 3) for k, v in th.items()},
                }
                joblib.dump(clf, STUDENTS / f"{name}.joblib")
                print(name, out["students"][name]["dev_auroc_vs_teacher"], out["students"][name]["dev_sent_fraction"], flush=True)
    (RESULTS / "train_metrics.json").write_text(json.dumps(out, indent=2))


def cmd_evaluate(args):
    """Benchmark sv_images_v1 (reference validated by hand): students alone, simulated cascade, judge alone."""
    import joblib
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.metrics import roc_auc_score

    from harmwatch.cascade import cascade, confusion
    from scripts.eval_sv_benchmark import save_matrix

    E = np.load(EMB)
    ids = list(E["bench_ids"])
    feats = {"T": E["bench_text"], "I": E["bench_image"], "IT": np.concatenate([E["bench_image"], E["bench_text"]], 1)}
    ref = {b["item_id"]: b["reference"] for b in load(BENCH / "sv_images_v1.jsonl")}
    yref = np.array([bool(ref[i]["sexual"]) for i in ids])
    v3 = {p["item_id"]: p for p in load(ROOT / "results" / "sv_benchmark_v3" / "qwen35-9b" / "image_text" / "predictions.jsonl")}
    judge = np.array([bool(v3[i]["prediction"]["sexual"]) for i in ids])
    v3_info = json.loads((ROOT / "results" / "sv_benchmark_v3" / "qwen35-9b" / "image_text" / "run_info.json").read_text())
    judge_s_per_img = v3_info["total_seconds"] / v3_info["n_items"]  # measured, 8 parallel requests
    tm = json.loads((RESULTS / "train_metrics.json").read_text())
    timing = json.loads((DATA / "embed_timing.json").read_text())
    emb_s_per_img = timing["bench_seconds"] / timing["bench_n"]  # text + image embeddings, measured on the benchmark
    m = {"judge_alone_v3": {**confusion(yref, judge), "seconds_per_image": round(judge_s_per_img, 3),
                            "note": "v3 was tuned after analysing this set: indicative"},
         "embedding_seconds_per_image": round(emb_s_per_img, 4), "students": {}}
    RESULTS.mkdir(parents=True, exist_ok=True)
    curves = {}
    for name, info in tm["students"].items():
        clf = joblib.load(STUDENTS / f"{name}.joblib")
        t0 = time.time()
        s = clf.predict_proba(feats[info["kind"]])[:, 1]
        clf_s = (time.time() - t0) / len(ids)
        st = {"auroc_vs_reference": round(roc_auc_score(yref, s), 3), "target": info["target"],
              "throughput_images_per_s": round(1 / (emb_s_per_img + clf_s), 1), "alone": {}, "cascade": {}}
        for k, t in info["thresholds"].items():
            st["alone"][k] = confusion(yref, s >= t)
            pred, sent = cascade(s, t, judge)
            est = len(ids) * (emb_s_per_img + clf_s) + sent.sum() * judge_s_per_img
            st["cascade"][k] = {**confusion(yref, pred), "sent_fraction": round(float(sent.mean()), 3),
                                "reference_positives_lost_by_filter": int((yref & ~sent).sum()),
                                "judge_positives_lost_by_filter": int((judge & ~sent).sum()),
                                "estimated_seconds": round(est, 1),
                                "judge_alone_seconds": round(len(ids) * judge_s_per_img, 1),
                                "speedup": round(len(ids) * judge_s_per_img / est, 2)}
            if name in ("T_logreg", "I_logreg", "IT_logreg") and k == "95":
                save_matrix(RESULTS / f"confusion_cascade_{name}_{k}", st["cascade"][k], f"cascade {name} @ recall {k} % (DEV)")
                save_matrix(RESULTS / f"confusion_student_{name}_{k}", st["alone"][k], f"student {name} alone @ {k} %")
        order = np.argsort(-s)
        curves[name] = [(float(sent), float((yref & (s >= s[order[j]])).sum() / yref.sum()))
                        for j, sent in enumerate(np.arange(1, len(ids) + 1) / len(ids))]
        st["scores"] = {i: round(float(v), 4) for i, v in zip(ids, s)}
        m["students"][name] = st
    save_matrix(RESULTS / "confusion_judge_alone_v3", m["judge_alone_v3"], "Qwen3.5-9B v3 alone (indicative)")
    fig, ax = plt.subplots(figsize=(5, 4))
    for name in ("T_logreg", "I_logreg", "IT_logreg"):
        xs, ys = zip(*curves[name])
        ax.plot(xs, ys, label=name.replace("_logreg", ""))
    ax.set_xlabel("fraction of images sent to the judge")
    ax.set_ylabel("recall of confirmed sexual images (benchmark)")
    ax.axhline(0.95, ls="--", lw=0.8, color="grey")
    ax.set_title("student filter: recall vs share sent to Qwen", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "threshold_curve.png", dpi=120)
    plt.close(fig)
    (RESULTS / "metrics.json").write_text(json.dumps(m, indent=2))
    for name, st in m["students"].items():
        c = st["cascade"]["95"]
        print(f"{name:<28} AUROC {st['auroc_vs_reference']} | alone@95 F1 {st['alone']['95']['f1']} | cascade@95 F1 {c['f1']} "
              f"sent {c['sent_fraction']} lost(ref) {c['reference_positives_lost_by_filter']} speedup x{c['speedup']} "
              f"| {st['throughput_images_per_s']} img/s")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pool")
    lb = sub.add_parser("label")
    lb.add_argument("--api-model", default="qwen3.5-9b")
    lb.add_argument("--workers", type=int, default=8)
    sub.add_parser("label-report")
    em = sub.add_parser("embed")
    em.add_argument("--keep-images", action="store_true", help="debug only: do not delete the pool images")
    sub.add_parser("train")
    sub.add_parser("evaluate")
    args = ap.parse_args()
    {"pool": cmd_pool, "label": cmd_label, "label-report": cmd_label_report, "embed": cmd_embed, "train": cmd_train,
     "evaluate": cmd_evaluate}[args.cmd](args)


if __name__ == "__main__":
    main()
