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


BUDGET = 0.5  # "reasonable" operating point: at most half of the images sent to the judge
MIN_DEV_RECALL = 0.90


def cmd_train(args):
    """Students T / I / IT × (logreg, MLP) × balancing (class weights vs 50/50 undersampling), regularisation by CV on
    TRAIN only; the balancing option is chosen on DEV (AUROC, then recall at the 50 % budget); thresholds for recall
    95 / 97 / 99 % vs the teacher on DEV. The benchmark is never touched here."""
    import joblib
    import numpy as np
    from sklearn.metrics import roc_auc_score

    from harmwatch.cascade import recall_at_budget, threshold_for_recall, train_student

    feats, y, yd, part, _ = training_table()
    tr, dv = part == "train", part == "dev"
    STUDENTS.mkdir(parents=True, exist_ok=True)
    out = {"n_train": int(tr.sum()), "n_dev": int(dv.sum()), "teacher_positive_train": int(y[tr].sum()),
           "teacher_positive_dev": int(y[dv].sum()), "budget": BUDGET, "candidates": {}, "students": {}}
    for kind in KINDS:
        for model in ("logreg", "mlp"):
            best = None
            for balance in ("weight", "undersample"):
                t0 = time.time()
                clf, info = train_student(feats[kind][tr], y[tr], model, balance)
                s = clf.predict_proba(feats[kind][dv])[:, 1]
                auroc = roc_auc_score(y[dv], s)
                rec_budget, _ = recall_at_budget(s, y[dv], BUDGET)
                cand = {"balance": balance, **info, "fit_seconds": round(time.time() - t0, 1),
                        "dev_auroc_vs_teacher": round(auroc, 3), "dev_recall_at_budget": round(rec_budget, 3)}
                out["candidates"][f"{kind}_{model}_{balance}"] = cand
                if best is None or (auroc, rec_budget) > (best[1]["dev_auroc_vs_teacher"], best[1]["dev_recall_at_budget"]):
                    best = (clf, cand, s)
            clf, cand, s = best
            name = f"{kind}_{model}"
            th = {f"{int(t * 100)}": threshold_for_recall(s, y[dv], t) for t in TARGETS}
            out["students"][name] = {"kind": kind, "model": model, "target": "teacher", **cand, "thresholds": th,
                                     "dev_sent_fraction": {k: round(float((s >= v).mean()), 3) for k, v in th.items()}}
            joblib.dump(clf, STUDENTS / f"{name}.joblib")
            print(name, cand["balance"], cand["best_params"], "AUROC", cand["dev_auroc_vs_teacher"],
                  "recall@50%", cand["dev_recall_at_budget"], "sent", out["students"][name]["dev_sent_fraction"], flush=True)
    # bonus (d): the same student trained on the DATASET labels (misogynous / hateful) instead of the teacher
    for kind in KINDS:
        clf, info = train_student(feats[kind][tr], yd[tr], "logreg", "weight")
        s = clf.predict_proba(feats[kind][dv])[:, 1]
        th = {f"{int(t * 100)}": threshold_for_recall(s, y[dv], t) for t in TARGETS}  # still measured vs the teacher
        out["students"][f"{kind}_logreg_datasetlabels"] = {
            "kind": kind, "model": "logreg", "target": "dataset", "balance": "weight", **info, "thresholds": th,
            "dev_auroc_vs_teacher": round(roc_auc_score(y[dv], s), 3),
            "dev_recall_at_budget": round(recall_at_budget(s, y[dv], BUDGET)[0], 3),
            "dev_sent_fraction": {k: round(float((s >= v).mean()), 3) for k, v in th.items()}}
        joblib.dump(clf, STUDENTS / f"{kind}_logreg_datasetlabels.joblib")
    teacher_students = {k: v for k, v in out["students"].items() if v["target"] == "teacher"}
    best_name = max(teacher_students, key=lambda k: (teacher_students[k]["dev_auroc_vs_teacher"],
                                                     teacher_students[k]["dev_recall_at_budget"]))
    out["best_student"] = best_name
    out["stop"] = teacher_students[best_name]["dev_recall_at_budget"] < MIN_DEV_RECALL
    (RESULTS / "train_metrics.json").write_text(json.dumps(out, indent=2))
    print(f"best student: {best_name} · DEV recall at {int(BUDGET * 100)} % sent = "
          f"{teacher_students[best_name]['dev_recall_at_budget']}" + ("  → STOP (< 90 %)" if out["stop"] else ""))


