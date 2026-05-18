from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import error_response
from .parser import _parse_farfield_cut_payload


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
            "runtime_module": "cst_runtime.farfield_analysis",
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
            runtime_module="cst_runtime.farfield_analysis",
        )
