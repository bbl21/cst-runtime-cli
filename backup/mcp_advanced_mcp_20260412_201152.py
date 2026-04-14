import cst
import cst.interface
import os
import re
from typing import Union
from mcp.server import FastMCP
import json
from pathlib import Path

# 创建MCP实例
mcp = FastMCP("cst_interface", log_level="ERROR")

# ============================================================
# 全局变量
# ============================================================
_current_project = None
_current_fullpath = None
_open_des_list = []  # 保存所有打开的 DesignEnvironment 对象，用于退出 CST
global_parameters = {}
call_counts = {"cylinder": 0, "cone": 0, "port": 0, "brick": 0}
line_break = "\n"
defined_materials = set()
# 保存 pick_face 选中的轮廓实体（用于 loft 完成后自动删除）
_picked_profile_entities = []


# ============================================================
# 全局辅助函数
# ============================================================


def save_project_object(project, fullpath, de=None):
    """保存project对象和DesignEnvironment到全局变量"""
    global _current_project, _current_fullpath, _open_des_list
    _current_project = project
    _current_fullpath = fullpath
    if de is not None and de not in _open_des_list:
        _open_des_list.append(de)


def get_project_object():
    """从全局变量获取当前project对象；若当前进程没有缓存，则尝试附着到已打开的CST活动项目"""
    global _current_project, _current_fullpath
    if _current_project is not None:
        return {"project": _current_project, "fullpath": _current_fullpath}

    try:
        de = cst.interface.DesignEnvironment.connect_to_any()
        if de.has_active_project():
            project = de.active_project()
            open_projects = de.list_open_projects()
            fullpath = open_projects[0] if open_projects else None
            save_project_object(project, fullpath)
            return {"project": project, "fullpath": fullpath}
    except Exception:
        pass

    return None


def clear_project_object():
    """清除当前project对象"""
    global \
        _current_project, \
        _current_fullpath, \
        global_parameters, \
        call_counts, \
        defined_materials, \
        _picked_profile_entities, \
        _open_des_list
    _current_project = None
    _current_fullpath = None
    global_parameters.clear()
    defined_materials.clear()
    call_counts = {"cylinder": 0, "cone": 0, "port": 0, "brick": 0}
    _picked_profile_entities.clear()


def _generate_unique_param_name(name):
    """生成唯一的参数名

    CST参数名不分大小写，所以需要检查是否存在（不区分大小写）的参数
    如果存在同名参数（大小写不同），则用已有名称更新（避免在CST中创建重复参数）
    如果确实需要新建（完全新名），才生成带后缀的唯一名称
    """
    global global_parameters
    name_original = name

    # 检查是否已存在不区分大小写的同名参数
    name_upper = name.upper()
    existing_key = None
    for key in global_parameters:
        if key.upper() == name_upper:
            existing_key = key
            break

    if existing_key is not None:
        # 命中已有参数，直接用已有名称返回（让CST更新原参数，而不是创建新参数）
        return existing_key

    # 没有重名，直接使用原名
    return name_original


# ============================================================
# 🎛️ 控制类工具（不使用 add_to_history，共10个）
# 直接调用 CST API，不可使用 VBA 替代
# ============================================================

# ---------- 项目管理（4个）----------


@mcp.tool()
def init_cst_project(path: str, base_name: str, ext: str):
    """初始化CST项目"""
    global global_parameters, call_counts, defined_materials
    global_parameters.clear()
    defined_materials.clear()
    call_counts = {"cylinder": 0, "cone": 0, "port": 0, "brick": 0}

    idx = 0
    while True:
        filename = f"{base_name}_{idx}{ext}"
        fullpath = os.path.join(path, filename)
        if not os.path.exists(fullpath):
            break
        idx += 1

    try:
        de = cst.interface.DesignEnvironment.new()
        project = de.new_mws()
        project.save(fullpath)
        save_project_object(project, fullpath)
        return {"status": "success", "fullpath": fullpath}
    except Exception as e:
        return {"status": "error", "message": f"初始化CST项目失败: {str(e)}"}


@mcp.tool()
def open_project(fullpath: str):
    """打开现有CST项目"""
    global global_parameters, call_counts, defined_materials
    global_parameters.clear()
    defined_materials.clear()
    call_counts = {"cylinder": 0, "cone": 0, "port": 0, "brick": 0}

    if os.path.isdir(fullpath):
        return {"status": "error", "message": f"路径是文件夹，不是项目文件: {fullpath}"}

    if not fullpath.endswith(".cst"):
        cst_path = fullpath + ".cst"
        if os.path.exists(cst_path):
            fullpath = cst_path
        else:
            return {"status": "error", "message": f"项目文件不存在: {fullpath}"}

    if not os.path.exists(fullpath) or not os.path.isfile(fullpath):
        return {"status": "error", "message": f"项目文件不存在: {fullpath}"}

    try:
        de = cst.interface.DesignEnvironment()
        project = de.open_project(fullpath)
        save_project_object(project, fullpath, de)
        return {"status": "success", "fullpath": fullpath}
    except Exception as e:
        error_msg = str(e)
        if "cannot be opened" in error_msg.lower() or "正在使用" in error_msg:
            return {
                "status": "error",
                "message": f"项目文件正在被其他程序使用，请先关闭 CST Studio Suite\n路径: {fullpath}",
            }
        else:
            return {
                "status": "error",
                "message": f"打开项目失败: {error_msg}\n路径: {fullpath}",
            }


@mcp.tool()
def save_project():
    """保存当前项目"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    try:
        project_data["project"].save()
        return {
            "status": "success",
            "message": f"项目已保存: {project_data['fullpath']}",
        }
    except Exception as e:
        return {"status": "error", "message": f"保存项目失败: {str(e)}"}


@mcp.tool()
def close_project(save: bool = True):
    """关闭当前项目

    Args:
        save: 是否保存更改，默认为 True。远场导出后必须传 save=False 避免项目损坏。
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    try:
        project_data["project"].close(SaveChanges=save)
        clear_project_object()
        return {
            "status": "success",
            "message": f"项目已关闭: {project_data['fullpath']}",
        }
    except Exception as e:
        return {"status": "error", "message": f"关闭项目失败: {str(e)}"}


@mcp.tool()
def quit_cst(project_path: str = None, force: bool = False):
    """关闭 CST 进程。

    Args:
        project_path: 可选，指定项目路径，只关闭该项目对应的窗口。
                    窗口标题格式："{项目文件名} - CST Studio Suite 2026"
                    注意：仅按文件名匹配，不同路径的同名项目无法区分。
        force: True 时忽略 project_path，关闭所有 CST 窗口。
              用于：同一项目有多个 CST 窗口、或项目名相同无法区分时。
    """
    import subprocess, os

    script_path = os.path.join(
        os.path.dirname(__file__), "tools", "close_cst_by_name.ps1"
    )

    if force or not project_path:
        args = [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-Force",
        ]
    else:
        project_name = os.path.splitext(os.path.basename(project_path))[0]
        args = [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-ProjectName",
            project_name,
        ]

    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        _open_des_list.clear()
        clear_project_object()
        return {"status": "success", "message": "CST 进程已关闭"}
    except Exception as e:
        return {"status": "error", "message": "quit_cst failed: " + str(e)}


# ---------- 仿真运行（6个）----------


@mcp.tool()
def start_simulation():
    """开始仿真（同步执行，等待完成）"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        project.modeler.run_solver()
        return {"status": "success", "message": "仿真已成功完成"}
    except Exception as e:
        return {"status": "error", "message": f"仿真失败: {str(e)}"}


@mcp.tool()
def start_simulation_async():
    """异步开始仿真（启动后立即返回）"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        project.modeler.start_solver()
        return {"status": "success", "message": "仿真已成功启动"}
    except Exception as e:
        return {"status": "error", "message": f"仿真启动失败: {str(e)}"}


@mcp.tool()
def is_simulation_running():
    """检查仿真状态"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        running = project.modeler.is_solver_running()
        return {
            "status": "success",
            "message": f"仿真状态: {'运行中' if running else '未运行'}",
            "running": running,
        }
    except Exception as e:
        return {"status": "error", "message": f"检查仿真状态失败: {str(e)}"}


@mcp.tool()
def pause_simulation():
    """暂停仿真"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        project.modeler.pause_solver()
        return {"status": "success", "message": "仿真已成功暂停"}
    except Exception as e:
        return {"status": "error", "message": f"暂停仿真失败: {str(e)}"}


@mcp.tool()
def resume_simulation():
    """恢复仿真"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        project.modeler.resume_solver()
        return {"status": "success", "message": "仿真已成功恢复"}
    except Exception as e:
        return {"status": "error", "message": f"恢复仿真失败: {str(e)}"}


@mcp.tool()
def stop_simulation():
    """停止仿真"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        project.modeler.abort_solver()
        return {"status": "success", "message": "仿真已成功停止"}
    except Exception as e:
        return {"status": "error", "message": f"停止仿真失败: {str(e)}"}


# ============================================================
# 🔧 使用 add_to_history 的工具（共28个）
# 可直接使用 VBA 代码替代
# ============================================================

# ---------- 自定义操作（1个）----------


