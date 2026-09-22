"""Backends behind every LLM-shaped call.

    ScriptedBackend - deterministic reference policy, $0, no API key. It plays the model's role
                      in the SAME loop the live model uses: it asks for tools, reads the tool
                      messages, and answers with JSON. It uses public inputs and tool results only
                      (rules engine), never labels. A marker can reproduce the harness with it.
    LiveBackend     - OpenRouter via src/llm.py (cache, cost, budget guard).

Interface: complete(messages, tools, purpose, cfg, meta, context) -> LLMResponse
purpose in {"agent", "read_note", "decide_from_records", "compile_checklist", "judge"}
"""
from __future__ import annotations

import json

from .llm import LLMClient, LLMResponse
from .tools import ARG_NAME
from .verifiers import rules


class ScriptedBackend:
    name = "scripted"

    def __init__(self, case: dict | None = None):
        self.case = case
        self._issued: dict[str, tuple[str, str]] = {}   # tool_call_id -> (tool, arg)
        self._queue: list[tuple[str, str]] | None = None
        self._checks = None
        self._retried: set = set()
        self._n = 0

    # -----------------------------------------------------------------------------------
    def complete(self, messages, tools=None, purpose="agent", cfg=None, meta=None, context=None) -> LLMResponse:
        if purpose == "agent":
            return self._agent_step(messages, cfg)
        if purpose == "read_note":  # naive reader: trusts a declared closure note
            note = (self.case or {}).get("proposed_closure", {}).get("closure_note", "")
            return self._final({"decision": "VERIFIED" if note else "ESCALATE",
                                "reason": "closure note claims the runbook steps were completed",
                                "cited_conditions": [], "evidence": [], "confidence": 0.6})
        if purpose == "decide_from_records":
            checks, _ = rules.plan_calls(self.case, context["obs"].get(
                ("get_hr_employee", self.case["ticket"]["subject_email"])))
            return self._final(rules.decide(checks, context["obs"], cfg.early_exit).model_dump())
        if purpose == "compile_checklist":
            checks, _ = rules.plan_calls(self.case, context.get("hr_obs"))
            return self._final({"checks": [c.__dict__ for c in checks]})
        if purpose == "judge":
            return self._final({"names_real_problem": None, "note": "scripted judge: not evaluated"})
        raise ValueError(purpose)

    # ---- agent loop policy ------------------------------------------------------------
    def _agent_step(self, messages, cfg) -> LLMResponse:
        obs = self._observations(messages)
        allowed = {t["function"]["name"] for t in (cfg and _tools_of(cfg)) or []}
        # retry once on a failed observation (transient fault handling)
        for tcid, (tool, arg) in list(self._issued.items()):
            o = obs.get(tcid)
            if o is not None and _failed(o) and (tool, arg) not in self._retried:
                self._retried.add((tool, arg))
                return self._calls([(tool, arg)])
        latest = {}
        for tcid, key in self._issued.items():
            if tcid in obs:
                latest[key] = obs[tcid]
        if self._queue is None:
            base = [c for c in rules.base_calls(self.case) if c[0] in allowed]
            if not all(k in latest for k in base):
                todo = [k for k in base if k not in latest and k not in self._issued.values()]
                if todo:
                    return self._calls(todo if cfg.parallel_tools else todo[:1])
                return self._calls([k for k in base if k not in latest][:1])
            hr = latest.get(("get_hr_employee", self.case["ticket"]["subject_email"]))
            self._checks, calls = rules.plan_calls(self.case, hr)
            self._queue = [c for c in calls if c[0] in allowed]
        if self._queue:
            batch = self._queue if cfg.parallel_tools else self._queue[:1]
            self._queue = self._queue[len(batch):]
            return self._calls(batch)
        d = rules.decide(self._checks, latest, early_exit=cfg.early_exit)
        return self._final(d.model_dump())

    def _calls(self, keys) -> LLMResponse:
        calls, raw = [], []
        for tool, arg in keys:
            self._n += 1
            tcid = f"call_{self._n}"
            self._issued[tcid] = (tool, arg)
            args = {ARG_NAME[tool]: arg}
            calls.append({"id": tcid, "name": tool, "arguments": args})
            raw.append({"id": tcid, "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}})
        return LLMResponse(content=None, tool_calls=calls, model="scripted",
                           assistant_message={"role": "assistant", "content": "", "tool_calls": raw})

    @staticmethod
    def _final(obj: dict) -> LLMResponse:
        text = json.dumps(obj, default=str)
        return LLMResponse(content=text, tool_calls=[], model="scripted",
                           assistant_message={"role": "assistant", "content": text})

    @staticmethod
    def _observations(messages) -> dict[str, str]:
        return {m["tool_call_id"]: m["content"] for m in messages if m.get("role") == "tool"}


def _failed(obs: str) -> bool:
    r = rules.parse_obs(obs)
    return not r or r.get("ok") is False


def _tools_of(cfg):
    from .tools import tool_specs
    if cfg.descriptor_version == "v1":
        raise ValueError("scripted backend speaks v2 tool names; use descriptor_version v2 or v1_history")
    return tool_specs(cfg.descriptor_version, cfg.tool_subset, cfg.use_runbook)


class LiveBackend:
    name = "live"

    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()

    def complete(self, messages, tools=None, purpose="agent", cfg=None, meta=None, context=None) -> LLMResponse:
        return self.client.chat(model=cfg.model, messages=messages, tools=tools,
                                reasoning_effort=cfg.reasoning_effort, meta={**(meta or {}), "purpose": purpose},
                                parallel_tool_calls=bool(cfg.parallel_tools))


def make_backend(cfg, case: dict | None = None):
    return ScriptedBackend(case) if cfg.backend == "scripted" else LiveBackend()
