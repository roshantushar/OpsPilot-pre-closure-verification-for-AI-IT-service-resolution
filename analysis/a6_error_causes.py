"""A6 - cost-weighted error Pareto: label each held-out error with a root-cause layer (data, prompt, model, tool interface, control loop, guardrail), weight by C_FC/C_FB, rank fixes by ROI.

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d8/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "a6_error_causes"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  a6_error_causes: TODO")


if __name__ == "__main__":
    main()
