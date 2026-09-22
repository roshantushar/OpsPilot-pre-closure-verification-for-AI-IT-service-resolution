"""EXPERIMENTS_FOR_CLAUDE_CODE.md F1: every fixture must target a system its own case's runbook
actually requires - not a hardcoded system that happens to be wrong for some families (the bug
this fixture system replaces: D4-5 used to perturb Okta for every premature_dev case, including
two runbooks that never check Okta at all)."""
import json

from src.config import ROOT
from src.perturb import TOOL_SYSTEM
from src.verifiers.rules import build_checks

DS = ROOT / "data" / "opspilot_itsm_data"
DUMMY_CTX = {"subject": "x@acme.example", "caller": "y@acme.example", "ticket": "INC0000001",
            "group": "eng-all", "device_id": "LT-00000", "old_dept": "Finance", "new_dept": "Engineering"}


def _runbook_systems(runbook_id: str) -> set:
    return {TOOL_SYSTEM[c.tool] for c in build_checks(runbook_id, DUMMY_CTX, hr={"manager_email": "m@acme.example"})}


def test_fixtures_target_a_system_the_runbook_requires():
    public = {json.loads(l)["case_id"]: json.loads(l)["runbook_id"]
             for l in (DS / "public" / "cases" / "premature_dev.jsonl").read_text().splitlines() if l}
    for name, key in (("very_hard_stale", "stale"), ("hard_conflict", "conflict")):
        fixtures = json.loads((ROOT / "data" / "subsets" / "fixtures" / f"{name}.json").read_text())
        assert fixtures, f"{name}.json is empty - run data/make_perturb_fixtures.py"
        for case_id, pert in fixtures.items():
            allowed = _runbook_systems(public[case_id])
            assert pert[key] in allowed, (
                f"{name}: {case_id} (runbook {public[case_id]}) targets system {pert[key]!r}, "
                f"but that runbook only requires {sorted(allowed)}")
