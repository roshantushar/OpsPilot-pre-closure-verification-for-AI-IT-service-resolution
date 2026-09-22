"""Shared helpers for analysis scripts. Everything reads results/ (never re-runs models)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RESULTS = ROOT / "results"


def master(experiment: str | None = None):
    """master_runs.csv, deduplicated by run_id (last write wins)."""
    import pandas as pd
    p = RESULTS / "master_runs.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p).drop_duplicates("run_id", keep="last")
    return df[df.experiment_id == experiment] if experiment else df


def summaries(prefix: str = "") -> dict[str, dict]:
    d = RESULTS / "summaries"
    return {p.stem: json.loads(p.read_text()) for p in sorted(d.glob(f"{prefix}*.json"))} if d.exists() else {}


def trace(run_id: str) -> list[dict]:
    p = RESULTS / "traces" / f"{run_id}.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def out_dir(name: str) -> Path:
    p = RESULTS / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def savefig(fig, name: str, sub: str) -> Path:
    p = out_dir(sub) / f"{name}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    return p


def need(df, what: str) -> bool:
    if df is None or len(df) == 0:
        print(f"  (skip: no logged runs for {what} yet)")
        return False
    return True