@mcp.tool()
def add_to_history(command: str, history_name: str = None):
    """直接添加VBA命令到CST历史记录"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    if history_name is None:
        history_name = "CustomCommand"
    sCommand = command.replace("\\n", line_break).replace("\n", line_break)
    try:
        project.modeler.add_to_history(history_name, sCommand)
        return {"status": "success", "message": f"命令已添加到历史记录: {history_name}"}
    except Exception as e:
        return {"status": "error", "message": f"添加命令失败: {str(e)}"}


# ---------- 参数管理（1个）----------


@mcp.tool()
def parameter_set(name: str, value=None):
    """设置CST参数,返回的参数名可能带后缀以避免重复

    注意: CST中参数名不分大小写，如果传入已存在的参数名（大小写不同）会自动添加后缀区分
    """
    global global_parameters
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 生成唯一参数名（大小写不敏感检测）
    param_name = _generate_unique_param_name(name)

    if isinstance(value, (int, float)):
        sCommand = f'MakeSureParameterExists("{param_name}", "{value:.6f}")'
    else:
        sCommand = f'MakeSureParameterExists("{param_name}", "{value}")'
    if project.modeler is not None:
        project.modeler.add_to_history("StoreParameter", sCommand)
    global_parameters[param_name] = value
    return {"status": "success", "message": f"Parameter {param_name} set to {value}"}


# ---------- 建模工具（14个）----------


@mcp.tool()
def define_brick(
    name: str,
    component: str,
    material: str,
    x_min: Union[float, str],
    x_max: Union[float, str],
    y_min: Union[float, str],
    y_max: Union[float, str],
    z_min: Union[float, str],
    z_max: Union[float, str],
):
    """定义长方体"""
    global call_counts, global_parameters, line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    call_counts["brick"] += 1

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    try:
        project.modeler.add_to_history(f"Define Brick:{name}", sCommand)
        return {"status": "success", "message": f"Brick {name} created successfully"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"创建长方体失败: {str(e)}",
            "command": sCommand,
        }


@mcp.tool()
def define_cylinder(
    name: str,
    component: str,
    material: str,
    outer_radius: Union[float, str],
    inner_radius: Union[float, str],
    axis: str,
    range_min: Union[float, str] = None,
    range_max: Union[float, str] = None,
    z_min: Union[float, str] = None,
    z_max: Union[float, str] = None,
    center1: Union[float, str] = 0.0,
    center2: Union[float, str] = 0.0,
    x_center: Union[float, str] = None,
    y_center: Union[float, str] = None,
    segments: int = 0,
):
    """
    定义圆柱体，支持沿X轴、Y轴或Z轴创建。

    参数说明：
    - axis="z": 使用 z_min/z_max 定义高度，x_center/y_center 定义中心
    - axis="x": 使用 range_min/range_max 定义X方向长度，y_center/z_center 定义中心
    - axis="y": 使用 range_min/range_max 定义Y方向长度，x_center/z_center 定义中心

    示例：
    - 沿Z轴：define_cylinder(name="cyl", component="comp", material="PEC", outer_radius=5, inner_radius=0, axis="z", z_min=0, z_max=10, x_center=0, y_center=0)
    - 沿X轴：define_cylinder(name="cyl", component="comp", material="PEC", outer_radius=5, inner_radius=0, axis="x", range_min=-10, range_max=10, y_center=0, z_center=2)
    - 沿Y轴：define_cylinder(name="cyl", component="comp", material="PEC", outer_radius=5, inner_radius=0, axis="y", range_min=-10, range_max=10, x_center=0, z_center=2)
    """
    if range_min is None and z_min is not None:
        range_min = z_min
    if range_max is None and z_max is not None:
        range_max = z_max
    if center1 is None and x_center is not None:
        center1 = x_center
    if center2 is None and y_center is not None:
        center2 = y_center
    if range_min is None or range_max is None:
        return {"status": "error", "message": "缺少必要参数: range_min 或 range_max"}

    global call_counts, line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    call_counts["cylinder"] += 1

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    axis_lower = axis.lower()
    if axis_lower == "x":
        range_param = f"Xrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Ycenter", ".Zcenter"
    elif axis_lower == "y":
        range_param = f"Yrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Xcenter", ".Zcenter"
    else:
        range_param = f"Zrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Xcenter", ".Ycenter"

    VBA_code = [
        "With Cylinder",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f"    .OuterRadius {outer_radius}",
        f"    .InnerRadius {inner_radius}",
        f'    .Axis "{axis}"',
        f"    .{range_param}",
        f"    {center1_vba} {center1}",
        f"    {center2_vba} {center2}",
        f'    .Segments "{segments}"',
        "    .Create",
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"Define Cylinder:{name}", sCommand)
    return {"status": "success", "message": f"Cylinder {name} created successfully"}


@mcp.tool()
def define_cone(
    name: str,
    component: str,
    material: str,
    bottom_radius: Union[float, str],
    top_radius: Union[float, str],
    axis: str,
    range_min: Union[float, str] = None,
    range_max: Union[float, str] = None,
    z_min: Union[float, str] = None,
    z_max: Union[float, str] = None,
    center1: Union[float, str] = 0.0,
    center2: Union[float, str] = 0.0,
    x_center: Union[float, str] = None,
    y_center: Union[float, str] = None,
    segments: int = 0,
):
    """
    定义圆锥体，支持沿X轴、Y轴或Z轴创建。

    参数说明：
    - axis="z": 使用 z_min/z_max 定义高度，x_center/y_center 定义底面中心
    - axis="x": 使用 range_min/range_max 定义X方向长度，y_center/z_center 定义底面中心
    - axis="y": 使用 range_min/range_max 定义Y方向长度，x_center/z_center 定义底面中心

    锥形变化：
    - bottom_radius > top_radius: 渐缩（从大到小）
    - bottom_radius < top_radius: 渐扩（从小到大，喇叭天线用）

    示例：
    - 沿Z轴喇叭：define_cone(name="horn", component="comp", material="PEC", bottom_radius=10, top_radius=30, axis="z", z_min=50, z_max=150, x_center=0, y_center=0)
    - 沿X轴：define_cone(name="cone", component="comp", material="PEC", bottom_radius=5, top_radius=15, axis="x", range_min=0, range_max=100, y_center=0, z_center=0)
    - 沿Y轴：define_cone(name="cone", component="comp", material="PEC", bottom_radius=5, top_radius=15, axis="y", range_min=0, range_max=100, x_center=0, z_center=0)
    """
    if range_min is None and z_min is not None:
        range_min = z_min
    if range_max is None and z_max is not None:
        range_max = z_max
    if center1 is None and x_center is not None:
        center1 = x_center
    if center2 is None and y_center is not None:
        center2 = y_center
    if range_min is None or range_max is None:
        return {"status": "error", "message": "缺少必要参数: range_min 或 range_max"}

    global call_counts, line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    call_counts["cone"] += 1

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    axis_lower = axis.lower()
    if axis_lower == "x":
        range_param = f"Xrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Ycenter", ".Zcenter"
    elif axis_lower == "y":
        range_param = f"Yrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Xcenter", ".Zcenter"
    else:
        range_param = f"Zrange {range_min}, {range_max}"
        center1_vba, center2_vba = ".Xcenter", ".Ycenter"

    VBA_code = [
        "With Cone",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f"    .BottomRadius {bottom_radius}",
        f"    .TopRadius {top_radius}",
        f'    .Axis "{axis}"',
        f"    .{range_param}",
        f"    {center1_vba} {center1}",
        f"    {center2_vba} {center2}",
        f'    .Segments "{segments}"',
        "    .Create",
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"Define Cone:{name}", sCommand)
    return {"status": "success", "message": f"Cone {name} created successfully"}


@mcp.tool()
def define_rectangle(
    name: str,
    curve: str,
    x_min: Union[float, str],
    x_max: Union[float, str],
    y_min: Union[float, str],
    y_max: Union[float, str],
):
    """定义长方形"""
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        "With Rectangle",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Curve "{curve}"',
        f"    .Xrange {x_min}, {x_max}",
        f"    .Yrange {y_min}, {y_max}",
        "    .Create",
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"Define Rectangle:{name}", sCommand)
    return {"status": "success", "message": f"Rectangle {name} created successfully"}


@mcp.tool()
def boolean_subtract(target: str, tool: str):
    """布尔差集运算

    参数:
    - target: 被减的实体，支持 "component:name" 或 "name" 格式
    - tool: 要减去的实体，支持 "component:name" 或 "name" 格式

    注意: 如果使用简单名称（无冒号），将自动添加默认组件前缀
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 解析实体名称
    target_comp, target_name = _parse_entity_name(target)
    tool_comp, tool_name = _parse_entity_name(tool)

    # 如果只有一个有组件前缀，使用另一个的组件
    if target_comp and tool_comp and target_comp != tool_comp:
        return {
            "status": "error",
            "message": f"目标和工具必须在同一组件中: {target} vs {tool}",
        }
    component = target_comp or tool_comp

    # 生成完整的实体名称
    full_target = _make_full_name(component, target_name)
    full_tool = _make_full_name(component, tool_name)

    # 生成 VBA 命令
    sCommand = f'Solid.Subtract "{full_target}", "{full_tool}"'

    try:
        project.modeler.add_to_history(
            f"boolean subtract shapes: {full_target} - {full_tool}", sCommand
        )
        return {
            "status": "success",
            "message": f"Boolean subtract {full_target} - {full_tool} completed",
        }
    except Exception as e:
        return {"status": "error", "message": f"布尔差集运算失败: {str(e)}"}


