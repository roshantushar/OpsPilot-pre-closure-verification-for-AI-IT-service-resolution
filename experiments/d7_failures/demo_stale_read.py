#!/usr/bin/env python3
"""D7-2 WORKED EXAMPLE: the stale read, done once so you can copy the method.

    python -m experiments.d7_failures.demo_stale_read

Same method as demo_loop_failure.py: "the working interface, minus X" - not a
separately written bad reader. Here X is the compact-v2 rule that a tool
returns CURRENT STATE ONLY (src/tools.py:_format, the F2 fix in
EXPERIMENTS_FOR_CLAUDE_CODE.md - v2 strips any `status_history` a `stale`
perturbation injects; only `v1_history` keeps it).

src/verifiers/rules.py's deterministic engine only ever reads a row's CURRENT
top-level field, so it is never fooled by history regardless of descriptor -
that immunity is exactly the property this demo isolates and measures, using a
small NAIVE READER (defined below, not shipped in src/) that stands in for a
careless prompt or a hurried live model: "grab the most detailed-looking data
you can see." It reads `status_history[0]` when one is present, and only
falls back to the current top-level field when it is not - the mistake is
believable because history sorts first-to-last and a reader in a hurry grabs
the first hit.

Fed a v1_history response, that reader is WRONG (the interface handed it a
stale value to find). Fed a v2 compact response, it is RIGHT - not because it
got smarter, but because there is nothing stale left in the record to grab.
That is the poka-yoke argument: the fix removes the error, it does not ask
the reader (model or prompt) to behave better.

Runs on the SCRIPTED backend's ToolRuntime directly: $0, deterministic, no
API key needed. Numbers below are printed from a real (perturbed) tool call
each time, never hand-typed (CLAUDE.md rule 6).
"""
from __future__ import annotations

import json

from src.data import load_subset
from src.perturb import Perturber
from src.tools import ToolRuntime

CASE_ID = "off-02-cor"  # fail_fixtures: standard_offboarding, correctly closed
FIELD = "status"
# Constructed for this demo (like A2's demo_loop_failure.py hand-builds its looping script):
# a plausible pre-offboarding value, older than the case's real current one.
OLD_VALUE = "ACTIVE"
REQUIRED_VALUE = "DEACTIVATED"  # OFF-R1: get_okta_user status eq DEACTIVATED


def naive_read_status(obs: str) -> tuple[str, bool]:
    """Stand-in for a careless reader: prefer status_history[0] if present,
    else the current top-level field. Returns (value read, was_history_used)."""
    row = json.loads(obs)["results"][0]
    if "status_history" in row:
        return row["status_history"][0][FIELD], True
    return row[FIELD], False


def fetch(descriptor_version: str) -> tuple[str, str]:
    case = next(c for c in load_subset("fail_fixtures") if c["case_id"] == CASE_ID)
    perturber = Perturber({"stale": "okta", "field": FIELD, "old_value": OLD_VALUE})
    runtime = ToolRuntime(perturber.case_view(case), descriptor_version=descriptor_version,
                          dedup=False, perturber=perturber)
    email = case["ticket"]["subject_email"]
    return runtime.call("get_okta_user", {"email": email}, turn=0), runtime._env.get_okta_user(email)["results"][0][FIELD]


def main():
    print(f"\nDemonstrating on {CASE_ID} (fail_fixtures), field={FIELD}, "
          f"fabricated old_value={OLD_VALUE!r}, OFF-R1 requires {REQUIRED_VALUE!r}\n")

    for label, descriptor in (("BROKEN (v1_history)", "v1_history"), ("FIXED (v2 compact)", "v2")):
        obs, true_current = fetch(descriptor)
        read, used_history = naive_read_status(obs)
        correct = read == true_current
        print(f"  {label:<20} true current={true_current!r:<14} naive reader saw={read!r:<14} "
              f"(from status_history: {used_history})  ->  reader is {'RIGHT' if correct else 'WRONG'}")
        if descriptor == "v1_history" and not correct:
            required_met = read == REQUIRED_VALUE
            print(f"      OFF-R1 needs {REQUIRED_VALUE!r}: the naive reader would report "
                  f"{'MET' if required_met else 'NOT MET'}, the truth is "
                  f"{'MET' if true_current == REQUIRED_VALUE else 'NOT MET'} - "
                  f"{'a false pass' if required_met and true_current != REQUIRED_VALUE else 'a false block' if true_current == REQUIRED_VALUE else 'coincidentally consistent'}.")
    print()

    print("=" * 70)
    print("1 - THE INSTRUMENTATION THAT FOUND IT")
    print("    src/verifiers/rules.py never calls naive_read_status - it only reads the current")
    print("    top-level field, so this rules-based verifier is immune by construction on BOTH")
    print("    descriptors. The fault is only visible if you instrument what a LESS careful reader")
    print("    (a live model skimming a fat record, or a prompt that says 'check the history') would")
    print("    see - which is what this demo isolates directly, rather than waiting for a live run.")
    print("2 - THE GUARD THAT DID NOT FIRE")
    print("    Nothing in src/guardrails.py inspects tool-observation CONTENT for staleness - step cap")
    print("    and budget cap bound turns and cost, not what a fat record hands the model to misread.")
    print("    A loop-control guard cannot catch this; it is the wrong layer for this failure.")
    print("3 - THE FIX, AND WHY IT BELONGS IN THIS LAYER")
    print("    src/tools.py:_format strips status_history under v2 (F2): the CODE/interface layer")
    print("    removes the stale value from the record entirely, so no reader - careful or not - can")
    print("    retrieve it. A prompt fix ('always use the CURRENT status, not history') asks a model to")
    print("    behave; the interface fix makes the mistake impossible to make, which is the poka-yoke")
    print("    OpsPilot's tool layer already claims for v2 (src/tools.py module docstring).")
    print("4 - BEFORE AND AFTER")
    print("    Restoring v2 must not remove information a legitimate check needs - v1_history stays")
    print("    available for the one design (D2b) that deliberately wants history; check D7-2's manifest")
    print("    result across all 6 fail_fixtures cases, not this one, before generalising.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
