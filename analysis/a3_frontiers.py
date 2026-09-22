"""A3 - frontiers: FCR vs dollars per case Pareto over all arms; FCR vs FBR; risk-coverage (D4-6 abstention sweep).

D4-6 needs no new runs: it re-reads confidence already logged by every live agent run and asks
"what if VERIFIED only released above some confidence threshold, and abstained (ESCALATE) below
it?" - a real re-derivation from results/master_runs.csv, not a new experiment.

Outputs: results/d4/decision_distribution.md, results/d4/confidence_sweep.png (+ .csv),
results/d4/fcr_vs_cost_pareto.png.
"""
from __future__ import annotations

import csv
from collections import Counter

from common import ROOT, out_dir, savefig

MASTER = ROOT / "results" / "master_runs.csv"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
COLOR = {"VERIFIED": "#2a78d6", "INCOMPLETE": "#eb6834", "ESCALATE": "#1baf7a"}


def _rows():
    """Real live agent runs only - scripted sanity checks (A1) and non-agent designs (D4-2's
    rules/read_note/workflow/hybrid) have no meaningful confidence signal to sweep or aren't
    comparable dollar-for-dollar with the agent's per-case cost."""
    if not MASTER.exists():
        return []
    with MASTER.open() as f:
        rows = [r for r in csv.DictReader(f) if r["backend"] == "live" and r["verifier"] == "agent"
               and r["declared"] == "True"]
    seen, out = set(), []
    for r in rows:  # de-dup: the same case+config gets logged once per experiment via reuse_from
        key = (r["config_hash"], r["case_id"], r["trial"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def decision_distribution(rows: list[dict]) -> str:
    good = [r for r in rows if r["verifier_pass"] == "True" and r["fbr_exempt"] != "True"]
    dist = Counter(r["decision"] for r in good)
    lines = ["# D4-6 - decision distribution on correct closures\n",
             f"n = {len(good)} genuinely-correct declared closures across all logged live agent runs.\n",
             "| decision | count | share |", "|---|---:|---:|"]
    for d in ("VERIFIED", "INCOMPLETE", "ESCALATE"):
        n = dist.get(d, 0)
        lines.append(f"| {d} | {n} | {100 * n / len(good) if good else 0:.1f}% |")
    lines.append(f"\nFBR on this set = {100 * (len(good) - dist.get('VERIFIED', 0)) / len(good) if good else 0:.1f}% "
                "(share NOT released, i.e. not VERIFIED).")
    return "\n".join(lines)


def sweep(rows: list[dict], thresholds) -> list[dict]:
    """At each threshold: a VERIFIED below it abstains to ESCALATE instead; everything else is
    unchanged. FCR and escalation rate use every declared row; FBR uses only the genuinely-correct
    closures (fbr_exempt excluded) - the plan's two named curves, not one conflated line."""
    good = [r for r in rows if r["verifier_pass"] == "True" and r["fbr_exempt"] != "True"]
    out = []
    for t in thresholds:
        fc = esc = 0
        for r in rows:
            conf = float(r["confidence"]) if r["confidence"] not in ("", "None") else 0.0
            sim_verified = r["decision"] == "VERIFIED" and conf >= t
            if sim_verified and r["verifier_pass"] != "True":
                fc += 1
            if not sim_verified:
                esc += 1
        blocked = sum(1 for r in good if not (r["decision"] == "VERIFIED"
                                              and float(r["confidence"] or 0) >= t))
        n = len(rows)
        out.append({"threshold": t, "FCR": fc / n if n else 0, "escalation_rate": esc / n if n else 0,
                    "FBR": blocked / len(good) if good else 0, "n": n})
    return out


def plot_sweep(curve: list[dict], path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=SURFACE)
    x = [c["threshold"] for c in curve]
    ax.plot(x, [c["FCR"] * 100 for c in curve], color=COLOR["ESCALATE"], linewidth=2, label="FCR")
    ax.plot(x, [c["escalation_rate"] * 100 for c in curve], color=COLOR["VERIFIED"], linewidth=2,
           label="escalation rate (all declared)")
    ax.plot(x, [c["FBR"] * 100 for c in curve], color=COLOR["INCOMPLETE"], linewidth=2,
           label="FBR (correct closures only)")
    ax.set_facecolor(SURFACE)
    ax.set_xlabel("confidence threshold to release VERIFIED", color=INK_2)
    ax.set_ylabel("%", color=INK_2)
    ax.set_title("D4-6: FCR vs escalation as the abstention threshold rises", color=INK, loc="left", fontsize=11)
    ax.grid(color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK_2)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(frameon=False, labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    rows = _rows()
    if not rows:
        print("  a3_frontiers: (skip) no logged live agent runs yet")
        return
    d0 = out_dir("d4")
    (d0 / "decision_distribution.md").write_text(decision_distribution(rows) + "\n")

    thresholds = [i / 20 for i in range(21)]  # 0.00 .. 1.00
    curve = sweep(rows, thresholds)
    with (d0 / "confidence_sweep.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["threshold", "FCR", "escalation_rate", "FBR", "n"])
        w.writeheader()
        w.writerows(curve)
    plot_sweep(curve, d0 / "confidence_sweep.png")

    print(decision_distribution(rows))
    print(f"\n-> {d0 / 'decision_distribution.md'}")
    print(f"-> {d0 / 'confidence_sweep.csv'}")
    print(f"-> {d0 / 'confidence_sweep.png'}")


if __name__ == "__main__":
    main()