@mcp.tool()
def boolean_add(shape1: str, shape2: str):
    """布尔和运算"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    # 解析实体名称
    comp1, name1 = _parse_entity_name(shape1)
    comp2, name2 = _parse_entity_name(shape2)

    if comp1 and comp2 and comp1 != comp2:
        return {
            "status": "error",
            "message": f"两个实体必须在同一组件中: {shape1} vs {shape2}",
        }
    component = comp1 or comp2

    full_shape1 = _make_full_name(component, name1)
    full_shape2 = _make_full_name(component, name2)

    sCommand = f'Solid.Add "{full_shape1}", "{full_shape2}"'
    try:
        project.modeler.add_to_history(
            f"boolean add shapes: {full_shape1} + {full_shape2}", sCommand
        )
        return {
            "status": "success",
            "message": f"Boolean add {full_shape1} + {full_shape2} completed",
        }
    except Exception as e:
        return {"status": "error", "message": f"布尔和运算失败: {str(e)}"}


@mcp.tool()
def boolean_intersect(shape1: str, shape2: str):
    """布尔交集运算"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    # 解析实体名称
    comp1, name1 = _parse_entity_name(shape1)
    comp2, name2 = _parse_entity_name(shape2)

    if comp1 and comp2 and comp1 != comp2:
        return {
            "status": "error",
            "message": f"两个实体必须在同一组件中: {shape1} vs {shape2}",
        }
    component = comp1 or comp2

    full_shape1 = _make_full_name(component, name1)
    full_shape2 = _make_full_name(component, name2)

    sCommand = f'Solid.Intersect "{full_shape1}", "{full_shape2}"'
    try:
        project.modeler.add_to_history(
            f"boolean intersect shapes: {full_shape1} and {full_shape2}", sCommand
        )
        return {
            "status": "success",
            "message": f"Boolean intersect {full_shape1} & {full_shape2} completed",
        }
    except Exception as e:
        return {"status": "error", "message": f"布尔交集运算失败: {str(e)}"}


@mcp.tool()
def boolean_insert(shape1: str, shape2: str):
    """布尔插入运算

    参数:
    - shape1: 目标实体，支持 'component:name' 或 'name' 格式
    - shape2: 插入的实体，支持 'component:name' 或 'name' 格式
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 解析实体名称
    comp1, name1 = _parse_entity_name(shape1)
    comp2, name2 = _parse_entity_name(shape2)

    if comp1 and comp2 and comp1 != comp2:
        return {
            "status": "error",
            "message": f"两个实体必须在同一组件中: {shape1} vs {shape2}",
        }
    component = comp1 or comp2

    full_shape1 = _make_full_name(component, name1)
    full_shape2 = _make_full_name(component, name2)

    sCommand = f'Solid.Insert "{full_shape1}", "{full_shape2}"'
    try:
        project.modeler.add_to_history(
            f"boolean insert shapes: {full_shape1} insert {full_shape2}", sCommand
        )
        return {
            "status": "success",
            "message": f"Boolean insert {full_shape1} insert {full_shape2} completed",
        }
    except Exception as e:
        return {"status": "error", "message": f"布尔插入运算失败: {str(e)}"}


@mcp.tool()
def delete_entity(component: str, name: str):
    """删除几何实体"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    full_name = f"{component}:{name}"
    sCommand = f'Solid.Delete "{full_name}"'
    try:
        project.modeler.add_to_history(f"delete entity: {full_name}", sCommand)
        return {"status": "success", "message": f"已删除几何实体 {full_name}"}
    except Exception as e:
        return {"status": "error", "message": f"删除实体失败: {str(e)}"}


@mcp.tool()
def create_horn_segment(
    segment_id: int, bottom_radius: float, top_radius: float, z_min: float, z_max: float
):
    """创建喇叭段（外圆台+内圆台+布尔差集）"""
    define_cone(
        name=str(segment_id),
        component="component1",
        material="PEC",
        bottom_radius=f"{bottom_radius}+d",
        top_radius=f"{top_radius}+d",
        axis="z",
        z_min=z_min,
        z_max=z_max,
    )
    define_cone(
        name=f"solid{segment_id}",
        component="component1",
        material="PEC",
        bottom_radius=bottom_radius,
        top_radius=top_radius,
        axis="z",
        z_min=z_min,
        z_max=z_max,
    )
    boolean_subtract(f"component1:{segment_id}", f"component1:solid{segment_id}")
    return {
        "status": "success",
        "message": f"Horn segment {segment_id} created successfully",
    }


@mcp.tool()
def pick_face(component: str, name: str, face_id: str):
    """
    选择实体的指定面（用于 loft 放样操作）。

    **重要：此工具专为 loft 放样设计，仅适用于零厚度实体。**
    对于非零厚度实体，VBA 中的 PickFaceFromId 无法准确定位面，必须在 GUI 中手动操作。

    **注意：选择的面所属的实体会在 loft 完成后自动删除（辅助轮廓清理）。**

    参数：
    - component: 组件名称
    - name: 实体名称
    - face_id: 面 ID（通常为 "1"，表示实体的第一个面）

    示例：
    pick_face(component="component1", name="solid4", face_id="1")
    """
    global _picked_profile_entities
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    full_name = f"{component}:{name}"
    sCommand = f'Pick.PickFaceFromId "{full_name}", "{face_id}"'
    project.modeler.add_to_history(f"Pick face: {full_name}", sCommand)
    # 保存选中的实体信息，用于 loft 完成后自动删除
    _picked_profile_entities.append({"component": component, "name": name})
    return {"status": "success", "message": f"已选择面 {full_name}, face_id={face_id}"}


@mcp.tool()
def define_loft(
    name: str,
    component: str,
    material: str,
    tangency: int = 0,
    minimize_twist: bool = True,
):
    """
    执行放样(Loft)操作。

    **前置条件：必须先通过 pick_face 选择两个零厚度实体的对应面。**

    **自动清理：loft 完成后会自动删除之前 pick_face 选中的辅助轮廓实体。**

    参数：
    - name: 放样生成的实体名称
    - component: 组件名称
    - material: 材料（如 PEC, Copper (pure)）
    - tangency: 正切值（0=无）
    - minimize_twist: 是否最小化扭曲

    **使用流程：**
    1. 创建第一个零厚度实体 (define_brick, zrange 相同值)
    2. 创建第二个零厚度实体 (define_brick, zrange 相同值)
    3. pick_face 选择第二个实体的面
    4. pick_face 选择第一个实体的面
    5. define_loft 执行放样（辅助轮廓自动删除）

    示例：
    define_loft(name="loft1", component="component1", material="PEC", tangency=0, minimize_twist=True)
    """
    global line_break, _picked_profile_entities
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    VBA_code_loft = [
        "With Loft",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Tangency "{tangency}"',
        f'    .Minimizetwist "{"true" if minimize_twist else "false"}"',
        "    .CreateNew",
        "End With",
    ]
    sCommand_loft = line_break.join(VBA_code_loft)
    project.modeler.add_to_history(f"Define Loft:{name}", sCommand_loft)

    # 自动删除之前 pick_face 选中的辅助轮廓实体
    deleted_entities = []
    for entity in _picked_profile_entities:
        full_name = f"{entity['component']}:{entity['name']}"
        sCommand_delete = f'Solid.Delete "{full_name}"'
        project.modeler.add_to_history(
            f"Delete profile:{entity['name']}", sCommand_delete
        )
        deleted_entities.append(entity["name"])
    _picked_profile_entities.clear()

    if deleted_entities:
        return {
            "status": "success",
            "message": f"Loft {name} 执行成功（已删除辅助轮廓: {', '.join(deleted_entities)}）",
        }
    return {"status": "success", "message": f"Loft {name} 执行成功"}


# ---------- 复合放样工具（P0 升级）----------


def _parse_entity_name(entity: str):
    """解析实体名称，返回 (component, name)

    支持格式:
    - "component:name" -> ("component", "name")
    - "name" -> (None, "name")
    """
    if ":" in entity:
        parts = entity.split(":", 1)
        return parts[0], parts[1]
    return None, entity


def _make_full_name(component: str, name: str) -> str:
    """生成完整的实体名称"""
    if component:
        return f"{component}:{name}"
    return name


