"""Fakes for the analyze tests (no GPU, no model server): a scripted judge, safety filter, pre-filter and video."""

from harmwatch.safety import SafetyDecision
from harmwatch.sv_scores import Scores, SVScoreOutput, finalize_scores
from harmwatch.video_segments import Segment


def judge_output(sexual=True, sv=70, sh=20, hate=10, misogyny=30, violence=5, relation="SV-REL-2",
                 category="threat_incitement", minor=False, reason="Threat of sexual violence against a group (SV-REL-2)."):
    return SVScoreOutput(possible_minor=minor, scores=Scores(sexual_violence=sv, sexual_harassment=sh, hate=hate,
                                                             misogyny=misogyny, other_violence=violence),
                         sexual=sexual, hateful=False, misogynous=misogyny >= 50, primary_relation=relation,
                         category=category, reason=reason)


class FakeJudge:
    """Returns the SVScorer result shape; `script(item)` → SVScoreOutput (default: a sexual threat)."""
    model = "fake-qwen"

    def __init__(self, script=None):
        self.script = script or (lambda item: judge_output())
        self.calls = []

    def assess(self, item):
        self.calls.append(item)
        out = self.script(item)
        a = finalize_scores(out, item_id=str(item["id"]), embedded_text=item.get("text") or "")
        a.p_true = {"sexual": 0.9 if out.sexual else 0.1}
        return {"assessment": a, "raw": out.model_dump_json(), "usage": {}, "seconds": 0.0, "error": None}


class FakeSafety:
    def __init__(self, quarantine=False, child_visual=False):
        self.quarantine, self.child_visual = quarantine, child_visual

    def check(self, img):
        return SafetyDecision(quarantine=self.quarantine, reasons=["falconsai 0.99 >= 0.3"] if self.quarantine else [],
                              child_visual=self.child_visual)


class FakePrefilter:
    threshold = 0.5

    def __init__(self, score=0.8):
        self.score = score

    def score_images(self, images):
        return [self.score] * len(images)

    def passes(self, score):
        return score >= self.threshold


class FakeVideo:
    """Two segments: 0-10 s harmless, 10-25 s harmful (the judge script decides from the speech)."""

    def segments(self, path):
        from PIL import Image

        f = [Image.new("RGB", (32, 32), c) for c in ("red", "green", "blue")]
        return [Segment(video="clip", index=1, n=2, start=0.0, end=10.0, speech="weather report", frames=f),
                Segment(video="clip", index=2, n=2, start=10.0, end=25.0, speech="THREAT", on_screen_text="", frames=f)]


def video_script(item):
    if "THREAT" in item["text"]:
        return judge_output()
    return judge_output(sexual=False, sv=0, sh=0, relation=None, category="none", reason="Harmless weather report.")
