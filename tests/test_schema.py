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
