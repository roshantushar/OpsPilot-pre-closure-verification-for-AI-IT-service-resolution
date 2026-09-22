"""Fixed workflow: code calls a FIXED tool sequence (every system, subject + ticket), then ONE
LLM decision call over the collected records. No model-chosen steps.
"""
from __future__ import annotations

import json

from ..agent_loop import LoopResult, _add_usage
from ..prompt import WORKFLOW_PROMPT, case_message
from ..schema import fail_safe, parse_decision
from ..tools import ARG_NAME
from .rules import ticket_context

FIXED_ORDER = ["lookup_runbook", "get_hr_employee", "list_security_exceptions", "get_okta_user",
               "get_google_user", "get_slack_user", "list_devices", "get_device", "get_incident",
               "list_slas", "list_approvals"]


def fixed_calls(case: dict) -> list[tuple[str, str]]:
    ctx = ticket_context(case)
    arg = {"lookup_runbook": case["runbook_id"], "get_hr_employee": ctx["subject"],
           "list_security_exceptions": ctx["subject"], "get_okta_user": ctx["subject"],
           "get_google_user": ctx["subject"], "get_slack_user": ctx["subject"], "list_devices": ctx["subject"],
           "get_device": ctx.get("device_id"), "get_incident": ctx["ticket"], "list_slas": ctx["ticket"],
           "list_approvals": ctx["ticket"]}
    return [(t, arg[t]) for t in FIXED_ORDER if arg.get(t)]


def verify(case, runtime, cfg, backend, meta=None) -> LoopResult:
    obs = {}
    for tool, a in fixed_calls(case):
        if tool == "lookup_runbook" and not cfg.use_runbook:
            continue
        obs[(tool, a)] = runtime.call(tool, {ARG_NAME[tool]: a}, turn=0)
    records = "\n".join(f"## {t}({a})\n{o}" for (t, a), o in obs.items())
    msgs = [{"role": "system", "content": WORKFLOW_PROMPT},
            {"role": "user", "content": case_message(case, cfg) + "\n\nRECORDS:\n" + records}]
    r = backend.complete(msgs, tools=None, purpose="decide_from_records", cfg=cfg, meta=meta, context={"obs": obs})
    res = LoopResult(decision=fail_safe("unparsed"), turns=1)
    _add_usage(res, r)
    d, err = parse_decision(r.content)
    res.decision, res.schema_validation_failed = (d, False) if d else (fail_safe(err), True)
    res.trace += [{"event": "llm", "turn": 1, **r.usage, "cost_usd": r.cost_usd, "records_chars": len(records)},
                  {"event": "final", "decision": res.decision.decision, "turns": 1}]
    return res
