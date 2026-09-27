"""Cascade: a fast "student" screens every image, the full judge (Qwen3.5-9B, prompt v3 frozen) only sees suspects.

The student is distilled from the judge ("teacher"): it learns P(sexual) of the teacher from FEATURES only
(text embedding of the embedded text, image embedding), never from stored images (B5). Images of the training pool are
deleted once their embeddings are computed; only embeddings, hashes and labels are kept.

Nothing here changes the existing policy, prompts or modules: they are imported and read, never modified.
"""

import numpy as np

# --- near-duplicates (anti-leakage) ----------------------------------------------------------------------------

def phash(img) -> int:
    """64-bit perceptual hash as an int."""
    import imagehash

    return int(str(imagehash.phash(img.convert("RGB"))), 16)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def near_duplicates(candidates: dict[str, int], reference: dict[str, int], max_distance: int = 8) -> dict[str, str]:
    """{candidate_id: closest reference_id} for every candidate within `max_distance` bits of a reference hash."""
    if not reference:
        return {}
    ref_ids, ref = list(reference), np.array([reference[r] for r in reference], dtype=np.uint64)
    out = {}
    for cid, h in candidates.items():
        d = np.unpackbits((ref ^ np.uint64(h)).view(np.uint8).reshape(-1, 8), axis=1).sum(axis=1)  # popcount
        i = int(d.argmin())
        if d[i] <= max_distance:
            out[cid] = ref_ids[i]
    return out


def dedupe_within(hashes: dict[str, int], max_distance: int = 8) -> dict[str, str]:
    """Greedy: {dropped_id: kept_id} for items within `max_distance` of an earlier kept item (order = dict order)."""
    kept: dict[str, int] = {}
    dropped = {}
    for cid, h in hashes.items():
        hit = near_duplicates({cid: h}, kept, max_distance)
        if hit:
            dropped[cid] = hit[cid]
        else:
            kept[cid] = h
    return dropped


# --- features ---------------------------------------------------------------------------------------------------

class TextEmbedder:
    """Qwen/Qwen3-Embedding-0.6B, last-token pooling, L2-normalised (empty text → embedding of an empty marker)."""

    def __init__(self, model: str = "Qwen/Qwen3-Embedding-0.6B", device: str = "cuda"):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(model, padding_side="left")
        self.model = AutoModel.from_pretrained(model, dtype=torch.float16).to(device).eval()
        self.device = device

    def __call__(self, texts: list[str], batch: int = 64) -> np.ndarray:
        import torch

        out = []
        for i in range(0, len(texts), batch):
            chunk = [t.strip() or "(no text)" for t in texts[i:i + batch]]
            enc = self.tok(chunk, padding=True, truncation=True, max_length=256, return_tensors="pt").to(self.device)
            with torch.no_grad():
                h = self.model(**enc).last_hidden_state[:, -1]
            out.append(torch.nn.functional.normalize(h.float(), dim=-1).cpu().numpy())
        return np.concatenate(out)


class ImageEmbedder:
    """google/siglip2-so400m-patch14-384 image features, L2-normalised."""

    def __init__(self, model: str = "google/siglip2-so400m-patch14-384", device: str = "cuda"):
        import torch
        from transformers import AutoModel, AutoProcessor

        self.proc = AutoProcessor.from_pretrained(model)
        self.model = AutoModel.from_pretrained(model, dtype=torch.float16).to(device).eval()
        self.device = device

    def __call__(self, images: list, batch: int = 32) -> np.ndarray:
        import torch

        out = []
        for i in range(0, len(images), batch):
            px = self.proc(images=[im.convert("RGB") for im in images[i:i + batch]], return_tensors="pt")
            px = px["pixel_values"].to(self.device, torch.float16)
            with torch.no_grad():
                f = self.model.get_image_features(pixel_values=px)
            out.append(torch.nn.functional.normalize(f.float(), dim=-1).cpu().numpy())
        return np.concatenate(out)


