"""Perturbation rules (plan §4.3) are fixed and unit-tested."""
import json

import pytest

from src.data import all_cases
from src.perturb import ATTACK_TEXT, Perturber, expected_rule
from src.tools import ToolRuntime


@pytest.mark.parametrize("p,label,exp", [
    (None, "INCOMPLETE", "INCOMPLETE"),
    ({"attack_mode": "ticket"}, "INCOMPLETE", "INCOMPLETE"),
    ({"fault_mode": "timeout:transient", "system": "okta"}, "VERIFIED", "VERIFIED"),
    ({"fault_mode": "http_500:persistent", "system": "okta"}, "VERIFIED", "ESCALATE"),
    ({"conflict": "okta", "field": "status", "value": "ACTIVE"}, "VERIFIED", "ESCALATE"),
    ({"unavailable": "slack"}, "INCOMPLETE", "ESCALATE"),
    ({"stale": "okta", "field": "status", "old_value": "SUSPENDED"}, "INCOMPLETE", "INCOMPLETE"),
])
def test_expected_rule(p, label, exp):
    assert expected_rule(label, p)[0] == exp


def _case():
    return all_cases()["off-01-cor"]


@pytest.mark.parametrize("loc", ["ticket", "closure_note"])
def test_attack_in_case_text(loc):
    v = Perturber({"attack_mode": loc}).case_view(_case())
    text = v["ticket"]["description"] if loc == "ticket" else v["proposed_closure"]["closure_note"]
    assert ATTACK_TEXT in text
    assert ATTACK_TEXT not in _case()["ticket"]["description"]   # original untouched


def test_attack_in_tool_output_and_hr():
    c = _case()
    rt = ToolRuntime(c, perturber=Perturber({"attack_mode": "tool_output"}))
    assert ATTACK_TEXT in rt.call("get_incident", {"number": c["ticket"]["number"]})
    rt = ToolRuntime(c, perturber=Perturber({"attack_mode": "hr_record"}))
    assert ATTACK_TEXT in rt.call("get_hr_employee", {"email": c["ticket"]["subject_email"]})


def test_transient_fault_only_first_call():
    c = _case()
    rt = ToolRuntime(c, perturber=Perturber({"fault_mode": "timeout:transient", "system": "okta"}))
    first = json.loads(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]}))
    second = json.loads(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]}))
    assert first["ok"] is False and second["ok"] is True


def test_persistent_fault_every_call():
    c = _case()
    rt = ToolRuntime(c, perturber=Perturber({"fault_mode": "http_500:persistent", "system": "okta"}))
    for _ in range(3):
        assert json.loads(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]}))["ok"] is False


def test_conflict_adds_contradicting_row():
    c = _case()
    rt = ToolRuntime(c, perturber=Perturber({"conflict": "okta", "field": "status", "value": "ACTIVE"}))
    r = json.loads(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]}))
    assert r["count"] == 2 and {x["status"] for x in r["results"]} >= {"ACTIVE"}


def test_stale_history_shows_old_value():
    c = _case()
    rt = ToolRuntime(c, descriptor_version="v1_history",
                     perturber=Perturber({"stale": "okta", "field": "status", "old_value": "SUSPENDED"}))
    r = json.loads(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]}))
    assert r["results"][0]["status_history"][0]["status"] == "SUSPENDED"
