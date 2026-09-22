"""Hybrid: the LLM compiles runbook + ticket into a checklist; CODE runs the checks and decides.

Unmappable condition (tool null / unknown field) -> ESCALATE. The decision rule is the same
deterministic function the rules verifier uses (rules.decide).
"""
from __future__ import annotations

import json

from ..agent_loop import LoopResult, _add_usage
from ..data import runbook_text
from ..prompt import HYBRID_COMPILE_PROMPT, case_message
from ..schema import Decision
from ..tools import ARG_NAME
from . import rules


def verify(case, runtime, cfg, backend, meta=None) -> LoopResult:
    subject = case["ticket"]["subject_email"]
    hr_obs = runtime.call("get_hr_employee", {"email": subject}, turn=0)
    rb = runtime.perturber.runbook(runbook_text(case["runbook_id"]) or "") if cfg.use_runbook else ""
    msgs = [{"role": "system", "content": HYBRID_COMPILE_PROMPT},
            {"role": "user", "content": case_message(case, cfg) + f"\n\nHR RECORD:\n{hr_obs}\n\nRUNBOOK:\n{rb}"}]
    r = backend.complete(msgs, tools=None, purpose="compile_checklist", cfg=cfg, meta=meta, context={"hr_obs": hr_obs})
    res = LoopResult(decision=Decision(decision="ESCALATE", reason="checklist not compiled"), turns=1)
    _add_usage(res, r)
    try:
        raw = json.loads((r.content or "").replace("```json", "").replace("```", "").strip())["checks"]
        checks = [rules.Check(**{k: c.get(k) for k in ("id", "kind", "tool", "arg", "field", "op", "value")},
                              agg=c.get("agg") or "one", where=c.get("where") or {},
                              where_not=c.get("where_not") or {}) for c in raw]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        res.schema_validation_failed = True
        res.decision = Decision(decision="ESCALATE", reason=f"checklist unparseable: {e}")
        res.trace.append({"event": "final", "decision": "ESCALATE", "turns": 1})
        return res
    unmappable = [c.id for c in checks if c.tool not in ARG_NAME or not c.field or not c.arg]
    obs = {("get_hr_employee", subject): hr_obs}
    for c in checks:
        if c.id not in unmappable and (c.tool, c.arg) not in obs:
            obs[(c.tool, c.arg)] = runtime.call(c.tool, {ARG_NAME[c.tool]: c.arg}, turn=1)
    d = rules.decide([c for c in checks if c.id not in unmappable], obs, cfg.early_exit)
    if unmappable:
        d = Decision(decision="ESCALATE", reason=f"unmappable conditions {unmappable}; " + d.reason,
                     cited_conditions=unmappable + d.cited_conditions, evidence=d.evidence, confidence=0.5)
    res.decision = d
    res.trace += [{"event": "llm", "turn": 1, **r.usage, "cost_usd": r.cost_usd, "n_checks": len(checks)},
                  {"event": "final", "decision": d.decision, "turns": 1}]
    return res
