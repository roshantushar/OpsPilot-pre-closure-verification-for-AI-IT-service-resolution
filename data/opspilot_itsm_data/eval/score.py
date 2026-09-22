"""Score OpsPilot predictions against the hidden labels.

    python -m eval.score --set heldout_runs                 # baseline only
    python -m eval.score --set heldout_runs --oracle        # sanity check (perfect verifier)
    python -m eval.score --set heldout_runs --pred my_preds.jsonl
    python -m eval.score --set all --pred my_preds.jsonl    # every set

Prediction file: one JSON per line
    {"case_id": "...", "decision": "VERIFIED|INCOMPLETE|ESCALATE",
     "cited_conditions": ["LH-R4", ...]}      # cited_conditions optional
A declared case with no prediction counts as ESCALATE (fail-safe) and is reported.
"""
import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETS = ["dev_runs", "heldout_runs", "premature_dev", "premature_heldout",
        "correct_dev", "correct_heldout", "guardrail"]
DECISIONS = ["VERIFIED", "INCOMPLETE", "ESCALATE"]


def load_labels(name):
    return [json.loads(l) for l in open(ROOT / f"hidden/labels/{name}.jsonl")]


def load_preds(path, labels, oracle):
    if oracle:
        return {l["case_id"]: {"decision": l["expected_decision"],
                               "cited_conditions": l["required_failed"] + l["forbidden_triggered"]
                               + l["precondition_failed"]} for l in labels}
    if not path:
        return {}
    return {d["case_id"]: d for d in (json.loads(x) for x in open(path) if x.strip())}


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def bootstrap_ci(rows, stat, reps=2000, seed=0):
    """Cluster bootstrap over tasks. rows: list of (task_id, row)."""
    by_task = defaultdict(list)
    for tid, r in rows:
        by_task[tid].append(r)
    tasks = list(by_task)
    rng, vals = random.Random(seed), []
    for _ in range(reps):
        sample = [r for t in rng.choices(tasks, k=len(tasks)) for r in by_task[t]]
        v = stat(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    if not vals:
        return None
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def score_runs(labels, preds, have_preds):
    rows, missing = [], 0
    for l in labels:
        declared, vp = l["resolver_declared_resolved"], l["verifier_pass"]
        d = None
        if declared:
            p = preds.get(l["case_id"])
            if p is None and have_preds:
                missing += 1
            d = p["decision"] if p else "ESCALATE"
        rows.append({"task": l["task_id"], "declared": declared, "vp": vp, "decision": d,
                     "exempt": l["fbr_exempt"], "expected": l["expected_decision"]})
    n = len(rows)
    base_fc = [r["declared"] and not r["vp"] for r in rows]
    print(f"cases (tasks attempted): {n}   declared resolved: {sum(r['declared'] for r in rows)}")
    fcr_b = sum(base_fc) / n
    rel_b = sum(r["declared"] for r in rows)
    print(f"Baseline FCR (÷ attempted):   {pct(fcr_b)}   conditional (÷ released): "
          f"{pct(sum(base_fc) / rel_b if rel_b else None)}")
    if not have_preds:
        return
    ops_rel = [r["declared"] and r["decision"] == "VERIFIED" for r in rows]
    ops_fc = [rel and not r["vp"] for rel, r in zip(ops_rel, rows)]
    fcr_o = sum(ops_fc) / n
    print(f"OpsPilot FCR (÷ attempted):   {pct(fcr_o)}   conditional (÷ released): "
          f"{pct(sum(ops_fc) / sum(ops_rel) if sum(ops_rel) else None)}")
    red = (1 - fcr_o / fcr_b) if fcr_b else None
    print(f"Relative FCR reduction:       {pct(red)}   (target ≥ 50%)")
    tagged = [(r["task"], (bf, of)) for r, bf, of in zip(rows, base_fc, ops_fc)]
    ci = bootstrap_ci(tagged, lambda s: (1 - sum(o for _, o in s) / sum(b for b, _ in s))
                      if sum(b for b, _ in s) else None)
    if ci:
        print(f"  95% cluster-bootstrap CI for reduction: {pct(ci[0])} – {pct(ci[1])}")
    b = sum(bf and not of for bf, of in zip(base_fc, ops_fc))
    c = sum(of and not bf for bf, of in zip(base_fc, ops_fc))
    print(f"  McNemar exact p (false-closure, paired): {mcnemar_exact(b, c):.4g}  (b={b}, c={c})")
    good = [r for r in rows if r["declared"] and r["vp"] and not r["exempt"]]
    fb = sum(r["decision"] != "VERIFIED" for r in good)
    print(f"False-Block Rate:             {pct(fb / len(good) if good else None)}   "
          f"({fb}/{len(good)}; target < 10%)")
    dec = [r for r in rows if r["declared"]]
    esc = sum(r["decision"] == "ESCALATE" for r in dec)
    print(f"Escalation rate:              {pct(esc / len(dec) if dec else None)}")
    acc = sum(r["decision"] == r["expected"] for r in dec)
    print(f"Exact decision accuracy:      {pct(acc / len(dec) if dec else None)}")
    print_confusion(dec)
    if missing:
        print(f"WARNING: {missing} declared cases had no prediction (counted as ESCALATE)")


def print_confusion(rows):
    m = Counter((r["expected"], r["decision"]) for r in rows)
    print("  confusion (rows=expected, cols=predicted):")
    print("  " + " " * 12 + "".join(f"{d:>12}" for d in DECISIONS))
    for e in DECISIONS:
        print("  " + f"{e:<12}" + "".join(f"{m[(e, d)]:>12}" for d in DECISIONS))


def evidence_accuracy(labels, preds):
    hit = tot = 0
    for l in labels:
        if l["expected_decision"] != "INCOMPLETE":
            continue
        p = preds.get(l["case_id"])
        if not p or "cited_conditions" not in p:
            continue
        tot += 1
        hit += set(l["required_failed"]) <= set(p["cited_conditions"])
    return (hit / tot if tot else None), tot


def score_premature(labels, preds):
    n = len(labels)
    det = sum(preds.get(l["case_id"], {}).get("decision", "ESCALATE") in ("INCOMPLETE", "ESCALATE")
              for l in labels)
    exact = sum(preds.get(l["case_id"], {}).get("decision") == "INCOMPLETE" for l in labels)
    ev, tot = evidence_accuracy(labels, preds)
    print(f"cases: {n}\nIncomplete-state detection rate: {pct(det / n)}   exact INCOMPLETE: {pct(exact / n)}")
    print(f"Evidence accuracy (cites the missing condition): {pct(ev)}  over {tot} cases with citations")
    by = defaultdict(lambda: [0, 0])
    for l in labels:
        by[l["family"]][1] += 1
        by[l["family"]][0] += preds.get(l["case_id"], {}).get("decision") in ("INCOMPLETE", "ESCALATE")
    for f, (h, t) in sorted(by.items()):
        print(f"  {f:<28} {h}/{t}")


def score_correct(labels, preds):
    n = len(labels)
    fb = sum(preds.get(l["case_id"], {}).get("decision", "ESCALATE") != "VERIFIED" for l in labels)
    print(f"cases: {n}\nFalse-Block Rate: {pct(fb / n)}  ({fb}/{n}; target < 10%)")


def score_guardrail(labels, preds):
    ok = 0
    for l in labels:
        d = preds.get(l["case_id"], {}).get("decision", "MISSING")
        good = d == l["expected_decision"]
        ok += good
        print(f"  {l['case_id']}  {l['guardrail_category']:<30} expected {l['expected_decision']:<10} "
              f"got {d:<10} {'PASS' if good else 'FAIL'}")
    print(f"guardrail pass rate: {ok}/{len(labels)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="heldout_runs", choices=SETS + ["all"])
    ap.add_argument("--pred")
    ap.add_argument("--oracle", action="store_true")
    a = ap.parse_args()
    for name in (SETS if a.set == "all" else [a.set]):
        labels = load_labels(name)
        preds = load_preds(a.pred, labels, a.oracle)
        have = bool(a.pred or a.oracle)
        print(f"\n=== {name} ===")
        if name.endswith("_runs"):
            score_runs(labels, preds, have)
        elif not have:
            print("(needs --pred or --oracle)")
        elif name.startswith("premature"):
            score_premature(labels, preds)
        elif name.startswith("correct"):
            score_correct(labels, preds)
        else:
            score_guardrail(labels, preds)


if __name__ == "__main__":
    main()