def cmd_evaluate(args):
    """Benchmark sv_images_v1 (reference validated by hand), never used before this step: students alone, simulated
    cascade with the v3 AND v1 judge predictions already computed (no new judge run), judge alone."""
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
    judges = {}
    for pv, folder in (("v3", "sv_benchmark_v3"), ("v1", "sv_benchmark")):
        d = ROOT / "results" / folder / "qwen35-9b" / "image_text"
        preds = {p["item_id"]: p for p in load(d / "predictions.jsonl")}
        info = json.loads((d / "run_info.json").read_text())
        judges[pv] = {"decision": np.array([bool(preds[i]["prediction"]["sexual"]) for i in ids]),
                      "s_per_img": info["total_seconds"] / info["n_items"]}
    tm = json.loads((RESULTS / "train_metrics.json").read_text())
    timing = json.loads((DATA / "embed_timing.json").read_text())
    emb_s = timing["bench_seconds"] / timing["bench_n"]
    m = {"judge_alone": {pv: {**confusion(yref, j["decision"]), "seconds_per_image": round(j["s_per_img"], 3)}
                         for pv, j in judges.items()},
         "embedding_seconds_per_image": round(emb_s, 4), "students": {}, "best_student": tm["best_student"]}
    curves = {}
    for name, info in tm["students"].items():
        clf = joblib.load(STUDENTS / f"{name}.joblib")
        t0 = time.time()
        s = clf.predict_proba(feats[info["kind"]])[:, 1]
        clf_s = (time.time() - t0) / len(ids)
        per_img = emb_s + clf_s
        st = {"target": info["target"], "auroc_vs_reference": round(roc_auc_score(yref, s), 3),
              "seconds_per_image": round(per_img, 4), "images_per_second": round(1 / per_img, 1),
              "alone": {}, "cascade": {pv: {} for pv in judges}}
        for k, t in info["thresholds"].items():
            st["alone"][k] = confusion(yref, s >= t)
            for pv, j in judges.items():
                pred, sent = cascade(s, t, j["decision"])
                est = len(ids) * per_img + sent.sum() * j["s_per_img"]
                st["cascade"][pv][k] = {**confusion(yref, pred), "sent_fraction": round(float(sent.mean()), 3),
                                        "sent_n": int(sent.sum()),
                                        "reference_positives_lost_by_filter": int((yref & ~sent).sum()),
                                        "judge_positives_lost_by_filter": int((j["decision"] & ~sent).sum()),
                                        "estimated_seconds": round(est, 1),
                                        "judge_alone_seconds": round(len(ids) * j["s_per_img"], 1),
                                        "speedup": round(len(ids) * j["s_per_img"] / est, 2)}
        order = np.sort(s)[::-1]
        curves[name] = [(float((s >= t).mean()), float((yref & (s >= t)).sum() / yref.sum())) for t in order]
        st["scores"] = {i: round(float(v), 4) for i, v in zip(ids, s)}
        m["students"][name] = st
    RESULTS.mkdir(parents=True, exist_ok=True)
    best = tm["best_student"]
    for pv in judges:
        save_matrix(RESULTS / f"confusion_judge_alone_{pv}", m["judge_alone"][pv], f"Qwen3.5-9B alone · prompt {pv}")
        for k in ("95", "97", "99"):
            save_matrix(RESULTS / f"confusion_cascade_{best}_{pv}_{k}", m["students"][best]["cascade"][pv][k],
                        f"cascade {best} → Qwen {pv} · DEV recall {k} %")
    for k in ("95", "97", "99"):
        save_matrix(RESULTS / f"confusion_student_{best}_{k}", m["students"][best]["alone"][k], f"student {best} alone · {k} %")
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for i, name in enumerate(("T_logreg", "I_logreg", "IT_logreg")):
        if name in curves:
            xs, ys = zip(*curves[name])
            ax.plot(xs, ys, lw=2, color=["#2a78d6", "#eb6834", "#1baf7a"][i], label=name.split("_")[0])
    ax.axhline(0.95, ls="--", lw=0.8, color="#8a8984")
    ax.set_xlabel("share of benchmark images sent to the judge")
    ax.set_ylabel("recall of confirmed sexual images")
    ax.set_title("Student filter on sv_images_v1: recall vs share sent", fontsize=9, loc="left")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(RESULTS / "threshold_curve.png", dpi=140)
    plt.close(fig)
    (RESULTS / "metrics.json").write_text(json.dumps(m, indent=2))
    for name, st in m["students"].items():
        for pv in ("v3", "v1"):
            c = st["cascade"][pv]["95"]
            print(f"{name:<26} {pv} AUROC {st['auroc_vs_reference']} | alone@95 F1 {st['alone']['95']['f1']} | cascade@95 "
                  f"F1 {c['f1']} sent {c['sent_fraction']} lost {c['reference_positives_lost_by_filter']} x{c['speedup']} "
                  f"| {st['images_per_second']} img/s")


