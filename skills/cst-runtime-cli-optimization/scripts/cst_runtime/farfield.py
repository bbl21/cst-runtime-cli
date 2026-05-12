from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from . import process_cleanup
from .errors import error_response

FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS = 6
FARFIELD_EXPORT_HARD_MAX_ATTEMPTS = 12


def _normalize_project_path(project_path: str) -> str:
    normalized = os.path.abspath(os.path.expanduser(project_path))
    if not normalized.lower().endswith(".cst"):
        normalized += ".cst"
    return normalized


def _normalize_output_path(output_file: str, suffix: str) -> str:
    normalized = os.path.abspath(os.path.expanduser(output_file))
    if not normalized.lower().endswith(suffix.lower()):
        normalized += suffix
    output_dir = os.path.dirname(normalized)
    if not output_dir:
        raise ValueError(f"invalid output path: {output_file}")
    os.makedirs(output_dir, exist_ok=True)
    return normalized


def _serialize_value(value: Any) -> Any:
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag, "complex_str": str(value)}
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "tolist"):
        return _serialize_value(value.tolist())
    return value


def _extract_farfield_frequency_ghz(farfield_name: str) -> float | None:
    match = re.search(r"f\s*=\s*([0-9]+(?:\.[0-9]+)?)", farfield_name)
    if not match:
        return None
    return float(match.group(1))


def _build_farfield_angle_values(
    minimum: float,
    maximum: float,
    step: float,
    *,
    upper_bound: float,
    exclude_upper_endpoint: bool = False,
) -> list[float]:
    if step <= 0:
        raise ValueError("angle step must be positive")
    if minimum < 0 or maximum > upper_bound or minimum > maximum:
        raise ValueError(
            f"invalid angle range: min={minimum}, max={maximum}, upper_bound={upper_bound}"
        )

    values: list[float] = []
    value = minimum
    if exclude_upper_endpoint:
        while value < maximum - 1e-9:
            values.append(round(value, 10))
            value += step
    else:
        while value <= maximum + 1e-9:
            values.append(round(value, 10))
            value += step
    if not values:
        raise ValueError(
            f"angle range produced no sample points: min={minimum}, max={maximum}, step={step}"
        )
    return values


def inspect_farfield_ascii_grid(file_path: str) -> dict[str, Any]:
    theta_values: set[float] = set()
    phi_values: set[float] = set()
    row_count = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                theta = float(parts[0])
                phi = float(parts[1])
            except Exception:
                continue
            theta_values.add(theta)
            phi_values.add(phi)
            row_count += 1
    return {
        "row_count": row_count,
        "theta_count": len(theta_values),
        "phi_count": len(phi_values),
        "theta_min": min(theta_values) if theta_values else None,
        "theta_max": max(theta_values) if theta_values else None,
        "phi_min": min(phi_values) if phi_values else None,
        "phi_max": max(phi_values) if phi_values else None,
    }


def _derive_farfield_cut_tree_path(
    farfield_name: str, cut_axis: str = "Phi", cut_angle: str = "0"
) -> str | None:
    match = re.fullmatch(r"farfield \(f=(.+?)\) \[(\d+)\]", farfield_name.strip())
    if not match:
        return None
    frequency, port = match.groups()
    normalized_axis = cut_axis.strip().capitalize()
    if normalized_axis not in {"Phi", "Theta"}:
        return None
    return (
        f"Farfields\\Farfield Cuts\\Excitation [{port}]\\"
        f"{normalized_axis}={cut_angle}\\farfield (f={frequency})"
    )


def _build_farfield_cut_export_command(tree_path: str, output_file: str) -> str:
    return "\n".join(
        [
            f'SelectTreeItem "{tree_path}"',
            "With ASCIIExport",
            "    .Reset",
            f'    .FileName "{output_file}"',
            "    .Execute",
            "End With",
        ]
    )


def _normalize_farfield_plot_mode(plot_mode: str) -> dict[str, str]:
    normalized = (plot_mode or "").strip().lower()
    normalized = normalized.replace("_", " ").replace("-", " ").replace(".", " ")
    normalized = " ".join(normalized.split())

    if normalized in {"", "realized gain", "realizedgain", "rlzd gain", "rlzdgain"}:
        return {
            "result_type": "Realized Gain",
            "header_quantity": "Abs(Realized Gain)",
            "unit": "dBi",
        }
    if normalized in {"gain", "abs gain", "absgain"}:
        return {
            "result_type": "Gain",
            "header_quantity": "Abs(Gain)",
            "unit": "dBi",
        }
    if normalized in {"directivity", "abs directivity", "absdirectivity"}:
        return {
            "result_type": "Directivity",
            "header_quantity": "Abs(Directivity)",
            "unit": "dBi",
        }
    if normalized in {"efield", "e field", "electric field", "field", "abs e", "abse"}:
        raise ValueError(
            "Efield/Abs(E) is not supported for gain evidence. Use Realized Gain, Gain, or Directivity."
        )
    raise ValueError("unsupported plot_mode; use Realized Gain, Gain, or Directivity")


