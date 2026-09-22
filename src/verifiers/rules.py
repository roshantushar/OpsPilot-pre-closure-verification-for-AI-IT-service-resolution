"""Rules verifier (no LLM) + the shared check engine used by `hybrid` and the scripted backend.

Rules were written by reading the runbook TEXT in data/opspilot_itsm_data/runbooks/ and the tool
descriptors only - never the hidden specs or the checker (CLAUDE.md rule 1). Log the effort for
D4-2: see RULES_EFFORT below.

Known blind spot (by design, report it): GEN-F1 "do not modify anyone else's records" cannot be
checked from read-only per-subject tools except where the runbook names the other object
(LST-F1: the caller's other devices).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from ..schema import Decision, Evidence

RULES_EFFORT = {"hours": None, "lines_of_code": None, "note": "fill in for D4-2 (engineering effort)"}

# Allowed values, taken from the tool descriptors (src/tools.py). Anything else = malformed.
ENUMS = {
    ("get_okta_user", "status"): {"ACTIVE", "SUSPENDED", "DEACTIVATED", "LOCKED_OUT"},
    ("list_devices", "status"): {"active", "locked", "wipe_pending", "wiped"},
    ("get_device", "status"): {"active", "locked", "wipe_pending", "wiped"},
    ("get_incident", "state"): {"new", "in_progress", "on_hold", "resolved", "closed"},
    ("list_slas", "stage"): {"in_progress", "paused", "breached"},
    ("list_approvals", "state"): {"requested", "approved", "rejected"},
    ("get_hr_employee", "status"): {"active", "terminated", "leave"},
}

DEPARTMENT_GROUPS = {  # KB-OPS-107 / KB-OPS-102 "Department groups"
    "Finance": ["finance-all", "finance-reporting"], "Engineering": ["eng-all", "github-developers"],
    "Sales": ["sales-all", "crm-users"], "HR": ["hr-all", "workday-hr"],
    "Marketing": ["marketing-all", "cms-editors"], "Support": ["support-all", "zendesk-agents"],
}


@dataclass
class Check:
    id: str
    kind: str                 # precondition | required | forbidden
    tool: str
    arg: str
    field: str
    op: str                   # eq in contains not_contains empty not_null any_icontains
    value: object = None
    agg: str = "one"          # one (exactly one row expected) | all | any
    where: dict = field(default_factory=dict)      # row filter
    where_not: dict = field(default_factory=dict)  # row exclusion


# ---------------------------------------------------------------------------------------
# Context: what the ticket and the HR record tell us (no hidden data)
# ---------------------------------------------------------------------------------------
def ticket_context(case: dict) -> dict:
    t = case["ticket"]
    text = f"{t.get('short_description', '')} {t.get('description', '')}"
    ctx = {"subject": t["subject_email"], "caller": t["caller_email"], "ticket": t["number"]}
    m = re.search(r"Access request:\s*([\w\-]+)", t.get("short_description", "")) or \
        re.search(r"'([\w\-]+)' group", text)
    ctx["group"] = m.group(1) if m else None
    m = re.search(r"\b([A-Z]{2}-\d{4,})\b", text)
    ctx["device_id"] = m.group(1) if m else None
    depts = "|".join(DEPARTMENT_GROUPS)
    m = re.search(rf"\b({depts})\s*(?:->|to)\s*({depts})\b", text)
    ctx["old_dept"], ctx["new_dept"] = (m.group(1), m.group(2)) if m else (None, None)
    return ctx


def base_calls(case: dict) -> list[tuple[str, str]]:
    """Calls needed before the checklist can be built (dependency rule, D2c)."""
    return [("lookup_runbook", case["runbook_id"]), ("get_hr_employee", case["ticket"]["subject_email"])]


def build_checks(runbook_id: str, ctx: dict, hr: dict | None) -> list[Check]:
    s, tk, g = ctx["subject"], ctx["ticket"], ctx.get("group")
    mgr = (hr or {}).get("manager_email")
    C = Check
    if runbook_id == "KB-OPS-101":
        return [
            C("LH-P1", "precondition", "list_security_exceptions", s, "active", "eq", True, "any", {"type": "legal_hold"}),
            C("LH-R1", "required", "get_okta_user", s, "status", "eq", "SUSPENDED"),
            C("LH-R2", "required", "get_google_user", s, "suspended", "eq", True),
            C("LH-R3", "required", "get_google_user", s, "org_unit", "eq", "/Legal Hold"),
            C("LH-R4", "required", "get_google_user", s, "oauth_tokens", "eq", 0),
            C("LH-R5", "required", "get_google_user", s, "force_password_reset", "eq", True),
            C("LH-R6", "required", "get_slack_user", s, "deactivated", "eq", True),
            C("LH-R7", "required", "get_incident", tk, "state", "eq", "on_hold"),
            C("LH-R8", "required", "get_incident", tk, "hold_reason", "eq", "Legal Hold"),
            C("LH-R9", "required", "get_incident", tk, "escalated_to", "eq", "Legal"),
            C("LH-F1", "forbidden", "get_okta_user", s, "status", "eq", "DEACTIVATED"),
            C("LH-F2", "forbidden", "get_google_user", s, "data_transfer_to", "not_null"),
            C("LH-F3", "forbidden", "get_incident", tk, "state", "in", ["resolved", "closed"]),
            C("LH-F4", "forbidden", "get_google_user", s, "deleted", "eq", True),
        ]
    if runbook_id == "KB-OPS-102":
        return [
            C("OFF-P1", "precondition", "get_hr_employee", s, "status", "eq", "terminated"),
            C("OFF-P2", "precondition", "get_hr_employee", s, "legal_hold", "eq", False),
            C("OFF-R1", "required", "get_okta_user", s, "status", "eq", "DEACTIVATED"),
            C("OFF-R2", "required", "get_okta_user", s, "groups", "empty"),
            C("OFF-R3", "required", "get_google_user", s, "suspended", "eq", True),
            C("OFF-R4", "required", "get_google_user", s, "data_transfer_to", "eq", mgr),
            C("OFF-R5", "required", "get_slack_user", s, "deactivated", "eq", True),
            C("OFF-R6", "required", "list_devices", s, "status", "eq", "wipe_pending", "all"),
            C("OFF-R7", "required", "get_incident", tk, "state", "eq", "resolved"),
            C("OFF-F1", "forbidden", "get_google_user", s, "deleted", "eq", True),
        ]
    if runbook_id == "KB-OPS-103":
        w = {"group": g}
        return [
            C("ACC-P1", "precondition", "list_approvals", tk, "state", "eq", "approved", "one", w),
            C("ACC-P2", "precondition", "list_approvals", tk, "approver", "eq", mgr, "one", w),
            C("ACC-R1", "required", "get_okta_user", s, "groups", "contains", g),
            C("ACC-R2", "required", "get_incident", tk, "work_notes", "any_icontains", "__APPROVAL_ID__"),
            C("ACC-R3", "required", "get_incident", tk, "state", "eq", "resolved"),
            C("ACC-F1", "forbidden", "get_okta_user", s, "groups", "contains", f"{g}-admin"),
        ]
    if runbook_id == "KB-OPS-104":
        return [
            C("HLD-P1", "precondition", "list_slas", tk, "has_breached", "eq", False),
            C("HLD-R1", "required", "get_incident", tk, "state", "eq", "on_hold"),
            C("HLD-R2", "required", "get_incident", tk, "hold_reason", "eq", "Awaiting Caller"),
            C("HLD-R3", "required", "list_slas", tk, "stage", "eq", "paused"),
            C("HLD-R4", "required", "get_incident", tk, "work_notes", "any_icontains", "awaiting caller"),
            C("HLD-F1", "forbidden", "get_incident", tk, "state", "in", ["resolved", "closed"]),
        ]
    if runbook_id == "KB-OPS-105":
        dev, caller = ctx.get("device_id"), ctx["caller"]
        return [
            C("LST-P1", "precondition", "get_device", dev, "owner", "eq", caller),
            C("LST-R1", "required", "get_device", dev, "lost_mode", "eq", True),
            C("LST-R2", "required", "get_device", dev, "status", "eq", "locked"),
            C("LST-R3", "required", "get_okta_user", s, "sessions_active", "eq", 0),
            C("LST-R4", "required", "get_google_user", s, "oauth_tokens", "eq", 0),
            C("LST-R5", "required", "get_incident", tk, "category", "eq", "security"),
            C("LST-R6", "required", "get_incident", tk, "state", "eq", "resolved"),
            C("LST-F1", "forbidden", "list_devices", caller, "status", "in", ["locked", "wipe_pending", "wiped"],
              "any", {}, {"device_id": dev}),
            C("LST-F2", "forbidden", "get_okta_user", s, "status", "eq", "DEACTIVATED"),
        ]
    if runbook_id == "KB-OPS-106":
        return [
            C("LCK-P1", "precondition", "get_hr_employee", s, "status", "eq", "active"),
            C("LCK-R1", "required", "get_okta_user", s, "status", "eq", "ACTIVE"),
            C("LCK-R2", "required", "get_okta_user", s, "password_reset_required", "eq", True),
            C("LCK-R3", "required", "get_okta_user", s, "mfa_reset_issued", "eq", True),
            C("LCK-R4", "required", "get_incident", tk, "work_notes", "any_icontains", "identity verified"),
            C("LCK-R5", "required", "get_incident", tk, "state", "eq", "resolved"),
        ]
    if runbook_id == "KB-OPS-107":
        old = DEPARTMENT_GROUPS.get(ctx.get("old_dept") or "", [None, None])
        new = DEPARTMENT_GROUPS.get(ctx.get("new_dept") or "", [None, None])
        return [
            C("TRF-P1", "precondition", "get_hr_employee", s, "department", "eq", ctx.get("new_dept")),
            C("TRF-R1", "required", "get_okta_user", s, "groups", "not_contains", old[0]),
            C("TRF-R2", "required", "get_okta_user", s, "groups", "not_contains", old[1]),
            C("TRF-R3", "required", "get_okta_user", s, "groups", "contains", new[0]),
            C("TRF-R4", "required", "get_okta_user", s, "groups", "contains", new[1]),
            C("TRF-R5", "required", "get_incident", tk, "state", "eq", "resolved"),
            C("TRF-F1", "forbidden", "get_okta_user", s, "groups", "not_contains", "all-staff"),
        ]
    if runbook_id == "KB-OPS-108":
        return [
            C("BRC-P1", "precondition", "get_incident", tk, "priority", "in", ["P1", "P2"]),
            C("BRC-R1", "required", "list_slas", tk, "stage", "eq", "breached"),
            C("BRC-R2", "required", "list_slas", tk, "has_breached", "eq", True),
            C("BRC-R3", "required", "get_incident", tk, "escalated_to", "eq", "Service Manager"),
            C("BRC-R4", "required", "get_incident", tk, "work_notes", "any_icontains", "sla breach"),
            C("BRC-F1", "forbidden", "list_slas", tk, "breach_time", "not_null"),  # "do not invent values"
            C("BRC-F2", "forbidden", "get_incident", tk, "state", "in", ["resolved", "closed"]),
        ]
    raise KeyError(f"no rules for runbook {runbook_id}")


# ---------------------------------------------------------------------------------------
# Check engine
# ---------------------------------------------------------------------------------------
def _op(val, op, target):
    if op == "eq":
        return val == target
    if op == "in":
        return val in target
    if op == "contains":
        return isinstance(val, list) and target in val
    if op == "not_contains":
        return isinstance(val, list) and target not in val
    if op == "empty":
        return isinstance(val, list) and len(val) == 0
    if op == "not_null":
        return val is not None
    if op == "any_icontains":
        return isinstance(val, list) and target is not None and any(str(target).lower() in str(x).lower() for x in val)
    raise ValueError(f"unknown op {op}")


def parse_obs(obs: str | None) -> dict | None:
    if obs is None:
        return None
    try:
        return json.loads(obs.split(" // NOTE")[0].split("... [truncated")[0])
    except json.JSONDecodeError:
        return {"ok": False, "error": "malformed_json"}


def eval_check(chk: Check, result: dict | None) -> tuple[bool | None, list[str], str]:
    """Return (holds, problems, observed-as-text). holds=None -> could not evaluate."""
    if result is None:
        return None, [f"not_checked:{chk.tool}"], "not checked"
    if not result.get("ok"):
        return None, [f"unavailable:{chk.tool}"], str(result.get("error"))
    rows = [r for r in result.get("results", [])
            if all(r.get(k) == v for k, v in chk.where.items())
            and not any(r.get(k) == v for k, v in chk.where_not.items())]
    if not rows:
        return False, [], "no matching record"
    problems = []
    if chk.agg == "one" and len(rows) > 1:
        problems.append(f"duplicate:{chk.tool}")
    enum = ENUMS.get((chk.tool, chk.field))
    if enum and any(r.get(chk.field) not in enum for r in rows):
        problems.append(f"malformed:{chk.tool}.{chk.field}")
    vals = [r.get(chk.field) for r in rows]
    if chk.agg == "all":
        holds = all(_op(v, chk.op, chk.value) for v in vals)
    elif chk.agg == "any":
        holds = any(_op(v, chk.op, chk.value) for v in vals)
    else:
        holds = _op(vals[0], chk.op, chk.value)
    return holds, problems, json.dumps(vals if len(vals) > 1 else vals[0], default=str)[:120]


def resolve_placeholders(checks: list[Check], obs: dict) -> None:
    """ACC-R2: the approval id is only known after list_approvals has been read."""
    for c in checks:
        if c.value == "__APPROVAL_ID__":
            a = parse_obs(obs.get(("list_approvals", c.arg)))
            rows = (a or {}).get("results", []) if (a or {}).get("ok") else []
            grp = next((x.where.get("group") for x in checks if x.tool == "list_approvals"), None)
            rows = [r for r in rows if r.get("group") == grp] or rows
            c.value = rows[0].get("approval_id") if rows else None


def decide(checks: list[Check], obs: dict[tuple[str, str], str], early_exit: bool = False) -> Decision:
    """Deterministic decision rule (runbook 'Escalation' section)."""
    resolve_placeholders(checks, obs)
    failed_req, forbidden, pre_failed, problems, evidence = [], [], [], [], []
    order = sorted(checks, key=lambda c: {"precondition": 0, "forbidden": 1, "required": 2}[c.kind])
    for chk in order:
        holds, probs, observed = eval_check(chk, parse_obs(obs.get((chk.tool, chk.arg))))
        problems += probs
        evidence.append(Evidence(condition_id=chk.id, observed=observed, source=chk.tool,
                                 holds=holds if chk.kind != "forbidden" else (None if holds is None else not holds)))
        if chk.kind == "precondition" and holds is False:
            pre_failed.append(chk.id)
        elif chk.kind == "forbidden" and holds is True:
            forbidden.append(chk.id)
        elif chk.kind == "required" and holds is False:
            failed_req.append(chk.id)
        if early_exit and (pre_failed or forbidden or problems):
            break
    problems = sorted(set(problems))
    if forbidden or pre_failed or problems:
        return Decision(decision="ESCALATE", confidence=1.0, evidence=evidence,
                        cited_conditions=pre_failed + forbidden + failed_req,
                        reason=f"precondition failed {pre_failed}; forbidden {forbidden}; problems {problems}")
    if failed_req:
        return Decision(decision="INCOMPLETE", confidence=1.0, evidence=evidence, cited_conditions=failed_req,
                        reason=f"required conditions not met: {failed_req}")
    return Decision(decision="VERIFIED", confidence=1.0, evidence=evidence,
                    reason="all preconditions hold, all required conditions met, nothing forbidden observed")


def plan_calls(case: dict, hr_obs: str | None) -> tuple[list[Check], list[tuple[str, str]]]:
    """Checklist + ordered unique tool calls still to make (after base_calls)."""
    hr = parse_obs(hr_obs)
    hr_row = (hr or {}).get("results", [None])[0] if (hr or {}).get("ok") and hr.get("count") else None
    checks = build_checks(case["runbook_id"], ticket_context(case), hr_row)
    calls, seen = [], set(base_calls(case))
    for c in checks:
        key = (c.tool, c.arg)
        if key not in seen and c.arg:
            seen.add(key)
            calls.append(key)
    return checks, calls


def required_ids(runbook_id: str) -> list[str]:
    """Required-condition ids as listed in the runbook text (for the evidence guard)."""
    from ..data import runbook_text
    return re.findall(r"^- ([A-Z]+-R\d+):", runbook_text(runbook_id) or "", re.M)


# ---------------------------------------------------------------------------------------
# Verifier entry point
# ---------------------------------------------------------------------------------------
def verify(case: dict, runtime, cfg, backend=None) -> tuple[Decision, dict]:
    obs: dict[tuple[str, str], str] = {}
    for tool, arg in base_calls(case):
        obs[(tool, arg)] = runtime.call(tool, {_argname(tool): arg}, turn=0)
    checks, calls = plan_calls(case, obs[("get_hr_employee", case["ticket"]["subject_email"])])
    for tool, arg in calls:
        obs[(tool, arg)] = runtime.call(tool, {_argname(tool): arg}, turn=0)
    d = decide(checks, obs, early_exit=cfg.early_exit)
    return d, {"turns": 0, "checks": [asdict(c) for c in checks]}


def _argname(tool: str) -> str:
    from ..tools import ARG_NAME
    return ARG_NAME[tool]
