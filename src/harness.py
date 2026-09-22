"""One harness (plan §6.1): every experiment is a configuration of run_eval(...).

For each case x trial:
    perturb the public case -> ToolRuntime (only path to state) -> verifier -> policy flags
    -> run record (+ trace) -> score (labels joined in scoring.py) -> console line
Then one summary per arm, paired with the resolver-alone baseline on the same cases.
"""
from __future__ import annotations

import hashlib
import json
import time

from . import budget, scoring
from .backends import make_backend
from .config import SETTINGS, RunConfig
from .data import declared, is_heldout, load_subset
from .decision_log import append_master, compact_view, find_reusable, git_commit, write_compact, write_run, write_summary
from .perturb import Perturber, describe, difficulty
from .schema import NOT_DECLARED, apply_policy_flags, fail_safe
from .tools import ToolRuntime
from .verifiers import get_verifier
from .verifiers.rules import required_ids

PLANNING_USD_PER_CASE = 0.006  # replaced by the A2 cost probe (docs/cost_assumptions.md)
COST_FACTOR = {"agent": 1.0, "read_note": 0.3, "workflow": 0.4, "hybrid": 0.3}
NO_POLICY_FLAGS = {"always_verified", "always_escalate"}


def _state_hash(runtime: ToolRuntime) -> str:
    return hashlib.sha256(json.dumps(runtime._env._state, sort_keys=True).encode()).hexdigest()[:12]


def projected_usd_per_case(cfg: RunConfig) -> float:
    if cfg.backend == "scripted" or cfg.verifier not in COST_FACTOR:
        return 0.0
    return PLANNING_USD_PER_CASE * COST_FACTOR[cfg.verifier]


def run_case(case: dict, cfg: RunConfig, trial: int = 1) -> tuple[dict, list[dict]]:
    run_id = f"{cfg.experiment_id}__{cfg.arm}__{case['case_id']}__t{trial}"
    base = {"experiment_id": cfg.experiment_id, "arm": cfg.arm, "run_id": run_id, "trial": trial,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "git_commit": git_commit(),
            "config_hash": cfg.config_hash, "dataset_version": SETTINGS.dataset_version,
            "case_id": case["case_id"], "task_id": case["task_id"], "family": case["family"],
            **{k: v for k, v in cfg.__dict__.items() if k not in ("trials", "experiment_id", "arm")},
            "perturbation": cfg.perturbation, "difficulty": difficulty(cfg.perturbation, case["family"]),
            "declared": declared(case)}
    reused = find_reusable(cfg.config_hash, case["case_id"], trial)
    if reused and reused["run_id"] == run_id:      # same arm re-run: keep the logged record
        return reused, None
    if reused:                                      # same behaviour logged by another experiment
        # cost is kept (it is a property of the config); the ledger shows no new spend
        rec = {**reused, **base, "reused_from": reused["run_id"]}
        return rec, [{"event": "reused", "from": reused["run_id"]}]

    if not declared(case):  # nothing to verify: attempted, never released
        rec = {**base, "decision": NOT_DECLARED, "reason": "resolver did not declare completion",
               "cited_conditions": [], "evidence": [], "confidence": None, "turns": 0, "tool_call_count": 0,
               "llm_cost_usd": 0.0, "total_cost_usd": 0.0, "latency_ms": 0.0}
        return rec, [{"event": "final", "decision": NOT_DECLARED}]

    perturber = Perturber(cfg.perturbation)
    view = perturber.case_view(case)
    runtime = ToolRuntime(view, cfg.descriptor_version, cfg.compact_returns, cfg.tool_subset,
                          cfg.use_runbook, cfg.dedup, perturber)
    h_before = _state_hash(runtime)
    backend = make_backend(cfg, view)
    meta = {"experiment_id": cfg.experiment_id, "arm": cfg.arm, "run_id": run_id}
    t0 = time.perf_counter()
    error_type = None
    try:
        res = get_verifier(cfg.verifier)(view, runtime, cfg, backend, meta)
    except budget.BudgetExceeded:
        raise
    except Exception as e:  # noqa: BLE001 - a crash is logged as a fail-safe ESCALATE, never hidden
        from .agent_loop import LoopResult
        res, error_type = LoopResult(decision=fail_safe(f"{type(e).__name__}: {e}")), type(e).__name__
    latency_ms = (time.perf_counter() - t0) * 1000
    d = res.decision
    if cfg.verifier not in NO_POLICY_FLAGS:
        d = apply_policy_flags(d, cfg.allow_escalate, cfg.require_evidence, required_ids(case["runbook_id"]))
    g = res.guard
    rec = {**base, "decision": d.decision, "reason": d.reason, "cited_conditions": d.cited_conditions,
           "evidence": [e.model_dump() for e in d.evidence], "confidence": d.confidence,
           **runtime.stats(), "turns": res.turns,
           "step_cap_hit": bool(g and g.step_cap_hit), "budget_cap_hit": bool(g and g.budget_cap_hit),
           "early_exit_triggered": bool(g and g.early_exit_triggered),
           "schema_validation_failed": res.schema_validation_failed,
           **res.usage, "total_tokens": res.usage["input_tokens"] + res.usage["output_tokens"],
           "llm_cost_usd": round(res.llm_cost_usd, 8), "total_cost_usd": round(res.llm_cost_usd, 8),
           "latency_ms": round(latency_ms, 1), "llm_latency_ms": round(res.llm_latency_ms, 1),
           "retry_attempted": res.retry_attempted, "retry_success": res.retry_success,
           "state_hash_before": h_before, "state_hash_after": _state_hash(runtime),
           "error_type": error_type}
    assert rec["state_hash_before"] == rec["state_hash_after"], "verifier changed state (must be read-only)"
    return rec, res.trace


