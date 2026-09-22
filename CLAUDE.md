# CLAUDE.md — OpsPilot (read first, every session)

Full plan: `docs/PROJECT_PLAN.md` (OPSPILOT_FINAL_PLAN v4). It overrides older plan files.

## What we build
OpsPilot: a bounded, **read-only** verification agent. Input: ticket, runbook id, resolver's
closure claim. It inspects enterprise state via `data/opspilot_itsm_data/tools/mock_tools.py`
and returns `VERIFIED | INCOMPLETE | ESCALATE` with evidence (`cited_conditions`).
Headline metric: **FCR** (÷ tasks attempted). Guardrails: FBR < 10%, escalation rate, attack
success = 0, cost/latency.

## Hard rules
1. Never import `lib/checker.py`, read `hidden/`, or open `public/states/*.json` from OpsPilot
   code. Labels are joined only in `src/scoring.py`. `tests/test_no_leakage.py` enforces it.
2. Tune on dev subsets only. Held-out (`heldout_mini`) runs **once**, after the freeze.
3. Every experiment = a config of `run_eval(...)` + a manifest YAML committed before the run.
4. Budget US$3.50 total (`MAX_BUDGET_USD`). Cache every LLM call. Develop with `BACKEND=scripted`
   or the free model. Print projected cost before each batch; ask if it exceeds the manifest cap.
5. OpsPilot has no write tools. Guardrails (step cap, dedup, budget cap, allowlist, schema check)
   live in code.
6. Log facts once (run JSON, trace JSONL, master CSV, ledger). Never hand-type results.
7. A2 = techniques only. Mirror its structure; do not copy its code, data or text.
8. Ask before adding dependencies, changing the dataset, or exceeding a cap.

## Scaffolding (A2 mirror)
`src/` (config, backends, llm, budget, tools, perturb, guardrails, prompt, schema, verifiers/,
resolver, decision_log, harness, judge, scoring, run_eval) · `data/` (dataset, make_subsets,
check_my_data, subsets/) · `experiments/d0…d8/` · `results/` · `analysis/` · `docs/D0…D9` ·
`app/streamlit_app.py` (last) · `tests/`.

## Build order
Subsets + EDA → scripted harness + tests → LLM client + cost probe → verifiers (agent, rules,
read-note, workflow, hybrid) → D4 → D2 → D3 → D7 → Tier 2 if budget → freeze → D8 → analyses,
D6, D9, README.
