"""Read-note baseline: one LLM call, NO tools. Sees ticket + runbook + closure note only.

Tests storyline sentence 3: reading the agent's note does not catch false closures.
"""
from __future__ import annotations

from ..agent_loop import LoopResult, _add_usage
from ..data import runbook_text
from ..prompt import READ_NOTE_PROMPT, case_message
from ..schema import fail_safe, parse_decision


def verify(case, runtime, cfg, backend, meta=None) -> LoopResult:
    user = case_message(case, cfg)
    if cfg.use_runbook:
        user += "\n\nRUNBOOK:\n" + runtime.perturber.runbook(runbook_text(case["runbook_id"]) or "")
    msgs = [{"role": "system", "content": READ_NOTE_PROMPT}, {"role": "user", "content": user}]
    r = backend.complete(msgs, tools=None, purpose="read_note", cfg=cfg, meta=meta)
    res = LoopResult(decision=fail_safe("unparsed"), turns=1)
    _add_usage(res, r)
    d, err = parse_decision(r.content)
    res.decision, res.schema_validation_failed = (d, False) if d else (fail_safe(err), True)
    res.trace += [{"event": "llm", "turn": 1, **r.usage, "cost_usd": r.cost_usd},
                  {"event": "final", "decision": res.decision.decision, "turns": 1}]
    return res
