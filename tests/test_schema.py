from src.schema import Decision, Evidence, apply_policy_flags, parse_decision


def test_parse_json_in_fences():
    d, err = parse_decision('```json\n{"decision": "incomplete", "cited_conditions": ["LH-R4"]}\n```')
    assert err is None and d.decision == "INCOMPLETE"


def test_parse_rejects_bad_label():
    d, err = parse_decision('{"decision": "DONE"}')
    assert d is None and err


def test_evidence_guard_downgrades_verified_without_full_evidence():
    d = Decision(decision="VERIFIED", evidence=[Evidence(condition_id="X-R1", holds=True)])
    out = apply_policy_flags(d, allow_escalate=True, require_evidence=True, required_ids=["X-R1", "X-R2"])
    assert out.decision == "ESCALATE"
    full = apply_policy_flags(d, True, True, ["X-R1"])
    assert full.decision == "VERIFIED"


def test_no_escalate_ablation():
    d = apply_policy_flags(Decision(decision="ESCALATE"), allow_escalate=False, require_evidence=False)
    assert d.decision == "INCOMPLETE"


def test_evidence_observed_coerces_non_string():
    """Caught live on A2's first paid run: gemini emitted observed: true (a native JSON bool)
    for a boolean field instead of a string. That used to raise a pydantic ValidationError and
    fail-safe the whole decision to ESCALATE - a parsing bug, not a real model judgment."""
    d, err = parse_decision({"decision": "VERIFIED", "evidence": [
        {"condition_id": "X-R1", "observed": True, "source": "get_okta_user", "holds": True},
        {"condition_id": "X-R2", "observed": 3, "source": "get_okta_user", "holds": True},
    ]})
    assert err is None
    assert d.evidence[0].observed == "true" and d.evidence[1].observed == "3"


def test_evidence_source_none_coerces_to_empty_string():
    """Caught live on D4-3 (v2b, 9 of 24 cases): the blind-spot note tells the model to report
    GEN-F1-style conditions as holds: null with no tool called - it then naturally sent
    source: null, which used to crash validation on every case that mentioned it."""
    d, err = parse_decision({"decision": "ESCALATE", "evidence": [
        {"condition_id": "GEN-F1", "observed": "not checked", "source": None, "holds": None}]})
    assert err is None and d.evidence[0].source == ""


def test_evidence_guard_catches_fabricated_source():
    """Caught live on A2's first paid run: a model cited get_okta_user as the source for a
    condition without ever calling it. All required ids are 'covered' on paper; only checking
    the source against real tool calls catches it."""
    d = Decision(decision="VERIFIED", evidence=[Evidence(condition_id="X-R1", source="get_okta_user", holds=True)])
    out = apply_policy_flags(d, True, True, ["X-R1"], tools_called=["lookup_runbook"])
    assert out.decision == "ESCALATE" and "never called" in out.reason
    real = apply_policy_flags(d, True, True, ["X-R1"], tools_called=["lookup_runbook", "get_okta_user"])
    assert real.decision == "VERIFIED"


def test_evidence_guard_allows_compound_source():
    """Caught live on D4-1 (off-01-cor, lst-01-cor): a model cited a compound source like
    'get_google_user & get_hr_employee' when it genuinely called both. An exact-match version of
    the fabrication check flagged this as fabricated; substring matching does not."""
    d = Decision(decision="VERIFIED", evidence=[
        Evidence(condition_id="X-R1", source="get_google_user & get_hr_employee", holds=True)])
    out = apply_policy_flags(d, True, True, ["X-R1"],
                             tools_called=["lookup_runbook", "get_google_user", "get_hr_employee"])
    assert out.decision == "VERIFIED"
