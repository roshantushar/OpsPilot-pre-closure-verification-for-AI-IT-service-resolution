"""Verifier registry. Every verifier: verify(case, runtime, cfg, backend, meta) -> LoopResult.

`case` is the (possibly perturbed) PUBLIC case; `runtime` is the only path to state.
"""
from __future__ import annotations


def get_verifier(name: str):
    from . import agent, baselines, hybrid, read_note, rules_entry, workflow
    return {
        "always_verified": baselines.always_verified,
        "always_escalate": baselines.always_escalate,
        "rules": rules_entry.verify,
        "read_note": read_note.verify,
        "workflow": workflow.verify,
        "agent": agent.verify,
        "hybrid": hybrid.verify,
    }[name]
