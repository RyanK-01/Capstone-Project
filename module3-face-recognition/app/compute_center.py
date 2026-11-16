"""
Offline: compute the mean dlib embedding over a diverse set of faces and save
it as embedding_center.npy next to main.py. main.py subtracts this before the
SimHash projection so the hyperplanes split the region where faces actually live.

Usage:
    python compute_center.py /path/to/faces [--per-dir 1] [--limit 1000]

Use a dataset that does NOT overlap with test images (e.g. a folder of LFW
people, one image per person). Re-run this whenever the embedding model changes,
and re-enroll everyone afterwards: a new center changes every hash.

Privacy: the output is an average over many people, not any individual's
biometric. Source images are read from local disk only and never written.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from main import (
    FaceEmbeddingError, ImageDecodeError, _EMBEDDING_DIM,
    detect_face, extract_face_embedding,
)
from PIL import Image

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def iter_images(root: Path, per_dir: int):
    """Yield image paths, at most `per_dir` from each folder (LFW = 1 folder/person)."""
    counts = defaultdict(int)
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in EXTS and counts[path.parent] < per_dir:
            counts[path.parent] += 1
            yield path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image_dir", type=Path)
    ap.add_argument("--per-dir", type=int, default=1, help="max images per folder (default 1)")
    ap.add_argument("--limit", type=int, default=1000, help="max faces to use (default 1000)")
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("embedding_center.npy"))
    args = ap.parse_args()

    embeddings, skipped = [], 0
    for path in iter_images(args.image_dir, args.per_dir):
        if len(embeddings) >= args.limit:
            break
        try:
            img = np.array(Image.open(path).convert("RGB"))
            det = detect_face(img)
            if not det.detections:
                skipped += 1
                continue
            embeddings.append(extract_face_embedding(img, det.detections[0], num_jitters=1))
        except (OSError, ImageDecodeError, FaceEmbeddingError) as e:
            print(f"skip {path.name}: {e}", file=sys.stderr)
            skipped += 1
        if len(embeddings) % 50 == 0 and embeddings:
            print(f"{len(embeddings)} faces encoded...")

    if len(embeddings) < 50:
        sys.exit(f"Only {len(embeddings)} usable faces; need at least 50 for a stable center.")

    center = np.mean(np.stack(embeddings), axis=0)
    assert center.shape == (_EMBEDDING_DIM,)
    np.save(args.out, center)
    print(f"Saved center from {len(embeddings)} faces ({skipped} skipped) -> {args.out}")


if __name__ == "__main__":
    main()