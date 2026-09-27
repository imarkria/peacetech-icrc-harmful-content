"""Extract sexual-violence candidates from data/processed/telegram.jsonl (two stages).

    python scripts/extract_sv.py regex  --region ru_ua     # stage (a): patterns from policy/regions/<region>_filter.yaml
    python scripts/extract_sv.py embed  --region ru_ua     # stage (b): Qwen3-Embedding similarity to the region's positive examples
    python scripts/extract_sv.py report --region ru_ua     # merge → data/processed/sv_candidates.jsonl + counts

Nothing here is region-specific: patterns come from the filter file and prototypes from the examples file.
Posts where an age indicator co-occurs with a hit are marked possible_minor_rule: they are counted, never
displayed, and never sampled for review or training (CH-5).
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harmwatch.lexicon import age_indicators, normalize  # noqa: E402
from harmwatch.policy_loader import region_age_matcher  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
CORPUS = PROCESSED / "telegram.jsonl"
WORD = re.compile(r"\w+")


class Filter:
    def __init__(self, region: str):
        cfg = yaml.safe_load((ROOT / "policy" / "regions" / f"{region}_filter.yaml").read_text(encoding="utf-8"))
        self.age = region_age_matcher(region)  # CH-2 words: generic profile + region age_terms
        self.patterns = []
        for p in cfg["patterns"]:
            if "regex" in p:
                self.patterns.append((p["id"], p["strength"], re.compile(r"(?<!\w)(?:" + p["regex"] + ")"), None))
            else:
                a, b, window = p["near"]
                self.patterns.append((p["id"], p["strength"], (re.compile(rf"^(?:{a})$"), re.compile(rf"^(?:{b})$")),
                                      window))

    def hits(self, text: str) -> list[tuple[str, str]]:
        norm = normalize(text)
        words = None
        found = []
        for pid, strength, pat, window in self.patterns:
            if window is None:
                if pat.search(norm):
                    found.append((pid, strength))
            else:
                words = words or WORD.findall(norm)
                pa = [i for i, w in enumerate(words) if pat[0].match(w)]
                if pa:
                    pb = [i for i, w in enumerate(words) if pat[1].match(w)]
                    if any(abs(i - j) <= window for i in pa for j in pb):
                        found.append((pid, strength))
        return found


def text_hash(text: str) -> str:
    return hashlib.sha1(" ".join(WORD.findall(normalize(text))).encode()).hexdigest()[:16]


_FILTER: Filter | None = None


def _init(region):
    global _FILTER
    _FILTER = Filter(region)


def _scan(lines: list[str]) -> tuple[list[dict], Counter, Counter]:
    out, totals_side, totals_month = [], Counter(), Counter()
    for line in lines:
        rec = json.loads(line)
        totals_side[rec["side"]] += 1
        totals_month[(rec.get("date") or "")[:7] or "unknown"] += 1
        hits = _FILTER.hits(rec["text"])
        if hits:
            rec["filter_hits"] = [h for h, _ in hits]
            rec["filter_strength"] = "strong" if any(s == "strong" for _, s in hits) else "weak"
            rec["possible_minor_rule"] = bool(age_indicators(rec["text"], _FILTER.age))
            rec["text_hash"] = text_hash(rec["text"])
            out.append(rec)
    return out, totals_side, totals_month


def _batches(path: Path, size: int = 20000):
    batch = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            batch.append(line)
            if len(batch) == size:
                yield batch
                batch = []
    if batch:
        yield batch


def stage_regex(region: str, workers: int):
    totals_side, totals_month, n = Counter(), Counter(), 0
    with Pool(workers, initializer=_init, initargs=(region,)) as pool, \
            open(PROCESSED / "sv_regex_hits.jsonl", "w", encoding="utf-8") as out:
        for hits, ts, tm in pool.imap_unordered(_scan, _batches(CORPUS), chunksize=1):
            totals_side.update(ts)
            totals_month.update(tm)
            for rec in hits:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    (PROCESSED / "corpus_totals.json").write_text(
        json.dumps({"by_side": totals_side, "by_month": totals_month}, ensure_ascii=False, indent=1))
    print(f"stage (a): {n} posts with a pattern hit out of {sum(totals_side.values())}")


EMB_DIR = PROCESSED / "emb"
INSTRUCT = ("Instruct: Given a Telegram post, retrieve posts that threaten, glorify, justify, deny or mock sexual "
            "violence, or stigmatise or expose its survivors\nQuery:")


def _load_model():
    import torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cuda",
                                model_kwargs={"dtype": torch.float16})
    model.max_seq_length = 64  # short posts are what patterns miss; long posts are mostly caught by stage (a)
    return model


def prototypes(region: str) -> tuple[list[str], list[str]]:
    """Positive / negative prototype texts from the region's examples file (flag true / false)."""
    pos, neg = [], []
    for line in (ROOT / "policy" / "regions" / f"{region}_examples.jsonl").read_text(encoding="utf-8").splitlines():
        x = json.loads(line)
        if x["expected"]["route"] == "restricted_escalation":
            continue  # abstract placeholder, not a text
        (pos if x["expected"]["flag"] else neg).append(x["text"])
    return pos, neg