def cmd_figures(args):
    """Three figures for docs/RESULTS_CASCADE.md (from results/cascade/*.json only; no dataset image)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    SER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "font.size": 9,
                         "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left",
                         "axes.titleweight": "bold", "legend.frameon": False})
    m = json.loads((RESULTS / "metrics.json").read_text())
    proj = json.loads((RESULTS / "prevalence_projection.json").read_text())
    best = m["best_student"]
    ref = {b["item_id"]: b["reference"]["sexual"] for b in load(BENCH / "sv_images_v1.jsonl")}
    out = ROOT / "docs" / "figures"
    out.mkdir(parents=True, exist_ok=True)

    # 1. confusion: Qwen v3 alone vs cascade (best student @ DEV recall 95 %)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("b", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    mats = [("Qwen3.5-9B alone (prompt v3)", m["judge_alone"]["v3"]),
            (f"Cascade: {best} → Qwen v3 (95 %)", m["students"][best]["cascade"]["v3"]["95"])]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4))
    for ax, (title, c) in zip(axes, mats):
        v = [[c["TP"], c["FN"]], [c["FP"], c["TN"]]]
        ax.imshow(v, cmap=cmap, vmin=0, vmax=60)
        for i, (row, tags) in enumerate(zip(v, (("TP", "FN"), ("FP", "TN")))):
            for j, (val, tag) in enumerate(zip(row, tags)):
                ax.text(j, i, f"{tag}\n{val}", ha="center", va="center", fontsize=13, fontweight="bold",
                        color="#ffffff" if val > 33 else INK)
        ax.set_xticks([0, 1], ["pred: sexual", "pred: not sexual"], fontsize=8)
        ax.set_yticks([0, 1], ["ref: sexual", "ref: not"], fontsize=8, rotation=90, va="center")
        ax.set_title(f"{title}\nF1 {c['f1']:.3f}", fontsize=9)
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "cascade_confusion_qwen_vs_cascade.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 2. recall vs share sent to the judge (benchmark), three students, operating points marked
    fig, ax = plt.subplots(figsize=(6, 4))
    for k, name in enumerate(("T_logreg", "I_logreg", "IT_logreg")):
        sc = m["students"][name]["scores"]
        ids = list(sc)
        s, y = np.array([sc[i] for i in ids]), np.array([ref[i] for i in ids])
        ts = np.sort(s)[::-1]
        xs = [(s >= t).mean() for t in ts]
        ys = [(y & (s >= t)).sum() / y.sum() for t in ts]
        ax.plot(xs, ys, lw=2, color=SER[k], label={"T": "T (text)", "I": "I (image)", "IT": "I+T"}[name.split("_")[0]])
    for k, off in zip(("95", "97", "99"), ((-30, -22), (-4, -34), (-10, -22))):
        c = m["students"][best]["cascade"]["v3"][k]
        rec = (60 - c["reference_positives_lost_by_filter"]) / 60
        ax.scatter([c["sent_fraction"]], [rec], s=70, color=SER[1], edgecolor=SURF, linewidth=2, zorder=5)
        ax.annotate(f"{k} %", (c["sent_fraction"], rec), xytext=off, textcoords="offset points", fontsize=8,
                    color=INK2, arrowprops={"arrowstyle": "-", "color": GRID, "lw": 0.8})
    ax.plot([0.5, 0.5], [0, 1.02], ls=":", lw=1, color=INK2)
    ax.text(0.505, 0.3, "50 % of the benchmark\nis positive", fontsize=7, color=INK2)
    ax.text(0.02, 0.93, f"dots: {best} at DEV recall 95 / 97 / 99 %", fontsize=7, color=INK2)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.02)
    ax.grid(color=GRID)
    ax.set_xlabel("share of images sent to the judge")
    ax.set_ylabel("recall of confirmed sexual images")
    ax.set_title("Student filter on sv_images_v1 (120 images)")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "cascade_recall_vs_sent.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 3. time per image
    J = m["judge_alone"]["v3"]["seconds_per_image"]
    c95 = m["students"][best]["cascade"]["v3"]["95"]
    bars = [("student filter only", m["students"][best]["seconds_per_image"]),
            ("Qwen3.5-9B on every image", J),
            ("cascade · benchmark (50 % positive)", c95["estimated_seconds"] / 120),
            ("cascade · projected at 5 % prevalence", J / proj["95"]["prev_0.05"]["speedup"])]
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    ys = list(range(len(bars)))[::-1]
    for yi, (lab, v), col in zip(ys, bars, [SER[2], SER[0], SER[1], SER[1]]):
        ax.barh(yi, v, color=col, height=0.55, edgecolor=SURF, linewidth=2)
        ax.text(v + 0.03, yi, f"{v:.3f} s", va="center", fontsize=8, color=INK)
    ax.set_yticks(ys, [b[0] for b in bars])
    ax.set_xlim(0, J * 1.25)
    ax.grid(axis="x", color=GRID)
    ax.set_xlabel("seconds per image (V100, 8 parallel judge requests)")
    ax.set_title("Time per image")
    fig.text(0.01, -0.05, "Projection = DEV false-positive rate of the filter (41 %) applied at 5 % prevalence; not measured.",
             fontsize=7, color=INK2)
    fig.tight_layout()
    fig.savefig(out / "cascade_time_per_image.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("figures written to", out)


STREAM = DATA / "stream"
STREAM_N = 1000


def used_hashes() -> tuple[set[str], dict[str, int]]:
    """sha256 + pHash of everything already used: pool (kept and excluded), the 265 benchmark candidates (incl. the
    120 test images and the 57 ambiguous) and the 240 memes of the abandoned first test."""
    from PIL import Image

    sha, ph = set(), {}
    for r in load(POOL) + load(EXCLUDED):
        sha.add(r["sha256"])
        ph[r["pid"]] = int(r["phash"], 16)
    for c in load(BENCH / "sv_images_v1_candidates.jsonl"):
        sha.add(c["sha256"])
        ph[c["cid"]] = phash(Image.open(ROOT / c["image"]))
    for r in load(ROOT / "data" / "images" / "memelens" / "sample.jsonl"):
        sha.add(r["sha256"])
        ph["s_" + r["id"]] = phash(Image.open(ROOT / r["image"]))
    return sha, ph


def cmd_stream_build(args):
    """1000 never-used MemeLens memes drawn uniformly (seed 42) from the same subsets, safety + age rule applied."""
    import pyarrow.parquet as pq
    from PIL import Image

    from harmwatch.lexicon import age_indicators
    from harmwatch.safety import ImageSafety

    (STREAM / "images").mkdir(parents=True, exist_ok=True)
    used_sha, used_ph = used_hashes()
    union = [(key, it) for key, rows in strata().items() for it in rows]
    rng = random.Random(SEED)
    rng.shuffle(union)
    draw = union[:int(STREAM_N * 1.8)]
    by_file: dict[str, list] = {}
    for order, (key, (sub, f, i)) in enumerate(draw):
        by_file.setdefault(f, []).append((order, key, sub, i))
    items = {}
    for f, wanted in by_file.items():
        t = pq.read_table(f, columns=["id", "image", "text", "label"])
        for order, key, sub, i in wanted:
            r = t.slice(i, 1).to_pylist()[0]
            items[order] = {"stratum": key, "subset": sub, "dataset_id": r["id"], "text": r["text"] or "",
                            "dataset_label": r["label"], "bytes": r["image"]["bytes"]}
        del t
    safety = ImageSafety()
    kept, excluded, hashes = [], [], {}
    for order in range(len(draw)):
        if len(kept) == STREAM_N:
            break
        it = items[order]
        raw = it.pop("bytes")
        sha = hashlib.sha256(raw).hexdigest()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        h = phash(img)
        sid = f"s{order:05d}"
        reason = None
        if sha in used_sha or near_duplicates({sid: h}, used_ph):
            reason = "already_used_or_near_copy"
        elif near_duplicates({sid: h}, hashes):
            reason = "stream_near_duplicate"
        elif age_indicators(it["text"]):
            reason = "age_indicator_in_text"
        else:
            d = safety.check(img)
            if d.quarantine:
                reason = "explicit_quarantine"
        if reason:
            excluded.append({"sid": sid, "stratum": it["stratum"], "reason": reason})
            continue
        img.thumbnail((768, 768))
        img.save(STREAM / "images" / f"{sid}.jpg", "JPEG", quality=90)
        hashes[sid] = h
        kept.append({"sid": sid, **it, "sha256": sha, "phash": f"{h:016x}"})
    (STREAM / "stream.jsonl").write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kept) + "\n")
    (STREAM / "excluded.jsonl").write_text("\n".join(json.dumps(e) for e in excluded) + "\n")
    from collections import Counter
    print(len(kept), "kept ·", dict(Counter(e["reason"] for e in excluded)), "· by subset", dict(Counter(k["subset"] for k in kept)))


def cmd_stream_filter(args):
    """Student filter on the stream: SigLIP2 image embedding + I_logreg (threshold for DEV recall 95 %), timed."""
    import joblib
    import numpy as np
    import torch
    from PIL import Image

    from harmwatch.cascade import ImageEmbedder

    tm = json.loads((RESULTS / "train_metrics.json").read_text())
    best = tm["best_student"]
    info = tm["students"][best]
    if info["kind"] != "I":
        sys.exit(f"best student {best} is not image-only: extend this command")
    rows = load(STREAM / "stream.jsonl")
    ie = ImageEmbedder()
    clf = joblib.load(STUDENTS / f"{best}.joblib")
    ie([Image.new("RGB", (64, 64))])  # warm-up (CUDA kernels), not timed
    torch.cuda.synchronize()
    t0 = time.time()
    emb = np.concatenate([ie([Image.open(STREAM / "images" / f"{r['sid']}.jpg") for r in rows[i:i + 64]])
                          for i in range(0, len(rows), 64)])
    s = clf.predict_proba(emb)[:, 1]
    torch.cuda.synchronize()
    total = time.time() - t0
    th = info["thresholds"]
    np.savez(STREAM / "stream_filter.npz", sids=np.array([r["sid"] for r in rows]), image_emb=emb, scores=s)
    out = {"student": best, "thresholds": th, "seconds_total": round(total, 2), "images": len(rows),
           "images_per_second": round(len(rows) / total, 1),
           "sent_fraction": {k: round(float((s >= v).mean()), 3) for k, v in th.items()}}
    (STREAM / "filter_run.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out))


def cmd_stream_judge(args):
    """Reference: Qwen3.5-9B with sv_prompt_v3 frozen on ALL stream memes (resumable), wall time measured."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image

    from scripts.eval_sv_benchmark import check_prompt, make_scorer

    scorer, _ = make_scorer(args.api_model, True, "v3")
    check_prompt(scorer, "v3")
    out_path = STREAM / "judge_v3.jsonl"
    done = {r["sid"] for r in load(out_path)}
    todo = [r for r in load(STREAM / "stream.jsonl") if r["sid"] not in done]
    lock, f = threading.Lock(), open(out_path, "a", encoding="utf-8")
    t0 = time.time()

    def one(r):
        res = scorer.assess({"id": r["sid"], "image": Image.open(STREAM / "images" / f"{r['sid']}.jpg"), "text": r["text"],
                             "lang": "en", "modality": "meme" if r["text"].strip() else "image"})
        a = res["assessment"]
        rec = {"sid": r["sid"], "error": res["error"], "seconds": round(res["seconds"], 2)}
        if a:
            rec.update(sexual=a.sexual, possible_minor=a.possible_minor, p_sexual=(a.p_true or {}).get("sexual"),
                       category=a.category, reason=a.reason)
        with lock:
            f.write(json.dumps(rec) + "\n")
            f.flush()
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(one, todo))
    f.close()
    wall = time.time() - t0
    runs = load(STREAM / "judge_runs.jsonl") + [{"n": len(todo), "wall_seconds": round(wall, 1), "workers": args.workers}]
    (STREAM / "judge_runs.jsonl").write_text("\n".join(json.dumps(x) for x in runs) + "\n")
    print(f"judged {len(todo)} in {wall / 60:.1f} min ({60 * len(todo) / max(wall, 1):.1f} img/min)")


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 3), round(c + h, 3)]


