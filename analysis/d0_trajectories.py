"""D0-2/D0-4 - trajectory examples (short/medium/long/early-exit/retry) and reliability vs turns s = P^(1/T) from D4/D8 traces.

Scaffold stub: inputs are results/master_runs.csv, results/summaries/ and results/traces/.
Outputs go to results/d0/. Fill in once the experiments it reads have been logged.
"""
from __future__ import annotations

from common import master, need


def main():
    df = master()
    if not need(df, "d0_trajectories"):
        return
    # TODO: implement (see docs/PROJECT_PLAN.md §8 / §10 for the formula and plot)
    print("  d0_trajectories: TODO")


if __name__ == "__main__":
    main()
