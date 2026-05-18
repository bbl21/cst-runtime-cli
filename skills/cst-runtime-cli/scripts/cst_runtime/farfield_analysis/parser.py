from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _extract_farfield_frequency_ghz(farfield_name: str) -> float | None:
    match = re.search(r"f\s*=\s*([0-9]+(?:\.[0-9]+)?)", farfield_name)
    if not match:
        return None
    return float(match.group(1))


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