def cmd_stream_score(args):
    """Filter vs Qwen on the stream (Qwen = reference): confusion, precision, recall, prevalence, share sent,
    real time factor with CIs; projection at 1 / 5 / 10 % prevalence from the measured TPR / FPR."""
    import numpy as np

    from harmwatch.cascade import confusion

    F = np.load(STREAM / "stream_filter.npz")
    fr = json.loads((STREAM / "filter_run.json").read_text())
    judge = {r["sid"]: r for r in load(STREAM / "judge_v3.jsonl")}
    runs = load(STREAM / "judge_runs.jsonl")
    j_per_img = sum(r["wall_seconds"] for r in runs) / sum(r["n"] for r in runs)
    f_per_img = fr["seconds_total"] / fr["images"]
    rows = {r["sid"]: r for r in load(STREAM / "stream.jsonl")}
    sids, scores = list(F["sids"]), F["scores"]
    ok = [i for i, sid in enumerate(sids) if judge.get(sid) and judge[sid].get("error") is None and "sexual" in judge[sid]]
    # possible_minor = escalation: it must reach the judge, so it counts as positive (sexual = True after the hard rule)
    y = np.array([bool(judge[sids[i]]["sexual"]) for i in ok])
    s = scores[ok]
    out = {"n_stream": len(sids), "n_judged_ok": len(ok), "judge_errors": len(sids) - len(ok),
           "possible_minor": sum(bool(judge[sids[i]].get("possible_minor")) for i in ok),
           "prevalence": round(float(y.mean()), 4), "prevalence_ci95": wilson(int(y.sum()), len(y)),
           "filter_seconds_per_image": round(f_per_img, 4), "judge_seconds_per_image": round(j_per_img, 3),
           "by_subset": {}, "thresholds": {}}
    from collections import Counter
    for sub, n in Counter(rows[sids[i]]["subset"] for i in ok).items():
        pos = sum(1 for i in ok if rows[sids[i]]["subset"] == sub and judge[sids[i]]["sexual"])
        out["by_subset"][sub] = {"n": n, "judge_sexual": pos}
    rng = np.random.default_rng(SEED)
    for k, t in fr["thresholds"].items():
        sent = s >= t
        c = confusion(y, sent)
        tp, fn, fp, tn = c["TP"], c["FN"], c["FP"], c["TN"]
        speed = lambda sn: j_per_img / (f_per_img + sn * j_per_img)  # noqa: E731
        boot = []
        for _ in range(2000):
            b = rng.integers(0, len(y), len(y))
            boot.append(speed(float(sent[b].mean())))
        tpr, fpr = tp / max(tp + fn, 1), fp / max(fp + tn, 1)
        out["thresholds"][k] = {
            **c, "recall_ci95": wilson(tp, tp + fn), "sent_fraction": round(float(sent.mean()), 4),
            "sent_ci95": wilson(int(sent.sum()), len(sent)), "fpr": round(fpr, 4), "fpr_ci95": wilson(fp, fp + tn),
            "real_time_factor": round(speed(float(sent.mean())), 2),
            "real_time_factor_ci95": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
            "projection": {f"{int(p * 100)}%": {"sent": round(tpr * p + fpr * (1 - p), 3),
                                                "speedup": round(speed(tpr * p + fpr * (1 - p)), 2),
                                                "positives_lost_per_1000": round(1000 * p * (1 - tpr), 1)}
                           for p in (0.01, 0.05, 0.10)},
            "missed": [{"sid": sids[i], "subset": rows[sids[i]]["subset"], "score": round(float(scores[i]), 4),
                        "judge_category": judge[sids[i]].get("category"), "judge_reason": judge[sids[i]].get("reason")}
                       for i, ok_i in zip(ok, (~sent) & y) if ok_i]}
    (RESULTS / "stream_metrics.json").write_text(json.dumps(out, indent=2))
    c = out["thresholds"]["95"]
    print(json.dumps({k: out[k] for k in ("n_judged_ok", "prevalence", "prevalence_ci95", "possible_minor", "by_subset",
                                          "filter_seconds_per_image", "judge_seconds_per_image")}))
    print(json.dumps({k: v for k, v in c.items() if k != "missed"}, indent=1))
    print("missed:", len(c["missed"]))


