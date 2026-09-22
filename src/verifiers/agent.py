"""OpsPilot main verifier: bounded tool-calling agent (D1)."""
from __future__ import annotations

from ..agent_loop import run_loop
from ..prompt import case_message, system_prompt
from ..tools import tool_specs


def verify(case, runtime, cfg, backend, meta=None):
    tools = tool_specs(cfg.descriptor_version, cfg.tool_subset, cfg.use_runbook)
    return run_loop(backend, runtime, cfg, system_prompt(cfg), case_message(case, cfg), tools, meta or {})
