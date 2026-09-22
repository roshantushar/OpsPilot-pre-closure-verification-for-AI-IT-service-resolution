"""OpenRouter (OpenAI-compatible) client: disk cache, retries, usage + real cost, budget guard.

Every call goes through `LLMClient.chat`. Identical requests are served from `.cache/llm/`
at $0 (plan §9: "cache every call"). Real cost comes from OpenRouter's `usage.cost` when
available; otherwise it is computed from the prices in .env and marked `cost_source=estimated`.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

from . import budget
from .config import SETTINGS

NO_TEMPERATURE_PREFIXES = ("openai/gpt-5", "openai/o1", "openai/o3", "openai/o4")


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict]                    # [{"id", "name", "arguments": dict}]
    assistant_message: dict                   # to append to the transcript as-is
    usage: dict = field(default_factory=dict)  # input/output/reasoning/cached tokens
    cost_usd: float = 0.0
    cost_source: str = "none"
    latency_ms: float = 0.0
    cache_hit: bool = False
    model: str = ""


def _cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _estimate_cost(u: dict) -> float:
    fresh_in = max(0, u.get("input_tokens", 0) - u.get("cached_tokens", 0))
    return (fresh_in * SETTINGS.price_input_per_m + u.get("cached_tokens", 0) * SETTINGS.price_cached_input_per_m
            + u.get("output_tokens", 0) * SETTINGS.price_output_per_m) / 1e6


class LLMClient:
    def __init__(self, client=None, cache_dir=None, use_cache: bool = True):
        self._client = client  # inject a fake in tests
        self.cache_dir = cache_dir or SETTINGS.cache_dir
        self.use_cache = use_cache

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: scripted runs never need the SDK or a key
            if not SETTINGS.api_key or SETTINGS.api_key.startswith("sk-or-REPLACE"):
                raise RuntimeError("OPENROUTER_API_KEY not set - use BACKEND=scripted or fill .env")
            headers = {k: v for k, v in {"HTTP-Referer": SETTINGS.http_referer,
                                         "X-Title": SETTINGS.app_title}.items() if v}
            self._client = OpenAI(api_key=SETTINGS.api_key, base_url=SETTINGS.base_url,
                                  timeout=SETTINGS.request_timeout_s, default_headers=headers)
        return self._client

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None,
             reasoning_effort: str | None = None, max_tokens: int | None = None,
             meta: dict | None = None, parallel_tool_calls: bool = False) -> LLMResponse:
        meta = meta or {}
        payload = {"model": model, "messages": messages, "tools": tools or None,
                   "max_tokens": max_tokens or SETTINGS.max_output_tokens,
                   "reasoning_effort": reasoning_effort, "parallel_tool_calls": parallel_tool_calls,
                   "temperature": None if model.startswith(NO_TEMPERATURE_PREFIXES) else SETTINGS.temperature}
        key = _cache_key(payload)
        path = self.cache_dir / f"{key}.json"
        if self.use_cache and path.exists():
            resp = LLMResponse(**json.loads(path.read_text()))
            resp.cache_hit, resp.cost_usd, resp.latency_ms = True, 0.0, 0.0
            budget.record({**self._ledger_meta(meta, model), **resp.usage, "cost_usd": 0.0,
                           "cost_source": "cache", "cache_hit": 1})
            return resp

        budget.guard(next_call_estimate_usd=0.0, experiment_id=meta.get("experiment_id"))
        resp = self._call_with_retries(payload)
        budget.record({**self._ledger_meta(meta, model), **resp.usage, "cost_usd": resp.cost_usd,
                       "cost_source": resp.cost_source, "cache_hit": 0})
        if self.use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(resp.__dict__, default=str))
        return resp

    # -----------------------------------------------------------------------------------
    def _call_with_retries(self, payload: dict) -> LLMResponse:
        kwargs = {"model": payload["model"], "messages": payload["messages"],
                  "max_tokens": payload["max_tokens"], "extra_body": {"usage": {"include": True}}}
        if payload["tools"]:
            kwargs["tools"] = payload["tools"]
            kwargs["parallel_tool_calls"] = payload["parallel_tool_calls"]
        if payload["temperature"] is not None:
            kwargs["temperature"] = payload["temperature"]
        if payload["reasoning_effort"]:
            kwargs["extra_body"]["reasoning"] = {"effort": payload["reasoning_effort"]}
        last = None
        for attempt in range(SETTINGS.max_retries):
            try:
                t0 = time.perf_counter()
                r = self.client.chat.completions.create(**kwargs)
                return self._parse(r, payload["model"], (time.perf_counter() - t0) * 1000)
            except Exception as e:  # noqa: BLE001 - provider errors vary; retry then re-raise
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM call failed after {SETTINGS.max_retries} attempts: {last}")

    @staticmethod
    def _parse(r, model: str, latency_ms: float) -> LLMResponse:
        msg = r.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__unparseable__": tc.function.arguments}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        u = r.usage
        details_in = getattr(u, "prompt_tokens_details", None)
        details_out = getattr(u, "completion_tokens_details", None)
        usage = {"input_tokens": getattr(u, "prompt_tokens", 0) or 0,
                 "output_tokens": getattr(u, "completion_tokens", 0) or 0,
                 "reasoning_tokens": (getattr(details_out, "reasoning_tokens", 0) or 0) if details_out else 0,
                 "cached_tokens": (getattr(details_in, "cached_tokens", 0) or 0) if details_in else 0}
        reported = getattr(u, "cost", None)
        cost, src = (float(reported), "reported") if reported is not None else (_estimate_cost(usage), "estimated")
        assistant = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant["tool_calls"] = [{"id": tc.id, "type": "function", "function": {
                "name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        return LLMResponse(content=msg.content, tool_calls=calls, assistant_message=assistant, usage=usage,
                           cost_usd=cost, cost_source=src, latency_ms=latency_ms, model=model)

    @staticmethod
    def _ledger_meta(meta: dict, model: str) -> dict:
        return {"experiment_id": meta.get("experiment_id", ""), "arm": meta.get("arm", ""),
                "run_id": meta.get("run_id", ""), "purpose": meta.get("purpose", "verify"), "model": model}
