"""Decision / Evidence models (plan §6.2) and the fail-safe parser.

Invalid verifier output -> one repair attempt (caller's job) -> ESCALATE with
schema_validation_failed=True. Never VERIFIED by default.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

DecisionLabel = Literal["VERIFIED", "INCOMPLETE", "ESCALATE"]
NOT_DECLARED = "NOT_DECLARED"  # harness-only marker: resolver did not claim completion


class Evidence(BaseModel):
    condition_id: str
    observed: str = ""
    source: str = ""          # tool name that produced the observation
    holds: bool | None = None  # True / False / None (could not check)


class Decision(BaseModel):
    decision: DecisionLabel
    reason: str = ""
    cited_conditions: list[str] = Field(default_factory=list)  # conditions that FAIL / block
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("decision", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


def fail_safe(reason: str) -> Decision:
    return Decision(decision="ESCALATE", reason=f"fail-safe: {reason}", confidence=0.0)


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_decision(text: str | dict | None) -> tuple[Decision | None, str | None]:
    """Return (decision, error). Accepts a dict, raw JSON, or JSON inside prose/code fences."""
    if text is None:
        return None, "empty output"
    try:
        if isinstance(text, dict):
            return Decision.model_validate(text), None
        cleaned = text.replace("```json", "").replace("```", "").strip()
        m = _JSON_BLOCK.search(cleaned)
        if not m:
            return None, "no JSON object found"
        return Decision.model_validate(json.loads(m.group(0))), None
    except (json.JSONDecodeError, ValidationError) as e:
        return None, f"{type(e).__name__}: {str(e)[:300]}"


def apply_policy_flags(d: Decision, allow_escalate: bool, require_evidence: bool,
                       required_ids: list[str] | None = None) -> Decision:
    """Code-side post-processing for ablation arms and the evidence guard.

    - allow_escalate=False ("- escalation" ablation): ESCALATE is coerced to INCOMPLETE.
    - require_evidence=True: VERIFIED without evidence for every known required condition is
      downgraded to ESCALATE (plan success line 5). `required_ids` comes from the verifier's own
      reading of the runbook (never from hidden specs); if unknown, only 'some evidence' is required.
    """
    if not allow_escalate and d.decision == "ESCALATE":
        d = d.model_copy(update={"decision": "INCOMPLETE", "reason": d.reason + " [escalate disabled]"})
    if require_evidence and d.decision == "VERIFIED":
        cited = {e.condition_id for e in d.evidence if e.holds is not False}
        missing = [c for c in (required_ids or []) if c not in cited]
        if not d.evidence or missing:
            d = d.model_copy(update={
                "decision": "ESCALATE",
                "reason": d.reason + f" [evidence guard: missing {missing or 'all'}]",
            })
    return d
