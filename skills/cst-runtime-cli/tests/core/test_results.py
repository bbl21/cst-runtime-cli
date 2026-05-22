"""Test core/results.py: error paths for results functions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import assert_json_error


def test_open_project_file_missing():
    """open_project returns error when file doesn't exist."""
    from cst_runtime.core.results import open_project

    result = open_project("/nonexistent/path.cst")
    assert_json_error(result, "project_file_missing")


def test_get_1d_result_export_not_json(mocker):
    """get_1d_result with non-.json export path returns error."""
    mocker.patch("cst_runtime.core.results._load_project", return_value=(
        mocker.MagicMock(), {"fullpath": "/tmp/test.cst"},
    ))
    mocker.patch("cst_runtime.core.results._get_result_module", return_value=(
        mocker.MagicMock(), "3d",
    ))

    from cst_runtime.core.results import get_1d_result
    result = get_1d_result(
        "/tmp/test.cst", treepath="S1,1", export_path="/tmp/test.txt",
    )
    assert_json_error(result, "invalid_export_extension")


def test_get_2d_result_export_not_json(mocker):
    """get_2d_result with non-.json export path returns error."""
    mocker.patch("cst_runtime.core.results._load_project", return_value=(
        mocker.MagicMock(), {"fullpath": "/tmp/test.cst"},
    ))
    mocker.patch("cst_runtime.core.results._get_result_module", return_value=(
        mocker.MagicMock(), "3d",
    ))

    from cst_runtime.core.results import get_2d_result
    result = get_2d_result(
        "/tmp/test.cst", treepath="test", export_path="/tmp/test.txt",
    )
    assert_json_error(result, "invalid_export_extension")


def test_get_parameter_combination_no_cst():
    """get_parameter_combination with nonexistent project — cst.results not available."""
    from cst_runtime.core.results import get_parameter_combination
    try:
        result = get_parameter_combination("/nonexistent.cst", run_id=1)
        assert result["status"] == "error"
    except ImportError:
        pass


def test_get_1d_result_no_cst():
    """get_1d_result with nonexistent project — cst.results not available."""
    from cst_runtime.core.results import get_1d_result
    try:
        result = get_1d_result("/nonexistent.cst", treepath="S1,1")
        assert result["status"] == "error"
    except ImportError:
        pass


def test_list_result_items_no_cst():
    """list_result_items without CST — cst.results not available."""
    from cst_runtime.core.results import list_result_items
    try:
        result = list_result_items("/nonexistent.cst")
        assert result["status"] == "error"
    except ImportError:
        pass
