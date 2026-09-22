"""D4-8 retry recovery (Tier 2) - small resolver with typed WRITE tools on a COPY of the state.

Not part of OpsPilot (OpsPilot stays read-only). Planned design:
  1. copy the case's public state into a temp dir (never modify the dataset)
  2. give a resolver model typed write tools (set_okta_status, remove_group, set_ticket_state, ...)
  3. arm (a): feedback = OpsPilot's evidence + cited_conditions; arm (b): "re-check your work"
  4. one corrective attempt, then the HARNESS (not OpsPilot) re-scores the new state with the
     hidden checker inside src/scoring.py -> Retry Recovery Rate per arm.
Build only if the measured budget allows (plan §9 cut order: D4-8 is cut first).
"""
from __future__ import annotations


def run_retry(case: dict, opspilot_decision: dict, arm: str, cfg):  # pragma: no cover - Tier 2
    raise NotImplementedError("D4-8 retry recovery is Tier 2: implement after D8 budget is secured")