@mcp.tool()
def create_loft_sweep(
    name: str,
    component: str,
    material: str,
    x_min1: float,
    x_max1: float,
    y_min1: float,
    y_max1: float,
    z1: float,
    x_min2: float,
    x_max2: float,
    y_min2: float,
    y_max2: float,
    z2: float,
    tangency: int = 0,
    minimize_twist: bool = True,
):
    """
    创建放样实体 - 一次性完成整个操作（复合工具）

    这是一个复合工具，自动完成以下步骤:
    1. 创建第一个零厚度实体（轮廓1）
    2. 创建第二个零厚度实体（轮廓2）
    3. 按正确顺序选择面（先选2再选1，与 loft 方向一致）
    4. 执行 loft 操作

    参数:
    - name: 放样生成的实体名称
    - component: 组件名称
    - material: 材料（如 PEC, Copper (pure)）
    - x_min1, x_max1, y_min1, y_max1, z1: 第一个轮廓的坐标
    - x_min2, x_max2, y_min2, y_max2, z2: 第二个轮廓的坐标
    - tangency: 正切值（0=无）
    - minimize_twist: 是否最小化扭曲

    示例:
    create_loft_sweep(name="horn_shell", component="HornAntenna", material="PEC",
                     x_min1=-10, x_max1=10, y_min1=-10, y_max1=10, z1=50,
                     x_min2=-35, x_max2=35, y_min2=-35, y_max2=35, z2=100)
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 1. 创建两个轮廓的零厚度实体
    profile1_name = f"_profile1_{name}"
    profile2_name = f"_profile2_{name}"

    # 定义第一个轮廓（零厚度）
    VBA_code_profile1 = [
        "With Brick",
        f'    .Name "{profile1_name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Xrange "{x_min1}", "{x_max1}"',
        f'    .Yrange "{y_min1}", "{y_max1}"',
        f'    .Zrange "{z1}", "{z1}"',
        "    .Create",
        "End With",
    ]
    sCommand_profile1 = line_break.join(VBA_code_profile1)
    project.modeler.add_to_history(
        f"Create Profile1:{profile1_name}", sCommand_profile1
    )

    # 定义第二个轮廓（零厚度）
    VBA_code_profile2 = [
        "With Brick",
        f'    .Name "{profile2_name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Xrange "{x_min2}", "{x_max2}"',
        f'    .Yrange "{y_min2}", "{y_max2}"',
        f'    .Zrange "{z2}", "{z2}"',
        "    .Create",
        "End With",
    ]
    sCommand_profile2 = line_break.join(VBA_code_profile2)
    project.modeler.add_to_history(
        f"Create Profile2:{profile2_name}", sCommand_profile2
    )

    # 2. 按正确顺序选择面（先 profile2 再 profile1，与 loft 方向一致）
    # Pick face for profile2 (output/end)
    full_profile2 = f"{component}:{profile2_name}"
    sCommand_pick2 = f'Pick.PickFaceFromId "{full_profile2}", "1"'
    project.modeler.add_to_history(
        f"Pick face profile2:{profile2_name}", sCommand_pick2
    )

    # Pick face for profile1 (input/start)
    full_profile1 = f"{component}:{profile1_name}"
    sCommand_pick1 = f'Pick.PickFaceFromId "{full_profile1}", "1"'
    project.modeler.add_to_history(
        f"Pick face profile1:{profile1_name}", sCommand_pick1
    )

    # 3. 执行 loft
    VBA_code_loft = [
        "With Loft",
        "    .Reset",
        f'    .Name "{name}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Tangency "{tangency}"',
        f'    .Minimizetwist "{"true" if minimize_twist else "false"}"',
        "    .CreateNew",
        "End With",
    ]
    sCommand_loft = line_break.join(VBA_code_loft)
    project.modeler.add_to_history(f"Define Loft:{name}", sCommand_loft)

    # 删除临时0厚度轮廓实体
    for temp_name in [profile1_name, profile2_name]:
        sCommand_delete = f'Solid.Delete "{component}:{temp_name}"'
        project.modeler.add_to_history(f"Delete temp:{temp_name}", sCommand_delete)

    return {
        "status": "success",
        "message": f"Loft sweep {name} 创建成功（临时轮廓已删除）",
    }


@mcp.tool()
def create_hollow_sweep(
    name: str,
    component: str,
    material: str,
    x_min1: float,
    x_max1: float,
    y_min1: float,
    y_max1: float,
    z1: float,
    x_min2: float,
    x_max2: float,
    y_min2: float,
    y_max2: float,
    z2: float,
    wall_thickness: float = 2.0,
    tangency: int = 0,
    minimize_twist: bool = True,
):
    """
    创建中空放样实体（复合工具，一次性完成外壳+内腔+布尔运算）

    这是一个复合工具，自动完成以下步骤:
    1. 创建外轮廓1和2
    2. 创建内轮廓1和2（各向内缩进 wall_thickness）
    3. 执行两次 loft 生成外壳和内腔
    4. 执行布尔差集得到中空结构

    参数:
    - name: 放样生成的实体名称
    - component: 组件名称
    - material: 材料（如 PEC, Copper (pure)）
    - x_min1, x_max1, y_min1, y_max1, z1: 外轮廓1的坐标
    - x_min2, x_max2, y_min2, y_max2, z2: 外轮廓2的坐标
    - wall_thickness: 壁厚（默认2mm）
    - tangency: 正切值（0=无）
    - minimize_twist: 是否最小化扭曲

    示例:
    create_hollow_sweep(name="horn", component="HornAntenna", material="PEC",
                       x_min1=-10, x_max1=10, y_min1=-10, y_max1=10, z1=50,
                       x_min2=-35, x_max2=35, y_min2=-35, y_max2=35, z2=100,
                       wall_thickness=2.0)
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 计算内轮廓（各边向内缩进 wall_thickness）
    inner_x_min1 = x_min1 + wall_thickness
    inner_x_max1 = x_max1 - wall_thickness
    inner_y_min1 = y_min1 + wall_thickness
    inner_y_max1 = y_max1 - wall_thickness

    inner_x_min2 = x_min2 + wall_thickness
    inner_x_max2 = x_max2 - wall_thickness
    inner_y_min2 = y_min2 + wall_thickness
    inner_y_max2 = y_max2 - wall_thickness

    # 轮廓名称
    outer_p1 = f"_outer_p1_{name}"
    outer_p2 = f"_outer_p2_{name}"
    inner_p1 = f"_inner_p1_{name}"
    inner_p2 = f"_inner_p2_{name}"
    outer_loft = f"_outer_{name}"
    inner_loft = f"_inner_{name}"

    # ========== 1. 创建外轮廓 ==========
    for p_name, xmin, xmax, ymin, ymax, z in [
        (outer_p1, x_min1, x_max1, y_min1, y_max1, z1),
        (outer_p2, x_min2, x_max2, y_min2, y_max2, z2),
    ]:
        VBA_code = [
            "With Brick",
            f'    .Name "{p_name}"',
            f'    .Component "{component}"',
            f'    .Material "{material}"',
            f'    .Xrange "{xmin}", "{xmax}"',
            f'    .Yrange "{ymin}", "{ymax}"',
            f'    .Zrange "{z}", "{z}"',
            "    .Create",
            "End With",
        ]
        sCommand = line_break.join(VBA_code)
        project.modeler.add_to_history(f"Create:{p_name}", sCommand)

    # ========== 2. 创建内轮廓 ==========
    for p_name, xmin, xmax, ymin, ymax, z in [
        (inner_p1, inner_x_min1, inner_x_max1, inner_y_min1, inner_y_max1, z1),
        (inner_p2, inner_x_min2, inner_x_max2, inner_y_min2, inner_y_max2, z2),
    ]:
        VBA_code = [
            "With Brick",
            f'    .Name "{p_name}"',
            f'    .Component "{component}"',
            f'    .Material "{material}"',
            f'    .Xrange "{xmin}", "{xmax}"',
            f'    .Yrange "{ymin}", "{ymax}"',
            f'    .Zrange "{z}", "{z}"',
            "    .Create",
            "End With",
        ]
        sCommand = line_break.join(VBA_code)
        project.modeler.add_to_history(f"Create:{p_name}", sCommand)

    # ========== 3. 外壳 Loft ==========
    # Pick outer_p2 first (end), then outer_p1 (start)
    project.modeler.add_to_history(
        f"Pick:{outer_p2}", f'Pick.PickFaceFromId "{component}:{outer_p2}", "1"'
    )
    project.modeler.add_to_history(
        f"Pick:{outer_p1}", f'Pick.PickFaceFromId "{component}:{outer_p1}", "1"'
    )

    VBA_code_outer = [
        "With Loft",
        "    .Reset",
        f'    .Name "{outer_loft}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Tangency "{tangency}"',
        f'    .Minimizetwist "{"true" if minimize_twist else "false"}"',
        "    .CreateNew",
        "End With",
    ]
    project.modeler.add_to_history(
        f"Loft:{outer_loft}", line_break.join(VBA_code_outer)
    )

    # ========== 4. 内腔 Loft ==========
    # Pick inner_p2 first (end), then inner_p1 (start)
    project.modeler.add_to_history(
        f"Pick:{inner_p2}", f'Pick.PickFaceFromId "{component}:{inner_p2}", "1"'
    )
    project.modeler.add_to_history(
        f"Pick:{inner_p1}", f'Pick.PickFaceFromId "{component}:{inner_p1}", "1"'
    )

    VBA_code_inner = [
        "With Loft",
        "    .Reset",
        f'    .Name "{inner_loft}"',
        f'    .Component "{component}"',
        f'    .Material "{material}"',
        f'    .Tangency "{tangency}"',
        f'    .Minimizetwist "{"true" if minimize_twist else "false"}"',
        "    .CreateNew",
        "End With",
    ]
    project.modeler.add_to_history(
        f"Loft:{inner_loft}", line_break.join(VBA_code_inner)
    )

    # ========== 5. 布尔差集 ==========
    # Outer - Inner = Hollow structure
    full_outer = f"{component}:{outer_loft}"
    full_inner = f"{component}:{inner_loft}"
    sCommand = f'Solid.Subtract "{full_outer}", "{full_inner}"'
    project.modeler.add_to_history(f"BooleanSubtract:{name}", sCommand)

    # ========== 6. 删除临时0厚度轮廓实体 ==========
    temp_entities = [outer_p1, outer_p2, inner_p1, inner_p2]
    for temp_name in temp_entities:
        sCommand_delete = f'Solid.Delete "{component}:{temp_name}"'
        project.modeler.add_to_history(f"Delete temp:{temp_name}", sCommand_delete)

    return {
        "status": "success",
        "message": f"中空放样 {name} 创建成功（临时轮廓已删除）",
    }


# ---------- 材料定义（1个）----------


def read_mtd_file(file_path):
    """读取.mtd文件内容"""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception:
        return None


