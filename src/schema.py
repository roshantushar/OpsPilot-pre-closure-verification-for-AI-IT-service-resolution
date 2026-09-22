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

# Conditions no read-only, per-subject tool can ever observe (rules.py's documented blind spot:
# "do not modify anyone else's records" needs a scan-every-employee tool that does not exist).
# Shared by verifiers/hybrid.py (does not force ESCALATE over one) and scoring.py (does not require
# a citation for one in the evidence-accuracy check - D4-9 found ~half its L1 "misses" were only
# missing GEN-F1, which no verifier, however good, could ever cite).
KNOWN_BLIND_SPOTS = {"GEN-F1"}


class Evidence(BaseModel):
    condition_id: str
    observed: str = ""
    source: str = ""          # tool name that produced the observation
    holds: bool | None = None  # True / False / None (could not check)

    @field_validator("observed", "source", mode="before")
    @classmethod
    def _stringify(cls, v):
        """A model may emit a field's native JSON type instead of stringifying it itself - a raw
        bool/number in `observed` (A2, gemini) or `source: null` for a condition it explicitly
        did not check via any tool (D4-3, v2b: the new blind-spot note tells it to report exactly
        that). Either used to fail the whole Decision's validation and fail-safe to ESCALATE - a
        parsing bug masquerading as a model judgment. Coerce instead of reject."""
        if v is None:
            return ""
        return v if isinstance(v, str) else json.dumps(v)


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
                       required_ids: list[str] | None = None,
                       tools_called: list[str] | None = None) -> Decision:
    """Code-side post-processing for ablation arms and the evidence guard.

    - allow_escalate=False ("- escalation" ablation): ESCALATE is coerced to INCOMPLETE.
    - require_evidence=True: VERIFIED without evidence for every known required condition is
      downgraded to ESCALATE (plan success line 5). `required_ids` comes from the verifier's own
      reading of the runbook (never from hidden specs); if unknown, only 'some evidence' is required.
    - Fabrication check: an evidence item whose `source` names none of the tools actually called
      (per ToolRuntime, `tools_called`) is not real evidence - a model can name a plausible tool
      and a plausible value without calling anything. Caught live on the first paid run (A2,
      gemini case lck-01-cor: VERIFIED, correct by luck, citing get_hr_employee/get_okta_user/
      get_incident as sources while only lookup_runbook had actually been called). Matching is by
      substring, case-insensitive, not exact equality - a model may cite a compound source like
      "get_google_user & get_hr_employee" (D4-1, off-01-cor: both genuinely called; an exact-match
      version of this check flagged it anyway). Skipped when tools_called is None (verifiers that
      don't report it, e.g. rules/hybrid, whose engine already binds each Evidence to a real call).
    """
    if not allow_escalate and d.decision == "ESCALATE":
        d = d.model_copy(update={"decision": "INCOMPLETE", "reason": d.reason + " [escalate disabled]"})
    if require_evidence and d.decision == "VERIFIED":
        cited = {e.condition_id for e in d.evidence if e.holds is not False}
        missing = [c for c in (required_ids or []) if c not in cited]
        called_lower = [t.lower() for t in (tools_called or [])]
        fabricated = [e.condition_id for e in d.evidence if tools_called is not None and e.source
                     and not any(t in e.source.lower() for t in called_lower)]
        if not d.evidence or missing or fabricated:
            reason = d.reason
            if not d.evidence or missing:
                reason += f" [evidence guard: missing {missing or 'all'}]"
            if fabricated:
                reason += f" [evidence guard: source tool never called for {fabricated}]"
            d = d.model_copy(update={"decision": "ESCALATE", "reason": reason})
    return d
