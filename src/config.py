"""Settings: .env (secrets, defaults) + manifest YAML (per-experiment overrides) -> one object.

Every experiment is a configuration of `run_eval(...)`. `RunConfig` holds exactly the knobs
listed in docs/PROJECT_PLAN.md §6.1; its hash identifies "the same arm" for cache reuse.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

try:  # optional: python-dotenv
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: Any, cast=str):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    if cast is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return cast(raw)


@dataclass(frozen=True)
class Settings:
    """Process-wide settings from .env. Never printed with the key."""

    api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY", ""), repr=False)
    base_url: str = field(default_factory=lambda: _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    http_referer: str = field(default_factory=lambda: _env("OPENROUTER_HTTP_REFERER", ""))
    app_title: str = field(default_factory=lambda: _env("OPENROUTER_APP_TITLE", "OpsPilot-PE6201"))
    backend: str = field(default_factory=lambda: _env("BACKEND", "scripted"))
    model: str = field(default_factory=lambda: _env("OPSPILOT_MODEL", "openai/gpt-5-mini"))
    fallback_model: str = field(default_factory=lambda: _env("FALLBACK_MODEL", "openai/gpt-4o-mini"))
    dev_free_model: str = field(default_factory=lambda: _env("DEV_FREE_MODEL", ""))
    judge_model: str = field(default_factory=lambda: _env("JUDGE_MODEL", "google/gemini-2.5-flash-lite"))
    reasoning_effort: str = field(default_factory=lambda: _env("REASONING_EFFORT", "low"))
    temperature: float = field(default_factory=lambda: _env("TEMPERATURE", 0.0, float))
    max_output_tokens: int = field(default_factory=lambda: _env("MAX_OUTPUT_TOKENS", 800, int))
    request_timeout_s: int = field(default_factory=lambda: _env("REQUEST_TIMEOUT_S", 60, int))
    max_retries: int = field(default_factory=lambda: _env("MAX_RETRIES", 3, int))
    price_input_per_m: float = field(default_factory=lambda: _env("PRICE_INPUT_PER_M", 0.25, float))
    price_output_per_m: float = field(default_factory=lambda: _env("PRICE_OUTPUT_PER_M", 2.00, float))
    price_cached_input_per_m: float = field(default_factory=lambda: _env("PRICE_CACHED_INPUT_PER_M", 0.025, float))
    max_budget_usd: float = field(default_factory=lambda: _env("MAX_BUDGET_USD", 3.50, float))
    reserved_for_d8_usd: float = field(default_factory=lambda: _env("RESERVED_FOR_D8_USD", 0.62, float))
    default_experiment_cap_usd: float = field(default_factory=lambda: _env("DEFAULT_EXPERIMENT_CAP_USD", 0.30, float))
    max_cost_per_case_usd: float = field(default_factory=lambda: _env("MAX_COST_PER_CASE_USD", 0.03, float))
    require_confirm_above_cap: bool = field(default_factory=lambda: _env("REQUIRE_CONFIRM_ABOVE_CAP", True, bool))
    max_tool_output_chars: int = field(default_factory=lambda: _env("MAX_TOOL_OUTPUT_CHARS", 4000, int))
    data_dir: Path = field(default_factory=lambda: ROOT / _env("DATA_DIR", "data/opspilot_itsm_data"))
    subsets_dir: Path = field(default_factory=lambda: ROOT / _env("SUBSETS_DIR", "data/subsets"))
    results_dir: Path = field(default_factory=lambda: ROOT / _env("RESULTS_DIR", "results"))
    cache_dir: Path = field(default_factory=lambda: ROOT / _env("CACHE_DIR", ".cache/llm"))
    seed: int = field(default_factory=lambda: _env("RANDOM_SEED", 42, int))
    dataset_version: str = field(default_factory=lambda: _env("DATASET_VERSION", "synthetic-v1"))
    save_traces: bool = field(default_factory=lambda: _env("SAVE_TRACES", True, bool))


SETTINGS = Settings()

VERIFIERS = ("always_verified", "always_escalate", "rules", "read_note", "workflow", "agent", "hybrid")
BACKENDS = ("scripted", "live")


@dataclass
class RunConfig:
    """One arm of one experiment (docs/PROJECT_PLAN.md §6.1)."""

    subset: str = "smoke"
    verifier: str = "agent"
    backend: str = field(default_factory=lambda: SETTINGS.backend if SETTINGS.backend in BACKENDS else "scripted")
    model: str = field(default_factory=lambda: SETTINGS.model)
    reasoning_effort: str = field(default_factory=lambda: SETTINGS.reasoning_effort)
    prompt_version: str = "v1"                 # v1 | v2
    descriptor_version: str = "v2"             # v1 | v2 | v1_history
    compact_returns: bool = True
    tool_subset: Any = "all"                   # "all" or list of tool names
    parallel_tools: bool = False
    early_exit: bool = False
    show_closure_note: bool = True
    use_runbook: bool = True
    allow_escalate: bool = True
    require_evidence: bool = True
    dedup: bool = True
    step_cap: int = 8
    budget_cap_usd: float = 0.03
    perturbation: dict | None = None
    trials: int = 1
    experiment_id: str = "adhoc"
    arm: str = "default"

    # ---- identity -----------------------------------------------------------------
    # Fields that do NOT change model behaviour are excluded from the hash, so the same arm
    # used by two experiments is run once and reused (plan §9 "reuse by config hash").
    _NON_BEHAVIOURAL = ("subset", "trials", "experiment_id", "arm")

    def behaviour_dict(self) -> dict:
        d = asdict(self)
        for k in self._NON_BEHAVIOURAL:
            d.pop(k, None)
        if d["backend"] == "scripted" or d["verifier"] in ("always_verified", "always_escalate", "rules"):
            d.pop("model", None)
            d.pop("reasoning_effort", None)
        return d

    @property
    def config_hash(self) -> str:
        blob = json.dumps(self.behaviour_dict(), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def validate(self) -> "RunConfig":
        assert self.verifier in VERIFIERS, f"unknown verifier {self.verifier}"
        assert self.backend in BACKENDS, f"unknown backend {self.backend}"
        assert self.prompt_version in ("v1", "v2", "v2b"), self.prompt_version
        assert self.descriptor_version in ("v1", "v2", "v1_history"), self.descriptor_version
        assert 1 <= self.step_cap <= 30
        assert self.trials >= 1
        return self

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**d).validate()
