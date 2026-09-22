"""Code-side guardrails (plan §6.3). Prompts are only the second layer.

    StepCap      - hard limit on model turns; hitting it => ESCALATE (fail-safe)
    CaseBudget   - per-case $ cap; exceeding it => ESCALATE
    Dedup        - lives in ToolRuntime (identical call -> cached result + note)
    Allowlist    - lives in ToolRuntime (unknown tool -> structured error)
    Schema check - src/schema.py parse_decision + one repair attempt, then ESCALATE
    EarlyExit    - optional: stop as soon as an observation makes ESCALATE certain
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class GuardState:
    step_cap: int
    budget_cap_usd: float
    early_exit: bool = False
    turns: int = 0
    spent_usd: float = 0.0
    fired: list[str] = field(default_factory=list)

    # returns the name of the guard that stops the run, or None
    def before_turn(self) -> str | None:
        if self.turns >= self.step_cap:
            return self._fire("step_cap")
        if self.spent_usd > self.budget_cap_usd:
            return self._fire("budget_cap")
        return None

    def after_turn(self, cost_usd: float) -> None:
        self.turns += 1
        self.spent_usd += cost_usd or 0.0

    def after_observation(self, obs: str) -> str | None:
        """Early exit on signals that make ESCALATE certain regardless of anything else."""
        if not self.early_exit:
            return None
        reason = escalation_signal(obs)
        return self._fire(f"early_exit:{reason}") if reason else None

    def _fire(self, name: str) -> str:
        self.fired.append(name)
        return name

    @property
    def step_cap_hit(self) -> bool:
        return "step_cap" in self.fired

    @property
    def budget_cap_hit(self) -> bool:
        return "budget_cap" in self.fired

    @property
    def early_exit_triggered(self) -> bool:
        return any(f.startswith("early_exit") for f in self.fired)


_ID_KEYS = ("email", "device_id", "number", "sla_id", "approval_id", "exception_id")


def escalation_signal(obs: str) -> str | None:
    """Detect 'system cannot be checked' / 'records duplicated' from an observation string."""
    try:
        r = json.loads(obs.split(" // NOTE")[0])
    except (json.JSONDecodeError, AttributeError):
        return "malformed_observation"
    if not isinstance(r, dict):
        return None
    if r.get("ok") is False and r.get("system"):
        return "system_unavailable"
    if r.get("ok") and r.get("count", 0) > 1 and "results" in r:
        keys = [next((row[k] for k in _ID_KEYS if k in row), None) for row in r["results"]]
        if None not in keys and len(set(keys)) < len(keys):
            return "duplicate_records"
    return None
