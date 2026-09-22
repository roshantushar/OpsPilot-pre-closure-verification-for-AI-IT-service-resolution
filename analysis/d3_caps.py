"""D3-4 - offline step-cap and budget-cap counterfactuals from logged runs ($0).

A run whose turns (or cost) exceed a cap would have been stopped -> counted as ESCALATE.
"""
from __future__ import annotations

from common import master, need, out_dir


def main():
    df = master()
    df = df[df.verifier == "agent"] if len(df) else df
    if not need(df, "agent runs"):
        return
    dec = df[df.declared == True]  # noqa: E712
    legit = dec[dec.correct == True]  # noqa: E712
    print(f"  turns: median={dec.turns.median()} p90={dec.turns.quantile(.9)} p95={dec.turns.quantile(.95)} "
          f"max legit={legit.turns.max()}")
    rows = ["| cap | runs truncated | correct runs truncated |", "|---:|---:|---:|"]
    for cap in [6, 8, 10, 12]:
        rows.append(f"| {cap} | {(dec.turns > cap).sum()} | {(legit.turns > cap).sum()} |")
    rows += ["", "| budget $ | runs truncated |", "|---:|---:|"]
    for b in [0.005, 0.01, 0.02, 0.05]:
        rows.append(f"| {b} | {(dec.total_cost_usd > b).sum()} |")
    (out_dir("d3") / "caps_counterfactual.md").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
