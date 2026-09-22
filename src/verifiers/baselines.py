"""Degenerate corners for harness sanity (A1): accept everything / escalate everything."""
from __future__ import annotations

from ..agent_loop import LoopResult
from ..schema import Decision


def always_verified(case, runtime, cfg, backend=None, meta=None) -> LoopResult:
    return LoopResult(decision=Decision(decision="VERIFIED", reason="baseline: accept every declared closure",
                                        confidence=1.0))


def always_escalate(case, runtime, cfg, backend=None, meta=None) -> LoopResult:
    return LoopResult(decision=Decision(decision="ESCALATE", reason="baseline: escalate everything",
                                        confidence=1.0))