def _line(r: dict) -> str:
    mark = "·" if r["declared"] is False else ("✓" if r["correct"] else "✗")
    cap = " [cap]" if r.get("step_cap_hit") else ""
    return (f"  {r['case_id']:<16} exp={str(r['expected_decision'])[:4]:<4} got={str(r['decision'])[:4]:<4} {mark} "
            f"turns={r.get('turns') or 0:<2} tools={r.get('tool_call_count') or 0:<2} "
            f"dup={r.get('duplicate_tool_calls') or 0} ${float(r.get('total_cost_usd') or 0):.4f} "
            f"{float(r.get('latency_ms') or 0) / 1000:.1f}s{cap}{' (reused)' if r.get('reused_from') else ''}")


def run_eval(cfg: RunConfig | None = None, *, allow_heldout: bool = False, confirm=input,
             quiet: bool = False, manifest_cap_usd: float | None = None, assume_yes: bool = False,
             compact: bool = False, **overrides) -> dict:
    cfg = (cfg or RunConfig.from_dict(overrides)).validate()
    if is_heldout(cfg.subset) and not allow_heldout:
        raise PermissionError(f"'{cfg.subset}' is held-out: run it only via the frozen D8 manifest")
    cases = load_subset(cfg.subset)
    n = len(cases) * cfg.trials
    proj = budget.project(n, projected_usd_per_case(cfg), manifest_cap_usd or SETTINGS.default_experiment_cap_usd)
    say = (lambda *a: None) if quiet else print
    say(f"\n[{cfg.experiment_id} / {cfg.arm}] verifier={cfg.verifier} backend={cfg.backend} "
        f"subset={cfg.subset} n={n} hash={cfg.config_hash} projected=${proj['projected_usd']:.3f} "
        f"remaining=${proj['remaining_usd']:.3f}")
    if proj["over_global"]:
        raise budget.BudgetExceeded(f"projection ${proj['projected_usd']} exceeds remaining ${proj['remaining_usd']}")
    if proj["over_cap"] and SETTINGS.require_confirm_above_cap and not assume_yes:
        ans = confirm(f"Projected ${proj['projected_usd']:.3f} > manifest cap ${proj['cap_usd']:.3f}. Continue? [y/N] ")
        if ans.strip().lower() != "y":
            raise SystemExit("aborted: projection above manifest cap (CLAUDE.md rule 8)")

    rows = []
    for case in cases:
        for trial in range(1, cfg.trials + 1):
            rec, trace = run_case(case, cfg, trial)
            if trace is not None:
                write_run(rec, trace)
            scored = scoring.score_record(rec)
            rows.append(scored)
            write_compact(scored)  # every run, always (CLAUDE.md rule 6: logged, never hand-typed)
            say(json.dumps(compact_view(scored), indent=1) if compact else _line(scored))
    append_master(rows)
    base = scoring.baseline_rows(rows)
    summary = {"experiment_id": cfg.experiment_id, "arm": cfg.arm, "config_hash": cfg.config_hash,
               "config": cfg.__dict__, "perturbation": describe(cfg.perturbation),
               "metrics": scoring.summarize(rows), "baseline": scoring.summarize(base),
               "paired_test": scoring.paired_fcr_test(base, rows), "confusion": scoring.confusion(rows),
               "per_family": scoring.per_family(rows), "spent_total_usd": budget.total_spent()}
    write_summary(f"{cfg.experiment_id}__{cfg.arm}", summary)
    if not quiet:
        print_summary(summary)
    return summary


def _p(x):
    return "    n/a" if x is None else f"{100 * x:6.1f}%"


def print_summary(s: dict) -> None:
    m, b = s["metrics"], s["baseline"]
    print(f"  {'arm':<22}{'FCR':>7}{'FBR':>7}{'Esc':>7}{'Acc':>7}{'$/case':>9}{'p95 s':>7}")
    print(f"  {'resolver alone':<22}{_p(b['FCR'])}{'  -  ':>7}{'  -  ':>7}{'  -  ':>7}{0:>9.4f}{'-':>7}")
    p95 = (m["latency_p95_ms"] or 0) / 1000
    print(f"  {s['arm'][:22]:<22}{_p(m['FCR'])}{_p(m['FBR'])}{_p(m['escalation_rate'])}{_p(m['accuracy'])}"
          f"{(m['cost_per_case_usd'] or 0):>9.4f}{p95:>7.1f}")
    print(f"  McNemar p={s['paired_test']['mcnemar_p']:.4f}  spent total ${s['spent_total_usd']:.4f} "
          f"/ cap ${SETTINGS.max_budget_usd:.2f}")
