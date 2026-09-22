"""A4 - reliability: pass@k vs pass^k and flip rate from D4-7 (trials=3).

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d4/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "a4_reliability"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  a4_reliability: TODO")


if __name__ == "__main__":
    main()