def parse_mtd_definition(mtd_content):
    """解析.mtd文件中的[Definition]部分"""
    commands = []
    lines = mtd_content.split("\n")
    in_definition = False
    for line in lines:
        line = line.strip()
        if line == "[Definition]":
            in_definition = True
            continue
        elif line.startswith("[") and line.endswith("]"):
            break
        if in_definition and line:
            commands.append(line)
    return commands


def generate_material_vba(name, definition_commands):
    """从解析后的命令生成材料定义VBA脚本"""
    vba_lines = ["With Material", "    .Reset", f'    .Name "{name}"', '    .Folder ""']
    has_create = False
    for command in definition_commands:
        vba_lines.append(f"    {command}")
        if command.strip() == ".Create":
            has_create = True
    if not has_create:
        vba_lines.append("    .Create")
    vba_lines.append("End With")
    return "\n".join(vba_lines)


def _define_material(material_name: str):
    """内部函数：定义材料，带记忆功能"""
    global defined_materials
    if material_name in defined_materials:
        return {"status": "success", "message": f"材料 {material_name} 已经定义过"}
    if material_name in ["Vacuum", "PEC"]:
        defined_materials.add(material_name)
        return {"status": "success", "message": f"材料 {material_name} 是系统默认材料"}

    # Copper 别名映射
    copper_aliases = {"Copper": "Copper (pure)"}
    if material_name in copper_aliases:
        material_name = copper_aliases[material_name]

    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    material_library_path = r"c:/Users/z1376/Documents/CST_MCP/.trae/skills/cst-overview/reference/Materials"
    file_path = material_library_path + "/" + f"{material_name}.mtd"

    mtd_content = read_mtd_file(file_path)
    if not mtd_content:
        return {"status": "error", "message": f"无法读取文件: {file_path}"}

    definition_commands = parse_mtd_definition(mtd_content)
    if not definition_commands:
        return {
            "status": "error",
            "message": f"文件中没有找到[Definition]部分: {file_path}",
        }

    vba_script = generate_material_vba(material_name, definition_commands)
    try:
        project.modeler.add_to_history(f"Define Material: {material_name}", vba_script)
        defined_materials.add(material_name)
        return {
            "status": "success",
            "message": f"材料 {material_name} 已从文件 {file_path} 成功定义",
        }
    except Exception as e:
        return {"status": "error", "message": f"定义材料失败: {str(e)}"}


@mcp.tool()
def define_material_from_mtd(material_name: str):
    """从.mtd文件定义材料"""
    return _define_material(material_name)


# ---------- 高级建模工具（11个）----------


@mcp.tool()
def define_units(
    length_unit: str = "mm",
    frequency_unit: str = "GHz",
    voltage_unit: str = "V",
    resistance_unit: str = "Ohm",
    inductance_unit: str = "nH",
    temperature_unit: str = "degC",
    time_unit: str = "ns",
    current_unit: str = "A",
    conductance_unit: str = "S",
    capacitance_unit: str = "pF",
):
    """定义单位系统"""
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        "With Units",
        f'    .SetUnit "Length", "{length_unit}"',
        f'    .SetUnit "Frequency", "{frequency_unit}"',
        f'    .SetUnit "Voltage", "{voltage_unit}"',
        f'    .SetUnit "Resistance", "{resistance_unit}"',
        f'    .SetUnit "Inductance", "{inductance_unit}"',
        f'    .SetUnit "Temperature", "{temperature_unit}"',
        f'    .SetUnit "Time", "{time_unit}"',
        f'    .SetUnit "Current", "{current_unit}"',
        f'    .SetUnit "Conductance", "{conductance_unit}"',
        f'    .SetUnit "Capacitance", "{capacitance_unit}"',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Define Units", sCommand)
    return {
        "status": "success",
        "message": f"Units defined: {length_unit}, {frequency_unit}",
    }


@mcp.tool()
def rename_entity(old_name: str, new_name: str):
    """重命名几何实体"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Solid.Rename "{old_name}", "{new_name}"'
    project.modeler.add_to_history(f"rename entity: {new_name}", sCommand)
    return {
        "status": "success",
        "message": f"Entity renamed from {old_name} to {new_name}",
    }


@mcp.tool()
def create_component(component_name: str):
    """创建新组件"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Component.New "{component_name}"'
    project.modeler.add_to_history(f"create component: {component_name}", sCommand)
    return {"status": "success", "message": f"Component {component_name} created"}


@mcp.tool()
def define_polygon_3d(name: str, curve: str, points: list):
    """定义3D多边形曲线

    参数说明：
    - name: 多边形名称
    - curve: 所属curve组名称（如 "curve1"）
    - points: 点坐标数组，每个点为 [x, y, z]，支持数字或参数名字符串

    重要：用于 ExtrudeCurve 时必须传入闭合多边形（首尾点相同，共5个点），
    否则 CST 会报错 "The specified curve is not closed and planar"
    """
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        "With Polygon3D",
        "    .Reset",
        "    .Version 10",
        f'    .Name "{name}"',
        f'    .Curve "{curve}"',
    ]
    for point in points:
        if len(point) >= 3:
            VBA_code.append(f'    .Point "{point[0]}", "{point[1]}", "{point[2]}"')
    VBA_code.append("    .Create")
    VBA_code.append("End With")
    sCommand = line_break.join(VBA_code)
    try:
        project.modeler.add_to_history(f"Define Polygon3D: {name}", sCommand)
        return {
            "status": "success",
            "message": f"3D polygon {name} created with {len(points)} points",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"3D多边形创建失败: {str(e)}",
            "command": sCommand,
        }


@mcp.tool()
def define_analytical_curve(
    name: str,
    curve: str,
    law_x: str,
    law_y: str,
    law_z: str,
    param_start: str,
    param_end: str,
):
    """定义解析曲线

    参数说明：
    - name: 曲线名称
    - curve: 曲线所属的curve组名称（如 "curve1"）
    - law_x/law_y/law_z: 参数化方程，支持参数变量如 "C1*exp(R*t)+C2"、"t"、"0"
    - param_start/param_end: 参数 t 的起始和终止值（可用参数名如 "z1"、"Lf+L"）

    示例：定义xoz轴指数曲线，以z为自变量，x为因变量的函数曲线 law_x="C1*exp(R*t)+C2", law_y="0", law_z="t", param_start="z1", param_end="z2"
    """
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    try:
        project.modeler.add_to_history(f"Define AnalyticalCurve: {name}", sCommand)
        return {"status": "success", "message": f"Analytical curve {name} created"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"解析曲线创建失败: {str(e)}",
            "command": sCommand,
        }


@mcp.tool()
def define_extrude_curve(
    name: str,
    component: str,
    material: str,
    curve: str,
    thickness: Union[float, str],
    twist_angle: float = 0.0,
    taper_angle: float = 0.0,
    delete_profile: bool = True,
):
    """定义拉伸曲线（从曲线创建实体）

    参数说明：
    - curve: 截面轮廓曲线名称，格式 "curve1:polygon_name"（必须是闭合多边形），对于一组曲线也可以直接用组名"curve1"等
    """
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    try:
        project.modeler.add_to_history(f"Define ExtrudeCurve: {name}", sCommand)
        return {"status": "success", "message": f"Extrude curve {name} created"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"拉伸曲线创建失败: {str(e)}",
            "command": sCommand,
        }


@mcp.tool()
def transform_shape(
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
):
    """变换形状（镜像或旋转）

    参数说明：
    - shape_name: 目标实体名，支持 "component:name" 或 "name" 格式
    - transform_type: "mirror"（镜像）或 "rotate"（旋转）
    - center_x/y/z: 变换中心坐标（支持参数名如 "0"、"Lf/2"）
    - plane_normal_x/y/z: 镜像平面的法向量（默认YZ平面）；旋转轴方向（默认绕Z轴）
    - angle_x/y/z: 旋转角度（度），旋转时表示绕各轴的旋转分量
    - multiple_objects: 是否变换多个对象
    - repetitions: 重复次数（旋转时每次旋转angle度；例如 angle_z="90", repetitions=3 生成4个副本）
    - destination: 目标组件名（空则原地变换）

    重要：旋转时 angle_z="90", repetitions=3 表示在0°、90°、180°、270°各生成一个副本（共4个）
    """
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    transform_type_map = {"mirror": "Mirror", "rotate": "Rotate"}
    vba_transform = transform_type_map.get(transform_type.lower(), transform_type)

    # 镜像时不需要 Angle 参数
    if transform_type.lower() == "mirror":
        VBA_code = [
            "With Transform",
            "    .Reset",
            f'    .Name "{shape_name}"',
            '    .Origin "Free"',
            f'    .Center "{center_x}", "{center_y}", "{center_z}"',
            f'    .PlaneNormal "{plane_normal_x}", "{plane_normal_y}", "{plane_normal_z}"',
            f'    .MultipleObjects "True"',
            '    .GroupObjects "False"',
            '    .Repetitions "1"',
            '    .MultipleSelection "False"',
            f'    .Destination "{destination}"',
            '    .Material ""',
            '    .AutoDestination "True"',
            f'    .Transform "Shape", "{vba_transform}"',
            "End With",
        ]
    else:
        VBA_code = [
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
            f'    .Transform "Shape", "{vba_transform}"',
            "End With",
        ]
    sCommand = line_break.join(VBA_code)
    try:
        project.modeler.add_to_history(f"transform shape: {shape_name}", sCommand)
        return {
            "status": "success",
            "message": f"Shape {shape_name} transformed with {vba_transform}",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"变换形状失败: {str(e)}",
            "command": sCommand,
        }


