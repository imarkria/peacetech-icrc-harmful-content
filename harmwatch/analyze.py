"""Single entry point: analyse a text, an image, a meme or a video and write one row in the SQLite table `detections`.

    from harmwatch.analyze import analyze
    row = analyze({"modality": "text", "text": "...", "url": "https://..."}, region="global")

    python -m harmwatch.analyze text "some text"            [--region global] [--url URL] [--source cli]
    python -m harmwatch.analyze image path/to/meme.jpg      [--text "embedded text"]   (no --text: OCR if installed)
    python -m harmwatch.analyze video path/to/video.mp4     [--no-prefilter]

Pipeline (docs/platform/README.md):
  [1] safety filter (harmwatch/safety.py, images and video frames): explicit content = priority alert, never silently
      dropped and never sent to the judge; childlike appearance = raise-only signal for the minor rule (CH-2).
  [2] fast pre-filter (harmwatch/prefilter.py, weights in models/): images, memes, video frames. Below the threshold
      the item is recorded as "filtered_out" with its score, without calling the judge. Text has no pre-filter.
  [3] AI judge: Qwen3.5-9B through the local server (scripts/serve_llm.sh) with the FROZEN prompt v3 (fingerprint
      checked at load). Video: segments (harmwatch/video_segments.py), one judgement per segment, video = worst segment,
      flagged passage = its start / end in seconds.
  [4] one row in `detections` (harmwatch/detections.py). CH-5: possible_minor → restricted, no content stored.

The region selects the region-specific deterministic rules (age indicators of policy/regions/<region>.yaml for the
minor rule). The judge prompt stays the frozen v3 prompt (built with the global profile) for every region.
Route / priority are a simple triage of the judge output, documented in `triage` below (not a policy rule).
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V3_SYSTEM = ROOT / "docs" / "prompts" / "sv_prompt_v3_system.txt"
V3_SHA256 = "9160fe72836938169116baa9c1edf68918fd4e5c598c50bb1b5c7cb354760386"
PROMPT_VERSION = "sv_prompt_v3"
MODALITIES = ("text", "image", "meme", "video")
HIGH_RELATIONS = ("SV-REL-2", "SV-REL-5")  # threats / incitement, victim stigmatisation (core.md rule_priority)
SAFETY_MODEL = "image_safety (Falconsai + AdamCodd + CLIP)"
PREFILTER_MODEL = "prefilter_image_logreg"


# --- components (each can be replaced, e.g. by fakes in the tests) ---------------------------------------------------
class Judge:
    """AI judge: our definitions (frozen prompt v3 = policy layers + examples) + Qwen3.5-9B on llama-server."""

    def __init__(self, model: str | None = None):
        from harmwatch.crsv import DEFAULT_MODEL
        from harmwatch.policy_loader import load_policy
        from harmwatch.sv_scores import SVScorer

        self.model = model or os.getenv("LOCAL_LLM_MODEL", DEFAULT_MODEL)
        policy = load_policy("global", "generic", allow_no_approved=True)  # as scripts/eval_sv_benchmark.py
        self.with_image = SVScorer(policy, [], model=self.model, with_image=True)
        self.text_only = SVScorer(policy, [], model=self.model, with_image=False)
        system = V3_SYSTEM.read_text(encoding="utf-8")
        for s in (self.with_image, self.text_only):
            s.system = system
        if self.with_image.fingerprint() != V3_SHA256:
            raise RuntimeError("judge prompt differs from the frozen sv_prompt_v3: refusing to run")

    def assess(self, item: dict) -> dict:
        """item = {id, text, lang, modality, image (PIL or None)} → SVScorer result {assessment, raw, error, ...}."""
        return (self.with_image if item.get("image") is not None else self.text_only).assess(item)


class VideoProcessor:
    """Video → segments with 3 frames (start / middle / end), transcript and on-screen text (video_segments.py)."""

    def __init__(self):
        self._transcriber, self._ocr = None, None

    def segments(self, path: Path) -> list:
        from harmwatch import video_segments as vs

        if self._transcriber is None:
            self._transcriber, self._ocr = vs.Transcriber(), vs.OCR()
        bounds = vs.segment_bounds(vs.video_duration(path), vs.scene_cuts(path))
        speech = vs.attach(self._transcriber.phrases(path), bounds)
        out = []
        for i, (s, e) in enumerate(bounds):
            frames = vs.grab_frames(path, [s, (s + e) / 2, max(s, e - 0.1)])
            lines = list(dict.fromkeys(line for f in frames for line in self._ocr.lines(f)))
            out.append(vs.Segment(video=path.stem, index=i + 1, n=len(bounds), start=s, end=e, speech=speech[i],
                                  on_screen_text=" | ".join(lines), frames=frames))
        return out


def triage(a) -> tuple[str, str]:
    """(route, priority) from a judge assessment. Restricted → restricted_escalation / urgent; sexual with a threat or
    victim stigmatisation (SV-REL-2 / SV-REL-5) → priority_review / high; other sexual → standard_review / standard;
    otherwise not_flagged / none."""
    if a.possible_minor:
        return "restricted_escalation", "urgent"
    if a.sexual and a.primary_relation in HIGH_RELATIONS:
        return "priority_review", "high"
    if a.sexual:
        return "standard_review", "standard"
    return "not_flagged", "none"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --- analyser --------------------------------------------------------------------------------------------------------
class Analyzer:
    def __init__(self, judge=None, safety=None, prefilter=None, video=None, ocr=None, db: str | Path | None = None,
                 use_safety: bool = True, use_prefilter: bool = True):
        self._judge, self._safety, self._prefilter, self._video, self._ocr = judge, safety, prefilter, video, ocr
        self.db, self.use_safety, self.use_prefilter = db, use_safety, use_prefilter

    # lazy loading: GPU models are only loaded when a modality needs them
    @property
    def judge(self):
        if self._judge is None:
            self._judge = Judge()
        return self._judge

    @property
    def safety(self):
        if self._safety is None:
            from harmwatch.safety import ImageSafety

            self._safety = ImageSafety()
        return self._safety

    @property
    def prefilter(self):
        if self._prefilter is None:
            from harmwatch.prefilter import Prefilter

            self._prefilter = Prefilter.load()
        return self._prefilter

    @property
    def video(self):
        if self._video is None:
            self._video = VideoProcessor()
        return self._video

    def _ocr_text(self, img) -> tuple[str, str]:
        if self._ocr is None:
            try:
                from harmwatch.video_segments import OCR

                self._ocr = OCR()
            except ImportError:
                self._ocr = False
        if not self._ocr:
            return "", "none (OCR not installed)"
        return " ".join(self._ocr.lines(img)), "ocr"

    def _judge_item(self, item: dict, matcher, child_visual: bool):
        """Judge call, then the hard rules re-applied with the region's age indicators and the safety signal."""
        from harmwatch.sv_scores import SVScoreOutput, finalize_scores

        res = self.judge.assess(item)
        if res.get("error") or res.get("assessment") is None:
            return None, res.get("error") or "no assessment"
        a = finalize_scores(SVScoreOutput.model_validate_json(res["raw"]), item_id=item["id"],
                            embedded_text=item.get("text") or "", age_matcher=matcher, child_visual=child_visual)
        if res["assessment"].possible_minor and not a.possible_minor:  # never weaken a restriction
            a = res["assessment"]
        a.p_true = res["assessment"].p_true
        return a, None

    @staticmethod
    def _content(a) -> dict:
        if a.possible_minor or a.scores is None:
            return {"possible_minor": 1}
        return {**a.scores.model_dump(), "sexual": int(a.sexual), "category": a.category,
                "primary_relation": a.primary_relation, "summary": a.reason or None, "possible_minor": 0}

    def _safety_check(self, images: list) -> dict:
        out = {"quarantine": False, "child_visual": False, "reasons": []}
        if not self.use_safety:
            return out | {"skipped": True}
        for img in images:
            d = self.safety.check(img)
            out["quarantine"] |= d.quarantine
            out["child_visual"] |= d.child_visual
            out["reasons"] += d.reasons
        return out

    def _filter(self, images: list) -> tuple[float | None, bool]:
        if not self.use_prefilter or not images:
            return None, True
        score = max(self.prefilter.score_images(images))
        return round(score, 4), self.prefilter.passes(score)

    def _explicit_row(self, safety: dict) -> dict:
        # explicit + childlike appearance = sexual element + CH-2 signal → possible_minor (restricted, CH-5)
        route = "restricted_escalation" if safety["child_visual"] else "explicit_alert"
        return {"route": route, "priority": "urgent", "explicit_alert": 1,
                "possible_minor": int(safety["child_visual"]), "model": SAFETY_MODEL,
                "full_result_json": {"explicit_alert": True, "safety": safety,
                                     "note": "quarantined by the safety filter: never shown, never sent to the judge"}}

    def analyze(self, item: dict, region: str = "global") -> dict:
        from harmwatch import detections
        from harmwatch.lexicon import guess_lang
        from harmwatch.policy_loader import POLICY_DIR, region_age_matcher

        start = time.time()
        modality = item.get("modality")
        if modality not in MODALITIES:
            raise ValueError(f"modality must be one of {MODALITIES}, got {modality!r}")
        if not (POLICY_DIR / "regions" / f"{region}.yaml").exists():
            raise ValueError(f"unknown region {region!r}: no policy/regions/{region}.yaml")
        matcher = region_age_matcher(region)
        row = {"source": item.get("source"), "url": item.get("url"), "region": region}

        if modality == "text":
            text = item["text"]
            row |= {"modality": "text", "media_hash": sha256_bytes(text.encode("utf-8"))}
            row |= self._judged(row, {"text": text, "lang": guess_lang(text), "modality": "text", "image": None},
                                matcher, child_visual=False, filt=(None, None), extra={})
        elif modality in ("image", "meme"):
            img, raw = self._load_image(item)
            text, text_source = (item["text"], "given") if item.get("text") is not None else self._ocr_text(img)
            modality = "meme" if text.strip() else modality
            row |= {"modality": modality, "media_hash": sha256_bytes(raw)}
            safety = self._safety_check([img])
            if safety["quarantine"]:
                row |= self._explicit_row(safety)
            else:
                score, passed = self._filter([img])
                if not passed:
                    row |= self._filtered_row(score, {"safety": safety})
                else:
                    item_j = {"text": text, "lang": guess_lang(text) if text else "unknown", "modality": modality,
                              "image": img}
                    row |= self._judged(row, item_j, matcher, safety["child_visual"], (score, passed),
                                        {"safety": safety, "embedded_text_source": text_source})
        else:
            row |= self._video_rows(Path(item["path"]), matcher)

        row["latency_ms"] = int((time.time() - start) * 1000)
        conn = detections.connect(self.db)
        try:
            return detections.get_detection(conn, detections.insert_detection(conn, row))
        finally:
            conn.close()

    @staticmethod
    def _load_image(item: dict):
        from PIL import Image

        if item.get("path"):
            raw = Path(item["path"]).read_bytes()
            import io

            return Image.open(io.BytesIO(raw)).convert("RGB"), raw
        img = item["image"].convert("RGB")
        return img, img.tobytes()

    @staticmethod
    def _filtered_row(score, extra: dict) -> dict:
        return {"filter_score": score, "filter_passed": 0, "route": "filtered_out", "priority": "none",
                "model": PREFILTER_MODEL,
                "full_result_json": {"filter": {"score": score, "passed": False}, **extra,
                                     "note": "below the pre-filter threshold: not sent to the judge"}}

    def _judged(self, row: dict, item: dict, matcher, child_visual: bool, filt: tuple, extra: dict) -> dict:
        item = {"id": row["media_hash"][:16], **item}
        a, error = self._judge_item(item, matcher, child_visual)
        base = {"filter_score": filt[0], "filter_passed": None if filt[1] is None else int(filt[1]),
                "model": self.judge.model, "prompt_version": PROMPT_VERSION}
        if a is None:
            return base | {"route": "judge_error", "priority": "standard",
                           "full_result_json": {"error": error, "filter": {"score": filt[0], "passed": filt[1]}, **extra}}
        route, priority = triage(a)
        return base | self._content(a) | {"route": route, "priority": priority, "full_result_json": {
            "judge": a.model_dump(exclude={"item_id"}), "p_sexual": a.p_true.get("sexual"),
            "restricted_reason": a.restricted_reason, "rule_notes": a.rule_notes,
            "filter": {"score": filt[0], "passed": filt[1]}, **extra}}

    def _video_rows(self, path: Path, matcher) -> dict:
        from harmwatch.lexicon import guess_lang

        media_hash = sha256_bytes(path.read_bytes())
        out = {"modality": "video", "media_hash": media_hash}
        segs = self.video.segments(path)
        safety = self._safety_check([f for s in segs for f in s.frames])
        if safety["quarantine"]:
            return out | self._explicit_row(safety)
        per_seg = []
        for s in segs:
            score, passed = self._filter(s.frames)
            per_seg.append({"index": s.index, "start": s.start, "end": s.end, "filter_score": score, "passed": passed})
        scores = [p["filter_score"] for p in per_seg if p["filter_score"] is not None]
        video_score = max(scores) if scores else None
        if segs and not any(p["passed"] for p in per_seg):
            return out | self._filtered_row(video_score, {"segments": per_seg})
        judged = []
        for s, p in zip(segs, per_seg):
            if not p["passed"]:
                continue
            text = f"speech: {s.speech or '(no speech)'}\non-screen text: {s.on_screen_text or '(none)'}"
            item = {"id": f"{media_hash[:12]}#{s.index}", "text": text, "lang": guess_lang(s.speech or text),
                    "modality": "video", "image": s.frames[len(s.frames) // 2] if s.frames else None}
            a, error = self._judge_item(item, matcher, safety["child_visual"])
            p |= {"judged": True, "error": error}
            if a is not None:
                p |= {"sexual": a.sexual, "p_sexual": a.p_true.get("sexual"), "possible_minor": a.possible_minor,
                      "scores": a.scores.model_dump() if a.scores else None}
                judged.append((s, a))
        base = {"filter_score": video_score, "filter_passed": 1, "model": self.judge.model,
                "prompt_version": PROMPT_VERSION}
        details = {"filter": {"score": video_score, "passed": True}, "segments": per_seg,
                   "n_segments": len(segs), "n_judged": sum(1 for p in per_seg if p.get("judged"))}
        if any(a.possible_minor for _, a in judged):
            restricted = next(a for _, a in judged if a.possible_minor)
            return out | base | {"possible_minor": 1, "route": "restricted_escalation", "priority": "urgent",
                                 "full_result_json": details | {"restricted_reason": restricted.restricted_reason,
                                                                "rule_notes": restricted.rule_notes}}
        if not judged:
            return out | base | {"route": "judge_error", "priority": "standard",
                                 "full_result_json": details | {"error": "no segment could be judged"}}
        s, a = max(judged, key=lambda sa: (sa[1].sexual, max(sa[1].scores.sexual_violence, sa[1].scores.sexual_harassment),
                                           sa[1].p_true.get("sexual") or 0))
        route, priority = triage(a)
        flagged = {"flagged_start_s": s.start, "flagged_end_s": s.end} if a.sexual else {}
        return out | base | self._content(a) | flagged | {"route": route, "priority": priority, "full_result_json": details | {
            "worst_segment": s.index, "judge": a.model_dump(exclude={"item_id"}), "p_sexual": a.p_true.get("sexual"),
            "rule_notes": a.rule_notes}}


_default: Analyzer | None = None


def analyze(item: dict, region: str = "global") -> dict:
    """Analyse one item with the default components (loaded once) and return the row written in `detections`."""
    global _default
    if _default is None:
        _default = Analyzer()
    return _default.analyze(item, region=region)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m harmwatch.analyze", description=__doc__.split("\n\n")[0])
    ap.add_argument("modality", choices=("text", "image", "video"))
    ap.add_argument("value", help="the text itself, or the path of the image / video")
    ap.add_argument("--text", help="image: embedded text (else OCR if installed)")
    ap.add_argument("--region", default="global")
    ap.add_argument("--url")
    ap.add_argument("--source", default="cli")
    ap.add_argument("--db", help="SQLite file (default: HARMWATCH_DB or data/harmwatch.db)")
    ap.add_argument("--no-prefilter", action="store_true", help="send every image / segment to the judge")
    a = ap.parse_args(argv)
    item = {"modality": a.modality, "url": a.url, "source": a.source}
    item |= {"text": a.value} if a.modality == "text" else {"path": a.value, "text": a.text}
    row = Analyzer(db=a.db, use_prefilter=not a.no_prefilter).analyze(item, region=a.region)
    json.dump(row, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
