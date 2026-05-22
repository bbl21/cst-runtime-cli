"""Test core/simulation.py: guard integration."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import assert_json_error


def test_start_sim_async_rejects_dirty_project():
    """T2: start_simulation_async refuses dirty project without reopen."""
    from cst_runtime.core.simulation import start_simulation_async
    from cst_runtime.core import gateway
    from cst_runtime.core.utils import abs_project_path

    dummy = abs_project_path("/tmp/dirty.cst")
    gateway.mark_params_dirty(dummy)
    result = start_simulation_async(dummy)
    assert_json_error(result, "params_not_rebuilt")


def test_start_sim_allows_clean_project(mocker):
    """Start simulation passes on clean project (no gateway block)."""
    from cst_runtime.core.simulation import start_simulation_async

    mock_project = mocker.MagicMock()
    mocker.patch(
        "cst_runtime.core.simulation.attach_expected_project",
        return_value=(mock_project, {"status": "success"}),
    )

    dummy = "/tmp/clean.cst"
    result = start_simulation_async(dummy)
    assert result["status"] == "success"


def test_start_sim_sync_also_rejects_dirty():
    """T2: synchronous start_simulation also checks dirty flag."""
    from cst_runtime.core.simulation import start_simulation
    from cst_runtime.core import gateway
    from cst_runtime.core.utils import abs_project_path

    dummy = abs_project_path("/tmp/dirty2.cst")
    gateway.mark_params_dirty(dummy)
    result = start_simulation(dummy)
    assert_json_error(result, "params_not_rebuilt")


def test_is_simulation_running_no_project(mocker):
    """is_simulation_running when project not attached returns the status error."""
    from cst_runtime.core.simulation import is_simulation_running

    mocker.patch(
        "cst_runtime.core.simulation.attach_expected_project",
        return_value=(None, {"status": "error", "error_type": "project_not_open"}),
    )
    result = is_simulation_running("/nonexistent.cst")
    assert result["status"] == "error"
