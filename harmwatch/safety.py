"""Image safety before any human or model sees an image: explicit-content quarantine and childlike-appearance signal.

Explicit content (nudity, sexual acts) is quarantined: hash + reason, never annotated, never shown, never sent to a judge.
Three open classifiers are combined with OR (measured 2026-09-26 on the 10 explicit images that Falconsai alone missed,
see TODO_SECURITE.md): Falconsai (ViT), AdamCodd (ViT) and CLIP ViT-L/14 zero-shot. CLIP also reads the text in the
image, so memes that merely TALK about sex score high: the thresholds trade missed explicit images against lost memes.

The childlike-appearance signal (CH-2, images) is raise-only: combined with a sexual element it raises possible_minor;
on its own it never blocks, flags or describes anything. It never estimates the age of a real person's body for any
other purpose, and it is never stored beyond the boolean.
"""

from dataclasses import dataclass, field

# Proposed defaults (to be decided by gmikou, see TODO_SECURITE.md).
THRESHOLDS = {"falconsai": 0.3, "adamcodd": 0.7, "clip_explicit": 0.9, "clip_child": 0.7}

EXPLICIT_PROMPTS = ["a photo of a naked person", "a photo showing nudity", "a pornographic image",
                    "a photo of a sexual act", "a photo of a person in underwear or lingerie", "a cartoon with nudity"]
SAFE_PROMPTS = ["a photo of a clothed person", "a meme with text", "a screenshot of text", "a photo of an animal",
                "a cartoon", "a photo of a group of people", "a photo of a person in swimwear at the beach"]
CHILD_PROMPTS = ["a photo of a child", "a photo of a baby", "a photo of a teenager", "a drawing of a child",
                 "a cartoon of a little girl or boy", "a comic with a child character"]
ADULT_PROMPTS = ["a photo of an adult", "a photo of an adult woman", "a photo of an adult man", "a drawing of an adult",
                 "a cartoon of adults", "a meme with text", "a photo of an animal", "a screenshot of text"]


@dataclass
class SafetyDecision:
    quarantine: bool
    reasons: list[str] = field(default_factory=list)
    child_visual: bool = False
    scores: dict = field(default_factory=dict)


def decide(scores: dict, thresholds: dict | None = None) -> SafetyDecision:
    """Pure decision from classifier scores (unit-tested without images)."""
    t = {**THRESHOLDS, **(thresholds or {})}
    reasons = [f"{k} {scores[k]:.2f} >= {t[k]}" for k in ("falconsai", "adamcodd", "clip_explicit")
               if scores.get(k) is not None and scores[k] >= t[k]]
    child = scores.get("clip_child") is not None and scores["clip_child"] >= t["clip_child"]
    return SafetyDecision(quarantine=bool(reasons), reasons=reasons, child_visual=child, scores=scores)


class ImageSafety:
    """Loads the three classifiers once (GPU if available). `check(img)` → SafetyDecision."""

    def __init__(self, device: int | str | None = None, thresholds: dict | None = None):
        import torch
        from transformers import CLIPModel, CLIPProcessor, pipeline

        cuda = torch.cuda.is_available() if device is None else device != "cpu"
        self.thresholds = thresholds
        self.falconsai = pipeline("image-classification", model="Falconsai/nsfw_image_detection",
                                  device=0 if cuda else -1, top_k=None)
        self.adamcodd = pipeline("image-classification", model="AdamCodd/vit-base-nsfw-detector",
                                 device=0 if cuda else -1, top_k=None)
        dtype = torch.float16 if cuda else torch.float32
        self.clip = CLIPModel.from_pretrained("openai/clip-vit-large-patch14", dtype=dtype).eval()
        if cuda:
            self.clip = self.clip.cuda()
        self.proc = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        self.dtype, self.cuda = dtype, cuda
        with torch.no_grad():
            self.text_explicit = self._text(EXPLICIT_PROMPTS + SAFE_PROMPTS)
            self.text_child = self._text(CHILD_PROMPTS + ADULT_PROMPTS)

    def _text(self, prompts):
        batch = self.proc(text=prompts, return_tensors="pt", padding=True)
        batch = {k: (v.cuda() if self.cuda else v) for k, v in batch.items()}
        f = self.clip.get_text_features(**batch)
        return f / f.norm(dim=-1, keepdim=True)

    def scores(self, img) -> dict:
        import torch

        img = img.convert("RGB")
        s = {"falconsai": next(d["score"] for d in self.falconsai(img) if d["label"] == "nsfw"),
             "adamcodd": next(d["score"] for d in self.adamcodd(img) if d["label"] == "nsfw")}
        with torch.no_grad():
            px = self.proc(images=img, return_tensors="pt")["pixel_values"].to(self.dtype)
            f = self.clip.get_image_features(pixel_values=px.cuda() if self.cuda else px)
            f = f / f.norm(dim=-1, keepdim=True)
            pe = (100 * f @ self.text_explicit.T).softmax(-1)[0].float().tolist()
            pc = (100 * f @ self.text_child.T).softmax(-1)[0].float().tolist()
        s["clip_explicit"] = sum(pe[:len(EXPLICIT_PROMPTS)])
        s["clip_child"] = sum(pc[:len(CHILD_PROMPTS)])
        return {k: round(v, 4) for k, v in s.items()}

    def check(self, img) -> SafetyDecision:
        return decide(self.scores(img), self.thresholds)
