"""Public-data loaders. OpsPilot-side code may use ONLY this module to get cases.

It never touches `hidden/` (labels, specs) or the checker. Labels are joined in
`src/scoring.py` only (CLAUDE.md rule 1, enforced by tests/test_no_leakage.py).
"""
from __future__ import annotations

import json
from functools import lru_cache

from .config import SETTINGS

PUBLIC_SETS = ["dev_runs", "heldout_runs", "premature_dev", "premature_heldout",
               "correct_dev", "correct_heldout", "guardrail"]
HELDOUT_SUBSETS = {"heldout_mini", "heldout_runs", "premature_heldout", "correct_heldout"}


@lru_cache(maxsize=None)
def load_public_set(name: str) -> tuple[dict, ...]:
    path = SETTINGS.data_dir / "public" / "cases" / f"{name}.jsonl"
    return tuple(json.loads(line) for line in path.read_text().splitlines() if line.strip())


@lru_cache(maxsize=None)
def all_cases() -> dict[str, dict]:
    """case_id -> public case dict (ticket, proposed_closure, runbook_id, state_file)."""
    out: dict[str, dict] = {}
    for s in PUBLIC_SETS:
        for c in load_public_set(s):
            out[c["case_id"]] = c
    return out


def load_subset(name: str) -> list[dict]:
    """A subset is either a dataset set (e.g. 'dev_runs') or data/subsets/<name>.json."""
    if name in PUBLIC_SETS:
        return list(load_public_set(name))
    path = SETTINGS.subsets_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run: python data/make_subsets.py")
    ids = json.loads(path.read_text())["case_ids"]
    cases = all_cases()
    return [cases[i] for i in ids]


def is_heldout(subset: str) -> bool:
    return subset in HELDOUT_SUBSETS


def runbook_text(runbook_id: str) -> str | None:
    p = SETTINGS.data_dir / "runbooks" / f"{runbook_id}.md"
    return p.read_text() if p.exists() else None


def declared(case: dict) -> bool:
    """Did the resolver claim completion? Undeclared runs are attempted but never released."""
    pc = case.get("proposed_closure")
    return bool(pc and pc.get("resolver_declared_resolved"))
