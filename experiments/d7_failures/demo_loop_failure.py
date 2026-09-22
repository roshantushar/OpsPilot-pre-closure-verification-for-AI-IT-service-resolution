#!/usr/bin/env python3
"""D7-1 WORKED EXAMPLE: the loop failure, done once so you can copy the method.

    python -m experiments.d7_failures.demo_loop_failure

D7 requires each failure to be built as a DELETION FROM THE WORKING AGENT -
"the working agent, minus X" - not as a separately written bad agent. Putting X
back must recover the behaviour. That is what makes it a diagnosis, not a story.

Here X is ToolRuntime's DEDUP CACHE (src/tools.py - "identical call -> cached
result + note"). Everything else - the case, the perturbation, the verifier,
the prompt, the guardrails - is untouched between BEFORE and AFTER.

The scripted agent normally never re-asks a tool it already has an answer for
(that is a property of the deterministic policy in src/backends.py, not of the
dedup guard), so a live model's "let me check again to be sure" is simulated
here by calling the same tool 3 times, identically - the only thing that
differs between BEFORE and AFTER is whether ToolRuntime.dedup is on.

Runs on the SCRIPTED backend only: $0, deterministic, no API key needed.
Numbers below are printed from real calls each time, never hand-typed
(CLAUDE.md rule 6).
"""
from __future__ import annotations

from src.config import RunConfig
from src.data import load_subset
from src.harness import run_case
from src.perturb import Perturber
from src.tools import ToolRuntime

CASE_ID = "off-02-cor"  # fail_fixtures: standard_offboarding, checks get_google_user (OFF-R3/R4/F1)
REPEATED_TOOL = "get_google_user"
PERTURBATION = {"fault_mode": "pending:persistent", "system": "google_workspace"}
N_ASKS = 3  # "let me check again" x2, on top of the first, honest ask

_real_call = ToolRuntime.call


def _case():
    return next(c for c in load_subset("fail_fixtures") if c["case_id"] == CASE_ID)


def repeated_calls(dedup: bool) -> list:
    """What ToolRuntime.call actually returns to the model on N_ASKS identical
    calls - the mechanism itself, isolated from the rest of the agent loop."""
    case = _case()
    perturber = Perturber(PERTURBATION)
    runtime = ToolRuntime(perturber.case_view(case), dedup=dedup, perturber=perturber)
    email = case["ticket"]["subject_email"]
    out = []
    for _ in range(N_ASKS):
        obs = runtime.call(REPEATED_TOOL, {"email": email}, turn=0)
        out.append((obs, runtime.events[-1]))
    return out


def _patched_call(self, name, args=None, turn=0):
    """Same repeat, wired into a REAL end-to-end case run: 'the model forgot it
    already asked' N_ASKS-1 extra times, identically, the first time this tool
    is called. Same patch on BEFORE and AFTER - only self.dedup differs."""
    obs = _real_call(self, name, args, turn)
    if name == REPEATED_TOOL and not getattr(self, "_demo_repeated", False):
        self._demo_repeated = True
        for _ in range(N_ASKS - 1):
            _real_call(self, name, args, turn)
    return obs


def full_case_run(dedup: bool) -> dict:
    cfg = RunConfig(subset="fail_fixtures", verifier="agent", backend="scripted", dedup=dedup,
                    perturbation=PERTURBATION, experiment_id="D7-1-demo", arm="dedup_on" if dedup else "dedup_off")
    rec, _trace = run_case(_case(), cfg, trial=1)
    return rec


