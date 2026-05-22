"""Test core/project.py: change_parameter guard integration."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import assert_json_error


def test_change_parameter_missing_name():
    """change_parameter with empty name returns error."""
    from cst_runtime.core.project import change_parameter
    result = change_parameter("/fake/project.cst", name="", value=None)
    assert_json_error(result, "parameter_name_missing")


def test_change_parameter_missing_value():
    """change_parameter with None value returns error."""
    from cst_runtime.core.project import change_parameter
    result = change_parameter("/fake/project.cst", name="g", value=None)
    assert_json_error(result, "parameter_value_missing")


def test_change_parameter_marks_dirty_and_annotates(mocker):
    """Mock COM layer, verify gateway.mark_params_dirty called + T13 warning."""
    from cst_runtime.core.project import change_parameter
    from cst_runtime.core import gateway
    from cst_runtime.core.utils import abs_project_path

    mock_project = mocker.MagicMock()
    mocker.patch(
        "cst_runtime.core.project.attach_expected_project",
        return_value=(mock_project, {"status": "success"}),
    )

    dummy = "/tmp/test_gate.cst"
    result = change_parameter(dummy, name="g", value=24.0)

    assert result["status"] == "success"
    assert result["changed"] == {"g": 24.0}
    assert "warning" in result
    assert "T13" in result.get("trap_note", "")

    norm = abs_project_path(dummy)
    st = gateway._get_state(norm)
    assert st is not None
    assert st.stage == "params_dirty"
