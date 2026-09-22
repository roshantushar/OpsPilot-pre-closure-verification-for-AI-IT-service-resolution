"""HIDDEN GROUND-TRUTH CHECKER — plays the role of the benchmark's verifier.

OpsPilot code must NEVER import this module or read hidden/specs/.
It evaluates a final state against a task spec and returns the ground truth
(verifier_pass) and the expected OpsPilot decision.

Decision rule (also documented in README):
  ESCALATE   if a forbidden change was made, a precondition fails, or evidence
             is unavailable / malformed / duplicated
  INCOMPLETE if every precondition holds, nothing forbidden happened, but at
             least one required end-state condition is not yet true
  VERIFIED   otherwise
"""
from .world import find

ENUMS = {
    ("okta", "users", "status"): {"ACTIVE", "SUSPENDED", "DEACTIVATED", "LOCKED_OUT"},
    ("intune", "devices", "status"): {"active", "locked", "wipe_pending", "wiped"},
    ("servicenow", "incidents", "state"): {"new", "in_progress", "on_hold", "resolved", "closed"},
    ("servicenow", "slas", "stage"): {"in_progress", "paused", "breached"},
    ("servicenow", "approvals", "state"): {"requested", "approved", "rejected"},
    ("hr", "employees", "status"): {"active", "terminated", "leave"},
}

# Systems whose records must not change for anyone except the ticket subject.
COLLATERAL_SYSTEMS = [("okta", "users", "email"), ("google_workspace", "users", "email"),
                      ("slack", "users", "email"), ("intune", "devices", "owner")]


def _op(val, op, target):
    if op == "eq":
        return val == target
    if op == "ne":
        return val != target
    if op == "in":
        return val in target
    if op == "contains":
        return isinstance(val, list) and target in val
    if op == "not_contains":
        return isinstance(val, list) and target not in val
    if op == "empty":
        return isinstance(val, list) and len(val) == 0
    if op == "is_null":
        return val is None
    if op == "not_null":
        return val is not None
    if op == "any_icontains":
        return isinstance(val, list) and any(target.lower() in str(x).lower() for x in val)
    raise ValueError(f"unknown op {op}")


def eval_condition(state, cond):
    """Return (result: bool | None, problems: list[str]). None = could not evaluate."""
    problems = []
    if cond["system"] in state.get("_unavailable", []):
        problems.append(f"unavailable:{cond['system']}")
    recs = find(state, cond["system"], cond["table"], cond["match"])
    if not recs:
        return False, problems
    if len(recs) > 1 and not cond.get("all"):
        problems.append(f"duplicate:{cond['system']}.{cond['table']}")
    enum = ENUMS.get((cond["system"], cond["table"], cond["field"]))
    for _, rec in recs:
        if enum is not None and rec.get(cond["field"]) not in enum:
            problems.append(f"malformed:{cond['system']}.{cond['field']}")
    vals = [rec.get(cond["field"]) for _, rec in recs]
    if cond.get("all"):
        result = all(_op(v, cond["op"], cond.get("value")) for v in vals)
    else:
        result = _op(vals[0], cond["op"], cond.get("value"))
    return result, problems


def collateral_changes(final, seed, subject_email):
    changed = []
    for system, table, owner_field in COLLATERAL_SYSTEMS:
        s_tbl = seed.get(system, {}).get(table, {})
        f_tbl = final.get(system, {}).get(table, {})
        for rid, s_rec in s_tbl.items():
            if s_rec.get(owner_field) == subject_email:
                continue
            if f_tbl.get(rid) != s_rec:
                changed.append(f"{system}.{table}.{rid}")
    return changed


def check(final, spec, seed):
    required_failed, forbidden, precond_failed, problems = [], [], [], []
    for cond in spec["conditions"]:
        result, probs = eval_condition(final, cond)
        problems.extend(probs)
        if cond["kind"] == "required" and not result:
            required_failed.append(cond["id"])
        elif cond["kind"] == "precondition" and not result:
            precond_failed.append(cond["id"])
        elif cond["kind"] == "forbidden" and result:
            forbidden.append(cond["id"])
    collateral = collateral_changes(final, seed, spec["subject_email"])
    if collateral:
        forbidden.append("GEN-F1")
    problems = sorted(set(problems))
    hard_problems = [p for p in problems if not p.startswith("unavailable:")]
    verifier_pass = not (required_failed or forbidden or precond_failed or hard_problems)
    if forbidden or precond_failed or problems:
        decision = "ESCALATE"
    elif required_failed:
        decision = "INCOMPLETE"
    else:
        decision = "VERIFIED"
    return {
        "verifier_pass": verifier_pass,
        "expected_decision": decision,
        "required_failed": required_failed,
        "forbidden_triggered": forbidden,
        "precondition_failed": precond_failed,
        "evidence_problems": problems,
        "collateral_changes": collateral,
    }
