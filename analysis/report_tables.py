"""Headline tables for the report, regenerated from results/summaries (never hand-typed)."""
from __future__ import annotations

from common import out_dir, summaries


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def main():
    S = summaries()
    if not S:
        print("  (skip: no summaries yet)")
        return
    rows = ["| experiment/arm | n | FCR | FBR | Esc | Acc | Attack | $/case | p95 s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, s in S.items():
        m = s["metrics"]
        rows.append(f"| {name} | {m['n_attempted']} | {pct(m['FCR'])} | {pct(m['FBR'])} | {pct(m['escalation_rate'])} "
                    f"| {pct(m['accuracy'])} | {pct(m['attack_success_rate'])} | {m['cost_per_case_usd'] or 0:.4f} "
                    f"| {(m['latency_p95_ms'] or 0) / 1000:.1f} |")
    p = out_dir("summaries") / "ALL_ARMS.md"
    p.write_text("\n".join(rows) + "\n")
    print("\n".join(rows[:20]), f"\n-> {p}")


if __name__ == "__main__":
    main()
