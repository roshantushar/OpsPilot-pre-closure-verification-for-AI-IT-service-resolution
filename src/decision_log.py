"""Log facts once (plan §6.4): run JSON, trace JSONL, master CSV, per-experiment summary.

Reported numbers are regenerated from these files; never hand-typed (CLAUDE.md rule 6).
Scoring columns are added by src/scoring.py and live only in the master CSV / summaries.
"""
from __future__ import annotations

import csv
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from .config import ROOT, SETTINGS

RUN_FIELDS = [
    "experiment_id", "arm", "run_id", "trial", "timestamp", "git_commit", "config_hash", "dataset_version",
    "subset", "case_id", "task_id", "family", "verifier", "backend", "model", "reasoning_effort",
    "prompt_version", "descriptor_version", "compact_returns", "tool_subset", "parallel_tools", "early_exit",
    "show_closure_note", "use_runbook", "allow_escalate", "require_evidence", "dedup", "step_cap",
    "budget_cap_usd", "perturbation", "difficulty", "declared",
    "decision", "reason", "cited_conditions", "evidence", "confidence",
    "tools_called", "tool_call_count", "duplicate_tool_calls", "invalid_tool_calls", "observation_chars", "turns",
    "step_cap_hit", "budget_cap_hit", "early_exit_triggered", "schema_validation_failed",
    "input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens", "total_tokens",
    "llm_cost_usd", "total_cost_usd", "latency_ms", "llm_latency_ms", "tool_latency_ms",
    "retry_attempted", "retry_success", "state_hash_before", "state_hash_after", "error_type", "reused_from",
]
SCORE_FIELDS = ["expected_decision", "expected_rule", "verifier_pass", "variant", "correct", "released",
                "false_completion", "false_block", "fbr_exempt", "negative", "missing_state_detected",
                "evidence_correct", "evidence_judged", "attack_case", "attack_success", "severity_weight"]
MASTER_FIELDS = RUN_FIELDS + SCORE_FIELDS


@lru_cache(maxsize=1)
def git_commit() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                      stderr=subprocess.DEVNULL).decode().strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], cwd=ROOT, stderr=subprocess.DEVNULL) != 0
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def _dir(*parts) -> Path:
    p = SETTINGS.results_dir.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_run(record: dict, trace: list[dict]) -> None:
    (_dir("raw", "runs") / f"{record['run_id']}.json").write_text(json.dumps(record, indent=1, default=str))
    if SETTINGS.save_traces:
        with (_dir("traces") / f"{record['run_id']}.jsonl").open("w") as f:
            for ev in trace:
                f.write(json.dumps(ev, default=str) + "\n")


def append_master(rows: list[dict]) -> None:
    p = SETTINGS.results_dir / "master_runs.csv"
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MASTER_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, default=str) if isinstance(v, (list, dict)) else v)
                        for k, v in r.items()})


def find_reusable(config_hash: str, case_id: str, trial: int) -> dict | None:
    """A previous run of the same behaviour on the same case/trial (plan §9: reuse by hash)."""
    d = SETTINGS.results_dir / "raw" / "runs"
    if not d.exists():
        return None
    for p in d.glob(f"*__{case_id}__t{trial}.json"):
        rec = json.loads(p.read_text())
        if rec.get("config_hash") == config_hash and not rec.get("reused_from") and not rec.get("error_type"):
            return rec
    return None


def write_summary(experiment_id: str, summary: dict) -> Path:
    p = _dir("summaries") / f"{experiment_id}.json"
    p.write_text(json.dumps(summary, indent=1, default=str))
    return p


def _guard_note(rec: dict) -> str:
    """Which code-layer guard, if any, decided this run (no write tools to gate - rule 5)."""
    if rec.get("step_cap_hit"):
        return f"step_cap hit at turn {rec.get('turns')}"
    if rec.get("budget_cap_hit"):
        return "budget_cap hit"
    if rec.get("schema_validation_failed"):
        return "schema validation failed twice - fail-safe ESCALATE"
    if rec.get("early_exit_triggered"):
        return "early exit: precondition/forbidden signal seen, stopped early"
    return "none"


def compact_view(scored: dict) -> dict:
    """One human-readable object per run, derived from the already-scored record - never a
    second source of truth (CLAUDE.md rule 6). Written for EVERY run to results/compact/.

    Takes the SCORED record (scoring.score_record output), not the raw one, so it can carry
    the ground-truth comparison - that join already happened in scoring.py before this is
    called; compact_view only reads it, it does not perform it.
    """
    out = {
        "ts": scored.get("timestamp"), "case_id": scored.get("case_id"), "declared": scored.get("declared"),
        "decision": scored.get("decision"), "confidence": scored.get("confidence"),
        "reason": scored.get("reason"), "cited_conditions": scored.get("cited_conditions"),
        "evidence": scored.get("evidence"),          # structured: condition_id/observed/source/holds
        "tools_called": scored.get("tools_called"),  # call order, separate from the evidence above
        "guard": _guard_note(scored), "turns": scored.get("turns"),
        "tokens_in": scored.get("input_tokens"), "tokens_out": scored.get("output_tokens"),
        "cost_usd": scored.get("total_cost_usd"),
    }
    if "expected_decision" in scored:  # absent only if this dict was never scored
        out["expected_decision"] = scored["expected_decision"]
        out["correct"] = scored["correct"]
    if scored.get("attack_case"):
        out["attack_success"] = scored.get("attack_success")
    return out


def write_compact(scored: dict) -> Path:
    p = _dir("compact") / f"{scored['run_id']}.json"
    p.write_text(json.dumps(compact_view(scored), indent=1, default=str))
    return p
