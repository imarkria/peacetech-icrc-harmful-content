"""Cascade helpers: near-duplicate detection, recall thresholds, cascade decision (synthetic data, no real image)."""

import numpy as np
from PIL import Image, ImageDraw

from harmwatch.cascade import (cascade, confusion, dedupe_within, hamming, near_duplicates, phash,
                               threshold_for_recall)


def _img(seed: int, size=256):
    """Structurally different synthetic images per seed (layout, not noise, drives the perceptual hash)."""
    im = Image.new("RGB", (size, size), (255, 255, 255) if seed % 2 else (0, 0, 0))
    d = ImageDraw.Draw(im)
    if seed == 1:
        d.rectangle([10, 10, 120, 240], fill=(200, 30, 30))
        d.ellipse([150, 20, 240, 110], fill=(20, 20, 200))
    else:
        d.polygon([(128, 10), (246, 246), (10, 246)], fill=(250, 220, 0))
        d.line([(0, 128), (256, 128)], fill=(0, 200, 0), width=20)
    return im


def test_phash_is_robust_to_resizing_and_separates_different_images():
    a = _img(1)
    assert hamming(phash(a), phash(a.resize((128, 128)))) <= 8
    assert hamming(phash(a), phash(_img(2))) > 8


def test_near_duplicates_and_dedupe():
    ha, hb = phash(_img(1)), phash(_img(2))
    ref = {"bench": ha}
    assert near_duplicates({"x": phash(_img(1).resize((300, 300))), "y": hb}, ref) == {"x": "bench"}
    assert dedupe_within({"a": ha, "a2": phash(_img(1).resize((200, 200))), "b": hb}) == {"a2": "a"}


def test_threshold_for_recall_keeps_the_target():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 1000)
    s = np.clip(y * 0.5 + rng.normal(0.3, 0.2, 1000), 0, 1)
    for target in (0.95, 0.97, 0.99):
        t = threshold_for_recall(s, y, target)
        assert ((s >= t) & (y == 1)).sum() / (y == 1).sum() >= target


def test_cascade_only_suspects_reach_the_judge():
    scores = np.array([0.9, 0.1, 0.6, 0.2])
    judge = np.array([True, True, False, True])
    pred, sent = cascade(scores, 0.5, judge)
    assert sent.tolist() == [True, False, True, False]
    assert pred.tolist() == [True, False, False, False]  # non-suspects are 'not sexual' whatever the judge would say


def test_confusion_counts():
    c = confusion([1, 1, 0, 0], [1, 0, 1, 0])
    assert (c["TP"], c["FP"], c["FN"], c["TN"]) == (1, 1, 1, 1) and c["f1"] == 0.5
