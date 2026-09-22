"""Dataset + subset sanity: re-validate every label, then check subsets.

    python data/check_my_data.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE / "opspilot_itsm_data"

print("== dataset labels (eval/validate.py) ==")
rc = subprocess.call([sys.executable, "-m", "eval.validate"], cwd=DS)
if rc != 0:
    sys.exit("dataset validation failed")

print("\n== subsets ==")
public = {}
for p in (DS / "public" / "cases").glob("*.jsonl"):
    for line in p.read_text().splitlines():
        if line:
            c = json.loads(line)
            public[c["case_id"]] = c
dev_tasks = set(json.loads((DS / "splits.json").read_text())["dev"])
problems = 0
for f in sorted((HERE / "subsets").glob("*.json")):
    s = json.loads(f.read_text())
    ids = s["case_ids"]
    missing = [i for i in ids if i not in public]
    dupes = len(ids) - len(set(ids))
    held = s["name"] == "heldout_mini"
    wrong_split = [i for i in ids if i in public and (public[i]["task_id"] in dev_tasks) == held
                   and public[i]["set"] != "guardrail"]
    ok = not (missing or dupes or wrong_split)
    problems += not ok
    print(f"  {'ok ' if ok else 'BAD'} {s['name']:<16} n={len(ids):<3} missing={len(missing)} dupes={dupes} "
          f"wrong_split={len(wrong_split)}")
sys.exit(1 if problems else 0)
