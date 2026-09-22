"""CLI: every experiment is a manifest (plan §6.1).

    python -m src.run_eval --manifest experiments/d4_evaluation/d4_1_core.yaml
    python -m src.run_eval --manifest experiments/d4_evaluation/d4_1_core.yaml --arm opspilot_v1 --yes
    python -m src.run_eval --subset smoke --verifier rules                    # ad-hoc (experiment_id=adhoc)
    python -m src.run_eval --manifest ... --backend scripted                  # force $0 run of any manifest
    python -m src.run_eval --subset smoke --prompt                           # exactly what the model is sent
    python -m src.run_eval --manifest ... --arm opspilot_v1 --prompt         # same, for one manifest arm

Manifest keys: experiment_id, question, hypothesis, subset, trials, manifest_cap_usd, decision_rule,
next_step, frozen, defaults{RunConfig fields}, arms[{arm, overrides{...}}]. Commit it BEFORE the run.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from .config import ROOT, RunConfig
from .data import load_subset
from .harness import run_eval
from .prompt import case_message, system_prompt

ANALYSIS_ONLY_ARMS = {"from_logs", "from_d4_logs", "judge_on_best", "eda"}
REQUIRED_KEYS = {"experiment_id", "question", "hypothesis", "subset", "arms", "decision_rule"}


def load_manifest(path: str | Path) -> dict:
    m = yaml.safe_load(Path(path).read_text())
    missing = REQUIRED_KEYS - set(m)
    if missing:
        raise ValueError(f"{path}: manifest missing {sorted(missing)}")
    return m


def arm_configs(m: dict, backend: str | None = None) -> list[tuple[RunConfig, dict]]:
    out = []
    for a in m["arms"]:
        d = {**(m.get("defaults") or {}), **(a.get("overrides") or {})}
        d.update(subset=a.get("subset", m["subset"]), trials=a.get("trials", m.get("trials", 1)),
                 experiment_id=m["experiment_id"], arm=a["arm"])
        if backend:
            d["backend"] = backend
        out.append((RunConfig.from_dict(d), a))
    return out


def show_prompt(cfg: RunConfig) -> None:
    """Print exactly what the model is sent for one case (no run, no cost)."""
    case = load_subset(cfg.subset)[0]
    sys_p, user_p = system_prompt(cfg), case_message(case, cfg)
    for label, text in (("SYSTEM", sys_p), ("USER", user_p)):
        print("=" * 70)
        print(f"{label} ({len(text)} chars - a rough proxy for tokens, not a measured count)")
        print("=" * 70)
        print(text, "\n")


def check_frozen(m: dict) -> None:
    """D8 gate: clean tree + filled success criteria, else refuse (plan: Freeze)."""
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    if dirty.returncode != 0 or dirty.stdout.strip():
        sys.exit("refusing frozen manifest: git tree is dirty or not a git repo")
    crit = (ROOT / "docs" / "success_criteria.md").read_text()
    if "___" in crit or "TBD" in crit:
        sys.exit("refusing frozen manifest: docs/success_criteria.md still has blanks")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--arm", help="run only this arm")
    ap.add_argument("--backend", choices=["scripted", "live"], help="override backend for every arm")
    ap.add_argument("--yes", action="store_true", help="do not ask when projection exceeds the cap")
    ap.add_argument("--subset")
    ap.add_argument("--verifier")
    ap.add_argument("--prompt", action="store_true",
                    help="print the exact system/user prompt for one case and exit; no run, no cost")
    ap.add_argument("--compact", action="store_true",
                    help="print one readable JSON object per case (ts/decision/reason/evidence/guard/cost) "
                        "instead of the terse status line")
    args = ap.parse_args(argv)

    if not args.manifest:
        cfg = RunConfig.from_dict({k: v for k, v in {"subset": args.subset or "smoke",
                                                     "verifier": args.verifier or "rules",
                                                     "backend": args.backend}.items() if v})
        if args.prompt:
            return show_prompt(cfg)
        return run_eval(cfg, assume_yes=args.yes, compact=args.compact)

    m = load_manifest(args.manifest)
    if args.prompt:
        cfgs = [cfg for cfg, a in arm_configs(m, args.backend) if not args.arm or a["arm"] == args.arm]
        if not cfgs:
            sys.exit(f"no arm named {args.arm!r} in {args.manifest}")
        return show_prompt(cfgs[0])
    if m.get("status") == "not_implemented":
        print(f"[{m['experiment_id']}] status: not_implemented - skipping the whole manifest "
              f"(EXPERIMENTS_FOR_CLAUDE_CODE.md F7)")
        return []
    frozen = bool(m.get("frozen"))
    if frozen:
        check_frozen(m)
    results = []
    for cfg, a in arm_configs(m, args.backend):
        if args.arm and a["arm"] != args.arm:
            continue
        if a["arm"] in ANALYSIS_ONLY_ARMS:
            print(f"[{m['experiment_id']} / {a['arm']}] analysis-only (see analysis/); no run")
            continue
        if a.get("reuse_from"):
            print(f"[{m['experiment_id']} / {a['arm']}] reused from {a['reuse_from']} (no run)")
            continue
        if a.get("live_only") and cfg.backend == "scripted":
            print(f"[{m['experiment_id']} / {a['arm']}] live_only: skipped under --backend scripted "
                  f"(EXPERIMENTS_FOR_CLAUDE_CODE.md F8)")
            continue
        results.append(run_eval(cfg, allow_heldout=frozen, manifest_cap_usd=m.get("manifest_cap_usd"),
                                assume_yes=args.yes, compact=args.compact))
    return results


if __name__ == "__main__":
    main()