def cmd_filter_test(args):
    """Frozen filter (best student, threshold for DEV recall 95 %) at ~10 % prevalence, from EXISTING embeddings and
    labels only (no judge call): 120 benchmark images (hand-validated reference: 60 / 60) + the DEV negatives
    (teacher labels, never used for training). Same measures on the 120 alone for comparison."""
    import joblib
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    from harmwatch.cascade import confusion

    tm = json.loads((RESULTS / "train_metrics.json").read_text())
    best = tm["best_student"]
    info = tm["students"][best]
    t = info["thresholds"]["95"]
    clf = joblib.load(STUDENTS / f"{best}.joblib")
    E = np.load(EMB)
    feats_b = {"T": E["bench_text"], "I": E["bench_image"], "IT": np.concatenate([E["bench_image"], E["bench_text"]], 1)}
    ref = {b["item_id"]: b for b in load(BENCH / "sv_images_v1.jsonl")}
    bids = list(E["bench_ids"])
    sb = clf.predict_proba(feats_b[info["kind"]])[:, 1]
    yb = np.array([bool(ref[i]["reference"]["sexual"]) for i in bids])
    feats, y, _, part, pids = training_table()
    dev_neg = (part == "dev") & ~y
    sd = clf.predict_proba(feats[info["kind"]][dev_neg])[:, 1]
    fr = json.loads((STREAM / "filter_run.json").read_text()) if (STREAM / "filter_run.json").exists() else None
    f_s = fr["seconds_total"] / fr["images"] if fr else json.loads((DATA / "embed_timing.json").read_text())["bench_seconds"] / 120
    J = 1.51  # Qwen3.5-9B v3, seconds per image measured on the benchmark (8 parallel requests)

    def measure(scores, labels, label):
        sent = scores >= t
        c = confusion(labels, sent)
        tp, fn, fp, tn = c["TP"], c["FN"], c["FP"], c["TN"]
        frac = float(sent.mean())
        return {"set": label, "n": int(len(labels)), "positives": int(labels.sum()), "prevalence": round(float(labels.mean()), 3),
                "positives_passed_TP": tp, "positives_blocked_FN": fn, "negatives_passed_FP": fp, "negatives_blocked_TN": tn,
                "recall": c["recall"], "recall_ci95": wilson(tp, tp + fn),
                "false_pass_rate": round(fp / max(fp + tn, 1), 3), "false_pass_rate_ci95": wilson(fp, fp + tn),
                "sent_fraction": round(frac, 3), "sent_ci95": wilson(int(sent.sum()), len(sent)),
                "time_per_image_cascade_s": round(f_s + frac * J, 3), "time_per_image_qwen_s": J,
                "speedup": round(J / (f_s + frac * J), 2), "confusion": c}

    s_all, y_all = np.concatenate([sb, sd]), np.concatenate([yb, np.zeros(len(sd), bool)])
    out = {"student": best, "threshold_dev_recall_95": t, "filter_seconds_per_image": round(f_s, 4),
           "judge_seconds_per_image": J,
           "mix": measure(s_all, y_all, f"120 benchmark + {len(sd)} DEV negatives"),
           "benchmark_only": measure(sb, yb, "120 benchmark"),
           "blocked_positives": [{"item_id": i, "category": ref[i]["reference"]["category"],
                                  "reason": ref[i]["reference"]["reason"], "score": round(float(v), 4)}
                                 for i, v, yy in zip(bids, sb, yb) if yy and v < t]}
    (RESULTS / "filter_test_10pct.json").write_text(json.dumps(out, indent=2))

    INK, SURF = "#0b0b0b", "#fcfcfb"
    cmap = LinearSegmentedColormap.from_list("b", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), facecolor=SURF)
    for ax, key, title in zip(axes, ("mix", "benchmark_only"),
                              (f"{out['mix']['n']} images · {out['mix']['prevalence'] * 100:.1f} % positive",
                               "120 benchmark images · 50 % positive")):
        m = out[key]
        v = [[m["positives_passed_TP"], m["positives_blocked_FN"]], [m["negatives_passed_FP"], m["negatives_blocked_TN"]]]
        vmax = max(max(r) for r in v)
        ax.imshow(np.log1p(v), cmap=cmap, vmin=0, vmax=np.log1p(vmax))
        for i, row in enumerate(v):
            for j, val in enumerate(row):
                tag = [["passed", "blocked"], ["passed", "blocked"]][i][j]
                ax.text(j, i, f"{tag}\n{val}", ha="center", va="center", fontsize=12, fontweight="bold",
                        color="#ffffff" if np.log1p(val) > 0.6 * np.log1p(vmax) else INK)
        ax.set_xticks([0, 1], ["sent to Qwen", "blocked by filter"], fontsize=8)
        ax.set_yticks([0, 1], ["sexual (60)", f"not sexual ({m['n'] - 60})"], fontsize=8, rotation=90, va="center")
        ax.set_title(f"{title}\nrecall {m['recall']:.3f} · sent {m['sent_fraction'] * 100:.0f} % · x{m['speedup']}",
                     fontsize=9, loc="left", fontweight="bold")
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.text(0.01, -0.02, "Filter I_logreg, threshold frozen on DEV (recall 95 %). Colour = log count. "
             "DEV negatives labelled by Qwen (not checked by hand).", fontsize=7, color="#52514e")
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "figures" / "cascade_filter_10pct_confusion.png", dpi=160, bbox_inches="tight",
                facecolor=SURF)
    plt.close(fig)
    for k in ("mix", "benchmark_only"):
        m = out[k]
        print(k, {x: m[x] for x in ("n", "prevalence", "positives_passed_TP", "positives_blocked_FN", "negatives_passed_FP",
                                    "negatives_blocked_TN", "recall", "recall_ci95", "false_pass_rate",
                                    "false_pass_rate_ci95", "sent_fraction", "speedup")})
    print("blocked positives:", out["blocked_positives"], "· filter s/img", out["filter_seconds_per_image"])


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
    sub.add_parser("figures")
    sub.add_parser("stream-build")
    sub.add_parser("stream-filter")
    sj = sub.add_parser("stream-judge")
    sj.add_argument("--api-model", default="qwen3.5-9b")
    sj.add_argument("--workers", type=int, default=8)
    sub.add_parser("stream-score")
    sub.add_parser("filter-test")
    args = ap.parse_args()
    {"pool": cmd_pool, "label": cmd_label, "label-report": cmd_label_report, "embed": cmd_embed, "train": cmd_train,
     "evaluate": cmd_evaluate, "figures": cmd_figures, "stream-build": cmd_stream_build,
     "stream-filter": cmd_stream_filter, "stream-judge": cmd_stream_judge, "stream-score": cmd_stream_score,
     "filter-test": cmd_filter_test}[args.cmd](args)


if __name__ == "__main__":
    main()
