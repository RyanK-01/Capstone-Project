"""
Chart Module 3's face-match calibration for the presentation.

Re-uses calibrate_threshold.py's pipeline (same LFW pairs, same SimHash scoring),
saves every score to calibration_scores.csv, and draws two slide-ready charts:

  1. calib_distributions.png - same-person vs different-person score histograms
                               with the decision threshold marked
  2. calib_error_rates.png   - false-accept / false-reject rate vs threshold

Put this file next to main.py and calibrate_threshold.py, then run in the
same environment as the service:

    python plot_calibration.py ~/scikit_learn_data/lfw_home/lfw_funneled --people 150

Re-draw the charts later without re-encoding faces:

    python plot_calibration.py --from-csv calibration_scores.csv
"""
import argparse
import csv
import itertools
import random
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Deck colours (dark theme)
BG, CARD, TXT, MUTED, GRID = "#0B1220", "#131D33", "#F1F5F9", "#94A3B8", "#2A3A5E"
SAME, DIFF, THR = "#2DD4BF", "#F87171", "#FBBF24"


# ---------------------------------------------------------------- scoring
def collect_scores(lfw_dir: Path, people: int, seed: int):
    import main
    from calibrate_threshold import EXTS, embed

    def score(a, b, center):
        # Same as calibrate_threshold.score but WITHOUT the max(0, ...) clamp,
        # so below-chance pairs show as negative instead of piling up at 0.
        # Pass/fail at the threshold (> 0) is unchanged.
        bits_a = main._SIMHASH_PLANES @ (a - center) >= 0
        bits_b = main._SIMHASH_PLANES @ (b - center) >= 0
        d = int(np.count_nonzero(bits_a != bits_b))
        return 1.0 - 2.0 * d / main._SIMHASH_BITS

    rng = random.Random(seed)
    folders = sorted(p for p in lfw_dir.iterdir() if p.is_dir())
    multi = [f for f in folders if sum(x.suffix.lower() in EXTS for x in f.iterdir()) >= 2]
    rng.shuffle(multi)
    multi = multi[:people]
    if len(multi) < 2:
        sys.exit("Need at least 2 people with 2+ images each.")

    enrolled, probe = [], []
    for f in multi:
        imgs = sorted(x for x in f.iterdir() if x.suffix.lower() in EXTS)[:2]
        e, p = embed(imgs[0], main._ENROLL_JITTERS), embed(imgs[1], main._VERIFY_JITTERS)
        if e is not None and p is not None:
            enrolled.append(e)
            probe.append(p)
        print(f"\rencoded {len(enrolled)} people", end="", flush=True)
    print()

    n = len(enrolled)
    diff_pairs = list(itertools.permutations(range(n), 2))
    rng.shuffle(diff_pairs)
    diff_pairs = diff_pairs[: 20 * n]

    center = main._EMBEDDING_CENTER
    rows = [("same", score(enrolled[i], probe[i], center)) for i in range(n)]
    rows += [("different", score(enrolled[i], probe[j], center)) for i, j in diff_pairs]
    threshold = main._RAW_MATCH_THRESHOLD
    return rows, threshold


def save_csv(rows, threshold, path: Path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair_type", "score", "threshold"])
        for kind, s in rows:
            w.writerow([kind, f"{s:.6f}", threshold])


def load_csv(path: Path):
    rows, threshold = [], None
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append((r["pair_type"], float(r["score"])))
            threshold = float(r["threshold"])
    return rows, threshold


# ---------------------------------------------------------------- charts
def _style(ax):
    ax.set_facecolor(BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.xaxis.label.set_color(TXT)
    ax.yaxis.label.set_color(TXT)


def plot(rows, threshold, out_dir: Path):
    same = np.array([s for k, s in rows if k == "same"])
    diff = np.array([s for k, s in rows if k == "different"])
    far = np.mean(diff >= threshold)
    frr = np.mean(same < threshold)

    plt.rcParams["font.family"] = "DejaVu Sans"

    # 1. Score distributions
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200, facecolor=BG)
    _style(ax)
    bins = np.linspace(min(same.min(), diff.min()), max(same.max(), diff.max()), 45)
    # density so 150 same-person pairs and 3000 different-person pairs are comparable
    ax.hist(diff, bins=bins, density=True, color=DIFF, alpha=0.75, label=f"Different people  (n={len(diff)})")
    ax.hist(same, bins=bins, density=True, color=SAME, alpha=0.75, label=f"Same person  (n={len(same)})")
    ax.axvline(threshold, color=THR, lw=2.5, ls="--")
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.25)
    ax.text(threshold, ymax * 1.22, f"match threshold {threshold:.2f}\n{far:.1%} false accepts  ·  {frr:.1%} false rejects",
            color=TXT, fontsize=12, va="top", ha="center", linespacing=1.6,
            bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD, edgecolor=THR))
    ax.set_xlabel("SimHash similarity score")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False, fontsize=12)
    for t in leg.get_texts():
        t.set_color(TXT)
    fig.tight_layout()
    p1 = out_dir / "calib_distributions.png"
    fig.savefig(p1, facecolor=BG)
    plt.close(fig)

    # 2. Error rates vs threshold
    ts = np.linspace(-0.2, 1.0, 241)
    far_c = np.array([np.mean(diff >= t) for t in ts]) * 100
    frr_c = np.array([np.mean(same < t) for t in ts]) * 100
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200, facecolor=BG)
    _style(ax)
    ax.plot(ts, far_c, color=DIFF, lw=2.5, label="False accept rate (impostor gets in)")
    ax.plot(ts, frr_c, color=SAME, lw=2.5, label="False reject rate (real student refused)")
    ax.axvline(threshold, color=THR, lw=2, ls="--")
    ax.scatter([threshold, threshold], [far * 100, frr * 100], color=THR, zorder=5, s=50)
    ax.text(threshold, 104, f"threshold {threshold:.2f}:  {far:.1%} false accepts  ·  {frr:.1%} false rejects",
            color=TXT, fontsize=12, ha="center", va="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD, edgecolor=THR))
    ax.set_xlabel("Match threshold")
    ax.set_ylabel("Error rate (%)")
    ax.set_ylim(0, 110)
    ax.grid(axis="y", color=GRID, lw=0.6)
    leg = ax.legend(loc="lower right", bbox_to_anchor=(1.0, 0.04), frameon=False, fontsize=12)
    for t in leg.get_texts():
        t.set_color(TXT)
    fig.tight_layout()
    p2 = out_dir / "calib_error_rates.png"
    fig.savefig(p2, facecolor=BG)
    plt.close(fig)

    print(f"\nthreshold {threshold:.2f}: false accepts {far:.1%}, false rejects {frr:.1%}")
    print(f"same-person pairs {len(same)}, different-person pairs {len(diff)}")
    print(f"wrote {p1}\nwrote {p2}")


def main_():
    ap = argparse.ArgumentParser()
    ap.add_argument("lfw_dir", type=Path, nargs="?")
    ap.add_argument("--people", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--from-csv", type=Path)
    ap.add_argument("--out", type=Path, default=Path("."))
    args = ap.parse_args()

    if args.from_csv:
        rows, threshold = load_csv(args.from_csv)
    else:
        if not args.lfw_dir:
            sys.exit("Give the LFW folder, or --from-csv calibration_scores.csv")
        rows, threshold = collect_scores(args.lfw_dir, args.people, args.seed)
        save_csv(rows, threshold, args.out / "calibration_scores.csv")
        print(f"saved {args.out / 'calibration_scores.csv'}")
    plot(rows, threshold, args.out)


if __name__ == "__main__":
    main_()
