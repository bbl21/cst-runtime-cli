from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from .errors import error_response
from .project_identity import attach_expected_project

_DEFINED_MATERIALS: set[str] = set()


def _materials_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "references" / "Materials"


def _parse_mtd_commands(mtd_content: str) -> list[str]:
    commands = []
    in_definition = False
    for line in mtd_content.split("\n"):
        line = line.strip()
        if line == "[Definition]":
            in_definition = True
            continue
        if line.startswith("[") and line.endswith("]"):
            break
        if in_definition and line:
            commands.append(line)
    return commands


def _generate_material_vba(name: str, commands: list[str]) -> list[str]:
    vba = ["With Material", "    .Reset", f'    .Name "{name}"', '    .Folder ""']
    has_create = False
    for cmd in commands:
        vba.append(f"    {cmd}")
        if cmd.strip() == ".Create":
            has_create = True
    if not has_create:
        vba.append("    .Create")
    vba.append("End With")
    return vba


def _define_material(project_path: str, material_name: str) -> dict[str, Any]:
    material_name = material_name.strip()
    if material_name in _DEFINED_MATERIALS:
        return {"status": "success"}
    if material_name in ("Vacuum", "PEC"):
        _DEFINED_MATERIALS.add(material_name)
        return {"status": "success"}
    copper_aliases = {"Copper": "Copper (pure)"}
    if material_name in copper_aliases:
        material_name = copper_aliases[material_name]
    mtd_path = _materials_dir() / f"{material_name}.mtd"
    if not mtd_path.is_file():
        candidates = sorted(
            p.stem for p in _materials_dir().glob("*.mtd")
        )
        close = difflib.get_close_matches(material_name, candidates, n=5, cutoff=0.4)
        msg = f"No .mtd file for '{material_name}'"
        if close:
            msg += f". Did you mean: {', '.join(close)}?"
        return error_response(
            "material_file_not_found",
            msg,
            suggestions=close if close else None,
        )
    try:
        mtd_content = mtd_path.read_text(encoding="utf-8")
    except Exception as exc:
        return error_response("material_read_failed", str(exc), file=str(mtd_path))
    commands = _parse_mtd_commands(mtd_content)
    if not commands:
        return error_response("material_no_definition", f"No [Definition] in {mtd_path}")
    vba = _generate_material_vba(material_name, commands)
    result = _add_vba_history(project_path, f"Define Material: {material_name}", vba)
    if result.get("status") == "success":
        _DEFINED_MATERIALS.add(material_name)
    return result


def define_material_from_mtd(project_path: str, material_name: str) -> dict[str, Any]:
    return _define_material(project_path, material_name)


def _abs_project_path(project_path: str) -> str:
    normalized = os.path.abspath(os.path.expanduser(project_path))
    if not normalized.lower().endswith(".cst"):
        normalized += ".cst"
    return normalized


def _add_vba_history(project_path: str, history_name: str, vba_lines: list[str]) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        sCommand = "\n".join(vba_lines)
        project.modeler.add_to_history(history_name, sCommand)
        return {"status": "success", "project_path": normalized_project}
    except Exception as exc:
        return error_response(
            f"{history_name}_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeling",
        )


def _single_vba(project_path: str, history_name: str, vba: str) -> dict[str, Any]:
    return _add_vba_history(project_path, history_name, [vba])