def stage_embed(region: str, shard_size: int = 250_000):
    """Embed every distinct text (dedup by normalised hash); score = max cosine to positive / negative prototypes."""
    import numpy as np

    EMB_DIR.mkdir(parents=True, exist_ok=True)
    seen, uids, texts = set(), [], []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            h = hash(" ".join(rec["text"].lower().split()))  # cheap exact-duplicate key
            if h in seen:
                continue
            seen.add(h)
            uids.append(rec["uid"])
            texts.append(rec["text"])
    print(f"{len(texts)} distinct texts to embed", flush=True)
    model = _load_model()
    pos, neg = prototypes(region)
    q_pos = model.encode([INSTRUCT + t for t in pos], normalize_embeddings=True)
    q_neg = model.encode([INSTRUCT + t for t in neg], normalize_embeddings=True)
    (EMB_DIR / "uids.json").write_text(json.dumps(uids))
    for s, start in enumerate(range(0, len(texts), shard_size)):
        out = EMB_DIR / f"shard_{s:03d}.npz"
        if out.exists():
            continue
        emb = model.encode(texts[start:start + shard_size], batch_size=512, normalize_embeddings=True,
                           convert_to_numpy=True).astype(np.float16)
        np.savez(out, emb=emb, pos=(emb @ q_pos.T.astype(np.float16)).max(1),
                 neg=(emb @ q_neg.T.astype(np.float16)).max(1))
        print(f"shard {s}: {start + len(emb)}/{len(texts)}", flush=True)


SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")


def minor_near(text: str, flt: Filter) -> bool:
    """Age indicator in the same sentence as a pattern hit (narrower variant of possible_minor_rule)."""
    return any(age_indicators(s, flt.age) and flt.hits(s) for s in SENTENCE.split(text))


def load_scores():
    import numpy as np

    uids = json.loads((EMB_DIR / "uids.json").read_text())
    pos, neg = [], []
    for shard in sorted(EMB_DIR.glob("shard_*.npz")):
        z = np.load(shard)
        pos.append(z["pos"])
        neg.append(z["neg"])
    pos, neg = np.concatenate(pos).astype("float32"), np.concatenate(neg).astype("float32")
    return uids[:len(pos)], pos, neg


def dup_key(text: str) -> str:
    """Exact-duplicate key: same normalisation as the dedup in stage_embed (case and whitespace)."""
    return hashlib.sha1(" ".join(text.lower().split()).encode()).hexdigest()[:16]