@mcp.tool()
def transform_curve(
    curve_name: str,
    transform_type: str,
    center_x: str = "0",
    center_y: str = "0",
    center_z: str = "0",
    plane_normal_x: str = "0",
    plane_normal_y: str = "1",
    plane_normal_z: str = "0",
    multiple_objects: bool = True,
    group_objects: bool = False,
):
    """变换曲线（仅镜像）"""
    global line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"transform curve: {curve_name}", sCommand)
    return {"status": "success", "message": f"Curve {curve_name} mirrored"}


@mcp.tool()
def change_material(shape_name: str, material: str):
    """更改实体的材料"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    material_result = _define_material(material)
    if material_result["status"] == "error":
        return material_result

    sCommand = f'Solid.ChangeMaterial "{shape_name}", "{material}"'
    project.modeler.add_to_history(f"change material: {shape_name}", sCommand)
    return {
        "status": "success",
        "message": f"Material of {shape_name} changed to {material}",
    }


@mcp.tool()
def set_entity_color(
    shape_name: str,
    use_individual_color: bool = True,
    r: int = 192,
    g: int = 192,
    b: int = 192,
):
    """设置实体的颜色"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        f'Solid.SetUseIndividualColor "{shape_name}", {"1" if use_individual_color else "0"}',
        f'Solid.ChangeIndividualColor "{shape_name}", "{r}", "{g}", "{b}"',
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"set color: {shape_name}", sCommand)
    return {"status": "success", "message": f"Color set for {shape_name}"}


# ---------- 仿真设置（7个）----------


@mcp.tool()
def change_parameter(para_name: str, para_value: float):
    """修改模型参数

    注意: CST中参数名不分大小写
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # CST参数名不分大小写，直接传入原参数名
    sCommand = f'StoreDoubleParameter "{para_name}", {para_value}'
    project.modeler.add_to_history("ChangeParameter", sCommand)
    return {"status": "success", "message": f"参数 {para_name} 已修改为 {para_value}"}


@mcp.tool()
def change_frequency_range(min_frequency: str, max_frequency: str):
    """修改仿真频率范围"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Solver.FrequencyRange "{min_frequency}", "{max_frequency}"'
    project.modeler.add_to_history("ChangeFrequency", sCommand)
    return {
        "status": "success",
        "message": f"频率范围已修改为 {min_frequency}-{max_frequency} GHz",
    }


@mcp.tool()
def define_frequency_range(start_freq: float, end_freq: float):
    """定义频率范围"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Solver.FrequencyRange "{start_freq}", "{end_freq}"'
    project.modeler.add_to_history("define frequency range", sCommand)
    return {
        "status": "success",
        "message": f"Frequency range set to {start_freq}-{end_freq}",
    }


@mcp.tool()
def define_background():
    """定义背景"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    vba_code = ["With Background", ".ResetBackground", '.Type "Normal"', "End With"]
    sCommand = line_break.join(vba_code)
    project.modeler.add_to_history("define background", sCommand)
    return {"status": "success", "message": "Background defined"}


@mcp.tool()
def define_boundary():
    """定义边界条件"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    vba_code = [
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
    sCommand = line_break.join(vba_code)
    project.modeler.add_to_history("define boundary", sCommand)
    return {"status": "success", "message": "Boundary conditions defined"}


@mcp.tool()
def define_mesh(
    steps_per_wave_near: int = 5,
    steps_per_wave_far: int = 5,
    steps_per_box_near: int = 5,
    steps_per_box_far: int = 1,
    edge_refinement_ratio: int = 2,
    edge_refinement_buffer_lines: int = 3,
    ratio_limit_geometry: int = 10,
    equilibrate_value: float = 1.5,
    use_gpu: bool = True,
):
    """定义网格"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        "With Mesh",
        '     .MeshType "PBA" ',
        '     .SetCreator "High Frequency"',
        "End With ",
        "With MeshSettings ",
        '     .SetMeshType "Hex" ',
        '     .Set "Version", 1%',
        "     'MAX CELL - WAVELENGTH REFINEMENT",
        f'     .Set "StepsPerWaveNear", "{steps_per_wave_near}" ',
        f'     .Set "StepsPerWaveFar", "{steps_per_wave_far}" ',
        '     .Set "WavelengthRefinementSameAsNear", "1" ',
        "     'MAX CELL - GEOMETRY REFINEMENT",
        f'     .Set "StepsPerBoxNear", "{steps_per_box_near}" ',
        f'     .Set "StepsPerBoxFar", "{steps_per_box_far}" ',
        '     .Set "MaxStepNear", "0" ',
        '     .Set "MaxStepFar", "0" ',
        '     .Set "ModelBoxDescrNear", "maxedge" ',
        '     .Set "ModelBoxDescrFar", "maxedge" ',
        '     .Set "UseMaxStepAbsolute", "0" ',
        '     .Set "GeometryRefinementSameAsNear", "0" ',
        "     'MIN CELL",
        '     .Set "UseRatioLimitGeometry", "1" ',
        f'     .Set "RatioLimitGeometry", "{ratio_limit_geometry}" ',
        '     .Set "MinStepGeometryX", "0" ',
        '     .Set "MinStepGeometryY", "0" ',
        '     .Set "MinStepGeometryZ", "0" ',
        '     .Set "UseSameMinStepGeometryXYZ", "1" ',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex" ',
        '     .Set "PlaneMergeVersion", "2" ',
        "End With",
        "With MeshSettings",
        '     .SetMeshType "Hex" ',
        '     .Set "FaceRefinementOn", "0" ',
        '     .Set "FaceRefinementPolicy", "2" ',
        '     .Set "FaceRefinementRatio", "2" ',
        '     .Set "FaceRefinementStep", "0" ',
        '     .Set "FaceRefinementNSteps", "2" ',
        '     .Set "EllipseRefinementOn", "0" ',
        '     .Set "EllipseRefinementPolicy", "2" ',
        '     .Set "EllipseRefinementRatio", "2" ',
        '     .Set "EllipseRefinementStep", "0" ',
        '     .Set "EllipseRefinementNSteps", "2" ',
        '     .Set "FaceRefinementBufferLines", "3" ',
        '     .Set "EdgeRefinementOn", "1" ',
        '     .Set "EdgeRefinementPolicy", "1" ',
        f'     .Set "EdgeRefinementRatio", "{edge_refinement_ratio}" ',
        '     .Set "EdgeRefinementStep", "0" ',
        f'     .Set "EdgeRefinementBufferLines", "{edge_refinement_buffer_lines}" ',
        '     .Set "RefineEdgeMaterialGlobal", "0" ',
        '     .Set "RefineAxialEdgeGlobal", "0" ',
        '     .Set "BufferLinesNear", "3" ',
        '     .Set "UseDielectrics", "1" ',
        '     .Set "EquilibrateOn", "1" ',
        f'     .Set "Equilibrate", "{equilibrate_value}" ',
        '     .Set "IgnoreThinPanelMaterial", "0" ',
        "End With ",
        "With MeshSettings ",
        '     .SetMeshType "Hex" ',
        '     .Set "SnapToAxialEdges", "1"',
        '     .Set "SnapToPlanes", "1"',
        '     .Set "SnapToSpheres", "1"',
        '     .Set "SnapToEllipses", "1"',
        '     .Set "SnapToCylinders", "1"',
        '     .Set "SnapToCylinderCenters", "1"',
        '     .Set "SnapToEllipseCenters", "1"',
        "End With ",
        "With Mesh ",
        '     .ConnectivityCheck "True"',
        '     .UsePecEdgeModel "True" ',
        '     .PointAccEnhancement "0" ',
        '     .TSTVersion "0"',
        '     .PBAVersion "2023042623" ',
        '     .SetCADProcessingMethod "MultiThread22", "-1" ',
        f'     .SetGPUForMatrixCalculationDisabled "{not use_gpu}" ',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Define Mesh", sCommand)
    return {
        "status": "success",
        "message": f"Mesh defined with steps_per_wave={steps_per_wave_near}, steps_per_box={steps_per_box_near}",
    }


@mcp.tool()
def define_solver(
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
):
    """定义求解器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    VBA_code = [
        'Mesh.SetCreator "High Frequency"',
        "With Solver",
        '     .Method "Hexahedral"',
        f'     .CalculationType "TD-S"',
        f'     .StimulationPort "{stimulation_port}"',
        f'     .StimulationMode "{stimulation_mode}"',
        f'     .SteadyStateLimit "{steady_state_limit}"',
        f'     .MeshAdaption "{"True" if mesh_adaption else "False"}"',
        f'     .AutoNormImpedance "{"True" if auto_norm_impedance else "False"}"',
        f'     .NormingImpedance "{norming_impedance}"',
        f'     .CalculateModesOnly "{"True" if calculate_modes_only else "False"}"',
        f'     .SParaSymmetry "{"True" if s_para_symmetry else "False"}"',
        f'     .StoreTDResultsInCache  "{"True" if store_td_results else "False"}"',
        f'     .RunDiscretizerOnly "{"True" if run_discretizer_only else "False"}"',
        f'     .FullDeembedding "{"True" if full_deembedding else "False"}"',
        f'     .SuperimposePLWExcitation "{"True" if superimpose_plw else "False"}"',
        f'     .UseSensitivityAnalysis "{"True" if use_sensitivity else "False"}"',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Define Solver", sCommand)
    return {"status": "success", "message": "Solver defined"}


@mcp.tool()
def change_solver_type(solver_type: str):
    """更改求解器类型"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'ChangeSolverType("{solver_type}")'
    project.modeler.add_to_history(f"change solver type to {solver_type}", sCommand)
    return {"status": "success", "message": f"Solver type changed to {solver_type}"}


