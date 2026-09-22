# Cost assumptions (label every number as measured or assumed)

## Measured (fill after A2 cost probe)
| model | reasoning | $/case (median) | input tok | output tok | reasoning tok | date |
|---|---|---:|---:|---:|---:|---|
| ___ | low | ___ | ___ | ___ | ___ | ___ |

Prices pinned on: ___ (verify on openrouter.ai; update `.env` PRICE_* only for fallback estimates).

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
