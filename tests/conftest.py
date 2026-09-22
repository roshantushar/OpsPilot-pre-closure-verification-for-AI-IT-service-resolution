"""Test isolation: results, cache and ledger go to a temp dir; backend forced to scripted."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="opspilot_test_")
os.environ.update(RESULTS_DIR=os.path.join(_TMP, "results"), CACHE_DIR=os.path.join(_TMP, "cache"),
                  BACKEND="scripted", SAVE_TRACES="true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
