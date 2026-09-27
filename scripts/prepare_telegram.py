"""Convert the raw Telegram datasets in data/raw/ to one common schema: data/processed/telegram.jsonl.

    python scripts/prepare_telegram.py [--workers 32]

Sources (text + metadata only, no media is ever downloaded):
  figshare  "Telegram as a Battlefield" (CC BY 4.0): pro-Kremlin and anti-Kremlin (Russian opposition) channels
  osf       milbloggers (CC BY): Russian military bloggers; the CSV has no channel column
  dehum     VettyCher/dehumanisation_study: 1,000 manually labelled posts (Russian and Ukrainian channels)

Schema: uid, source, side, channel, post_id, date, text, lang, has_media, media_type, views, forwards,
replies, reactions, is_forward, fwd_from, extra.
"""

import argparse
import ast
import csv
import glob
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harmwatch.lexicon import guess_lang  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
csv.field_size_limit(sys.maxsize)


def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _literal(x, default):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else default
    except (ValueError, SyntaxError):
        return default


def channel_sides() -> dict[str, str]:
    sides = {}
    for name in ("pro_kremlin_channels_list", "anti_kremlin_channel_list"):
        for _, r in pd.read_csv(RAW / "figshare" / f"{name}.csv").iterrows():
            side = "pro_kremlin" if r.pro_kremlin == 1 else "anti_kremlin_opposition" if r.anti_kremlin == 1 else "other"
            sides[str(r.username).lower()] = side
    return sides


def figshare_file(args) -> tuple[str, int]:
    path, default_side, sides = args
    part = OUT / "parts" / (Path(path).stem + ".jsonl")
    n = 0
    with open(part, "w", encoding="utf-8") as out:
        for chunk in pd.read_csv(path, chunksize=100_000, dtype=str, engine="python", on_bad_lines="skip"):
            for r in chunk.itertuples(index=False):
                text = r.message if isinstance(r.message, str) else ""
                if not text.strip():
                    continue
                media = _literal(r.media, {})
                fwd = _literal(r.fwd_from, [False, -1])
                reactions = _literal(r.reactions, {}) or {}
                channel = str(r.channel)
                has_media = bool(media.get("photos") or media.get("videos")) if isinstance(media, dict) else False
                rec = {
                    "uid": f"fs:{channel}:{r.post_id}",
                    "source": "figshare",
                    "side": sides.get(channel.lower(), default_side),
                    "channel": channel,
                    "post_id": r.post_id,
                    "date": (r.post_datetime or "")[:19],
                    "text": text,
                    "lang": guess_lang(text),
                    "has_media": has_media,
                    "media_type": ("video" if media.get("videos") else "photo" if media.get("photos") else None)
                    if isinstance(media, dict) else None,
                    "views": _int(r.post_views),
                    "forwards": _int(r.post_forwards),
                    "replies": None,
                    "reactions": reactions if isinstance(reactions, dict) else {},
                    "is_forward": bool(fwd[0]) if isinstance(fwd, (list, tuple)) and fwd else False,
                    "fwd_from": str(fwd[1]) if isinstance(fwd, (list, tuple)) and len(fwd) > 1 and fwd[0] else None,
                    "extra": {},
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    return path, n


def osf_file() -> tuple[str, int]:
    path = RAW / "osf" / "milbloggers.csv"
    part = OUT / "parts" / "osf_milbloggers.jsonl"
    n = 0
    with open(part, "w", encoding="utf-8") as out:
        for chunk in pd.read_csv(path, chunksize=100_000, dtype=str):
            for i, r in enumerate(chunk.itertuples(index=False)):
                text = r.message if isinstance(r.message, str) else ""
                if not text.strip():
                    continue
                rec = {
                    "uid": f"osf:{n}",
                    "source": "osf_milbloggers",
                    "side": "pro_kremlin",
                    "channel": None,  # not provided by the dataset
                    "post_id": None,
                    "date": (r.date or "")[:19],
                    "text": text,
                    "lang": guess_lang(text),
                    "has_media": r.contains_media == "1",
                    "media_type": {"MessageMediaPhoto": "photo", "MessageMediaDocument": "video_or_document"}.get(
                        r.media_type, None if r.media_type in (None, "NA") else "other"),
                    "views": _int(r.views),
                    "forwards": _int(r.number_forwards),
                    "replies": _int(r.number_replies),
                    "reactions": {},
                    "is_forward": r.is_forward == "1",
                    "fwd_from": None,
                    "extra": {"domain": None if r.domain in (None, "NA") else r.domain,
                              "video_duration_secs": _int(r.video_duration_secs)},
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    return str(path), n


def dehum_file() -> tuple[str, int]:
    d = pd.read_csv(RAW / "dehumanisation_study" / "manually labelled posts hf.csv")
    part = OUT / "parts" / "dehum.jsonl"
    n = 0
    with open(part, "w", encoding="utf-8") as out:
        for r in d.itertuples(index=False):
            text = r.message if isinstance(r.message, str) else ""
            if not text.strip():
                continue
            pos = r.positionality if isinstance(r.positionality, str) else ""
            rec = {
                "uid": f"dehum:{r[0]}",
                "source": "dehum",
                "side": "ukrainian" if pos.startswith("ukraine") else "russian" if pos == "russia" else "unknown",
                "channel": None, "post_id": str(r[0]), "date": None, "text": text, "lang": guess_lang(text),
                "has_media": None, "media_type": None, "views": None, "forwards": None, "replies": None,
                "reactions": {}, "is_forward": None, "fwd_from": None,
                "extra": {"positionality": pos, "dehumanising_outgroup": r.Dehumanising_outgroup},
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return "dehum", n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    sides = channel_sides()
    jobs = [(p, "pro_kremlin", sides) for p in sorted(glob.glob(str(RAW / "figshare/pro_kremlin_dataset/*.csv")))]
    jobs += [(p, "anti_kremlin_opposition", sides) for p in sorted(glob.glob(str(RAW / "figshare/anti_kremlin_dataset/*.csv")))]
    with Pool(args.workers) as pool:
        async_osf = pool.apply_async(osf_file)
        async_dehum = pool.apply_async(dehum_file)
        results = pool.map(figshare_file, jobs)
        results += [async_osf.get(), async_dehum.get()]
    total = sum(n for _, n in results)
    with open(OUT / "telegram.jsonl", "w", encoding="utf-8") as out:
        for part in sorted((OUT / "parts").glob("*.jsonl")):
            with open(part, encoding="utf-8") as f:
                for line in f:
                    out.write(line)
    print(f"{total} posts → {OUT / 'telegram.jsonl'}")
    for p, n in results:
        print(f"  {Path(p).name}: {n}")


if __name__ == "__main__":
    main()
