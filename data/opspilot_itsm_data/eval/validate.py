"""Re-verify the dataset: every stored label must match a fresh checker run.

    python -m eval.validate
"""
import copy
import json
from pathlib import Path

from lib.checker import check
from lib.world import apply_actions

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors, n = 0, 0
    specs = {p.stem: json.loads(p.read_text()) for p in (ROOT / "hidden/specs").glob("*.json")}
    seeds = {p.stem: json.loads(p.read_text())["seed_state"] for p in (ROOT / "public/seeds").glob("*.json")}

    for tid, spec in specs.items():  # gold passes; each drop-one fails exactly that condition
        seed = seeds[tid]
        if check(apply_actions(seed, spec["gold_actions"]), spec, seed)["expected_decision"] != "VERIFIED":
            print("gold does not verify:", tid); errors += 1
        for a in spec["gold_actions"]:
            res = check(apply_actions(seed, [x for x in spec["gold_actions"] if x is not a]), spec, seed)
            if res["required_failed"] != [a["satisfies"]] or res["expected_decision"] != "INCOMPLETE":
                print("drop-one mismatch:", tid, a["id"], res["required_failed"]); errors += 1

    for lab_file in sorted((ROOT / "hidden/labels").glob("*.jsonl")):
        for line in open(lab_file):
            lab = json.loads(line)
            state = json.loads((ROOT / f"public/states/{lab['case_id']}.json").read_text())
            spec = specs[lab["task_id"]]
            # escalate variants may start from a modified seed; collateral is judged
            # against that run's own start, so only re-check the non-collateral fields here
            res = check(state, spec, seeds[lab["task_id"]])
            keys = ["required_failed", "precondition_failed", "evidence_problems"]
            if any(res[k] != lab[k] for k in keys):
                print("label mismatch:", lab["case_id"], {k: (res[k], lab[k]) for k in keys}); errors += 1
            n += 1
    print(f"checked {len(specs)} tasks and {n} labelled cases — {errors} errors")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
