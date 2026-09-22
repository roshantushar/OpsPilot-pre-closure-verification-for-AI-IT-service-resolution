"""Regenerate every table and figure from results/ ($0):  python analysis/run_all.py"""
import importlib

SCRIPTS = ["eda", "report_tables", "d0_trajectories", "d3_caps", "a1_token_growth", "a2_cost_of_errors",
           "a3_frontiers", "a4_reliability", "a5_power", "a6_error_causes", "a7_latency", "d6_cost"]

if __name__ == "__main__":
    for s in SCRIPTS:
        print(f"\n== {s} ==")
        importlib.import_module(s).main()