def _write_farfield_scalar_ascii(
    output_file: str,
    *,
    header_quantity: str,
    unit: str,
    theta_values: list[float],
    phi_values: list[float],
    grid_values: list[list[float]],
) -> None:
    with open(output_file, "w", encoding="utf-8", newline="") as handle:
        handle.write(
            f"Theta [deg.]  Phi   [deg.]  {header_quantity}[{unit}]  "
            "Aux1[-]  Aux2[-]  Aux3[-]  Aux4[-]  Aux5[-]\n"
        )
        handle.write(
            "------------------------------------------------------------------------------------------------------------------------------------------------------\n"
        )
        for phi_idx, phi_value in enumerate(phi_values):
            for theta_idx, theta_value in enumerate(theta_values):
                scalar_value = float(grid_values[phi_idx][theta_idx])
                handle.write(
                    f"{theta_value:.3f} {phi_value:.3f} "
                    f"{scalar_value:.6E} 0.000000E+00 0.000000E+00 "
                    "0.000000E+00 0.000000E+00 0.000000E+00\n"
                )


def _kill_cst_processes() -> dict[str, Any]:
    return process_cleanup.cleanup_cst_processes(dry_run=False, settle_seconds=0.5)


def _gui_open_project(fullpath: str) -> dict[str, Any]:
    if os.path.isdir(fullpath):
        return error_response("project_path_is_dir", "project_path is a directory", project_path=fullpath)
    normalized_path = fullpath
    if not normalized_path.lower().endswith(".cst"):
        cst_path = normalized_path + ".cst"
        if os.path.exists(cst_path):
            normalized_path = cst_path
        else:
            return error_response("project_file_missing", "project file does not exist", project_path=fullpath)
    if not os.path.isfile(normalized_path):
        return error_response("project_file_missing", "project file does not exist", project_path=normalized_path)
    try:
        import cst.interface

        de = cst.interface.DesignEnvironment()
        project = de.open_project(normalized_path)
        return {
            "status": "success",
            "project": project,
            "design_environment": de,
            "fullpath": normalized_path,
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "gui_open_project_failed",
            str(exc),
            project_path=normalized_path,
            runtime_module="cst_runtime.farfield",
        )


def _gui_close_project(project: Any, fullpath: str, save: bool = False) -> dict[str, Any]:
    try:
        if save:
            project.save()
        project.close()
        return {
            "status": "success",
            "message": f"project closed: {fullpath}",
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "gui_close_project_failed",
            str(exc),
            project_path=fullpath,
            runtime_module="cst_runtime.farfield",
        )


def _gui_add_to_history(project: Any, command: str, history_name: str) -> dict[str, Any]:
    try:
        project.modeler.add_to_history(history_name, command)
        return {
            "status": "success",
            "message": f"command added to history: {history_name}",
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "add_to_history_failed",
            str(exc),
            runtime_module="cst_runtime.farfield",
        )


def _gui_execute_vba(project: Any, code: str) -> dict[str, Any]:
    errors: list[str] = []
    for entrypoint in ("schematic", "modeler"):
        target = getattr(project, entrypoint, None)
        if target is None:
            errors.append(f"{entrypoint}: missing")
            continue
        execute = getattr(target, "execute_vba_code", None)
        if not callable(execute):
            errors.append(f"{entrypoint}: execute_vba_code unavailable")
            continue
        try:
            result = execute(code)
            return {
                "status": "success",
                "entrypoint": entrypoint,
                "result": _serialize_value(result),
                "runtime_module": "cst_runtime.farfield",
            }
        except Exception as exc:
            errors.append(f"{entrypoint}: {str(exc)}")
    return error_response(
        "execute_vba_unavailable",
        " ; ".join(errors) if errors else "execute_vba_code unavailable",
        runtime_module="cst_runtime.farfield",
    )