def stage_report(region: str, top_k: int):
    import numpy as np

    flt = Filter(region)
    regex = {}
    with open(PROCESSED / "sv_regex_hits.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            regex[r["uid"]] = r

    uids, pos, neg = load_scores()
    rep_score = dict(zip(uids, zip(pos.tolist(), neg.tolist())))  # representative uid of each distinct text

    # Pass 1: scores by duplicate key (so forwarded copies share their text's score).
    score, key_of = {}, {}
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["uid"] in rep_score or rec["uid"] in regex:
                k = dup_key(rec["text"])
                key_of[rec["uid"]] = k
                if rec["uid"] in rep_score:
                    score[k] = rep_score[rec["uid"]]
    regex_keys = {key_of[u] for u in regex}

    # Stage (b): top-k distinct texts without a pattern hit, closer to the positive than the negative prototypes.
    emb_keys = []
    for i in np.argsort(-pos):
        if len(emb_keys) >= top_k:
            break
        k = key_of.get(uids[i])
        if pos[i] > neg[i] and k not in regex_keys:
            emb_keys.append(k)
    threshold = float(pos[np.argsort(-pos)][0]) if not emb_keys else min(score[k][0] for k in emb_keys)
    emb_keys = set(emb_keys)

    # Weak pattern hits need a second signal: embedding score ≥ median score of strong hits, and pos > neg.
    strong_scores = [score[key_of[u]][0] for u, r in regex.items() if r["filter_strength"] == "strong" and key_of[u] in score]
    weak_threshold = float(np.median(strong_scores)) if strong_scores else 1.0
    dropped_weak = 0
    for u in list(regex):
        r = regex[u]
        s = score.get(key_of[u])
        if r["filter_strength"] == "weak" and not (s and s[0] >= weak_threshold and s[0] > s[1]):
            del regex[u]
            dropped_weak += 1

    # Pass 2: stage (b) records (all copies) + copies / distinct channels per candidate text (coordination).
    copies, channels = Counter(), defaultdict(set)
    cands: dict[str, dict] = {}
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            k = key_of.get(rec["uid"]) or (dup_key(rec["text"]) if rec["uid"] not in regex else None)
            if rec["uid"] in regex:
                cands[rec["uid"]] = regex[rec["uid"]]
            elif k in emb_keys:
                rec.update(filter_hits=[], filter_strength=None, text_hash=text_hash(rec["text"]),
                           possible_minor_rule=bool(age_indicators(rec["text"], flt.age)))
                cands[rec["uid"]] = rec
            else:
                continue
            key_of[rec["uid"]] = k
            copies[k] += 1
            channels[k].add(rec.get("channel"))

    for uid, r in cands.items():
        k = key_of[uid]
        s = score.get(k)
        r["dup_key"] = k
        r["emb_pos"], r["emb_neg"] = (round(s[0], 4), round(s[1], 4)) if s else (None, None)
        in_b = s is not None and s[0] >= threshold and s[0] > s[1]
        r["stage"] = "both" if r["filter_hits"] and in_b else "regex" if r["filter_hits"] else "embedding"
        r["possible_minor_near"] = r["possible_minor_rule"] and minor_near(r["text"], flt)
        r["n_copies"] = copies[k]
        r["n_channels"] = len(channels[k] - {None})
    with open(PROCESSED / "sv_candidates.jsonl", "w", encoding="utf-8") as out:
        for r in cands.values():
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_report(region, list(cands.values()), threshold, top_k,
                 extra=[f"- Weak-only pattern hits dropped (embedding score < {weak_threshold:.3f}, the median of "
                        f"strong hits, or closer to negative prototypes): {dropped_weak:,}"])


def write_report(region: str, cands: list[dict], threshold, top_k: int, extra: list[str] = ()):
    totals = json.loads((PROCESSED / "corpus_totals.json").read_text())
    total = sum(totals["by_side"].values())
    by = lambda key: Counter(key(r) for r in cands)  # noqa: E731
    side, month, stage = by(lambda r: r["side"]), by(lambda r: (r.get("date") or "")[:7] or "unknown"), by(lambda r: r["stage"])
    lines = [
        f"# Sexual-violence candidate extraction: {region}",
        "",
        "Generated by `scripts/extract_sv.py report`. Counts only: no post text in this file. Channel counts describe "
        "where matching *content* appeared; they are not verdicts about channels (B6-1), and low counts never mean "
        "sexual violence is absent (B6-2).",
        "",
        f"- Corpus: **{total:,}** posts · candidates: **{len(cands):,}** ({len(cands) / total:.3%})",
        f"- Stage (a) patterns: {stage['regex'] + stage['both']:,} · stage (b) embeddings only: {stage['embedding']:,} "
        f"(top {top_k:,} distinct texts, cosine ≥ {threshold:.3f}) · both: {stage['both']:,}",
        f"- Strong pattern hits: {sum(r['filter_strength'] == 'strong' for r in cands):,} · weak only: "
        f"{sum(r['filter_strength'] == 'weak' for r in cands):,}",
        f"- Distinct texts: {len({r['text_hash'] for r in cands}):,} · texts relayed by ≥ 3 channels: "
        f"{len({r['text_hash'] for r in cands if r['n_channels'] >= 3}):,}",
        f"- possible_minor_rule (age indicator anywhere): {sum(r['possible_minor_rule'] for r in cands):,} · "
        f"same sentence as a hit: {sum(r['possible_minor_near'] for r in cands):,} — never displayed or sampled",
        f"- With media (indicator only, never downloaded): {sum(bool(r.get('has_media')) for r in cands):,}",
        *extra,
        "",
        "## By side",
        "",
        "| side | candidates | corpus | rate |",
        "|---|---|---|---|",
    ]
    for s, n in side.most_common():
        c = totals["by_side"].get(s, 0)
        lines.append(f"| {s} | {n:,} | {c:,} | {n / c:.3%} |" if c else f"| {s} | {n:,} | ? | ? |")
    lines += ["", "## By language", "", "| lang | candidates |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in by(lambda r: r["lang"]).most_common()]
    lines += ["", "## By pattern (stage a)", "", "| pattern | posts |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in Counter(h for r in cands for h in r["filter_hits"]).most_common()]
    lines += ["", "## By month", "", "| month | candidates | corpus | rate |", "|---|---|---|---|"]
    for m in sorted(month):
        c = totals["by_month"].get(m, 0)
        lines.append(f"| {m} | {month[m]:,} | {c:,} | {month[m] / c:.3%} |" if c else f"| {m} | {month[m]:,} | ? | ? |")
    lines += ["", "## Top 25 channels", "", "| channel | side | candidates |", "|---|---|---|"]
    ch_side = {r.get("channel"): r["side"] for r in cands}
    for ch, n in by(lambda r: r.get("channel") or f"({r['source']}, no channel)").most_common(25):
        lines.append(f"| {ch} | {ch_side.get(ch, '')} | {n:,} |")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"extraction_{region}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["regex", "embed", "report"])
    ap.add_argument("--region", default="ru_ua")
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--top-k", type=int, default=5000, help="stage (b): distinct texts kept by embedding score")
    args = ap.parse_args()
    if args.stage == "regex":
        stage_regex(args.region, args.workers)
    elif args.stage == "embed":
        stage_embed(args.region)
    elif args.stage == "report":
        stage_report(args.region, args.top_k)
