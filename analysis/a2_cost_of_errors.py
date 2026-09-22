"""A2 - cost of errors: severity-weighted FCR, threshold tau sweep on confidence, confusion matrix in dollars, tornado.

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d6/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "a2_cost_of_errors"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  a2_cost_of_errors: TODO")


if __name__ == "__main__":
    main()
