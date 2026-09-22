"""D6 - cost to serve (three layers) from logs + docs/cost_assumptions.md values ($0).

    MonthlyCost = Volume x (VariableCost + ExpectedFailureCost) + FixedCost
    ExpectedFailureCost = C_FC*P(false completion) + C_FB*P(false block) + C_ESC*P(escalate)
    Cost per verified-correct closure = total cost / closures correctly released
    Cheap-model break-even: required success = 1 - (E - C)/F
"""
from __future__ import annotations

from common import out_dir, summaries

# ASSUMPTIONS - keep in sync with docs/cost_assumptions.md (label as assumptions in the report)
A = {"analyst_usd_per_hour": 30.0, "min_recheck_false_block": 10, "min_escalation_review": 15,
     "min_rework_false_completion": 60, "fixed_monthly_usd": 200.0, "volumes": [1_000, 10_000, 100_000]}


def unit_costs():
    h = A["analyst_usd_per_hour"] / 60
    return {"C_FC": A["min_rework_false_completion"] * h, "C_FB": A["min_recheck_false_block"] * h,
            "C_ESC": A["min_escalation_review"] * h}


def monthly(m: dict, volume: int) -> float:
    c = unit_costs()
    var = m.get("cost_per_case_usd") or 0.0
    efc = c["C_FC"] * (m.get("FCR") or 0) + c["C_FB"] * (m.get("FBR") or 0) * 0.5 \
        + c["C_ESC"] * (m.get("escalation_rate") or 0)
    return volume * (var + efc) + A["fixed_monthly_usd"]


def main():
    S = summaries("D8") or summaries("D4")
    if not S:
        print("  (skip: no D8/D4 summaries yet)")
        return
    rows = ["| arm | $/case | FCR | monthly @1k | @10k | @100k |", "|---|---:|---:|---:|---:|---:|"]
    for name, s in S.items():
        for label, m in (("resolver alone", s["baseline"]), (name, s["metrics"])):
            rows.append(f"| {label} | {m.get('cost_per_case_usd') or 0:.4f} | {m['FCR']:.3f} | "
                        + " | ".join(f"{monthly(m, v):,.0f}" for v in A["volumes"]) + " |")
    (out_dir("d6") / "cost_to_serve.md").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))
    # TODO: 4 levers before/after (D2a, D2c, D2b, D4/D5), tornado chart, latency breakdown (A7)


if __name__ == "__main__":
    main()
