# Cost assumptions (label every number as measured or assumed)

## Measured (A2 cost probe, `smoke` n=4, live OpenRouter calls)
| model | reasoning | $/case (median) | input tok | output tok | reasoning tok | date |
|---|---|---:|---:|---:|---:|---|
| **openai/gpt-5-mini** (primary, pinned) | low | 0.00199 | 8450 | 613.5 | 414.5 | 2026-09-22 |
| openai/gpt-4o-mini | (n/a) | 0.00045 | 2391 | 257 | 0 | 2026-09-22 |
| google/gemini-2.5-flash-lite | (n/a) | 0.00083 | 2912 | 1426 | n/a | 2026-09-22 |

gpt-5-mini's $/case measurement was taken with `step_cap=8` (since raised to 10 after this same run
showed a case - `off-01-run1` - burn all 8 turns on tool calls with none left to answer, forcing a
fail-safe). Re-measure after any experiment that changes tool count or step cap materially.

**Decision (A2's own rule): gpt-5-mini stays primary.** 0.00199 << the $0.009/case switch threshold, and
it is the only one of the three that consistently did real evidence-gathering rather than tripping the
evidence guard (`src/schema.py`) by claiming completion without calling the tools that back it up -
gpt-4o-mini and gemini-2.5-flash-lite both did that on 3 of 4 cases each. Full per-model accuracy/FCR/FBR
comparison is in `results/summaries/A2__*.json` for each arm.

Prices pinned on: 2026-09-22 (OpenRouter; update `.env` PRICE_* only for fallback estimates when the
API doesn't report cost itself - these three runs all had `cost_source: reported`).

## Assumed (used in D6 / A2; kept in `analysis/d6_cost.py` → `A`)
| item | value | source / reasoning |
|---|---:|---|
| analyst cost (US$/hour, SG/IN blended) | 30 | assumption — tornado varies ±50% |
| minutes to re-check a false block | 10 | assumption |
| minutes per escalation review | 15 | assumption |
| rework minutes for a reopened false closure | 60 | assumption |
| fixed monthly cost (hosting, logging, maintenance) | 200 | assumption |
| volumes | 1k / 10k / 100k tickets per month | scenario |
| severity weights | high 3: legal hold, lost device, access · medium 2: offboarding, lockout, transfer · low 1: SLA tasks | `src/scoring.py` SEVERITY |
