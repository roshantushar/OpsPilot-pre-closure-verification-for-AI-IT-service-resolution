"""Tool layer: JSON-schema descriptors (v1 / v2 / v1_history) + a runtime that executes calls.

The runtime is the ONLY path from a verifier to enterprise state. It wraps the dataset's
read-only `MockITSM` and applies, in order:
    allowlist -> dedup -> perturbation(before) -> MockITSM -> perturbation(after)
    -> history/raw formatting -> truncation -> trace event
There are no write tools (plan hard rule 6).

Poka-yoke choices in v2 (D2b, "this makes X impossible"):
  * one tool per system with typed args -> a typo cannot hit the wrong system
  * tools return current state only     -> the model cannot read a stale value
  * no write tools                      -> the verifier cannot change state
  * bounded outputs                     -> a record cannot flood the context
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import time
from dataclasses import dataclass, field

from .config import SETTINGS
from .perturb import TOOL_SYSTEM, Perturber, dumps_result

# Load the dataset's public tool module by path (avoids a name clash with this file).
_spec = importlib.util.spec_from_file_location("opspilot_mock_tools", SETTINGS.data_dir / "tools" / "mock_tools.py")
_mock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mock)
MockITSM, TOOL_NAMES = _mock.MockITSM, _mock.TOOL_NAMES

# ---------------------------------------------------------------------------------------
# v2 descriptors: precise names, typed args, current state only
# ---------------------------------------------------------------------------------------
def _fn(name: str, desc: str, arg: str, arg_desc: str) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": {arg: {"type": "string", "description": arg_desc}},
                       "required": [arg], "additionalProperties": False}}}


V2_TOOLS = {
    "get_hr_employee": _fn("get_hr_employee", "HR record (source of truth for employment): status "
                           "active|terminated|leave, department, manager_email, legal_hold, notes.",
                           "email", "Employee email, e.g. jane.doe@acme.example"),
    "get_okta_user": _fn("get_okta_user", "Okta identity: status ACTIVE|SUSPENDED|DEACTIVATED|LOCKED_OUT, "
                         "groups, sessions_active, password_reset_required, mfa_reset_issued.",
                         "email", "User email"),
    "get_google_user": _fn("get_google_user", "Google Workspace account: suspended, org_unit, oauth_tokens "
                           "(count), force_password_reset, data_transfer_to, deleted.", "email", "User email"),
    "get_slack_user": _fn("get_slack_user", "Slack account: deactivated flag.", "email", "User email"),
    "list_devices": _fn("list_devices", "All Intune devices owned by a user (device_id, status "
                        "active|locked|wipe_pending|wiped, lost_mode, owner).", "owner_email", "Owner email"),
    "get_device": _fn("get_device", "One Intune device by id, including its owner.", "device_id",
                      "Device id, e.g. LT-12345"),
    "get_incident": _fn("get_incident", "ServiceNow incident: state, hold_reason, escalated_to, category, "
                        "priority, work_notes.", "number", "Incident number, e.g. INC0012345"),
    "list_slas": _fn("list_slas", "SLA records for an incident: stage in_progress|paused|breached, "
                     "has_breached, breach_time.", "incident_number", "Incident number"),
    "list_approvals": _fn("list_approvals", "Approval records for a ticket: state, approver, group.",
                          "ticket_number", "Ticket/incident number"),
    "list_security_exceptions": _fn("list_security_exceptions", "Security exceptions (e.g. legal_hold) "
                                    "for an employee: type, active.", "employee_email", "Employee email"),
    "lookup_runbook": _fn("lookup_runbook", "Full text of a runbook by id (conditions, never-do list, "
                          "escalation rule).", "runbook_id", "Runbook id, e.g. KB-OPS-101"),
}

# ---------------------------------------------------------------------------------------
# v1 descriptors: vague names, free-text args (the "before" arm of D2b)
# ---------------------------------------------------------------------------------------
def _fn2(name: str, desc: str, props: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
        "required": list(props)}}}


V1_TOOLS = {
    "get_user": _fn2("get_user", "Look up a user.", {"query": "who", "system": "which system"}),
    "get_ticket": _fn2("get_ticket", "Get a ticket.", {"query": "ticket"}),
    "get_ticket_details": _fn2("get_ticket_details", "More ticket info.", {"query": "ticket", "kind": "what"}),
    "get_devices": _fn2("get_devices", "Device info.", {"query": "device or person"}),
    "get_doc": _fn2("get_doc", "Get a document.", {"name": "document"}),
}
_V1_SYSTEM_ALIASES = {"hr": "get_hr_employee", "workday": "get_hr_employee", "okta": "get_okta_user",
                      "google": "get_google_user", "google workspace": "get_google_user",
                      "gsuite": "get_google_user", "slack": "get_slack_user"}
_V1_DETAIL_ALIASES = {"sla": "list_slas", "slas": "list_slas", "approval": "list_approvals",
                      "approvals": "list_approvals", "exception": "list_security_exceptions",
                      "security exception": "list_security_exceptions", "legal hold": "list_security_exceptions"}

ARG_NAME = {n: next(iter(V2_TOOLS[n]["function"]["parameters"]["properties"])) for n in V2_TOOLS}


def tool_specs(descriptor_version: str = "v2", tool_subset="all", use_runbook: bool = True) -> list[dict]:
    """Descriptors offered to the model for one run."""
    if descriptor_version == "v1":
        specs = dict(V1_TOOLS)
        if not use_runbook:
            specs.pop("get_doc")
        return list(specs.values())
    names = list(V2_TOOLS) if tool_subset in (None, "all") else list(tool_subset)
    if not use_runbook and "lookup_runbook" in names:
        names.remove("lookup_runbook")
    return [V2_TOOLS[n] for n in names]


def _translate_v1(name: str, args: dict) -> tuple[str | None, dict, str | None]:
    """Map a v1 call onto a real tool. Returns (tool, args, error)."""
    q = str(args.get("query", "")).strip()
    if name == "get_user":
        tool = _V1_SYSTEM_ALIASES.get(str(args.get("system", "")).strip().lower())
        return (tool, {ARG_NAME[tool]: q}, None) if tool else (None, {}, f"unknown system '{args.get('system')}'")
    if name == "get_ticket":
        return "get_incident", {"number": q}, None
    if name == "get_ticket_details":
        tool = _V1_DETAIL_ALIASES.get(str(args.get("kind", "")).strip().lower())
        return (tool, {ARG_NAME[tool]: q}, None) if tool else (None, {}, f"unknown kind '{args.get('kind')}'")
    if name == "get_devices":
        return ("get_device", {"device_id": q}, None) if "@" not in q else ("list_devices", {"owner_email": q}, None)
    if name == "get_doc":
        return "lookup_runbook", {"runbook_id": q}, None
    return None, {}, f"unknown tool '{name}'"


# ---------------------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------------------
_AUDIT = {"sys_created_by": "svc-integration", "sys_updated_by": "svc-integration",
          "sys_mod_count": 7, "sys_tags": [], "sys_domain": "global", "source_connector": "v3.2.1"}


def _collapse_long_lists(result: dict, max_items: int = 20) -> dict:
    """Compact returns: collapse long list fields (e.g. 400 heartbeat work notes) by pattern.

    Items that differ only in digits are merged into one entry with a count, order preserved.
    """
    r = copy.deepcopy(result)
    for row in r.get("results", []):
        for k, v in list(row.items()):
            if isinstance(v, list) and len(v) > max_items and all(isinstance(x, str) for x in v):
                groups: dict[str, list] = {}
                for x in v:
                    groups.setdefault(re.sub(r"\d+", "#", x), []).append(x)
                row[k] = [g[0] if len(g) == 1 else f"{g[0]} [+{len(g) - 1} similar entries collapsed]"
                          for g in groups.values()]
    return r


@dataclass
class ToolEvent:
    turn: int
    name: str
    args: dict
    output_chars: int
    latency_ms: float
    dup: bool = False
    invalid: bool = False
    error: str | None = None


@dataclass
class ToolRuntime:
    case: dict
    descriptor_version: str = "v2"
    compact_returns: bool = True
    tool_subset: object = "all"
    use_runbook: bool = True
    dedup: bool = True
    perturber: Perturber = field(default_factory=Perturber)
    max_chars: int = SETTINGS.max_tool_output_chars
    events: list[ToolEvent] = field(default_factory=list)
    _cache: dict = field(default_factory=dict)
    _seen: set = field(default_factory=set)

    def __post_init__(self):
        # The environment opens the case's state file; verifiers never do (leakage rule 1).
        self._env = MockITSM(self.case["state_file"])
        self._allowed = {s["function"]["name"] for s in tool_specs(
            self.descriptor_version, self.tool_subset, self.use_runbook)}

    # ------------------------------------------------------------------------------
    def call(self, name: str, args: dict | None, turn: int = 0) -> str:
        """Execute one tool call and return the observation string shown to the model."""
        args = args or {}
        t0 = time.perf_counter()
        key = (name, json.dumps(args, sort_keys=True))
        if name not in self._allowed:
            return self._log(turn, name, args, t0, json.dumps(
                {"ok": False, "error": f"tool '{name}' is not available",
                 "available": sorted(self._allowed)}), invalid=True)
        if self.dedup and key in self._cache:
            obs = self._cache[key] + ' // NOTE: identical call already made; result repeated from cache.'
            return self._log(turn, name, args, t0, obs, dup=True)
        dup_without_dedup = key in self._seen
        self._seen.add(key)
        real, real_args, err = (name, args, None)
        if self.descriptor_version == "v1":
            real, real_args, err = _translate_v1(name, args)
        if err:
            return self._log(turn, name, args, t0, json.dumps({"ok": False, "error": err}), invalid=True)
        arg_name = ARG_NAME[real]
        if arg_name not in real_args or not str(real_args[arg_name]).strip():
            return self._log(turn, name, args, t0, json.dumps(
                {"ok": False, "error": f"missing argument '{arg_name}'"}), invalid=True)
        forced = self.perturber.before_call(real)
        if forced is not None:
            result = forced
        elif real == "lookup_runbook":
            result = MockITSM.lookup_runbook(real_args[arg_name])
            if result.get("ok"):
                result["text"] = self.perturber.runbook(result["text"])
        else:
            result = getattr(self._env, real)(real_args[arg_name])
            result = self.perturber.after_call(real, result)
        obs = self._format(result)
        failed = not isinstance(result, dict) or result.get("ok") is False
        if not failed:  # never cache failures: a retry must reach the system again
            self._cache[key] = obs
        return self._log(turn, name, args, t0, obs, dup=dup_without_dedup,
                         error=result.get("error") if isinstance(result, dict) else "malformed")

    def _format(self, result) -> str:
        if isinstance(result, str):
            return result  # malformed JSON fault: pass through untouched
        r = copy.deepcopy(result)
        history = self.descriptor_version == "v1_history"
        if not history and r.get("ok") and "results" in r:
            # v2 (and v1) show current state only: strip any status_history a `stale`
            # perturbation injected (EXPERIMENTS_FOR_CLAUDE_CODE.md F2 - the poka-yoke must
            # hold regardless of descriptor version, not just when nothing perturbed the row).
            for row in r["results"]:
                row.pop("status_history", None)
        fat = self.descriptor_version in ("v1", "v1_history") or not self.compact_returns
        if fat and r.get("ok") and "results" in r:
            for row in r["results"]:
                row.update(_AUDIT)
                if history and "status_history" not in row:
                    snap = {k: v for k, v in row.items() if not k.startswith("sys_")}
                    row["status_history"] = [{"at": "2026-09-03T17:30:00Z", **snap}]
            s = json.dumps(r, indent=2, default=str)
        else:
            s = dumps_result(r)
            if len(s) > self.max_chars and r.get("ok"):
                s = dumps_result(_collapse_long_lists(r))   # compact mode keeps JSON valid
        if len(s) > self.max_chars:
            s = s[: self.max_chars] + f'... [truncated {len(s) - self.max_chars} chars]'
        return s

    def _log(self, turn, name, args, t0, obs, dup=False, invalid=False, error=None) -> str:
        self.events.append(ToolEvent(turn, name, args, len(obs), (time.perf_counter() - t0) * 1000,
                                     dup, invalid, error))
        return obs

    # ---- summaries for the run record -----------------------------------------------------
    @property
    def names_called(self) -> list[str]:
        return [e.name for e in self.events]

    def stats(self) -> dict:
        return {"tools_called": self.names_called, "tool_call_count": len(self.events),
                "duplicate_tool_calls": sum(e.dup for e in self.events),
                "invalid_tool_calls": sum(e.invalid for e in self.events),
                "tool_latency_ms": round(sum(e.latency_ms for e in self.events), 2),
                "observation_chars": sum(e.output_chars for e in self.events)}


def system_of(tool: str) -> str | None:
    return TOOL_SYSTEM.get(tool)


assert set(TOOL_NAMES) == set(V2_TOOLS), "descriptor set drifted from dataset tools"
