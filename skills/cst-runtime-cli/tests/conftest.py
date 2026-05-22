"""Pytest fixtures for cst-runtime-cli tests."""
import sys
import json
import subprocess
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

import pytest


@pytest.fixture(autouse=True)
def clear_gateway_registry():
    """Clear gateway state between tests."""
    from cst_runtime.core.gateway import _registry
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture
def run_cli():
    """Run cst_runtime CLI via subprocess, return parsed JSON."""
    python = sys.executable
    skill_scripts = str(SKILL_SCRIPTS)

    def _run(*args):
        r = subprocess.run(
            [python, "-m", "cst_runtime", *args],
            capture_output=True, text=True, cwd=str(Path.cwd()),
            env={**__import__("os").environ, "PYTHONPATH": skill_scripts},
        )
        return json.loads(r.stdout) if r.stdout.strip() else {"raw": r.stdout, "returncode": r.returncode}
    return _run


@pytest.fixture
def temp_workspace(tmp_path, run_cli):
    """Create a temporary workspace."""
    import tempfile
    # init-workspace needs a real path
    r = run_cli("init-workspace", "--workspace", str(tmp_path))
    assert r["status"] == "success"
    return tmp_path
