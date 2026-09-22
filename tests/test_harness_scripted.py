"""End-to-end on the scripted backend ($0): the harness, logs and scorer work together."""
import pytest

from src.harness import run_eval


def test_scripted_agent_dev_mini():
    s = run_eval(subset="dev_mini", verifier="agent", backend="scripted", experiment_id="t", arm="agent", quiet=True)
    assert s["metrics"]["accuracy"] >= 0.9
    assert s["metrics"]["FCR"] < s["baseline"]["FCR"]


def test_always_verified_reproduces_baseline():
    s = run_eval(subset="dev_runs", verifier="always_verified", experiment_id="t", arm="av", quiet=True)
    assert s["metrics"]["FCR"] == pytest.approx(s["baseline"]["FCR"]) == pytest.approx(0.521, abs=0.001)


def test_heldout_refused_without_freeze():
    with pytest.raises(PermissionError):
        run_eval(subset="heldout_mini", verifier="rules", experiment_id="t", arm="x", quiet=True)


def test_reuse_by_config_hash():
    a = run_eval(subset="smoke", verifier="rules", experiment_id="t1", arm="a", quiet=True)
    b = run_eval(subset="smoke", verifier="rules", experiment_id="t2", arm="b", quiet=True)
    assert a["config_hash"] == b["config_hash"] and a["metrics"]["accuracy"] == b["metrics"]["accuracy"]
