"""
Compare match-score distributions with and without the embedding centre, on
real same-person and different-person pairs, and report the error rates at
MATCH_THRESHOLD.

Run next to main.py, in the same environment the service uses:
    python calibrate_threshold.py ~/scikit_learn_data/lfw_home/lfw_funneled --people 150

Uses people with 2+ images for same-person pairs (first two images) and the
first image of different people for different-person pairs.
"""
import argparse
import itertools
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import main

EXTS = {".jpg", ".jpeg", ".png"}


def embed(path: Path, jitters: int):
    img = np.array(Image.open(path).convert("RGB"))
    det = main.detect_face(img)
    if not det.detections:
        return None
    try:
        return main.extract_face_embedding(img, det.detections[0], num_jitters=jitters)
    except main.FaceEmbeddingError:
        return None


def score(a: np.ndarray, b: np.ndarray, center: np.ndarray) -> float:
    bits_a = main._SIMHASH_PLANES @ (a - center) >= 0
    bits_b = main._SIMHASH_PLANES @ (b - center) >= 0
    d = int(np.count_nonzero(bits_a != bits_b))
    return max(0.0, 1.0 - 2.0 * d / main._SIMHASH_BITS)


def summarise(label, same, diff, threshold):
    same, diff = np.array(same), np.array(diff)
    frr = np.mean(same < threshold)
    far = np.mean(diff >= threshold)
    print(f"\n{label}")
    print(f"  same person : min {same.min():.3f}  5th pct {np.percentile(same, 5):.3f}  median {np.median(same):.3f}")
    print(f"  different   : max {diff.max():.3f}  95th pct {np.percentile(diff, 95):.3f}  median {np.median(diff):.3f}")
    print(f"  at threshold {threshold:.2f}: false rejects {frr:.1%}, false accepts {far:.1%}")
    # lowest threshold with false accepts <= 1%, and its false-reject rate
    for t in np.arange(0.0, 1.0001, 0.01):
        if np.mean(diff >= t) <= 0.01:
            print(f"  threshold for <=1% false accepts: {t:.2f} -> false rejects {np.mean(same < t):.1%}")
            break


def main_():
    ap = argparse.ArgumentParser()
    ap.add_argument("lfw_dir", type=Path)
    ap.add_argument("--people", type=int, default=150, help="people with 2+ images to use")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    folders = sorted(p for p in args.lfw_dir.iterdir() if p.is_dir())
    multi = [f for f in folders if sum(x.suffix.lower() in EXTS for x in f.iterdir()) >= 2]
    rng.shuffle(multi)
    multi = multi[: args.people]
    if len(multi) < 2:
        sys.exit("Need at least 2 people with 2+ images each.")

    enrolled, probe = [], []   # enrollment uses production jitters, probes use verify jitters
    for f in multi:
        imgs = sorted(x for x in f.iterdir() if x.suffix.lower() in EXTS)[:2]
        e, p = embed(imgs[0], main._ENROLL_JITTERS), embed(imgs[1], main._VERIFY_JITTERS)
        if e is not None and p is not None:
            enrolled.append(e)
            probe.append(p)
        print(f"\rencoded {len(enrolled)} people", end="", flush=True)
    print()

    n = len(enrolled)
    same_pairs = [(i, i) for i in range(n)]
    diff_pairs = [(i, j) for i, j in itertools.permutations(range(n), 2)]
    rng.shuffle(diff_pairs)
    diff_pairs = diff_pairs[: 20 * n]

    zero = np.zeros(main._EMBEDDING_DIM)
    for label, center in (("UNCENTRED", zero), ("CENTRED (embedding_center.npy)", main._EMBEDDING_CENTER)):
        if label.startswith("CENTRED") and not main._EMBEDDING_CENTER.any():
            print("\n(no embedding_center.npy loaded; skipping centred)")
            continue
        same = [score(enrolled[i], probe[j], center) for i, j in same_pairs]
        diff = [score(enrolled[i], probe[j], center) for i, j in diff_pairs]
        summarise(label, same, diff, main.MATCH_THRESHOLD)
    print(f"\n{n} same-person pairs, {len(diff_pairs)} different-person pairs")


if __name__ == "__main__":
    main_()