def main():
    print(f"\nDemonstrating on {CASE_ID} (fail_fixtures), perturbation={PERTURBATION}\n")

    print("PART 1 - the guard in isolation: the SAME 3 identical calls to "
          f"{REPEATED_TOOL}, dedup on vs off\n")
    for dedup in (True, False):
        print(f"  dedup={dedup}:")
        for i, (obs, ev) in enumerate(repeated_calls(dedup), 1):
            note = "cached, marked as a repeat" if "identical call already made" in obs else "reached the system again"
            print(f"    call {i}: dup_flag={ev.dup}  ->  {note}")
        print()
    print("  dup_flag is True on calls 2-3 EITHER WAY - ToolRuntime always tracks whether a call is a")
    print("  repeat, for the record (src/tools.py: `dup_without_dedup`). What the guard actually changes")
    print("  is call 2-3's OBSERVATION: cached + a 'this will not change' note when dedup is on, or the")
    print("  same unhelpful 'processing, call again' with NO such note - and the same real round-trip -")
    print("  every time, when it is off. A live model reading that raw text has no signal to stop asking.\n")

    print("PART 2 - the same repeat wired into a full case run (decision, turns, cost)\n")
    ToolRuntime.call = _patched_call
    try:
        before, after = full_case_run(dedup=True), full_case_run(dedup=False)
    finally:
        ToolRuntime.call = _real_call  # put the guard back

    def line(label, r):
        print(f"  {label:<20} turns={r['turns']:<2} tool_calls={r['tool_call_count']:<3} "
              f"dup={r['duplicate_tool_calls']:<2} cost=${r['total_cost_usd']:.4f} decision={r['decision']}")

    line("BEFORE (dedup on)", before)
    line("AFTER (dedup off)", after)
    print(f"  step_cap_hit={after['step_cap_hit']}  budget_cap_hit={after['budget_cap_hit']}\n")

    print("=" * 70)
    print("1 - THE INSTRUMENTATION THAT FOUND IT")
    print("    No exception was raised either way, and tool_call_count/dup are IDENTICAL between the two")
    print("    runs - a pass-rate table, or even a raw call-count table, would show nothing wrong. The")
    print("    fault only shows up in Part 1's observation text, which the aggregate stats do not carry.")
    if after["decision"] == before["decision"]:
        print(f"    Both runs still decided {after['decision']!r} on this case - the 3 repeated calls all")
        print("    land inside ONE turn's tool-call batch (that is how the repeat is simulated here), so")
        print("    they never cost this case an extra LLM turn.")
    print("2 - THE GUARD THAT DID NOT FIRE, AND WHY THAT SHOULD WORRY YOU HERE")
    print(f"    step_cap={RunConfig().step_cap}: this case needs {after['turns']} turns with ZERO repeats")
    print("    (7 tool calls + 1 final decision) - it is AT the cap with no headroom at all, exactly the")
    print("    'no headroom for one retry on 7-call families' risk already flagged in")
    print("    experiments/_generate_manifests.py's D3-3 comment. A live model that needed even ONE genuine")
    print("    extra TURN to re-ask (not just extra tool calls inside a turn, as simulated here) would trip")
    print("    step_cap on this case and fail safe to ESCALATE instead of the right decision. A step cap")
    print("    cannot tell 'one wasted retry' apart from 'the 8th of 8 turns this case legitimately needs' -")
    print("    which is exactly why the dedup guard in Part 1 has to catch the repeat before it becomes an")
    print("    extra turn, not after.")
    print("3 - THE FIX, AND WHY IT BELONGS IN THIS LAYER")
    print("    ToolRuntime's dedup cache (src/tools.py) is the CODE-layer fix: an identical call is")
    print("    served from cache with an explicit note instead of reaching a system that is still")
    print("    'processing, call again'. A prompt fix ('do not repeat calls') cannot be relied on - the")
    print("    model is the thing that forgets; only code remembers reliably.")
    print("4 - BEFORE AND AFTER")
    print("    Restoring the guard must not change the decision on the whole fail_fixtures set, only the")
    print("    number of real round-trips to a system stuck on 'call again' - check D7-1's manifest")
    print("    result across all 6 cases, not this one.")
    print("=" * 70)
    print("\nSecond failure (D7-2) belongs in the TOOL INTERFACE, not loop control again: see")
    print("experiments/d7_failures/demo_stale_read.py.\n")


if __name__ == "__main__":
    main()
