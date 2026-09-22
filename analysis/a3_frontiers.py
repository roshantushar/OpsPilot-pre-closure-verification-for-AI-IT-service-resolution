"""A3 - frontiers: FCR vs dollars per case Pareto over all arms; FCR vs FBR; risk-coverage (D4-6 abstention sweep).

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d4/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "a3_frontiers"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  a3_frontiers: TODO")


if __name__ == "__main__":
    main()