def features(kind: str, text_emb: np.ndarray, image_emb: np.ndarray) -> np.ndarray:
    """T = text only, I = image only, IT = concatenation."""
    return {"T": text_emb, "I": image_emb, "IT": np.concatenate([image_emb, text_emb], axis=1)}[kind]


# --- students and thresholds ------------------------------------------------------------------------------------

def train_student(X: np.ndarray, y: np.ndarray, kind: str = "logreg", balance: str = "weight", seed: int = 42,
                  cv_folds: int = 5):
    """Binary student on the teacher's decision (`y` in {0,1}); returns (fitted pipeline, info).

    balance = "weight" (class_weight="balanced") or "undersample" (negatives randomly reduced to 50/50).
    The regularisation (C for logistic regression, alpha for the MLP) is chosen by stratified cross-validation
    (ROC AUC) on the data passed in, i.e. on the TRAINING part only.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if balance == "undersample":
        rng = np.random.default_rng(seed)
        pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
        keep = np.concatenate([pos, rng.choice(neg, size=min(len(neg), len(pos)), replace=False)])
        X, y = X[keep], y[keep]
    cw = "balanced" if balance == "weight" else None
    if kind == "logreg":
        est = LogisticRegression(max_iter=5000, class_weight=cw, random_state=seed)
        grid = {"clf__C": [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 0.1, 1.0]}
    else:  # MLP has no class_weight: weighting falls back to plain training on the (possibly undersampled) set
        est = MLPClassifier(hidden_layer_sizes=(256,), early_stopping=True, max_iter=300, random_state=seed)
        grid = {"clf__alpha": [1e-4, 1e-3, 1e-2]}
    pipe = Pipeline([("scale", StandardScaler()), ("clf", est)])
    search = GridSearchCV(pipe, grid, scoring="roc_auc", cv=StratifiedKFold(cv_folds, shuffle=True, random_state=seed),
                          n_jobs=4)
    search.fit(X, y)
    return search.best_estimator_, {"best_params": search.best_params_, "cv_auroc": round(float(search.best_score_), 3),
                                    "n_fit": int(len(y)), "positives_fit": int(y.sum())}


def recall_at_budget(scores: np.ndarray, y: np.ndarray, max_sent: float) -> tuple[float, float]:
    """Best recall reachable when at most `max_sent` of the items are sent to the judge; returns (recall, threshold)."""
    t = float(np.quantile(scores, 1 - max_sent))
    sent = scores >= t
    return float((sent & (y == 1)).sum() / max((y == 1).sum(), 1)), t


def threshold_for_recall(scores: np.ndarray, y: np.ndarray, target: float) -> float:
    """Highest threshold t such that recall(scores >= t) >= target on (scores, y)."""
    pos = np.sort(scores[y == 1])
    if len(pos) == 0:
        return 0.0
    k = int(np.floor((1 - target) * len(pos)))  # number of positives we may lose
    return float(pos[k]) if k < len(pos) else float(pos[-1])


def confusion(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, bool), np.asarray(y_pred, bool)
    tp, fp = int((y_true & y_pred).sum()), int((~y_true & y_pred).sum())
    fn, tn = int((y_true & ~y_pred).sum()), int((~y_true & ~y_pred).sum())
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else 0.0
    return {"n": len(y_true), "TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": None if p is None else round(p, 3),
            "recall": None if r is None else round(r, 3), "f1": round(f1, 3),
            "accuracy": round((tp + tn) / len(y_true), 3) if len(y_true) else None,
            "specificity": round(tn / (tn + fp), 3) if tn + fp else None}


def cascade(student_scores: np.ndarray, threshold: float, judge_decisions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Suspects (score >= threshold) get the judge's decision, the others are 'not sexual'. Returns (pred, sent)."""
    sent = student_scores >= threshold
    return np.where(sent, judge_decisions, False), sent
