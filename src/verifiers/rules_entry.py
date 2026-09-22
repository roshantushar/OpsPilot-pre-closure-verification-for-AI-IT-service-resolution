"""Adapter: rules.verify -> LoopResult (rules makes no LLM calls; turns = 0)."""
from __future__ import annotations

from ..agent_loop import LoopResult
from . import rules


def verify(case, runtime, cfg, backend=None, meta=None) -> LoopResult:
    d, info = rules.verify(case, runtime, cfg)
    res = LoopResult(decision=d, turns=0)
    res.trace.append({"event": "final", "decision": d.decision, "turns": 0, "n_checks": len(info["checks"])})
    return res
