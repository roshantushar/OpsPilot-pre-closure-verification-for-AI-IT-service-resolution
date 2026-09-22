"""Thin demo (D9, built last): pick a logged run, see ticket, claim, tool calls, decision, evidence, cost.

    streamlit run app/streamlit_app.py
Reads results/ only; never calls a model.
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data import all_cases  # noqa: E402

runs = sorted((ROOT / "results/raw/runs").glob("*.json"))
st.title("OpsPilot — pre-closure verification")
if not runs:
    st.info("No logged runs yet. Try: python -m src.run_eval --subset smoke --verifier agent")
    st.stop()
choice = st.selectbox("Run", [p.stem for p in runs])
rec = json.loads((ROOT / "results/raw/runs" / f"{choice}.json").read_text())
case = all_cases()[rec["case_id"]]
c1, c2 = st.columns(2)
c1.subheader("Ticket")
c1.json(case["ticket"])
c2.subheader("Resolver claim")
c2.json(case["proposed_closure"] or {"declared": False})
st.subheader(f"Decision: {rec['decision']}")
st.write(rec.get("reason"))
st.write("Cited conditions:", rec.get("cited_conditions"))
st.dataframe(rec.get("evidence") or [])
st.caption(f"tools: {rec.get('tools_called')} · turns {rec.get('turns')} · ${rec.get('total_cost_usd', 0):.4f} "
           f"· {rec.get('latency_ms', 0) / 1000:.1f}s · model {rec.get('model')} · backend {rec.get('backend')}")
tr = ROOT / "results/traces" / f"{choice}.jsonl"
if tr.exists():
    with st.expander("Trace"):
        st.code(tr.read_text())