@mcp.tool()
def set_solver_acceleration(
    use_parallelization: bool = True,
    max_threads: int = 1024,
    max_cpu_devices: int = 2,
    remote_calc: bool = False,
    use_distributed: bool = False,
    max_distributed_ports: int = 64,
    distribute_matrix: bool = True,
    mpi_parallel: bool = False,
    auto_mpi: bool = False,
    hardware_accel: bool = True,
    max_gpus: int = 4,
):
    """设置求解器并行计算加速"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
        "With Solver",
        f'     .UseParallelization "{"True" if use_parallelization else "False"}"',
        f'     .MaximumNumberOfThreads "{max_threads}"',
        f'     .MaximumNumberOfCPUDevices "{max_cpu_devices}"',
        f'     .RemoteCalculation "{"True" if remote_calc else "False"}"',
        f'     .UseDistributedComputing "{"True" if use_distributed else "False"}"',
        f'     .MaxNumberOfDistributedComputingPorts "{max_distributed_ports}"',
        f'     .DistributeMatrixCalculation "{"True" if distribute_matrix else "False"}"',
        f'     .MPIParallelization "{"True" if mpi_parallel else "False"}"',
        f'     .AutomaticMPI "{"True" if auto_mpi else "False"}"',
        f'     .HardwareAcceleration "{"True" if hardware_accel else "False"}"',
        f'     .MaximumNumberOfGPUs "{max_gpus}"',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Set Solver Acceleration", sCommand)
    return {"status": "success", "message": "Solver acceleration settings applied"}


@mcp.tool()
def delete_monitor(monitor_name: str):
    """删除监视器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Monitor.Delete "{monitor_name}"'
    project.modeler.add_to_history(f"delete monitor: {monitor_name}", sCommand)
    return {"status": "success", "message": f"Monitor {monitor_name} deleted"}


@mcp.tool()
def set_farfield_monitor(
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
):
    """设置远场监视器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
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
        f'    .EnableNearfieldCalculation "{"True" if enable_nearfield else "False"}"',
        f'    .CreateUsingLinearStep "{start_freq}", "{end_freq}", "{step}"',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Set Farfield Monitor", sCommand)
    return {
        "status": "success",
        "message": f"Farfield monitor set: {start_freq}-{end_freq} GHz",
    }


@mcp.tool()
def set_efield_monitor(
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
):
    """设置电场监视器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Set Efield Monitor", sCommand)
    return {
        "status": "success",
        "message": f"E-field monitor set: {start_freq}-{end_freq} GHz",
    }


@mcp.tool()
def set_background_with_space(
    x_min_space: float = 30,
    x_max_space: float = 30,
    y_min_space: float = 30,
    y_max_space: float = 30,
    z_min_space: float = 50,
    z_max_space: float = 100,
):
    """设置背景空间"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    VBA_code = [
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
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Set Background Space", sCommand)
    return {"status": "success", "message": "Background space settings applied"}


@mcp.tool()
def create_mesh_group(group_name: str, items: list):
    """创建网格组并添加项目"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    sCommand = f'Group.Add "{group_name}", "mesh"'
    project.modeler.add_to_history(f"create mesh group: {group_name}", sCommand)

    for item in items:
        sCommand = f'Group.AddItem "solid${item}", "{group_name}"'
        project.modeler.add_to_history(f"add item to group: {group_name}", sCommand)

    return {
        "status": "success",
        "message": f"Mesh group {group_name} created with {len(items)} items",
    }


@mcp.tool()
def set_fdsolver_extrude_open_bc(enable: bool = True):
    """设置FD求解器展开开放边界"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'FDSolver.ExtrudeOpenBC "{"True" if enable else "False"}"'
    project.modeler.add_to_history("set FDSolver ExtrudeOpenBC", sCommand)
    return {"status": "success", "message": f"FDSolver.ExtrudeOpenBC set to {enable}"}


@mcp.tool()
def set_mesh_fpbavoid_nonreg_unite(enable: bool = True):
    """设置网格避免非正则联合"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Mesh.FPBAAvoidNonRegUnite "{"True" if enable else "False"}"'
    project.modeler.add_to_history("set Mesh.FPBAAvoidNonRegUnite", sCommand)
    return {
        "status": "success",
        "message": f"Mesh.FPBAAvoidNonRegUnite set to {enable}",
    }


@mcp.tool()
def set_mesh_minimum_step_number(num_steps: int = 5):
    """设置网格最小步数"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Mesh.MinimumStepNumber "{num_steps}"'
    project.modeler.add_to_history("set Mesh.MinimumStepNumber", sCommand)
    return {
        "status": "success",
        "message": f"Mesh.MinimumStepNumber set to {num_steps}",
    }


@mcp.tool()
def activate_post_process_operation(operation: str, enable: bool = True):
    """激活后处理操作"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'PostProcess1D.ActivateOperation "{operation}", "{"true" if enable else "false"}"'
    project.modeler.add_to_history(f"activate post process: {operation}", sCommand)
    return {
        "status": "success",
        "message": f"PostProcess1D operation '{operation}' {'activated' if enable else 'deactivated'}",
    }


@mcp.tool()
def set_farfield_plot_cuts(lateral_cuts: list = None, polar_cuts: list = None):
    """设置远场图切割线"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    if lateral_cuts is None:
        lateral_cuts = [("0", "1"), ("90", "1")]
    if polar_cuts is None:
        polar_cuts = [("90", "1")]

    VBA_code = ["With FarfieldPlot", "    .ClearCuts"]
    for phi, active in lateral_cuts:
        VBA_code.append(f'    .AddCut "lateral", "{phi}", "{active}"')
    for theta, active in polar_cuts:
        VBA_code.append(f'    .AddCut "polar", "{theta}", "{active}"')
    VBA_code.append("End With")

    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("set farfield cuts", sCommand)
    return {"status": "success", "message": "Farfield cuts set"}


# ---------- 端口与监视器（4个）----------


@mcp.tool()
def define_port(
    port_number: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    orientation: str,
):
    """定义端口"""
    global call_counts, line_break
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    call_counts["port"] += 1

    param_prefix = f"port_{port_number}_"
    x_min_param = parameter_set(f"{param_prefix}x_min", x_min)["message"].split()[1]
    x_max_param = parameter_set(f"{param_prefix}x_max", x_max)["message"].split()[1]
    y_min_param = parameter_set(f"{param_prefix}y_min", y_min)["message"].split()[1]
    y_max_param = parameter_set(f"{param_prefix}y_max", y_max)["message"].split()[1]
    z_min_param = parameter_set(f"{param_prefix}z_min", z_min)["message"].split()[1]
    z_max_param = parameter_set(f"{param_prefix}z_max", z_max)["message"].split()[1]

    VBA_code = [
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
        f"    .Xrange {x_min_param}, {x_max_param}",
        f"    .Yrange {y_min_param}, {y_max_param}",
        f"    .Zrange {z_min_param}, {z_max_param}",
        '    .XrangeAdd "0.0", "0.0"',
        '    .YrangeAdd "0.0", "0.0"',
        '    .ZrangeAdd "0.0", "0.0"',
        '    .SingleEnded "False"',
        '    .WaveguideMonitor "False"',
        "    .Create",
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history(f"Define Port:{port_number}", sCommand)
    project.modeler.add_to_history("ZoomToStructure", "Plot.ZoomToStructure")
    return {"status": "success", "message": f"Port {port_number} created successfully"}


@mcp.tool()
def define_monitor(start_freq: float, end_freq: float, step: float):
    """定义远场方向图监视器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    VBA_code = [
        "With Monitor",
        ".Reset ",
        '.Domain "Frequency"',
        '.FieldType "Farfield"',
        '.ExportFarfieldSource "False" ',
        '.UseSubvolume "False" ',
        '.Coordinates "Structure" ',
        '.SetSubvolume "-17.7", "17.7", "-17.7", "17.7", "0", "20" ',
        '.SetSubvolumeOffset "10", "10", "10", "10", "10", "10" ',
        '.SetSubvolumeInflateWithOffset "False" ',
        '.SetSubvolumeOffsetType "FractionOfWavelength" ',
        '.EnableNearfieldCalculation "True" ',
        f'.CreateUsingLinearStep "{start_freq}", "{end_freq}", "{step}"',
        "End With",
    ]
    sCommand = line_break.join(VBA_code)
    project.modeler.add_to_history("Define Monitor", sCommand)
    return {"status": "success", "message": f"Farfield monitor created"}


@mcp.tool()
def set_field_monitor(
    field_type: str, start_frequency: str, end_frequency: str, num_samples: str
):
    """设置场监视器"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Monitor.Reset{line_break}Monitor.Domain "Frequency"{line_break}Monitor.FieldType "{field_type}field"{line_break}Monitor.Dimension "Volume"{line_break}Monitor.CreateUsingLinearSamples "{start_frequency}", "{end_frequency}", "{num_samples}"'
    project.modeler.add_to_history(f"Set{field_type}Monitor", sCommand)
    return {
        "status": "success",
        "message": f"{field_type}场监视器已设置，频率范围 {start_frequency}-{end_frequency} GHz",
    }


@mcp.tool()
def set_probe(field_type: str, x_pos: str, y_pos: str, z_pos: str):
    """设置探针"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Probe.Reset{line_break}Probe.AutoLabel 1{line_break}Probe.Field "{field_type}field"{line_break}Probe.Orientation "All"{line_break}Probe.Xpos "{x_pos}"{line_break}Probe.Ypos "{y_pos}"{line_break}Probe.Zpos "{z_pos}"{line_break}Probe.Create'
    project.modeler.add_to_history(f"Set{field_type}Probe", sCommand)
    return {
        "status": "success",
        "message": f"{field_type}场探针已设置于 ({x_pos}, {y_pos}, {z_pos})",
    }


