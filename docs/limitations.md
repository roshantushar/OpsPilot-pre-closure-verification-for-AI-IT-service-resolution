# Limitations and threats to validity (keep updated; copy into report §14)

- Synthetic data and self-written runbooks: results may not transfer; real-data validation is future work.
- Simulated resolver mix: the ~52% baseline is designed, not observed (heldout_mini X = 47.5%).
- Runbooks, checker and rules were written by the same author: rules/hybrid may look strong by construction
  (rules scores 288/292 on all sets). OpsPilot never reads the checker (tests/test_no_leakage.py).
- GEN-F1 blind spot: "changes applied to the wrong user" cannot be seen with per-subject read-only tools
  (all 4 rules misses).
- Small n under a fixed US$3.50 budget: CIs, exact McNemar and power analysis (A5) reported.
- Few model families; template wording (the verifier may learn phrasing).
- Perturbation labels follow fixed rules (src/perturb.py expected_rule); attacks and faults are simulated,
  not adaptive adversaries.
- Cost figures rest on stated assumptions (docs/cost_assumptions.md; tornado chart).
