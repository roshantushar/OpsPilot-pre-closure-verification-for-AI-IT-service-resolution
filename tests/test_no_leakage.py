"""CLAUDE.md rule 1: OpsPilot code never reads hidden labels/specs, the checker, or state files.

Static: AST scan of src/ (docstrings ignored). Dynamic: run verifiers and record every file opened.
"""
import ast
import builtins
import io
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
LABEL_READERS = {"scoring.py"}                      # the only module allowed to read labels
HARNESS_SIDE = {"scoring.py", "harness.py", "run_eval.py", "judge.py", "decision_log.py"}
FORBIDDEN_STRINGS = ("hidden", "checker", "public/states", "/states/", "specs/")


def _docstring_nodes(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                out.add(id(node.body[0].value))
    return out


def _py_files():
    return [p for p in SRC.rglob("*.py")]


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_static_no_hidden_access(path):
    if path.name in LABEL_READERS:
        return
    tree = ast.parse(path.read_text())
    docs = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            low = node.value.lower()
            bad = [s for s in FORBIDDEN_STRINGS if s in low]
            assert not bad, f"{path.name}:{node.lineno} string literal mentions {bad}: {node.value!r}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            assert not any("checker" in n for n in names), f"{path.name} imports the checker"
            if path.name not in HARNESS_SIDE:
                assert not any(n.split(".")[-1] == "scoring" for n in names), \
                    f"{path.name} imports scoring (labels) - verifier side must not"


def test_dynamic_no_hidden_file_access(monkeypatch):
    from src.config import RunConfig
    from src.data import load_subset
    from src.harness import run_case

    opened = []
    real_open, real_io_open = builtins.open, io.open

    def spy(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def spy_io(file, *a, **k):
        opened.append(str(file))
        return real_io_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy_io)
    for verifier in ["agent", "rules", "workflow", "hybrid", "read_note"]:
        cfg = RunConfig(subset="smoke", verifier=verifier, backend="scripted", experiment_id="leak", arm=verifier)
        for case in load_subset("smoke"):
            from src.tools import ToolRuntime  # noqa: F401  (runtime loads state via mock_tools only)
            opened.clear()
            run_case(case, cfg)
            bad = [p for p in opened if "/hidden/" in p or "checker" in p]
            assert not bad, f"{verifier} opened {bad}"
