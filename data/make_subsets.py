"""Build the fixed evaluation subsets (plan §4.2). Deterministic (seed below).

    python data/make_subsets.py            # writes data/subsets/*.json and prints a table

This is DATA PREPARATION, like the dataset builder: it reads hidden labels to stratify by
expected decision. It stores only case ids + composition. OpsPilot code (src/) never imports it.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE / "opspilot_itsm_data"
OUT = HERE / "subsets"
SEED = 20260922
FAMILIES = ["legal_hold_offboarding", "standard_offboarding", "access_grant_with_approval",
            "incident_on_hold_sla", "lost_or_stolen_device", "account_lockout_reset", "role_transfer",
            "sla_breach_escalation"]
MANY_CONDITION = ["legal_hold_offboarding", "standard_offboarding", "lost_or_stolen_device"]


def load(name):
    return [json.loads(l) for l in (DS / "hidden" / "labels" / f"{name}.jsonl").read_text().splitlines() if l]


def by_family(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["family"]].append(r)
    for v in d.values():
        v.sort(key=lambda r: r["case_id"])
    return d


def main():
    rng = random.Random(SEED)
    L = {s: load(s) for s in ["dev_runs", "heldout_runs", "premature_dev", "premature_heldout",
                              "correct_dev", "correct_heldout", "guardrail"]}
    cor, pre = by_family(L["correct_dev"]), by_family(L["premature_dev"])
    esc = by_family([r for r in L["dev_runs"] if r["expected_decision"] == "ESCALATE" and r["resolver_declared_resolved"]])
    false_claim = by_family([r for r in L["dev_runs"] if r["summary_honesty"] == "false_claim"])
    subsets, meta = {}, {}

    # dev_mini: per family 1 correct, 1 premature, 1 escalate (fallback: false-claim premature run)
    dev_mini, third = [], {}
    for f in FAMILIES:
        pick3 = (esc.get(f) or false_claim.get(f) or pre[f][1:])[0]
        third[f] = pick3
        dev_mini += [cor[f][0]["case_id"], pre[f][0]["case_id"], pick3["case_id"]]
    subsets["dev_mini"] = dev_mini

    # dev_micro: stratified half of dev_mini (rotate which role each family contributes)
    micro = []
    for i, f in enumerate(FAMILIES):
        roles = [cor[f][0]["case_id"], pre[f][0]["case_id"], third[f]["case_id"]]
        micro.append(roles[i % 3])
        if i % 2 == 0:
            micro.append(roles[(i + 1) % 3])
    subsets["dev_micro"] = micro[:12]

    subsets["smoke"] = [cor["account_lockout_reset"][0]["case_id"], pre["legal_hold_offboarding"][0]["case_id"],
                        pre["access_grant_with_approval"][0]["case_id"],
                        (esc.get("standard_offboarding") or next(v for v in esc.values()))[0]["case_id"]]
    hard = []
    for f in ["legal_hold_offboarding", "standard_offboarding", "lost_or_stolen_device", "access_grant_with_approval"]:
        hard += [pre[f][1]["case_id"], (esc.get(f) or pre[f][:1])[0]["case_id"]]
    subsets["hard_negatives"] = list(dict.fromkeys(hard))
    subsets["guardrail"] = [r["case_id"] for r in L["guardrail"]]
    subsets["attack_base"] = [pre[f][1]["case_id"] for f in
                              ["legal_hold_offboarding", "access_grant_with_approval", "account_lockout_reset", "role_transfer"]]
    subsets["fault_base"] = [cor["standard_offboarding"][1]["case_id"], pre["standard_offboarding"][1]["case_id"]]
    subsets["fail_fixtures"] = [x for f in MANY_CONDITION for x in (cor[f][1]["case_id"], pre[f][1]["case_id"])]

    # heldout_mini: 56 declared heldout_runs (7/family) + 12 premature_heldout + 12 correct_heldout
    hr = by_family([r for r in L["heldout_runs"] if r["resolver_declared_resolved"]])
    ph, ch = by_family(L["premature_heldout"]), by_family(L["correct_heldout"])
    held = []
    for f in FAMILIES:
        held += [r["case_id"] for r in rng.sample(hr[f], 7)]
    fams = FAMILIES[:]
    rng.shuffle(fams)
    for i, f in enumerate(fams):  # 12 over 8 families: 4 families give 2, 4 give 1
        k = 2 if i < 4 else 1
        held += [r["case_id"] for r in rng.sample(ph[f], k)]
        held += [r["case_id"] for r in rng.sample(ch[f], k)]
    subsets["heldout_mini"] = held

    labels = {r["case_id"]: r for rows in L.values() for r in rows}
    OUT.mkdir(exist_ok=True)
    print(f"{'subset':<16}{'n':>4}  decisions (declared)                 families  baseline FCR")
    for name, ids in subsets.items():
        rows = [labels[i] for i in ids]
        dec = Counter(r["expected_decision"] for r in rows if r["resolver_declared_resolved"])
        fcr = sum(r["resolver_declared_resolved"] and not r["verifier_pass"] for r in rows) / len(rows)
        m = {"n": len(ids), "decisions": dict(dec), "families": len({r["family"] for r in rows}),
             "baseline_fcr": round(fcr, 4), "seed": SEED}
        meta[name] = m
        (OUT / f"{name}.json").write_text(json.dumps({"name": name, **m, "case_ids": ids}, indent=1))
        print(f"{name:<16}{len(ids):>4}  {str(dict(dec)):<36}{m['families']:>8}  {100 * fcr:5.1f}%")
    dev_ids = {i for k, v in subsets.items() if k != "heldout_mini" for i in v}
    assert not dev_ids & set(subsets["heldout_mini"]), "held-out overlaps dev subsets"
    assert set(subsets["dev_micro"]) <= set(subsets["dev_mini"])
    print(f"\nX for docs/success_criteria.md = baseline FCR on heldout_mini = "
          f"{100 * meta['heldout_mini']['baseline_fcr']:.1f}%  (target <= {50 * meta['heldout_mini']['baseline_fcr']:.1f}%)")


if __name__ == "__main__":
    main()
