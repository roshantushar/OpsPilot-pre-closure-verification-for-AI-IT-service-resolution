"""A7 - latency: latency ~ sum(llm + tool) per turn; fit vs turns; p50/p95 by decision.

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d6/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "a7_latency"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  a7_latency: TODO")


if __name__ == "__main__":
    main()
