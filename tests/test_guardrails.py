"""Guardrails live in code: step cap, dedup, allowlist, schema repair -> fail-safe, early exit."""
import json

from src.agent_loop import run_loop
from src.config import RunConfig
from src.data import all_cases
from src.guardrails import escalation_signal
from src.llm import LLMResponse
from src.perturb import Perturber
from src.tools import ToolRuntime


class LoopingBackend:
    """Always asks for the same tool: must be stopped by the step cap."""
    def complete(self, messages, tools=None, **k):
        tc = {"id": f"c{len(messages)}", "name": "get_okta_user", "arguments": {"email": "x@acme.example"}}
        return LLMResponse(content=None, tool_calls=[tc], assistant_message={"role": "assistant", "content": "",
                           "tool_calls": [{"id": tc["id"], "type": "function", "function": {
                               "name": tc["name"], "arguments": json.dumps(tc["arguments"])}}]})


class GarbageBackend:
    def complete(self, messages, tools=None, **k):
        return LLMResponse(content="I think it is fine", tool_calls=[], assistant_message={"role": "assistant",
                                                                                           "content": "fine"})


def _rt(**kw):
    return ToolRuntime(all_cases()["lck-01-cor"], **kw)


def test_step_cap_forces_escalate():
    cfg = RunConfig(step_cap=4)
    rt = _rt()
    res = run_loop(LoopingBackend(), rt, cfg, "sys", "user", [], {})
    assert res.decision.decision == "ESCALATE" and res.guard.step_cap_hit and res.turns == 4
    assert rt.stats()["duplicate_tool_calls"] == 3          # dedup served repeats from cache


def test_dedup_off_still_counts_duplicates():
    rt = _rt(dedup=False)
    run_loop(LoopingBackend(), rt, RunConfig(step_cap=3, dedup=False), "s", "u", [], {})
    assert rt.stats()["duplicate_tool_calls"] == 2 and "NOTE: identical call" not in "".join(
        e.name for e in rt.events)


def test_schema_repair_then_fail_safe():
    res = run_loop(GarbageBackend(), _rt(), RunConfig(), "s", "u", [], {})
    assert res.decision.decision == "ESCALATE" and res.schema_validation_failed and res.turns == 2


def test_allowlist_rejects_unknown_tool():
    rt = _rt(tool_subset=["get_okta_user"])
    out = json.loads(rt.call("get_slack_user", {"email": "a@b"}))
    assert out["ok"] is False and rt.events[-1].invalid


def test_early_exit_signal():
    c = all_cases()["lck-01-cor"]
    rt = ToolRuntime(c, perturber=Perturber({"unavailable": "okta"}))
    assert escalation_signal(rt.call("get_okta_user", {"email": c["ticket"]["subject_email"]})) == "system_unavailable"


def test_compact_returns_stay_valid_json_on_oversized_record():
    c = all_cases()["gr-10"]
    obs = _rt().__class__(c).call("get_incident", {"number": c["ticket"]["number"]})
    assert json.loads(obs)["ok"] is True and len(obs) < 4000
