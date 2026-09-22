"""Shared bounded tool-calling loop (D1). Used by verifiers/agent.py.

    while guards allow:
        model turn -> tool calls? execute via ToolRuntime (allowlist, dedup, perturbation)
                   -> final JSON?  parse -> one repair attempt -> fail-safe ESCALATE
Step cap, per-case budget cap and early exit are enforced HERE, in code.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .guardrails import GuardState
from .schema import Decision, fail_safe, parse_decision

REPAIR_MSG = ("Your last message was not a valid decision. Reply with ONLY the JSON object "
              "described in the instructions.")


@dataclass
class LoopResult:
    decision: Decision
    turns: int = 0
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0,
                                                 "reasoning_tokens": 0, "cached_tokens": 0})
    llm_cost_usd: float = 0.0
    llm_latency_ms: float = 0.0
    schema_validation_failed: bool = False
    guard: GuardState | None = None
    trace: list[dict] = field(default_factory=list)
    retry_attempted: bool = False
    retry_success: bool | None = None


def _add_usage(res: LoopResult, r) -> None:
    for k in res.usage:
        res.usage[k] += int(r.usage.get(k, 0) or 0)
    res.llm_cost_usd += r.cost_usd
    res.llm_latency_ms += r.latency_ms


def run_loop(backend, runtime, cfg, system: str, user: str, tools: list[dict], meta: dict) -> LoopResult:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    guard = GuardState(step_cap=cfg.step_cap, budget_cap_usd=cfg.budget_cap_usd, early_exit=cfg.early_exit)
    res = LoopResult(decision=fail_safe("not started"), guard=guard)
    repaired = False
    failed_calls: set = set()
    while True:
        stop = guard.before_turn()
        if stop:
            res.trace.append({"event": "guard", "guard": stop, "turn": guard.turns})
            res.decision = fail_safe(f"{stop} reached after {guard.turns} turns")
            break
        r = backend.complete(messages, tools=tools, purpose="agent", cfg=cfg, meta=meta)
        _add_usage(res, r)
        guard.after_turn(r.cost_usd)
        res.trace.append({"event": "llm", "turn": guard.turns, **r.usage, "cost_usd": r.cost_usd,
                          "latency_ms": round(r.latency_ms, 1), "cache_hit": r.cache_hit,
                          "n_tool_calls": len(r.tool_calls)})
        messages.append(r.assistant_message)
        if r.tool_calls:
            exit_reason = None
            for tc in r.tool_calls:
                t0 = time.perf_counter()
                obs = runtime.call(tc["name"], tc["arguments"], turn=guard.turns)
                ev = runtime.events[-1]
                key = (tc["name"], str(sorted(tc["arguments"].items())))
                if key in failed_calls:
                    res.retry_attempted = True
                    res.retry_success = ev.error is None
                if ev.error:
                    failed_calls.add(key)
                res.trace.append({"event": "tool", "turn": guard.turns, "name": tc["name"], "args": tc["arguments"],
                                  "output_chars": ev.output_chars, "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                                  "dup": ev.dup, "invalid": ev.invalid, "error": ev.error})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": obs})
                exit_reason = exit_reason or guard.after_observation(obs)
            if exit_reason:
                res.trace.append({"event": "guard", "guard": exit_reason, "turn": guard.turns})
                res.decision = Decision(decision="ESCALATE", confidence=0.9,
                                        reason=f"early exit: {exit_reason.split(':', 1)[1]}")
                break
            continue
        d, err = parse_decision(r.content)
        if d is not None:
            res.decision = d
            break
        if repaired:
            res.schema_validation_failed = True
            res.decision = fail_safe(f"schema validation failed twice: {err}")
            break
        repaired = True
        res.trace.append({"event": "guard", "guard": "schema_repair", "turn": guard.turns, "error": err})
        messages.append({"role": "user", "content": REPAIR_MSG})
    res.turns = guard.turns
    res.trace.append({"event": "final", "decision": res.decision.decision, "turns": res.turns})
    return res
