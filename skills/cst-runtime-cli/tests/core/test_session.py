"""Test session management functions (via subprocess CLI)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_session_inspect_no_project(run_cli):
    """cst-session-inspect returns valid JSON without project."""
    result = run_cli("cst-session-inspect")
    assert result["status"] == "success"
    assert "force_kill_allowlist" in result
    assert "process_count" in result
    assert "readiness" in result


def test_session_quit_dry_run(run_cli):
    """cst-session-quit --dry-run does not kill processes."""
    result = run_cli("cst-session-quit", "--dry-run", "true")
    assert result["status"] == "success"
    assert "dry_run" in result
