.PHONY: setup data test sanity smoke analysis app
setup:      ; pip install -r requirements.txt && cp -n .env.example .env || true
data:       ; python data/make_subsets.py && python data/check_my_data.py
test:       ; python -m pytest
sanity:     ; python -m src.run_eval --manifest experiments/a_setup/a1_harness_sanity.yaml
smoke:      ; python -m src.run_eval --subset smoke --verifier agent --backend scripted
analysis:   ; python analysis/run_all.py
app:        ; streamlit run app/streamlit_app.py