def _gui_set_result_navigator_selection(
    project: Any,
    run_ids: list[int] | None,
    selection_tree_path: str = "1D Results\\S-Parameters",
) -> dict[str, Any]:
    normalized_tree_path = (selection_tree_path or "").strip()
    if not normalized_tree_path:
        return error_response("selection_tree_path_missing", "selection_tree_path cannot be empty")

    normalized_ids = sorted({int(run_id) for run_id in (run_ids or [])})
    escaped_tree_path = normalized_tree_path.replace('"', '""')
    if normalized_ids:
        selection = " ".join(str(run_id) for run_id in normalized_ids)
        request = "set selection"
    else:
        selection = ""
        request = "reset selection"
    escaped_selection = selection.replace('"', '""')
    macro = "\n".join(
        [
            "Sub Main()",
            f'    SelectTreeItem("{escaped_tree_path}")',
            "    Dim response As String",
            f'    response = ResultNavigatorRequest("{request}", "{escaped_selection}")',
            "End Sub",
        ]
    )
    result = _gui_execute_vba(project, macro)
    if result.get("status") == "success":
        result.update(
            {
                "selection_tree_path": normalized_tree_path,
                "selected_run_ids": normalized_ids,
                "request": request,
            }
        )
    return result


def _read_farfield_scalar_grid_via_calculator(
    project: Any,
    farfield_name: str,
    result_type: str,
    unit: str,
    theta_step_deg: float,
    phi_step_deg: float,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    frequency_ghz = _extract_farfield_frequency_ghz(farfield_name)
    if frequency_ghz is None:
        return error_response(
            "farfield_frequency_parse_failed",
            f"cannot parse frequency from farfield_name: {farfield_name}",
            runtime_module="cst_runtime.farfield",
        )

    theta_step = max(0.1, float(theta_step_deg))
    phi_step = max(0.1, float(phi_step_deg))
    theta_min = 0.0 if theta_min_deg is None else float(theta_min_deg)
    theta_max = 180.0 if theta_max_deg is None else float(theta_max_deg)
    phi_min = 0.0 if phi_min_deg is None else float(phi_min_deg)
    phi_max = 360.0 if phi_max_deg is None else float(phi_max_deg)
    full_theta_range = abs(theta_min - 0.0) < 1e-9 and abs(theta_max - 180.0) < 1e-9
    full_phi_range = abs(phi_min - 0.0) < 1e-9 and abs(phi_max - 360.0) < 1e-9

    try:
        theta_values = _build_farfield_angle_values(theta_min, theta_max, theta_step, upper_bound=180.0)
        phi_values = _build_farfield_angle_values(
            phi_min,
            phi_max,
            phi_step,
            upper_bound=360.0,
            exclude_upper_endpoint=full_phi_range,
        )
    except ValueError as exc:
        return error_response("invalid_angle_range", str(exc), runtime_module="cst_runtime.farfield")

    try:
        calculator = project.model3d.FarfieldCalculator
        calculator.Reset()
        calculator.SetScaleLinear(False)
        calculator.DBUnit("0")

        tree_path = f"Farfields\\{farfield_name}"
        project.model3d.SelectTreeItem(tree_path)
        for phi_value in phi_values:
            for theta_value in theta_values:
                calculator.AddListEvaluationPoint(
                    theta_value,
                    phi_value,
                    1.0,
                    "spherical",
                    "frequency",
                    frequency_ghz,
                )
        calculator.CalculateList(tree_path, "farfield Eonly")

        scalar_values = [float(value) for value in calculator.GetList(result_type, "Spherical Abs")]
        point_theta = [float(value) for value in calculator.GetList(result_type, "Point_T")]
        point_phi = [float(value) for value in calculator.GetList(result_type, "Point_P")]

        expected_points = len(theta_values) * len(phi_values)
        if len(scalar_values) != expected_points:
            return error_response(
                "farfield_point_count_mismatch",
                f"points={len(scalar_values)}, expected={expected_points}",
                runtime_module="cst_runtime.farfield",
            )

        row_width = len(theta_values)
        grid_values = [
            scalar_values[idx : idx + row_width]
            for idx in range(0, len(scalar_values), row_width)
        ]

        peak_idx = max(range(len(scalar_values)), key=lambda idx: scalar_values[idx])
        boresight_value = None
        for theta_value, phi_value, scalar_value in zip(point_theta, point_phi, scalar_values):
            if abs(theta_value) <= 1e-9 and abs(phi_value) <= 1e-9:
                boresight_value = scalar_value
                break

        return {
            "status": "success",
            "source": "FarfieldCalculator",
            "quantity": result_type,
            "unit": unit,
            "tree_path": tree_path,
            "frequency_ghz": float(frequency_ghz),
            "scope": "full_sphere" if full_theta_range and full_phi_range else "partial_range",
            "is_full_sphere": full_theta_range and full_phi_range,
            "theta_min_deg": theta_min,
            "theta_max_deg": theta_max,
            "phi_min_deg": phi_min,
            "phi_max_deg": phi_max,
            "theta_values_deg": theta_values,
            "phi_values_deg": phi_values,
            "grid_values": grid_values,
            "sample_count": len(scalar_values),
            "peak_value": float(scalar_values[peak_idx]),
            "peak_theta_deg": float(point_theta[peak_idx]),
            "peak_phi_deg": float(point_phi[peak_idx]),
            "boresight_value": None if boresight_value is None else float(boresight_value),
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "farfield_calculator_read_failed",
            f"{result_type} read failed: {str(exc)}",
            runtime_module="cst_runtime.farfield",
        )


def _read_realized_gain_grid_via_calculator(
    project: Any,
    farfield_name: str,
    theta_step_deg: float,
    phi_step_deg: float,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    result = _read_farfield_scalar_grid_via_calculator(
        project=project,
        farfield_name=farfield_name,
        result_type="Realized Gain",
        unit="dBi",
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
    )
    if result.get("status") != "success":
        return result
    return {
        **result,
        "grid_db": result["grid_values"],
        "peak_realized_gain_dbi": result["peak_value"],
        "boresight_realized_gain_dbi": result["boresight_value"],
    }


def _export_farfield_grid_direct_com(
    project: Any,
    farfield_name: str,
    output_file: str,
    theta_step_deg: float,
    phi_step_deg: float,
    plot_mode: str,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    try:
        normalized_mode = _normalize_farfield_plot_mode(plot_mode)
    except ValueError as exc:
        return error_response(
            "unsupported_farfield_plot_mode",
            str(exc),
            alternative_tool="read-realized-gain-grid-fresh-session",
            runtime_module="cst_runtime.farfield",
        )

    read_result = _read_farfield_scalar_grid_via_calculator(
        project=project,
        farfield_name=farfield_name,
        result_type=normalized_mode["result_type"],
        unit=normalized_mode["unit"],
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
    )
    if read_result.get("status") != "success":
        return read_result

    _write_farfield_scalar_ascii(
        output_file,
        header_quantity=normalized_mode["header_quantity"],
        unit=normalized_mode["unit"],
        theta_values=read_result["theta_values_deg"],
        phi_values=read_result["phi_values_deg"],
        grid_values=read_result["grid_values"],
    )

    return {
        "status": "success",
        "message": f"farfield scalar grid exported: {output_file}",
        "tree_path": read_result["tree_path"],
        "frequency_ghz": read_result["frequency_ghz"],
        "requested_plot_mode": plot_mode,
        "exported_quantity": read_result["quantity"],
        "unit": read_result["unit"],
        "scope": read_result["scope"],
        "is_full_sphere": read_result["is_full_sphere"],
        "theta_min_deg": read_result["theta_min_deg"],
        "theta_max_deg": read_result["theta_max_deg"],
        "phi_min_deg": read_result["phi_min_deg"],
        "phi_max_deg": read_result["phi_max_deg"],
        "theta_count": len(read_result["theta_values_deg"]),
        "phi_count": len(read_result["phi_values_deg"]),
        "row_count": read_result["sample_count"],
        "peak_value": read_result["peak_value"],
        "peak_theta_deg": read_result["peak_theta_deg"],
        "peak_phi_deg": read_result["peak_phi_deg"],
        "boresight_value": read_result["boresight_value"],
        "runtime_module": "cst_runtime.farfield",
    }


def _cleanup_temp_export_file(file_path: str) -> None:
    try:
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
    except Exception:
        pass


def export_farfield_fresh_session(
    project_path: str,
    farfield_name: str,
    output_file: str,
    plot_mode: str = "Realized Gain",
    prime_with_cut: bool = False,
    cut_axis: str = "Phi",
    cut_angle: str = "0",
    theta_step_deg: float = 5.0,
    phi_step_deg: float = 5.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
    max_attempts: int = FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS,
    keep_prime_cut_file: bool = False,
) -> dict[str, Any]:
    normalized_project = _normalize_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response(
            "project_file_missing",
            "project_path does not exist",
            project_path=normalized_project,
            runtime_module="cst_runtime.farfield",
        )
    try:
        normalized_output = _normalize_output_path(output_file, ".txt")
    except ValueError as exc:
        return error_response("invalid_output_path", str(exc), runtime_module="cst_runtime.farfield")

    try:
        attempts = max(1, int(max_attempts))
    except Exception:
        return error_response("invalid_max_attempts", f"invalid max_attempts: {max_attempts}")
    attempts = min(attempts, FARFIELD_EXPORT_HARD_MAX_ATTEMPTS)

    derived_prime_tree = None
    if prime_with_cut:
        derived_prime_tree = _derive_farfield_cut_tree_path(farfield_name, cut_axis, cut_angle)
        if not derived_prime_tree:
            return error_response(
                "prime_cut_tree_parse_failed",
                f"cannot derive prime cut tree path from farfield_name: {farfield_name}",
                runtime_module="cst_runtime.farfield",
            )

    attempt_logs: list[dict[str, Any]] = []
    last_error = None
    for attempt in range(1, attempts + 1):
        flow_log: list[dict[str, Any]] = []
        prime_cut_output = None
        _cleanup_temp_export_file(normalized_output)

        start_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_before_open", "result": start_quit})
        if start_quit.get("status") != "success":
            last_error = "failed to clean CST processes before export"
            attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
            continue

        open_result = _gui_open_project(normalized_project)
        flow_log.append(
            {
                "step": "open_project",
                "result": {key: value for key, value in open_result.items() if key not in {"project", "design_environment"}},
            }
        )
        if open_result.get("status") != "success":
            last_error = f"failed to open project: {normalized_project}"
            attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
            continue

        project = open_result["project"]
        try:
            if prime_with_cut and derived_prime_tree:
                output_path = Path(normalized_output)
                prime_cut_output = str(
                    output_path.with_name(
                        f"{output_path.stem}__prime_{cut_axis.lower()}{cut_angle}_attempt{attempt}.txt"
                    )
                )
                _cleanup_temp_export_file(prime_cut_output)
                prime_result = _gui_add_to_history(
                    project,
                    _build_farfield_cut_export_command(derived_prime_tree, prime_cut_output),
                    history_name=f"PrimeFarfieldCut:{farfield_name}:attempt{attempt}",
                )
                flow_log.append({"step": "prime_cut", "result": prime_result})
                if prime_result.get("status") != "success":
                    last_error = f"prime cut export failed: {derived_prime_tree}"
                    attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                    continue
                if (not os.path.isfile(prime_cut_output)) or os.path.getsize(prime_cut_output) <= 0:
                    last_error = f"prime cut did not produce output: {prime_cut_output}"
                    flow_log.append(
                        {
                            "step": "prime_cut_validate",
                            "result": {"status": "error", "message": last_error, "output_file": prime_cut_output},
                        }
                    )
                    attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                    continue

            export_result = _export_farfield_grid_direct_com(
                project=project,
                farfield_name=farfield_name,
                output_file=normalized_output,
                plot_mode=plot_mode,
                theta_step_deg=theta_step_deg,
                phi_step_deg=phi_step_deg,
                theta_min_deg=theta_min_deg,
                theta_max_deg=theta_max_deg,
                phi_min_deg=phi_min_deg,
                phi_max_deg=phi_max_deg,
            )
            flow_log.append({"step": "export_farfield", "result": export_result})
            if export_result.get("status") != "success":
                last_error = f"farfield export failed: {farfield_name}"
                attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                continue

            if not os.path.isfile(normalized_output):
                last_error = f"export reported success but file was not created: {normalized_output}"
                attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                continue

            file_size = os.path.getsize(normalized_output)
            if file_size <= 0:
                last_error = f"export file is empty: {normalized_output}"
                attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                continue

            grid_info = inspect_farfield_ascii_grid(normalized_output)
            flow_log.append({"step": "validate_grid", "result": grid_info})
            is_full_sphere = export_result.get("is_full_sphere", True)
            if is_full_sphere and grid_info["phi_count"] <= 2:
                last_error = (
                    "exported file is a cut, not a full pattern: "
                    f"phi_count={grid_info['phi_count']}, row_count={grid_info['row_count']}"
                )
                attempt_logs.append({"attempt": attempt, "success": False, "flow_log": flow_log})
                continue

            payload = {
                "status": "success",
                "project_path": normalized_project,
                "farfield_name": farfield_name,
                "output_file": normalized_output,
                "plot_mode": plot_mode,
                "theta_step_deg": theta_step_deg,
                "phi_step_deg": phi_step_deg,
                "theta_min_deg": export_result.get("theta_min_deg"),
                "theta_max_deg": export_result.get("theta_max_deg"),
                "phi_min_deg": export_result.get("phi_min_deg"),
                "phi_max_deg": export_result.get("phi_max_deg"),
                "scope": export_result.get("scope"),
                "is_full_sphere": is_full_sphere,
                "file_size": file_size,
                "grid": grid_info,
                "attempt": attempt,
                "attempt_logs": attempt_logs + [{"attempt": attempt, "success": True, "flow_log": flow_log}],
                "runtime_module": "cst_runtime.farfield",
            }
            if prime_with_cut:
                payload["prime_cut_tree_path"] = derived_prime_tree
                if keep_prime_cut_file and prime_cut_output:
                    payload["prime_cut_output"] = prime_cut_output
            return payload
        finally:
            if prime_cut_output and not keep_prime_cut_file:
                _cleanup_temp_export_file(prime_cut_output)
            close_result = _gui_close_project(project, normalized_project, save=False)
            flow_log.append({"step": "close_project", "result": close_result})
            end_quit = _kill_cst_processes()
            flow_log.append({"step": "quit_after_close", "result": end_quit})

    return error_response(
        "farfield_export_failed",
        last_error or f"farfield export failed: {farfield_name}",
        attempt_logs=attempt_logs,
        project_path=normalized_project,
        farfield_name=farfield_name,
        output_file=normalized_output,
        plot_mode=plot_mode,
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
        prime_with_cut=prime_with_cut,
        prime_cut_tree_path=derived_prime_tree,
        attempts_used=attempts,
        runtime_module="cst_runtime.farfield",
    )


def export_existing_farfield_cut_fresh_session(
    project_path: str,
    tree_path: str,
    output_file: str,
) -> dict[str, Any]:
    normalized_project = _normalize_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response("project_file_missing", "project_path does not exist", project_path=normalized_project)

    normalized_tree_path = tree_path.strip()
    if not normalized_tree_path.startswith("Farfields\\Farfield Cuts\\"):
        return error_response(
            "invalid_farfield_cut_tree_path",
            "tree_path must point to an existing Farfield Cut result node",
            tree_path=normalized_tree_path,
        )
    try:
        normalized_output = _normalize_output_path(output_file, ".txt")
    except ValueError as exc:
        return error_response("invalid_output_path", str(exc), runtime_module="cst_runtime.farfield")

    flow_log: list[dict[str, Any]] = []
    start_quit = _kill_cst_processes()
    flow_log.append({"step": "quit_before_open", "result": start_quit})
    if start_quit.get("status") != "success":
        return error_response("kill_cst_failed", "failed to clean CST processes before export", flow_log=flow_log)

    open_result = _gui_open_project(normalized_project)
    flow_log.append(
        {
            "step": "open_project",
            "result": {key: value for key, value in open_result.items() if key not in {"project", "design_environment"}},
        }
    )
    if open_result.get("status") != "success":
        return error_response("gui_open_project_failed", "failed to open project", flow_log=flow_log)

    project = open_result["project"]
    try:
        export_result = _gui_add_to_history(
            project,
            _build_farfield_cut_export_command(normalized_tree_path, normalized_output),
            history_name=f"ExportFarfieldCutFresh:{normalized_tree_path}",
        )
        flow_log.append({"step": "export_farfield_cut", "result": export_result})
        if export_result.get("status") != "success":
            return error_response("farfield_cut_export_failed", "Farfield Cut export failed", flow_log=flow_log)
        if not os.path.isfile(normalized_output):
            return error_response("export_file_missing", "export command succeeded but file was not created", flow_log=flow_log)
        file_size = os.path.getsize(normalized_output)
        if file_size <= 0:
            return error_response("export_file_empty", "export file is empty", flow_log=flow_log)
        return {
            "status": "success",
            "project_path": normalized_project,
            "tree_path": normalized_tree_path,
            "output_file": normalized_output,
            "file_size": file_size,
            "flow_log": flow_log,
            "runtime_module": "cst_runtime.farfield",
        }
    finally:
        close_result = _gui_close_project(project, normalized_project, save=False)
        flow_log.append({"step": "close_project", "result": close_result})
        end_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_after_close", "result": end_quit})


def read_realized_gain_grid_fresh_session(
    project_path: str,
    farfield_name: str,
    run_id: int | None = None,
    theta_step_deg: float = 1.0,
    phi_step_deg: float = 2.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
    selection_tree_path: str = "1D Results\\S-Parameters",
    output_json: str = "",
) -> dict[str, Any]:
    normalized_project = _normalize_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response("project_file_missing", "project_path does not exist", project_path=normalized_project)

    normalized_output_json = ""
    if output_json:
        target = Path(output_json).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized_output_json = str(target)

    flow_log: list[dict[str, Any]] = []
    start_quit = _kill_cst_processes()
    flow_log.append({"step": "quit_before_open", "result": start_quit})
    if start_quit.get("status") != "success":
        return error_response("kill_cst_failed", "failed to clean CST processes before read", flow_log=flow_log)

    open_result = _gui_open_project(normalized_project)
    flow_log.append(
        {
            "step": "open_project",
            "result": {key: value for key, value in open_result.items() if key not in {"project", "design_environment"}},
        }
    )
    if open_result.get("status") != "success":
        return error_response("gui_open_project_failed", "failed to open project", flow_log=flow_log)

    project = open_result["project"]
    try:
        if run_id is not None:
            selection_result = _gui_set_result_navigator_selection(
                project=project,
                run_ids=[int(run_id)],
                selection_tree_path=selection_tree_path,
            )
            flow_log.append({"step": "set_result_navigator_selection", "result": selection_result})
            if selection_result.get("status") != "success":
                return error_response(
                    "result_navigator_selection_failed",
                    selection_result.get("message", f"run_id={run_id} selection failed"),
                    flow_log=flow_log,
                    project_path=normalized_project,
                    farfield_name=farfield_name,
                    run_id=int(run_id),
                    selection_tree_path=selection_tree_path,
                )

        read_result = _read_realized_gain_grid_via_calculator(
            project=project,
            farfield_name=farfield_name,
            theta_step_deg=theta_step_deg,
            phi_step_deg=phi_step_deg,
            theta_min_deg=theta_min_deg,
            theta_max_deg=theta_max_deg,
            phi_min_deg=phi_min_deg,
            phi_max_deg=phi_max_deg,
        )
        flow_log.append({"step": "read_realized_gain", "result": read_result})
        if read_result.get("status") != "success":
            return error_response(
                "realized_gain_read_failed",
                read_result.get("message", "Realized Gain read failed"),
                flow_log=flow_log,
                project_path=normalized_project,
                farfield_name=farfield_name,
            )

        result = {
            "status": "success",
            "project_path": normalized_project,
            "farfield_name": farfield_name,
            "run_id": None if run_id is None else int(run_id),
            "selection_tree_path": selection_tree_path if run_id is not None else None,
            "source": read_result["source"],
            "quantity": read_result["quantity"],
            "unit": read_result["unit"],
            "tree_path": read_result["tree_path"],
            "frequency_ghz": read_result["frequency_ghz"],
            "theta_step_deg": float(theta_step_deg),
            "phi_step_deg": float(phi_step_deg),
            "theta_min_deg": 0.0 if theta_min_deg is None else float(theta_min_deg),
            "theta_max_deg": 180.0 if theta_max_deg is None else float(theta_max_deg),
            "phi_min_deg": 0.0 if phi_min_deg is None else float(phi_min_deg),
            "phi_max_deg": 360.0 if phi_max_deg is None else float(phi_max_deg),
            "theta_count": len(read_result["theta_values_deg"]),
            "phi_count": len(read_result["phi_values_deg"]),
            "sample_count": read_result["sample_count"],
            "peak_realized_gain_dbi": read_result["peak_realized_gain_dbi"],
            "peak_theta_deg": read_result["peak_theta_deg"],
            "peak_phi_deg": read_result["peak_phi_deg"],
            "boresight_realized_gain_dbi": read_result["boresight_realized_gain_dbi"],
            "flow_log": flow_log,
            "runtime_module": "cst_runtime.farfield",
        }

        if normalized_output_json:
            payload = {
                **result,
                "theta_values_deg": read_result["theta_values_deg"],
                "phi_values_deg": read_result["phi_values_deg"],
                "grid_db": read_result["grid_db"],
            }
            Path(normalized_output_json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_json"] = normalized_output_json
        return result
    finally:
        if run_id is not None:
            reset_result = _gui_set_result_navigator_selection(
                project=project,
                run_ids=None,
                selection_tree_path=selection_tree_path,
            )
            flow_log.append({"step": "reset_result_navigator_selection", "result": reset_result})
        close_result = _gui_close_project(project, normalized_project, save=False)
        flow_log.append({"step": "close_project", "result": close_result})
        end_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_after_close", "result": end_quit})


def _parse_farfield_cut_payload(file_path: str) -> dict[str, Any]:
    payload = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    angle_deg = payload.get("angle_deg")
    primary_db = payload.get("primary_db")
    if not isinstance(angle_deg, list) or not isinstance(primary_db, list):
        raise ValueError(f"farfield cut JSON must contain angle_deg and primary_db: {file_path}")
    if len(angle_deg) != len(primary_db):
        raise ValueError(f"angle_deg and primary_db lengths differ: {file_path}")
    samples = [(float(angle), float(gain)) for angle, gain in zip(angle_deg, primary_db)]
    if not samples:
        raise ValueError(f"farfield cut data is empty: {file_path}")
    source = Path(file_path).resolve()
    return {
        "file_path": str(source),
        "label": source.stem,
        "frequency_ghz": payload.get("frequency_ghz"),
        "port": payload.get("port"),
        "cut": payload.get("cut"),
        "const_axis_value": payload.get("const_axis_value"),
        "samples": samples,
    }


def _evaluate_farfield_cut_neighborhood_flatness(cut_item: dict[str, Any], theta_max_deg: float) -> dict[str, Any]:
    samples = [
        (angle, gain)
        for angle, gain in cut_item["samples"]
        if 0.0 <= angle <= theta_max_deg
    ]
    if not samples:
        raise ValueError(f"no samples in theta <= {theta_max_deg:g} deg: {cut_item['file_path']}")
    gains = [gain for _, gain in samples]
    max_idx = max(range(len(samples)), key=lambda idx: samples[idx][1])
    min_idx = min(range(len(samples)), key=lambda idx: samples[idx][1])
    max_angle, max_gain = samples[max_idx]
    min_angle, min_gain = samples[min_idx]
    boresight_gain = next((gain for angle, gain in samples if abs(angle) <= 1e-9), None)

    frequency = cut_item.get("frequency_ghz")
    try:
        frequency = None if frequency is None else float(frequency)
    except Exception:
        frequency = None
    port = cut_item.get("port")
    try:
        port = None if port is None else int(port)
    except Exception:
        port = None

    return {
        "file_path": cut_item["file_path"],
        "label": cut_item["label"],
        "frequency_ghz": frequency,
        "port": port,
        "cut": cut_item.get("cut"),
        "const_axis_value": cut_item.get("const_axis_value"),
        "theta_max_deg": float(theta_max_deg),
        "sample_count": len(samples),
        "angle_range_deg": [samples[0][0], samples[-1][0]],
        "flatness_db": float(max_gain - min_gain),
        "max_gain_db": float(max_gain),
        "max_gain_angle_deg": float(max_angle),
        "min_gain_db": float(min_gain),
        "min_gain_angle_deg": float(min_angle),
        "boresight_gain_db": None if boresight_gain is None else float(boresight_gain),
    }


def _group_farfield_cut_flatness(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[float | None, int | None], list[dict[str, Any]]] = {}
    for item in items:
        key = (item.get("frequency_ghz"), item.get("port"))
        groups.setdefault(key, []).append(item)

    summaries: list[dict[str, Any]] = []
    for key in sorted(
        groups.keys(),
        key=lambda value: (
            float("inf") if value[0] is None else float(value[0]),
            float("inf") if value[1] is None else int(value[1]),
        ),
    ):
        members = groups[key]
        flatness_values = [float(member["flatness_db"]) for member in members]
        max_gain_values = [float(member["max_gain_db"]) for member in members]
        min_gain_values = [float(member["min_gain_db"]) for member in members]
        summaries.append(
            {
                "frequency_ghz": key[0],
                "port": key[1],
                "cut_count": len(members),
                "cuts": [member.get("cut") for member in members],
                "worst_flatness_db": max(flatness_values),
                "best_flatness_db": min(flatness_values),
                "mean_flatness_db": sum(flatness_values) / len(flatness_values),
                "max_gain_db": max(max_gain_values),
                "min_gain_db": min(min_gain_values),
                "files": [member["file_path"] for member in members],
            }
        )
    return summaries


def calculate_farfield_neighborhood_flatness(
    file_paths: list[str],
    theta_max_deg: float = 15.0,
    output_json: str = "",
) -> dict[str, Any]:
    try:
        if not file_paths:
            raise ValueError("file_paths cannot be empty")
        if theta_max_deg <= 0:
            raise ValueError("theta_max_deg must be positive")
        per_file = [
            _evaluate_farfield_cut_neighborhood_flatness(
                _parse_farfield_cut_payload(file_path),
                theta_max_deg,
            )
            for file_path in file_paths
        ]
        result = {
            "status": "success",
            "theta_max_deg": float(theta_max_deg),
            "file_count": len(per_file),
            "per_file": per_file,
            "grouped_summary": _group_farfield_cut_flatness(per_file),
            "runtime_module": "cst_runtime.farfield",
        }
        if output_json:
            target = Path(output_json).expanduser()
            if not target.is_absolute():
                target = (Path.cwd() / target).resolve()
            if target.suffix.lower() != ".json":
                target = target.with_suffix(".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["output_json"] = str(target)
        return result
    except Exception as exc:
        return error_response(
            "farfield_flatness_failed",
            str(exc),
            runtime_module="cst_runtime.farfield",
        )
