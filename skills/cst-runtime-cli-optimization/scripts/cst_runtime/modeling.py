from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import error_response
from .project_identity import attach_expected_project


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
