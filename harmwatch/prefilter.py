"""Fast pre-filter (step 2 of harmwatch/analyze.py): SigLIP 2 image embedding + trained logistic regression.

The trained weights are versioned in models/ (prefilter_image_logreg.joblib + prefilter.json: threshold, embedding
model, metrics). The embedding model itself (google/siglip2-so400m-patch14-384, ~1.1 GB) is NOT in git: Hugging Face
downloads it on first use. Training code and evaluation: scripts/eval_cascade.py, harmwatch/cascade.py,
docs/RESULTS_CASCADE.md. Research experiment: see the `status` field of models/prefilter.json.
"""

import hashlib
import json
from pathlib import Path

import numpy as np

MODELS = Path(__file__).resolve().parent.parent / "models"


class Prefilter:
    def __init__(self, clf, meta: dict, embedder=None):
        self.clf, self.meta = clf, meta
        self.threshold = float(meta["threshold"])
        self._embedder = embedder

    @classmethod
    def load(cls, models_dir: str | Path = MODELS, embedder=None) -> "Prefilter":
        """Loads models/prefilter.json and the weights it names; refuses a file whose sha256 differs
        (a joblib file is a pickle: never load one that is not the versioned file)."""
        import joblib

        models_dir = Path(models_dir)
        meta = json.loads((models_dir / "prefilter.json").read_text(encoding="utf-8"))
        path = models_dir / Path(meta["file"]).name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            raise ValueError(f"{path.name}: sha256 {digest[:12]}... differs from prefilter.json; refusing to load")
        return cls(joblib.load(path), meta, embedder)

    @property
    def embedder(self):
        if self._embedder is None:  # downloaded from Hugging Face on first use
            from harmwatch.cascade import ImageEmbedder

            self._embedder = ImageEmbedder(self.meta["embedding_model"])
        return self._embedder

    def score_embeddings(self, emb: np.ndarray) -> list[float]:
        emb = np.asarray(emb, dtype=np.float64)
        if emb.ndim != 2 or emb.shape[1] != self.meta["embedding_dim"]:
            raise ValueError(f"expected (n, {self.meta['embedding_dim']}) embeddings, got {emb.shape}")
        return [float(p) for p in self.clf.predict_proba(emb)[:, 1]]

    def score_images(self, images: list) -> list[float]:
        return self.score_embeddings(self.embedder(images)) if images else []

    def passes(self, score: float) -> bool:
        return score >= self.threshold
