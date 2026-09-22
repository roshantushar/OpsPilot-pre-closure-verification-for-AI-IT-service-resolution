"""Per-case perturbation fixtures (EXPERIMENTS_FOR_CLAUDE_CODE.md F1).

D4-5's hard_conflict/very_hard_stale arms used to perturb Okta for every premature_dev case, but
two of its eight runbooks (KB-OPS-104, KB-OPS-108) never check Okta at all - the perturbation was
silently inert for those cases while the expected rule still said the difficulty had gone up.

    python data/make_perturb_fixtures.py

For each premature_dev case, this targets the system/field of a REQUIRED condition its own
runbook actually uses: the condition the case is genuinely missing when one has a static scalar
value (CONDITION_FIELD below), else the runbook's default scalar condition (RUNBOOK_FALLBACK).
For `stale`, `old_value` is that condition's required value (the record now falsely looks done);
the real, still-failing current value is read live from the mock state, not written here.

Like make_subsets.py, this is DATA PREPARATION: it reads hidden labels to pick the right
condition. OpsPilot code (src/) never imports this script; at runtime it only reads the
case_id -> perturbation mapping this writes to data/subsets/fixtures/, which carries no label.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from src.perturb import TOOL_SYSTEM  # noqa: E402

DS = HERE / "opspilot_itsm_data"
OUT = HERE / "subsets" / "fixtures"

# (tool, field, required_value) for every required condition across all 8 runbooks that has a
# static, scalar value - extracted by hand from src/verifiers/rules.py build_checks(). Kept here
# rather than imported so this script has no runtime dependency on rules.py's internal shape.
# Omitted on purpose: list-valued conditions (e.g. Okta group membership) and conditions whose
# value depends on the ticket (approval id, department names) - a scalar eq/in check is what the
# stale/conflict mechanism (src/perturb.py) actually manipulates.
CONDITION_FIELD = {
    "LH-R1": ("get_okta_user", "status", "SUSPENDED"),
    "LH-R2": ("get_google_user", "suspended", True),
    "LH-R3": ("get_google_user", "org_unit", "/Legal Hold"),
    "LH-R4": ("get_google_user", "oauth_tokens", 0),
    "LH-R5": ("get_google_user", "force_password_reset", True),
    "LH-R6": ("get_slack_user", "deactivated", True),
    "LH-R7": ("get_incident", "state", "on_hold"),
    "LH-R8": ("get_incident", "hold_reason", "Legal Hold"),
    "LH-R9": ("get_incident", "escalated_to", "Legal"),
    "OFF-R1": ("get_okta_user", "status", "DEACTIVATED"),
    "OFF-R3": ("get_google_user", "suspended", True),
    "OFF-R5": ("get_slack_user", "deactivated", True),
    "OFF-R7": ("get_incident", "state", "resolved"),
    "ACC-R3": ("get_incident", "state", "resolved"),
    "HLD-R1": ("get_incident", "state", "on_hold"),
    "HLD-R2": ("get_incident", "hold_reason", "Awaiting Caller"),
    "HLD-R3": ("list_slas", "stage", "paused"),
    "LST-R1": ("get_device", "lost_mode", True),
    "LST-R2": ("get_device", "status", "locked"),
    "LST-R3": ("get_okta_user", "sessions_active", 0),
    "LST-R4": ("get_google_user", "oauth_tokens", 0),
    "LST-R5": ("get_incident", "category", "security"),
    "LST-R6": ("get_incident", "state", "resolved"),
    "LCK-R1": ("get_okta_user", "status", "ACTIVE"),
    "LCK-R2": ("get_okta_user", "password_reset_required", True),
    "LCK-R3": ("get_okta_user", "mfa_reset_issued", True),
    "LCK-R5": ("get_incident", "state", "resolved"),
    "TRF-R5": ("get_incident", "state", "resolved"),
    "BRC-R1": ("list_slas", "stage", "breached"),
    "BRC-R2": ("list_slas", "has_breached", True),
    "BRC-R3": ("get_incident", "escalated_to", "Service Manager"),
}
RUNBOOK_FALLBACK = {
    "KB-OPS-101": "LH-R1", "KB-OPS-102": "OFF-R1", "KB-OPS-103": "ACC-R3", "KB-OPS-104": "HLD-R1",
    "KB-OPS-105": "LST-R3", "KB-OPS-106": "LCK-R1", "KB-OPS-107": "TRF-R5", "KB-OPS-108": "BRC-R1",
}


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def target_condition(label: dict, runbook_id: str) -> str:
    failing = label.get("required_failed") or []
    return next((c for c in failing if c in CONDITION_FIELD), RUNBOOK_FALLBACK[runbook_id])


def main():
    public = {c["case_id"]: c for c in load_jsonl(DS / "public" / "cases" / "premature_dev.jsonl")}
    labels = {l["case_id"]: l for l in load_jsonl(DS / "hidden" / "labels" / "premature_dev.jsonl")}

    stale, conflict = {}, {}
    print(f"{'case':<14}{'runbook':<12}{'condition':<10}{'system':<12}{'field'}")
    for case_id, case in public.items():
        label = labels[case_id]
        runbook_id = case["runbook_id"]
        cond = target_condition(label, runbook_id)
        tool, field, value = CONDITION_FIELD[cond]
        system = TOOL_SYSTEM[tool]
        stale[case_id] = {"stale": system, "field": field, "old_value": value}
        conflict[case_id] = {"conflict": system, "field": field, "value": value}
        print(f"{case_id:<14}{runbook_id:<12}{cond:<10}{system:<12}{field}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "very_hard_stale.json").write_text(json.dumps(stale, indent=1))
    (OUT / "hard_conflict.json").write_text(json.dumps(conflict, indent=1))
    print(f"\n-> {OUT / 'very_hard_stale.json'}")
    print(f"-> {OUT / 'hard_conflict.json'}")


if __name__ == "__main__":
    main()