def define_brick(
    project_path: str,
    name: str,
    component: str,
    material: str,
    x_min: float | str,
    x_max: float | str,
    y_min: float | str,
    y_max: float | str,
    z_min: float | str,
    z_max: float | str,
) -> dict[str, Any]:
    mat_result = _define_material(project_path, material)
    if mat_result.get("status") == "error":
        return mat_result
    vba = [
        "With Brick",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f"    .Xrange {x_min}, {x_max}",
        f"    .Yrange {y_min}, {y_max}",
        f"    .Zrange {z_min}, {z_max}",
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Brick:{name}", vba)


def define_cylinder(
    project_path: str,
    name: str,
    component: str,
    material: str,
    outer_radius: float | str,
    inner_radius: float | str,
    axis: str,
    range_min: float | str | None = None,
    range_max: float | str | None = None,
    z_min: float | str | None = None,
    z_max: float | str | None = None,
    center1: float | str = 0.0,
    center2: float | str = 0.0,
    x_center: float | str | None = None,
    y_center: float | str | None = None,
    segments: int = 0,
) -> dict[str, Any]:
    if range_min is None and z_min is not None:
        range_min = z_min
    if range_max is None and z_max is not None:
        range_max = z_max
    if center1 is None and x_center is not None:
        center1 = x_center
    if center2 is None and y_center is not None:
        center2 = y_center
    if range_min is None or range_max is None:
        return error_response(
            "missing_argument",
            "range_min or z_min (and range_max or z_max) is required",
        )

    axis_lower = axis.lower()
    if axis_lower == "x":
        range_param = f"Xrange {range_min}, {range_max}"
        c1, c2 = ".Ycenter", ".Zcenter"
    elif axis_lower == "y":
        range_param = f"Yrange {range_min}, {range_max}"
        c1, c2 = ".Xcenter", ".Zcenter"
    else:
        range_param = f"Zrange {range_min}, {range_max}"
        c1, c2 = ".Xcenter", ".Ycenter"

    vba = [
        "With Cylinder",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f"    .OuterRadius {outer_radius}",
        f"    .InnerRadius {inner_radius}",
        f'    .Axis "{axis}"',
        f"    .{range_param}",
        f"    {c1} {center1}",
        f"    {c2} {center2}",
        f'    .Segments "{segments}"',
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Cylinder:{name}", vba)


def define_cone(
    project_path: str,
    name: str,
    component: str,
    material: str,
    bottom_radius: float | str,
    top_radius: float | str,
    axis: str,
    range_min: float | str | None = None,
    range_max: float | str | None = None,
    z_min: float | str | None = None,
    z_max: float | str | None = None,
    center1: float | str = 0.0,
    center2: float | str = 0.0,
    x_center: float | str | None = None,
    y_center: float | str | None = None,
    segments: int = 0,
) -> dict[str, Any]:
    if range_min is None and z_min is not None:
        range_min = z_min
    if range_max is None and z_max is not None:
        range_max = z_max
    if center1 is None and x_center is not None:
        center1 = x_center
    if center2 is None and y_center is not None:
        center2 = y_center
    if range_min is None or range_max is None:
        return error_response(
            "missing_argument",
            "range_min or z_min (and range_max or z_max) is required",
        )

    axis_lower = axis.lower()
    if axis_lower == "x":
        range_param = f"Xrange {range_min}, {range_max}"
        c1, c2 = ".Ycenter", ".Zcenter"
    elif axis_lower == "y":
        range_param = f"Yrange {range_min}, {range_max}"
        c1, c2 = ".Xcenter", ".Zcenter"
    else:
        range_param = f"Zrange {range_min}, {range_max}"
        c1, c2 = ".Xcenter", ".Ycenter"

    vba = [
        "With Cone",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f"    .BottomRadius {bottom_radius}",
        f"    .TopRadius {top_radius}",
        f'    .Axis "{axis}"',
        f"    .{range_param}",
        f"    {c1} {center1}",
        f"    {c2} {center2}",
        f'    .Segments "{segments}"',
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Cone:{name}", vba)


def define_rectangle(
    project_path: str,
    name: str,
    curve: str,
    x_min: float | str,
    x_max: float | str,
    y_min: float | str,
    y_max: float | str,
) -> dict[str, Any]:
    vba = [
        "With Rectangle",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Curve "{curve}"',
        f"    .Xrange {x_min}, {x_max}",
        f"    .Yrange {y_min}, {y_max}",
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Rectangle:{name}", vba)


def boolean_subtract(project_path: str, target: str, tool: str) -> dict[str, Any]:
    vba = f'Solid.Subtract "{target}", "{tool}"'
    return _single_vba(project_path, f"boolean subtract: {target} - {tool}", vba)


def boolean_add(project_path: str, shape1: str, shape2: str) -> dict[str, Any]:
    vba = f'Solid.Add "{shape1}", "{shape2}"'
    return _single_vba(project_path, f"boolean add: {shape1} + {shape2}", vba)


def boolean_intersect(project_path: str, shape1: str, shape2: str) -> dict[str, Any]:
    vba = f'Solid.Intersect "{shape1}", "{shape2}"'
    return _single_vba(project_path, f"boolean intersect: {shape1} & {shape2}", vba)


def boolean_insert(project_path: str, shape1: str, shape2: str) -> dict[str, Any]:
    vba = f'Solid.Insert "{shape1}", "{shape2}"'
    return _single_vba(project_path, f"boolean insert: {shape1} <- {shape2}", vba)


def delete_entity(project_path: str, component: str, name: str) -> dict[str, Any]:
    full_name = f"{component}:{name}"
    vba = f'Solid.Delete "{full_name}"'
    return _single_vba(project_path, f"delete entity: {full_name}", vba)


def create_component(project_path: str, component_name: str) -> dict[str, Any]:
    vba = f'Component.New "{component_name}"'
    return _single_vba(project_path, f"create component: {component_name}", vba)


def change_material(project_path: str, shape_name: str, material: str) -> dict[str, Any]:
    mat_result = _define_material(project_path, material)
    if mat_result.get("status") == "error":
        return mat_result
    vba = f'Solid.ChangeMaterial "{shape_name}", "{material}"'
    return _single_vba(project_path, f"change material: {shape_name}", vba)


def define_frequency_range(project_path: str, start_freq: float, end_freq: float) -> dict[str, Any]:
    vba = f'Solver.FrequencyRange "{start_freq}", "{end_freq}"'
    return _single_vba(project_path, "define frequency range", vba)


def change_frequency_range(project_path: str, min_frequency: str, max_frequency: str) -> dict[str, Any]:
    vba = f'Solver.FrequencyRange "{min_frequency}", "{max_frequency}"'
    return _single_vba(project_path, "ChangeFrequency", vba)


def change_solver_type(project_path: str, solver_type: str) -> dict[str, Any]:
    vba = f'ChangeSolverType("{solver_type}")'
    return _single_vba(project_path, f"change solver type to {solver_type}", vba)


def define_background(project_path: str) -> dict[str, Any]:
    vba = [
        "With Background",
        '.ResetBackground',
        '.Type "Normal"',
        "End With",
    ]
    return _add_vba_history(project_path, "define background", vba)


def define_boundary(project_path: str) -> dict[str, Any]:
    vba = [
        "With Boundary",
        '.Xmin "expanded open"',
        '.Xmax "expanded open"',
        '.Ymin "expanded open"',
        '.Ymax "expanded open"',
        '.Zmin "expanded open"',
        '.Zmax "expanded open"',
        '.Xsymmetry "none"',
        '.Ysymmetry "none"',
        '.Zsymmetry "none"',
        "End With",
    ]
    return _add_vba_history(project_path, "define boundary", vba)


def define_mesh(
    project_path: str,
    steps_per_wave_near: int = 5,
    steps_per_wave_far: int = 5,
    steps_per_box_near: int = 5,
    steps_per_box_far: int = 1,
    edge_refinement_ratio: int = 2,
    edge_refinement_buffer_lines: int = 3,
    ratio_limit_geometry: int = 10,
    equilibrate_value: float = 1.5,
    use_gpu: bool = True,
) -> dict[str, Any]:
    vba = [
        'With Mesh',
        '     .MeshType "PBA"',
        '     .SetCreator "High Frequency"',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex"',
        '     .Set "Version", 1%',
        f'     .Set "StepsPerWaveNear", "{steps_per_wave_near}"',
        f'     .Set "StepsPerWaveFar", "{steps_per_wave_far}"',
        '     .Set "WavelengthRefinementSameAsNear", "1"',
        f'     .Set "StepsPerBoxNear", "{steps_per_box_near}"',
        f'     .Set "StepsPerBoxFar", "{steps_per_box_far}"',
        '     .Set "MaxStepNear", "0"',
        '     .Set "MaxStepFar", "0"',
        '     .Set "ModelBoxDescrNear", "maxedge"',
        '     .Set "ModelBoxDescrFar", "maxedge"',
        '     .Set "UseMaxStepAbsolute", "0"',
        '     .Set "GeometryRefinementSameAsNear", "0"',
        '     .Set "UseRatioLimitGeometry", "1"',
        f'     .Set "RatioLimitGeometry", "{ratio_limit_geometry}"',
        '     .Set "MinStepGeometryX", "0"',
        '     .Set "MinStepGeometryY", "0"',
        '     .Set "MinStepGeometryZ", "0"',
        '     .Set "UseSameMinStepGeometryXYZ", "1"',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex"',
        '     .Set "PlaneMergeVersion", "2"',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex"',
        '     .Set "FaceRefinementOn", "0"',
        '     .Set "FaceRefinementPolicy", "2"',
        '     .Set "FaceRefinementRatio", "2"',
        '     .Set "FaceRefinementStep", "0"',
        '     .Set "FaceRefinementNSteps", "2"',
        '     .Set "EllipseRefinementOn", "0"',
        '     .Set "EllipseRefinementPolicy", "2"',
        '     .Set "EllipseRefinementRatio", "2"',
        '     .Set "EllipseRefinementStep", "0"',
        '     .Set "EllipseRefinementNSteps", "2"',
        '     .Set "FaceRefinementBufferLines", "3"',
        '     .Set "EdgeRefinementOn", "1"',
        '     .Set "EdgeRefinementPolicy", "1"',
        f'     .Set "EdgeRefinementRatio", "{edge_refinement_ratio}"',
        '     .Set "EdgeRefinementStep", "0"',
        f'     .Set "EdgeRefinementBufferLines", "{edge_refinement_buffer_lines}"',
        '     .Set "RefineEdgeMaterialGlobal", "0"',
        '     .Set "RefineAxialEdgeGlobal", "0"',
        '     .Set "BufferLinesNear", "3"',
        '     .Set "UseDielectrics", "1"',
        '     .Set "EquilibrateOn", "1"',
        f'     .Set "Equilibrate", "{equilibrate_value}"',
        '     .Set "IgnoreThinPanelMaterial", "0"',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex"',
        '     .Set "SnapToAxialEdges", "1"',
        '     .Set "SnapToPlanes", "1"',
        '     .Set "SnapToSpheres", "1"',
        '     .Set "SnapToEllipses", "1"',
        '     .Set "SnapToCylinders", "1"',
        '     .Set "SnapToCylinderCenters", "1"',
        '     .Set "SnapToEllipseCenters", "1"',
        "End With",
        "With Mesh",
        '     .ConnectivityCheck "True"',
        '     .UsePecEdgeModel "True"',
        '     .PointAccEnhancement "0"',
        '     .TSTVersion "0"',
        '     .PBAVersion "2023042623"',
        '     .SetCADProcessingMethod "MultiThread22", "-1"',
        f'     .SetGPUForMatrixCalculationDisabled "{ "0" if use_gpu else "1" }"',
        "End With",
    ]
    return _add_vba_history(project_path, "Define Mesh", vba)


def define_solver(
    project_path: str,
    stimulation_port: str = "All",
    stimulation_mode: str = "All",
    steady_state_limit: float = -40,
    mesh_adaption: bool = False,
    auto_norm_impedance: bool = True,
    norming_impedance: float = 50,
    calculate_modes_only: bool = False,
    s_para_symmetry: bool = False,
    store_td_results: bool = False,
    run_discretizer_only: bool = False,
    full_deembedding: bool = False,
    superimpose_plw: bool = False,
    use_sensitivity: bool = False,
) -> dict[str, Any]:
    def _b(v: bool) -> str:
        return "True" if v else "False"

    vba = [
        'Mesh.SetCreator "High Frequency"',
        "With Solver",
        '     .Method "Hexahedral"',
        '     .CalculationType "TD-S"',
        f'     .StimulationPort "{stimulation_port}"',
        f'     .StimulationMode "{stimulation_mode}"',
        f'     .SteadyStateLimit "{steady_state_limit}"',
        f'     .MeshAdaption "{_b(mesh_adaption)}"',
        f'     .AutoNormImpedance "{_b(auto_norm_impedance)}"',
        f'     .NormingImpedance "{norming_impedance}"',
        f'     .CalculateModesOnly "{_b(calculate_modes_only)}"',
        f'     .SParaSymmetry "{_b(s_para_symmetry)}"',
        f'     .StoreTDResultsInCache  "{_b(store_td_results)}"',
        f'     .RunDiscretizerOnly "{_b(run_discretizer_only)}"',
        f'     .FullDeembedding "{_b(full_deembedding)}"',
        f'     .SuperimposePLWExcitation "{_b(superimpose_plw)}"',
        f'     .UseSensitivityAnalysis "{_b(use_sensitivity)}"',
        "End With",
    ]
    return _add_vba_history(project_path, "Define Solver", vba)


def define_port(
    project_path: str,
    port_number: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    orientation: str,
) -> dict[str, Any]:
    vba = [
        "With Port",
        "    .Reset",
        f'    .PortNumber "{port_number}"',
        '    .Label ""',
        '    .Folder ""',
        '    .NumberOfModes "1"',
        '    .AdjustPolarization "False"',
        '    .PolarizationAngle "0.0"',
        '    .ReferencePlaneDistance "0"',
        '    .TextSize "50"',
        '    .TextMaxLimit "1"',
        '    .Coordinates "Free"',
        f'    .Orientation "{orientation}"',
        '    .PortOnBound "False"',
        '    .ClipPickedPortToBound "False"',
        f"    .Xrange {x_min}, {x_max}",
        f"    .Yrange {y_min}, {y_max}",
        f"    .Zrange {z_min}, {z_max}",
        '    .XrangeAdd "0.0", "0.0"',
        '    .YrangeAdd "0.0", "0.0"',
        '    .ZrangeAdd "0.0", "0.0"',
        '    .SingleEnded "False"',
        '    .WaveguideMonitor "False"',
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Port:{port_number}", vba)


def define_monitor(project_path: str, start_freq: float, end_freq: float, step: float) -> dict[str, Any]:
    vba = [
        "With Monitor",
        ".Reset",
        f'.SetName "farfield (f={start_freq})_1"',
        ".Dimension",
        ".SetDimensionType \"Farfield\"",
        ".SetDomain \"Frequency\"",
        f".SetDomainRange {start_freq}, {end_freq}",
        f".SetStep {step}",
        "      .SetPlane 0",
        "      .SetDistance 0",
        ".SetSubVolumeEnabledFlag 1",
        ".SetSubVolume  -105, 105, -105, 105, 0, 445",
        "      .SetSubVolumePadding 0",
        "      .SetExitPortID 0",
        ".SetBoundingBoxFlag 0",
        ".SetNearfieldSamplingFlag 1",
        ".SetCreateFieldsFlag 1",
        "      .SetCreateExcitationFieldFlag 0",
        "      .SetCreateVolumeCurrentFlag 0",
        "      .SetCreateSurfaceCurrentFlag 0",
        "      .SetCreateLoadFieldFlag 0",
        ".SetVertexposition 0",
        ".Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define Monitor:{start_freq}-{end_freq}", vba)


def rename_entity(project_path: str, old_name: str, new_name: str) -> dict[str, Any]:
    vba = f'Solid.Rename "{old_name}", "{new_name}"'
    return _single_vba(project_path, f"rename: {old_name} -> {new_name}", vba)


def set_entity_color(
    project_path: str,
    shape_name: str,
    use_individual_color: bool = True,
    r: int = 192,
    g: int = 192,
    b: int = 192,
) -> dict[str, Any]:
    vba_use = "1" if use_individual_color else "0"
    vba = [
        f'Solid.SetUseIndividualColor "{shape_name}", {vba_use}',
        f'Solid.ChangeIndividualColor "{shape_name}", "{r}", "{g}", "{b}"',
    ]
    return _add_vba_history(project_path, f"set color: {shape_name}", vba)


def define_units(
    project_path: str,
    length: str = "mm",
    frequency: str = "GHz",
    voltage: str = "V",
    resistance: str = "Ohm",
    inductance: str = "nH",
    temperature: str = "degC",
    time: str = "ns",
    current: str = "A",
    conductance: str = "S",
    capacitance: str = "pF",
) -> dict[str, Any]:
    vba = [
        "With Units",
        f'    .SetUnit "Length", "{length}"',
        f'    .SetUnit "Frequency", "{frequency}"',
        f'    .SetUnit "Voltage", "{voltage}"',
        f'    .SetUnit "Resistance", "{resistance}"',
        f'    .SetUnit "Inductance", "{inductance}"',
        f'    .SetUnit "Temperature", "{temperature}"',
        f'    .SetUnit "Time", "{time}"',
        f'    .SetUnit "Current", "{current}"',
        f'    .SetUnit "Conductance", "{conductance}"',
        f'    .SetUnit "Capacitance", "{capacitance}"',
        "End With",
    ]
    return _add_vba_history(project_path, "Define Units", vba)


def set_farfield_monitor(
    project_path: str,
    start_freq: float,
    end_freq: float,
    step: float = 1,
    subvolume_x_min: float = -105,
    subvolume_x_max: float = 105,
    subvolume_y_min: float = -105,
    subvolume_y_max: float = 105,
    subvolume_z_min: float = 0,
    subvolume_z_max: float = 445,
    enable_nearfield: bool = True,
) -> dict[str, Any]:
    def _b(v: bool) -> str:
        return "True" if v else "False"
    vba = [
        "With Monitor",
        "    .Reset",
        '    .Domain "Frequency"',
        '    .FieldType "Farfield"',
        '    .ExportFarfieldSource "False"',
        '    .UseSubvolume "False"',
        '    .Coordinates "Structure"',
        f'    .SetSubvolume "{subvolume_x_min}", "{subvolume_x_max}", "{subvolume_y_min}", "{subvolume_y_max}", "{subvolume_z_min}", "{subvolume_z_max}"',
        '    .SetSubvolumeOffset "10", "10", "10", "10", "10", "10"',
        '    .SetSubvolumeInflateWithOffset "False"',
        '    .SetSubvolumeOffsetType "FractionOfWavelength"',
        f'    .EnableNearfieldCalculation "{_b(enable_nearfield)}"',
        f'    .CreateUsingLinearStep "{start_freq}", "{end_freq}", "{step}"',
        "End With",
    ]
    return _add_vba_history(project_path, "Set Farfield Monitor", vba)


def set_efield_monitor(
    project_path: str,
    start_freq: float,
    end_freq: float,
    step: float = 1,
    dimension: str = "Volume",
    subvolume_x_min: float = -105,
    subvolume_x_max: float = 105,
    subvolume_y_min: float = -105,
    subvolume_y_max: float = 105,
    subvolume_z_min: float = 0,
    subvolume_z_max: float = 443,
) -> dict[str, Any]:
    vba = [
        "With Monitor",
        "    .Reset",
        '    .Domain "Frequency"',
        '    .FieldType "Efield"',
        f'    .Dimension "{dimension}"',
        '    .UseSubvolume "False"',
        '    .Coordinates "Structure"',
        f'    .SetSubvolume "{subvolume_x_min}", "{subvolume_x_max}", "{subvolume_y_min}", "{subvolume_y_max}", "{subvolume_z_min}", "{subvolume_z_max}"',
        '    .SetSubvolumeOffset "0.0", "0.0", "0.0", "0.0", "0.0", "0.0"',
        '    .SetSubvolumeInflateWithOffset "False"',
        f'    .CreateUsingLinearStep "{start_freq}", "{end_freq}", "{step}"',
        "End With",
    ]
    return _add_vba_history(project_path, "Set Efield Monitor", vba)


def set_field_monitor(project_path: str, field_type: str, start_frequency: str, end_frequency: str, num_samples: str) -> dict[str, Any]:
    vba = f'Monitor.Reset\nMonitor.Domain "Frequency"\nMonitor.FieldType "{field_type}field"\nMonitor.Dimension "Volume"\nMonitor.CreateUsingLinearSamples "{start_frequency}", "{end_frequency}", "{num_samples}"'
    return _single_vba(project_path, f"Set{field_type}Monitor", vba)


def set_probe(project_path: str, field_type: str, x_pos: str, y_pos: str, z_pos: str) -> dict[str, Any]:
    vba = f'Probe.Reset\nProbe.AutoLabel 1\nProbe.Field "{field_type}field"\nProbe.Orientation "All"\nProbe.Xpos "{x_pos}"\nProbe.Ypos "{y_pos}"\nProbe.Zpos "{z_pos}"\nProbe.Create'
    return _single_vba(project_path, f"Set{field_type}Probe", vba)


def delete_probe_by_id(project_path: str, probe_id: str) -> dict[str, Any]:
    vba = f'Probe.DeleteById "{probe_id}"'
    return _single_vba(project_path, f"DeleteProbe{probe_id}", vba)


def delete_monitor(project_path: str, monitor_name: str) -> dict[str, Any]:
    vba = f'Monitor.Delete "{monitor_name}"'
    return _single_vba(project_path, f"delete monitor: {monitor_name}", vba)


def set_background_with_space(
    project_path: str,
    x_min_space: float = 30,
    x_max_space: float = 30,
    y_min_space: float = 30,
    y_max_space: float = 30,
    z_min_space: float = 50,
    z_max_space: float = 100,
) -> dict[str, Any]:
    vba = [
        "With Background",
        "    .ResetBackground",
        f'    .XminSpace "{x_min_space}"',
        f'    .XmaxSpace "{x_max_space}"',
        f'    .YminSpace "{y_min_space}"',
        f'    .YmaxSpace "{y_max_space}"',
        f'    .ZminSpace "{z_min_space}"',
        f'    .ZmaxSpace "{z_max_space}"',
        '    .ApplyInAllDirections "False"',
        "End With",
    ]
    return _add_vba_history(project_path, "Set Background Space", vba)


def set_farfield_plot_cuts(project_path: str, lateral_cuts: list | None = None, polar_cuts: list | None = None) -> dict[str, Any]:
    if lateral_cuts is None:
        lateral_cuts = [("0", "1"), ("90", "1")]
    if polar_cuts is None:
        polar_cuts = [("90", "1")]
    vba = ["With FarfieldPlot", "    .ClearCuts"]
    for phi, active in lateral_cuts:
        vba.append(f'    .AddCut "lateral", "{phi}", "{active}"')
    for theta, active in polar_cuts:
        vba.append(f'    .AddCut "polar", "{theta}", "{active}"')
    vba.append("End With")
    return _add_vba_history(project_path, "set farfield cuts", vba)


def show_bounding_box(project_path: str) -> dict[str, Any]:
    return _single_vba(project_path, "switch bounding box", 'Plot.DrawBox "True"')


def activate_post_process_operation(project_path: str, operation: str, enable: bool = True) -> dict[str, Any]:
    flag = "true" if enable else "false"
    vba = f'PostProcess1D.ActivateOperation "{operation}", "{flag}"'
    return _single_vba(project_path, f"activate post process: {operation}", vba)


def create_mesh_group(project_path: str, group_name: str, items: list[str]) -> dict[str, Any]:
    result = _single_vba(project_path, f"create mesh group: {group_name}", f'Group.Add "{group_name}", "mesh"')
    if result.get("status") == "error":
        return result
    for item in items:
        sub = _single_vba(project_path, f"add item to group: {group_name}", f'Group.AddItem "solid${item}", "{group_name}"')
        if sub.get("status") == "error":
            return sub
    return {
        "status": "success",
        "project_path": result.get("project_path"),
        "message": f"Mesh group {group_name} created with {len(items)} items",
    }


def define_polygon_3d(project_path: str, name: str, curve: str, points: list[list]) -> dict[str, Any]:
    vba = [
        "With Polygon3D",
        "    .Reset",
        "    .Version 10",
        f'    .Name "{name}"',
        f'    .Curve "{curve}"',
    ]
    for pt in points:
        if len(pt) >= 3:
            vba.append(f'    .Point "{pt[0]}", "{pt[1]}", "{pt[2]}"')
    vba.append("    .Create")
    vba.append("End With")
    return _add_vba_history(project_path, f"Define Polygon3D: {name}", vba)


def define_analytical_curve(project_path: str, name: str, curve: str, law_x: str, law_y: str, law_z: str, param_start: str, param_end: str) -> dict[str, Any]:
    vba = [
        "With AnalyticalCurve",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Curve "{curve}"',
        f'    .LawX "{law_x}"',
        f'    .LawY "{law_y}"',
        f'    .LawZ "{law_z}"',
        f'    .ParameterRange "{param_start}", "{param_end}"',
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define AnalyticalCurve: {name}", vba)


def define_extrude_curve(
    project_path: str,
    name: str,
    component: str,
    material: str,
    curve: str,
    thickness: float | str,
    twist_angle: float = 0.0,
    taper_angle: float = 0.0,
    delete_profile: bool = True,
) -> dict[str, Any]:
    mat_result = _define_material(project_path, material)
    if mat_result.get("status") == "error":
        return mat_result
    vba = [
        "With ExtrudeCurve",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Thickness "{thickness}"',
        f'    .Twistangle "{twist_angle}"',
        f'    .Taperangle "{taper_angle}"',
        f'    .DeleteProfile "{"True" if delete_profile else "False"}"',
        f'    .Curve "{curve}"',
        "    .Create",
        "End With",
    ]
    return _add_vba_history(project_path, f"Define ExtrudeCurve: {name}", vba)


def transform_shape(
    project_path: str,
    shape_name: str,
    transform_type: str,
    center_x: str = "0",
    center_y: str = "0",
    center_z: str = "0",
    plane_normal_x: str = "0",
    plane_normal_y: str = "1",
    plane_normal_z: str = "0",
    angle_x: str = "0",
    angle_y: str = "0",
    angle_z: str = "0",
    multiple_objects: bool = True,
    group_objects: bool = False,
    repetitions: int = 1,
    destination: str = "",
) -> dict[str, Any]:
    ttype = {"mirror": "Mirror", "rotate": "Rotate"}.get(transform_type.lower(), transform_type)
    if transform_type.lower() == "mirror":
        vba = [
            "With Transform",
            "    .Reset",
            f'    .Name "{shape_name}"',
            '    .Origin "Free"',
            f'    .Center "{center_x}", "{center_y}", "{center_z}"',
            f'    .PlaneNormal "{plane_normal_x}", "{plane_normal_y}", "{plane_normal_z}"',
            '    .MultipleObjects "True"',
            '    .GroupObjects "False"',
            '    .Repetitions "1"',
            '    .MultipleSelection "False"',
            f'    .Destination "{destination}"',
            '    .Material ""',
            '    .AutoDestination "True"',
            f'    .Transform "Shape", "{ttype}"',
            "End With",
        ]
    else:
        vba = [
            "With Transform",
            "    .Reset",
            f'    .Name "{shape_name}"',
            '    .Origin "Free"',
            f'    .Center "{center_x}", "{center_y}", "{center_z}"',
            f'    .PlaneNormal "{plane_normal_x}", "{plane_normal_y}", "{plane_normal_z}"',
            f'    .Angle "{angle_x}", "{angle_y}", "{angle_z}"',
            f'    .MultipleObjects "{"True" if multiple_objects else "False"}"',
            f'    .GroupObjects "{"True" if group_objects else "False"}"',
            f'    .Repetitions "{repetitions}"',
            '    .MultipleSelection "False"',
            f'    .Destination "{destination}"',
            '    .Material ""',
            '    .AutoDestination "True"',
            f'    .Transform "Shape", "{ttype}"',
            "End With",
        ]
    return _add_vba_history(project_path, f"transform shape: {shape_name}", vba)


def transform_curve(
    project_path: str,
    curve_name: str,
    center_x: str = "0",
    center_y: str = "0",
    center_z: str = "0",
    plane_normal_x: str = "0",
    plane_normal_y: str = "1",
    plane_normal_z: str = "0",
    multiple_objects: bool = True,
    group_objects: bool = False,
) -> dict[str, Any]:
    vba = [
        "With Transform",
        "    .Reset",
        f'    .Name "{curve_name}"',
        '    .Origin "Free"',
        f'    .Center "{center_x}", "{center_y}", "{center_z}"',
        f'    .PlaneNormal "{plane_normal_x}", "{plane_normal_y}", "{plane_normal_z}"',
        f'    .MultipleObjects "{"True" if multiple_objects else "False"}"',
        f'    .GroupObjects "{"True" if group_objects else "False"}"',
        '    .Repetitions "1"',
        '    .MultipleSelection "False"',
        '    .Destination ""',
        f'    .Transform "Curve", "Mirror"',
        "End With",
    ]
    return _add_vba_history(project_path, f"transform curve: {curve_name}", vba)


def create_horn_segment(project_path: str, segment_id: int, bottom_radius: float, top_radius: float, z_min: float, z_max: float) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    d = 5
    outer = define_cone(project_path, name=str(segment_id), component="component1", material="PEC",
                        bottom_radius=bottom_radius + d, top_radius=top_radius + d, axis="z",
                        z_min=z_min, z_max=z_max, x_center=0, y_center=0)
    if outer.get("status") == "error":
        return outer
    inner = define_cone(project_path, name=f"solid{segment_id}", component="component1", material="PEC",
                        bottom_radius=bottom_radius, top_radius=top_radius, axis="z",
                        z_min=z_min, z_max=z_max, x_center=0, y_center=0)
    if inner.get("status") == "error":
        return inner
    remove = boolean_subtract(project_path, target=f"component1:{segment_id}", tool=f"component1:solid{segment_id}")
    if remove.get("status") == "error":
        return remove
    return {"status": "success", "project_path": normalized_project, "message": f"Horn segment {segment_id} created"}


def _profile_brick(project, component, name, material, xmin, xmax, ymin, ymax, z):
    vba = f'With Brick\n    .Name "{name}"\n    .Component "{component}"\n    .Material "{material}"\n    .Xrange "{xmin}", "{xmax}"\n    .Yrange "{ymin}", "{ymax}"\n    .Zrange "{z}", "{z}"\n    .Create\nEnd With'
    project.modeler.add_to_history(f"Create:{name}", vba)


def _pick_face(project, component, name):
    project.modeler.add_to_history(f"Pick:{name}", f'Pick.PickFaceFromId "{component}:{name}", "1"')


def _do_loft(project, name, component, material, tangency, minimize_twist):
    twist = "true" if minimize_twist else "false"
    vba = f'With Loft\n    .Reset\n    .Name "{name}"\n    .Component "{component}"\n    .Material "{material}"\n    .Tangency "{tangency}"\n    .Minimizetwist "{twist}"\n    .CreateNew\nEnd With'
    project.modeler.add_to_history(f"Loft:{name}", vba)


def _delete_temp(project, component, name):
    project.modeler.add_to_history(f"Delete:{name}", f'Solid.Delete "{component}:{name}"')


def create_loft_sweep(
    project_path: str, name: str, component: str, material: str,
    x_min1: float, x_max1: float, y_min1: float, y_max1: float, z1: float,
    x_min2: float, x_max2: float, y_min2: float, y_max2: float, z2: float,
    tangency: int = 0, minimize_twist: bool = True,
) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    p1, p2 = f"_p1_{name}", f"_p2_{name}"
    _profile_brick(project, component, p1, material, x_min1, x_max1, y_min1, y_max1, z1)
    _profile_brick(project, component, p2, material, x_min2, x_max2, y_min2, y_max2, z2)
    _pick_face(project, component, p2)
    _pick_face(project, component, p1)
    _do_loft(project, name, component, material, tangency, minimize_twist)
    _delete_temp(project, component, p1)
    _delete_temp(project, component, p2)
    return {"status": "success", "project_path": normalized_project, "message": f"Loft sweep {name} created"}


def create_hollow_sweep(
    project_path: str, name: str, component: str, material: str,
    x_min1: float, x_max1: float, y_min1: float, y_max1: float, z1: float,
    x_min2: float, x_max2: float, y_min2: float, y_max2: float, z2: float,
    wall_thickness: float = 2.0, tangency: int = 0, minimize_twist: bool = True,
) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    ix1, ix2 = x_min1 + wall_thickness, x_max1 - wall_thickness
    iy1, iy2 = y_min1 + wall_thickness, y_max1 - wall_thickness
    jx1, jx2 = x_min2 + wall_thickness, x_max2 - wall_thickness
    jy1, jy2 = y_min2 + wall_thickness, y_max2 - wall_thickness
    op1, op2, ip1, ip2 = f"_op1_{name}", f"_op2_{name}", f"_ip1_{name}", f"_ip2_{name}"
    ol, il = f"_ol_{name}", f"_il_{name}"
    _profile_brick(project, component, op1, material, x_min1, x_max1, y_min1, y_max1, z1)
    _profile_brick(project, component, op2, material, x_min2, x_max2, y_min2, y_max2, z2)
    _profile_brick(project, component, ip1, material, ix1, ix2, iy1, iy2, z1)
    _profile_brick(project, component, ip2, material, jx1, jx2, jy1, jy2, z2)
    _pick_face(project, component, op2)
    _pick_face(project, component, op1)
    _do_loft(project, ol, component, material, tangency, minimize_twist)
    _pick_face(project, component, ip2)
    _pick_face(project, component, ip1)
    _do_loft(project, il, component, material, tangency, minimize_twist)
    project.modeler.add_to_history(f"Bool:{name}", f'Solid.Subtract "{component}:{ol}", "{component}:{il}"')
    for t in [op1, op2, ip1, ip2]:
        _delete_temp(project, component, t)
    return {"status": "success", "project_path": normalized_project, "message": f"Hollow sweep {name} created"}


def add_to_history(project_path: str, command: str, history_name: str = "") -> dict[str, Any]:
    name = history_name or f"VBA: {command[:40]}"
    return _single_vba(project_path, name, command)


def pick_face(project_path: str, component: str, name: str, face_id: str) -> dict[str, Any]:
    full = f"{component}:{name}"
    return _single_vba(project_path, f"Pick face: {full}", f'Pick.PickFaceFromId "{full}", "{face_id}"')


def define_loft(project_path: str, name: str, component: str, material: str, tangency: int = 0, minimize_twist: bool = True) -> dict[str, Any]:
    mat_result = _define_material(project_path, material)
    if mat_result.get("status") == "error":
        return mat_result
    twist = "true" if minimize_twist else "false"
    return _add_vba_history(project_path, f"Define Loft:{name}", [
        "With Loft",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Tangency "{tangency}"',
        f'    .Minimizetwist "{twist}"',
        "    .CreateNew",
        "End With",
    ])


def _ascii_export(project_path: str, tree_path: str, file_path: str, history_name: str) -> dict[str, Any]:
    vba = f'SelectTreeItem "{tree_path}"\nASCIIExport.Reset\nASCIIExport.FileName "{file_path}"\nASCIIExport.Execute'
    return _single_vba(project_path, history_name, vba)


def export_e_field(project_path: str, frequency: str, file_path: str) -> dict[str, Any]:
    tree = f"2D/3D Results\\E-Field\\e-field (f={frequency}) [pw]"
    fpath = f"{file_path}\\E-field-{frequency}GHz.txt"
    return _ascii_export(project_path, tree, fpath, "ExportEField")


def export_surface_current(project_path: str, frequency: str, file_path: str) -> dict[str, Any]:
    tree = f"2D/3D Results\\Surface Current\\surface current (f={frequency}) [pw]"
    fpath = f"{file_path}\\Surface-Current-{frequency}GHz.txt"
    return _ascii_export(project_path, tree, fpath, "ExportSurfaceCurrent")


def export_voltage(project_path: str, voltage_index: str, file_path: str) -> dict[str, Any]:
    tree = f"1D Results\\Voltage Monitors\\voltage{voltage_index} [pw]"
    fpath = f"{file_path}\\voltage-{voltage_index}.txt"
    return _ascii_export(project_path, tree, fpath, f"ExportVoltage{voltage_index}")
