"""D4-9 L2 evidence judge: does `reason` name the real problem? (harness side; may see labels)

Rules: judge model != judged model (JUDGE_MODEL in .env). Hand-label 24 dev cases first
(docs/D4_EVALUATION.md) and report judge-human agreement BEFORE using judge scores.
"""
from __future__ import annotations

import json

from .config import SETTINGS, RunConfig
from .llm import LLMClient
from .schema import parse_decision  # noqa: F401 (kept for symmetry with verifiers)

JUDGE_PROMPT = """You grade an IT verification decision. Ground truth lists the conditions that
actually failed. Answer ONLY JSON: {"names_real_problem": true|false, "note": "<one sentence>"}.
true = the reason identifies at least the main failed condition (by id or clear description)."""


def judge_one(record: dict, failed_ids: list[str], client: LLMClient | None = None) -> dict:
    if record.get("model") == SETTINGS.judge_model:
        raise ValueError("judge model must differ from the judged model")
    client = client or LLMClient()
    user = json.dumps({"decision": record["decision"], "reason": record["reason"],
                       "cited_conditions": record.get("cited_conditions"), "ground_truth_failed": failed_ids})
    r = client.chat(SETTINGS.judge_model, [{"role": "system", "content": JUDGE_PROMPT},
                                          {"role": "user", "content": user}],
                    meta={"experiment_id": "D4-9", "arm": "judge", "run_id": record["run_id"], "purpose": "judge"})
    try:
        return json.loads((r.content or "").replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        return {"names_real_problem": None, "note": "unparseable judge output"}


def agreement(judge: list[bool | None], human: list[bool]) -> dict:
    pairs = [(j, h) for j, h in zip(judge, human) if j is not None]
    agree = sum(j == h for j, h in pairs)
    return {"n": len(pairs), "agreement": agree / len(pairs) if pairs else None}


_ = RunConfig  # judge runs are logged under experiment D4-9 via the ledger
