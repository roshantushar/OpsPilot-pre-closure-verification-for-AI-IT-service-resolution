"""Budget ledger and hard stop (US$3.50 total, plan §9).

Every PAID call appends one row to results/ledger.csv. Cache hits are logged with cost 0 and
cache_hit=1 so the ledger doubles as a call log. `total_spent()` is the single source of truth.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from .config import SETTINGS

LEDGER_FIELDS = ["timestamp", "experiment_id", "arm", "run_id", "purpose", "model", "input_tokens",
                 "output_tokens", "reasoning_tokens", "cached_tokens", "cost_usd", "cost_source", "cache_hit"]


class BudgetExceeded(RuntimeError):
    pass


def ledger_path() -> Path:
    return SETTINGS.results_dir / "ledger.csv"


def record(row: dict) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), **row})


def total_spent() -> float:
    p = ledger_path()
    if not p.exists():
        return 0.0
    with p.open() as f:
        return round(sum(float(r["cost_usd"] or 0) for r in csv.DictReader(f)), 6)


def spent_by(experiment_id: str) -> float:
    p = ledger_path()
    if not p.exists():
        return 0.0
    with p.open() as f:
        return round(sum(float(r["cost_usd"] or 0) for r in csv.DictReader(f)
                         if r["experiment_id"] == experiment_id), 6)


def remaining() -> float:
    return round(SETTINGS.max_budget_usd - total_spent(), 6)


def guard(next_call_estimate_usd: float = 0.0, experiment_id: str | None = None) -> None:
    """Raise before a call that would cross the global cap.

    Non-D8 calls are held to MAX_BUDGET_USD minus RESERVED_FOR_D8_USD, so earlier experiments
    cannot spend into D8's ring-fenced reserve (EXPERIMENTS_FOR_CLAUDE_CODE.md F4).
    """
    is_d8 = (experiment_id or "").startswith("D8")
    cap = SETTINGS.max_budget_usd if is_d8 else SETTINGS.max_budget_usd - SETTINGS.reserved_for_d8_usd
    if total_spent() + next_call_estimate_usd > cap:
        which = "global budget" if is_d8 else "budget minus the D8 reserve"
        raise BudgetExceeded(f"{which} ${cap:.2f} would be exceeded (spent ${total_spent():.4f})")


def project(n_case_runs: int, usd_per_case: float, cap_usd: float) -> dict:
    """Projected cost of a batch vs its manifest cap and the global remainder."""
    est = round(n_case_runs * usd_per_case, 4)
    return {"n_case_runs": n_case_runs, "usd_per_case": usd_per_case, "projected_usd": est,
            "cap_usd": cap_usd, "remaining_usd": remaining(),
            "over_cap": est > cap_usd, "over_global": est > remaining()}