@mcp.tool()
def delete_probe_by_id(probe_id: str):
    """删除探针"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'Probe.DeleteById "{probe_id}"'
    project.modeler.add_to_history(f"DeleteProbe{probe_id}", sCommand)
    return {"status": "success", "message": f"探针 {probe_id} 已删除"}


@mcp.tool()
def show_bounding_box():
    """显示边界框"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = 'Plot.DrawBox "True"'
    project.modeler.add_to_history("switch bounding box", sCommand)
    return {"status": "success", "message": "Bounding box displayed"}


# ---------- 数据导出（4个）----------


@mcp.tool()
def export_s_parameter(file_path: str, format_type: str = "csv"):
    """导出S参数数据"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'SelectTreeItem "1D Results\\S-Parameters"{line_break}ASCIIExport.Reset{line_break}ASCIIExport.FileName "{file_path}"{line_break}ASCIIExport.Execute'
    project.modeler.add_to_history("ExportSParameter", sCommand)
    return {"status": "success", "message": f"S参数已导出至 {file_path}"}


@mcp.tool()
def export_e_field_data(frequency: str, file_path: str):
    """导出电场仿真数据"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'SelectTreeItem "2D/3D Results\\E-Field\\e-field (f={frequency}) [pw]"{line_break}ASCIIExport.Reset{line_break}ASCIIExport.FileName "{file_path}\\E-field-{frequency}GHz.txt"{line_break}ASCIIExport.Execute'
    project.modeler.add_to_history("ExportEField", sCommand)
    return {"status": "success", "message": f"电场数据已导出至 {file_path}"}


@mcp.tool()
def export_surface_current_data(frequency: str, file_path: str):
    """导出表面电流仿真数据"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'SelectTreeItem "2D/3D Results\\Surface Current\\surface current (f={frequency}) [pw]"{line_break}ASCIIExport.Reset{line_break}ASCIIExport.FileName "{file_path}\\Surface-Current-{frequency}GHz.txt"{line_break}ASCIIExport.Execute'
    project.modeler.add_to_history("ExportSurfaceCurrent", sCommand)
    return {"status": "success", "message": f"表面电流数据已导出至 {file_path}"}


@mcp.tool()
def export_voltage_data(voltage_index: str, file_path: str):
    """导出电压监视器数据"""
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    sCommand = f'SelectTreeItem "1D Results\\Voltage Monitors\\voltage{voltage_index} [pw]"{line_break}ASCIIExport.Reset{line_break}ASCIIExport.FileName "{file_path}\\voltage-{voltage_index}.txt"{line_break}ASCIIExport.Execute'
    project.modeler.add_to_history(f"ExportVoltage{voltage_index}", sCommand)
    return {
        "status": "success",
        "message": f"电压数据 (index={voltage_index}) 已导出至 {file_path}",
    }


@mcp.tool()
def export_farfield(
    farfield_name: str, frequency: str, file_path: str, plot_mode: str = "Efield"
):
    """导出远场方向图数据（ASCII格式）

    参数:
        farfield_name: 远场结果名称（不含路径前缀），如 "farfield (f=10) [pw]"
        frequency: 频率值（GHz），如 "10"
        file_path: 导出文件路径（不含扩展名），如 "D:/export/farfield_10GHz"
                   实际导出会自动添加 .txt 扩展名
        plot_mode: 绘图模式，默认为 "Efield"，可选 "Directivity"、"Gain" 等

    示例:
        export_farfield(farfield_name="farfield (f=10) [pw]", frequency="10",
                       file_path="D:/export/farfield_10GHz")
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    # 先用 FarfieldPlot 配置参数
    farfieldplot_code = (
        f'FarfieldPlot.Plottype "3d"{line_break}'
        f'FarfieldPlot.Step "5"{line_break}'
        f'FarfieldPlot.SetColorByValue "True"{line_break}'
        f'FarfieldPlot.SetTheta360 "False"{line_break}'
        f'FarfieldPlot.SetPlotMode "{plot_mode}"{line_break}'
        f'FarfieldPlot.SetScaleLinear "True"{line_break}'
        f'FarfieldPlot.DBUnit "0"{line_break}'
        f'FarfieldPlot.Distance "1"'
    )

    # 选择远场结果树节点并用 FarfieldPlot.Plot 激活，然后用 ASCIIExport 导出
    tree_path = f"Farfields\\{farfield_name}"
    export_code = (
        f'SelectTreeItem "{tree_path}"{line_break}'
        f"With FarfieldPlot{line_break}"
        f'    .Step "5"{line_break}'
        f'    .Plottype "3d"{line_break}'
        f'    .SetPlotMode "{plot_mode}"{line_break}'
        f"    .Plot{line_break}"
        f"End With{line_break}"
        f"With ASCIIExport{line_break}"
        f"    .Reset{line_break}"
        f'    .FileName "{file_path}.txt"{line_break}'
        f"    .Execute{line_break}"
        f"End With"
    )

    # 组合两段代码
    sCommand = farfieldplot_code + line_break + export_code
    project.modeler.add_to_history("ExportFarfield", sCommand)
    return {
        "status": "success",
        "message": f"远场方向图已导出至 {file_path}.txt（plot_mode={plot_mode}）",
    }


@mcp.tool()
def export_farfield_ascii_selecttree(farfield_name: str, file_name: str):
    """按用户确认可用的 SelectTreeItem + ASCIIExport 最小流程导出远场 ASCII

    参数:
        farfield_name: Farfields 节点下的完整结果名，如 "farfield (f=10) [1]"
        file_name: 导出的文件名，如 "farfield_10GHz.txt"

    说明:
        本工具严格采用以下最小导出流程：
        SelectTreeItem("Farfields\\farfield (...) [1]")
        With ASCIIExport
            .Reset
            .FileName "farfield_xxGHz.txt"
            .Execute
        End With
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    tree_path = f"Farfields\\{farfield_name}"
    # 用户已确认可用的最小 VBA 模板（来自 cst-data-export skill）
    sCommand = (
        f'SelectTreeItem "{tree_path}"{line_break}'
        f"With ASCIIExport{line_break}"
        f"    .Reset{line_break}"
        f'    .FileName "{file_name}"{line_break}'
        f"    .Execute{line_break}"
        f"End With"
    )
    project.modeler.add_to_history("ExportFarfieldASCIISelectTree", sCommand)
    return {
        "status": "success",
        "tree_path": tree_path,
        "file_name": file_name,
        "message": f"已按 SelectTreeItem + ASCIIExport 最小流程导出远场：{file_name}",
    }


# ============================================================

# 查询工具（2个）
# ============================================================


@mcp.tool()
def list_entities(component: str = None):
    """列出项目中的所有实体（几何体）

    参数:
    - component: 可选，组件名称过滤（如 "component1"）。不填则返回所有组件下的实体。

    返回:
    - entities: 列表，每项为 {"component": "...", "name": "..."}
    - tree_paths: 原始树路径列表（Components/...）
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]
    try:
        all_items = project.modeler.get_tree_items()
        # 过滤 Components/ 开头的条目，格式通常为 "Components/component1/solid_name"
        entity_paths = [item for item in all_items if item.startswith("Components/")]
        entities = []
        for path in entity_paths:
            parts = path.split("/")
            if len(parts) >= 3:
                comp = parts[1]
                name = "/".join(parts[2:])
                # 如果指定了组件过滤
                if component is None or comp.lower() == component.lower():
                    entities.append({"component": comp, "name": name})
            elif len(parts) == 2:
                # 只有组件名，没有实体（空组件）
                pass
        return {
            "status": "success",
            "count": len(entities),
            "entities": entities,
            "tree_paths": entity_paths,
        }
    except Exception as e:
        return {"status": "error", "message": f"查询实体列表失败: {str(e)}"}


@mcp.tool()
def list_parameters():
    """列出项目中所有参数的名称和当前数值（通过 model3d API，不依赖 VBA）。

    使用 RestoreDoubleParameter(name) 读取参数值，返回 float。
    使用 StoreDoubleParameter / change_parameter 修改参数后，global_parameters 会同步更新。

    返回:
    - parameters: {name: value} 字典，value 为 float
    - count: 参数总数
    - session_parameters: 本次会话通过 API 修改过的参数（参考用）
    """
    project_data = get_project_object()
    if not project_data:
        return {"status": "error", "message": "当前没有活动的项目"}
    project = project_data["project"]

    try:
        m3d = project.model3d
        n = m3d.GetNumberOfParameters()
        params = {}
        for i in range(int(n)):
            try:
                name = m3d.GetParameterName(i)
                try:
                    val = m3d.RestoreDoubleParameter(name)
                    params[name] = round(val, 6) if isinstance(val, float) else val
                except Exception:
                    params[name] = None
            except Exception:
                pass
        return {
            "status": "success",
            "parameters": params,
            "count": len(params),
            "session_parameters": dict(global_parameters),
        }
    except Exception as e:
        return {"status": "error", "message": f"查询参数失败: {str(e)}"}


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("[MCP] advanced_mcp: starting", flush=True)
    mcp.run(transport="stdio")
