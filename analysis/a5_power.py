"""A5 - statistical power: simulate paired outcomes, exact McNemar, n in {24..120}. $0.

Default rates: baseline FCR from heldout_mini; verifier FCR = target (X/2). Replace p_arm with the
dev estimate after D4.
"""
from __future__ import annotations

import json
import random

from common import ROOT, savefig
from src.scoring import mcnemar_exact


def power(n, p_base, p_arm, reps=2000, alpha=0.05, seed=0):
    rng, hits = random.Random(seed), 0
    for _ in range(reps):
        b = c = 0
        for _ in range(n):
            base_fc = rng.random() < p_base
            arm_fc = base_fc and rng.random() < (p_arm / p_base)   # arm only fails where baseline fails
            b += base_fc and not arm_fc
            c += arm_fc and not base_fc
        hits += mcnemar_exact(b, c) < alpha
    return hits / reps


def main(p_arm=None):
    x = json.loads((ROOT / "data/subsets/heldout_mini.json").read_text())["baseline_fcr"]
    p_arm = p_arm if p_arm is not None else x / 2
    ns = [24, 48, 64, 80, 96, 120]
    pw = [power(n, x, p_arm) for n in ns]
    for n, p in zip(ns, pw):
        print(f"  n={n:<4} power={p:.2f}")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.plot(ns, pw, marker="o")
    ax.axvline(80, ls="--", c="grey")
    ax.axhline(0.8, ls=":", c="grey")
    ax.set(xlabel="n held-out cases", ylabel="power", title=f"A5 power (FCR {x:.2f} -> {p_arm:.2f})")
    print("  ->", savefig(fig, "a5_power", "d8"))


if __name__ == "__main__":
    main()
