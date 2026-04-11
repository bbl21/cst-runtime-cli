# CST_MCP 项目初始化

## 项目概览
- **名称**: CST MCP Project
- **技术栈**: Python 3.13+ / Streamlit / SQLite / MCP / CST Studio Suite 2026
- **包管理**: uv (推荐)
- **CST 版本**: CST Studio Suite 2026
- **MCP 版本**: >=1.25.0

## 沟通偏好
- 中文交流，直接高效
- 一次只做一件事，禁止四面出击
- 工具链优先：生产流程必须走 MCP tools / skills 链路

## 强制规则

### 项目/进程管理
- 任务完成后必须关闭项目 + 杀进程（`close_project` → 杀 CST 进程）
- 复制 CST 项目前必须先关闭项目，否则文件被锁定
- 复制时必须完整复制（`.cst` 文件 + 同名目录），缺一不可

### 远场导出
- 导出远场方向图后不能保存，会报错
- 远场导出必须放在流程最后，导出后 `close(save=False)` 不保存

## 文件/目录规范
- 临时脚本/测试文件：`C:\Users\z1376\Documents\CST_MCP\tmp\`
- 大型文件不进 Git：`.cst`、`.mat` 忽略版本控制
- 参数配置随任务走：记录在 `run_xxx/config.json`
- 命名规范：`task_{序号}_{简短描述}` / `run_{序号}`
- `tmp/` 超过30天的目录定期删除

### 工程文件管理规则
- 参考工程一律视为只读蓝本，禁止直接在 `ref/`、`ref_model/`、`prototype_optimizer/data/workspaces/*/projects/source/` 下修改
- 每次任务必须先创建独立工作副本，再在副本上建模、仿真、导出结果
- 复制 CST 工程时必须完整复制 `.cst` 文件和同名结果目录；禁止只复制单个 `.cst` 文件
- run 目录统一使用：`tasks/task_xxx_slug/runs/run_xxx/`
- `projects/` 只放当前 run 的工程副本与其同名目录，例如 `working.cst` 与 `working/`
- `exports/` 只放导出的 S 参数、远场、场分布、截图等外部结果文件，不存放源工程副本
- `logs/` 只放流程日志、诊断输出、报错记录
- `stages/` 只放阶段状态文件与阶段性元数据，避免混放导出物
- `analysis/` 只放分析结论、计算中间产物、对比表和结构化摘要
- `summary.md` 用于记录本次 run 的结果摘要；`status.json` 用于记录当前状态；`config.json` 用于记录输入参数与运行配置
- 若需要基于已有 run 派生新尝试，创建新的 `run_xxx`，不要覆盖旧 run 的工程和导出结果
- 在复制、移动、清理工程前，必须先关闭项目并结束相关 CST 进程，避免文件锁和结果目录损坏

## 项目结构

```
CST_MCP/
├── advanced_mcp.py          # MCP 建模服务 (modeler)
├── cst_results_mcp.py       # MCP 结果服务 (results)
├── prototype_optimizer/     # 原型优化器 (重点)
│   ├── app.py               # Streamlit 主入口
│   ├── adapters/            # CST 适配器
│   ├── core/                # 核心逻辑 (参数搜索、评分)
│   ├── config/              # 配置文件
│   ├── data/                # 数据目录 (蓝本、工作区)
│   ├── storage/             # 存储层 (SQLite、历史管理)
│   ├── ui/                  # Streamlit UI 组件
│   └── reports/             # 报告导出
├── tools/                   # 工具脚本
│   ├── cleanup_cst.ps1      # CST 清理脚本
│   ├── close_cst_by_name.ps1 # 按名称关闭 CST
│   ├── kill_cst.ps1         # 强制杀 CST 进程
│   ├── plot_farfield.py     # 远场绘图
│   └── ...
├── plot_previews/           # 交互式 HTML 预览输出
├── docs/                    # 文档
├── ref_vba_code/            # VBA 参考代码
├── ref_model/               # 参考模型
├── test/                    # 测试文件
└── test_skill_real/         # Skill 测试
```

## MCP 服务说明

### advanced_mcp (modeler)
- **用途**: CST 建模 + 仿真控制
- **启动**: `uv run advanced_mcp.py`
- **核心工具**:
  - 项目管理: `init_cst_project`, `open_project`, `save_project`, `close_project`, `quit_cst`
  - 仿真控制: `start_simulation`, `pause_simulation`, `stop_simulation`, `is_simulation_running`
  - 建模工具: `define_brick`, `define_cylinder`, `define_cone`, `define_loft`, `boolean_*`
  - 高级建模: `create_loft_sweep`, `create_hollow_sweep`, `define_polygon_3d`, `define_analytical_curve`
  - 参数管理: `parameter_set`
  - 材料定义: `define_material_from_mtd`

### cst_results_mcp (results)
- **用途**: 仿真结果读取 + 可视化
- **启动**: `uv run cst_results_mcp.py`
- **核心工具**:
  - 项目管理: `open_project`, `close_project`, `list_subprojects`, `load_subproject`
  - 结果查询: `list_result_items`, `list_run_ids`, `get_result_data`
  - 可视化: `plot_result`, `plot_farfield`, `plot_from_exported_file`
  - 远场导出: `export_farfield`, `export_farfield_ascii_selecttree`

## 四脊喇叭蓝本
- 路径：`C:/Users/z1376/Documents/CST_MCP/prototype_optimizer/data/workspaces/quad_ridged_horn_v1/projects/source/`
- 文件：`quad_ridged_horn_v1_0.cst` + `quad_ridged_horn_v1_0/` 结果目录
- 只读蓝本，禁止直接修改；测试需完整复制到 tmp/ 再操作

## 架构决策
- 技术栈：Streamlit + SQLite + Python
- CST 角色：仅作仿真 + 结果导出执行器
- 参数搜索、评分、流程编排、历史管理、报告导出均放在外部实现
- 决策：逐步迁移到 Skill 驱动编排，Python 胶水层 (orchestrator/CSTAdapter) 视为过渡期遗留
- 当前重点项目：`C:/Users/z1376/Documents/CST_MCP/prototype_optimizer/`
- 目录结构：`task_xxx_slug/run_xxx/{projects,exports,stages,logs}`

## Skill 管理
- 当前只管理一个正式 Skill：`cst-simulation-optimization`
- 仓库内维护路径：`C:\Users\z1376\Documents\CST_MCP\skills\cst-simulation-optimization\SKILL.md`
- opencode 生效路径：`C:\Users\z1376\.config\opencode\skills\cst-simulation-optimization\SKILL.md`
- 修改 Skill 内容时，优先改仓库内版本，再同步到 opencode 目录；不要只改用户目录副本
- Skill 同步脚本：`C:\Users\z1376\Documents\CST_MCP\tools\sync_opencode_skills.ps1`
- 只同步当前 Skill：`powershell -ExecutionPolicy Bypass -File tools/sync_opencode_skills.ps1 -SkillName "cst-simulation-optimization"`
- 若需要全量同步 `skills/` 目录：`powershell -ExecutionPolicy Bypass -File tools/sync_opencode_skills.ps1`

## CST 建模关键经验
- 布尔运算实体名必须使用完整 `component:name` 格式
- Loft 放样顺序：`pick_face` 先 top 再 bottom；完成后删除零厚度辅助 brick
- `transform_shape`：镜像不需要 Angle；旋转 `repetitions=3` 生成 4 个方位副本
- `define_port` 的坐标参数要求数值型，不能传参数表达式字符串
- 四脊脊片建模：`define_analytical_curve` + `define_polygon_3d` 共用 curve 组形成闭合轮廓 → `define_extrude_curve` 拉伸 → `boolean_add` 合并 → 旋转复制
- 轮廓设计原则：polygon 只补辅助边界，不要用 polygon 直连主曲线起终点把主曲线"短路"
- `define_extrude_curve` 的 `curve` 参数传曲线组名（如 `curve1`），不是单条曲线名
- 若目标是修改现有项目里的真实几何，不要只改磁盘上的 `ModelHistory.json` 指望 GUI 自动同步；优先删除旧实体后通过 MCP 重新建模
- 若四脊脊片需要让指数曲线真正参与实体生成，禁止把 polygon 写成 `x1,z1 -> x0,z0 -> x0,z1 -> x2,z2 -> x1,z1`，否则会用 `x2 -> x1` 直线把解析曲线短路
- 当前环境下四脊脊片的可行做法是：`define_analytical_curve` 与 `define_polygon_3d` 共用同一 curve 组，polygon 用 `x1,z1 -> x0,z0 -> x0,z1 -> x2,z2`，然后 `define_extrude_curve` 对整个 curve 组拉伸，即 `curve="curve1"`，不要写成 `curve="curve1:ridge_profile"`
- 四脊标准命名流程：先生成种子脊并镜像合并，重命名为 `ridge_x-`；旋转复制后依次重命名为 `ridge_y-`、`ridge_x+`、`ridge_y+`
- `cst-modeler_list_entities` 在部分 session 中不可靠，不能作为唯一验收依据；应结合 `delete_entity`、`rename_entity`、`transform_shape`、`boolean_add` 的成功返回判断状态
- `cst-modeler_close_project` 当前有接口不匹配问题；实践中先 `save_project()`，再 `quit_cst()` 结束会话更稳

## CST 结果获取
- 常规 1D 结果：优先直接读取接口
- 远场结果：先定位真实 farfield 名称，再通过 VBA 导出 ASCII/TXT，由外部程序解析
- farfield 名称格式：`farfield (f=10) [1]`（[1] 是端口后缀，不是通用编号）
- 远场数据格式：Theta 0-180°，Phi 0-355°，步进5°，共 2664 点
- `project.results` COM 对象不存在于 CST COM API
- `FarfieldPlot.Plot()` 无法激活 `ASCIIExport`，必须用 VBA 序列

## S11 数据格式
- 返回格式为复数字典 `{'real': ..., 'imag': ...}`，不是 dB 值
- 必须用 `math.hypot(real, imag)` 计算幅值，再用 `20*log10()` 转换

## MCP / COM Session 管理
- `advanced_mcp`（modeler）：`cst.interface.DesignEnvironment.open_project()` 非 interactive
- `cst_results_mcp`（results）：`cst.results.ProjectFile(allow_interactive=True)` 关联 GUI session
- 仿真结果存在于 modeler 内存，不自动传递给 results
- 正确流程：
  1. results 层使用 `allow_interactive=True`
  2. 仿真后强制 `save_project()` 将 modeler 内存结果传播到磁盘
  3. results 层执行 `close + reopen` 刷新 session

## 已修复 Bug 记录
- 远场导出后项目损坏：远场导出放流程最后，导出后 `close(save=False)`
- 远场 VBA 导出失败：导出前 `cst_results_mcp.close_project()` 释放文件锁
- orchestrator 双重 save_project() 冲突：移除仿真前的冗余 save_project() 调用
- CST 进程残留：`quit_cst()` 关闭所有 DesignEnvironment 实例

## 工具脚本目录
`C:\Users\z1376\Documents\CST_MCP\tools/`：
cleanup_cst.ps1, close_cst_by_name.ps1, diag_refresh.py, e2e_clean.py, e2e_final.py, explore_results.py, find_cst.ps1, kill_cst.ps1, plot_farfield.py, read_pdf.py, sync_opencode_skills.ps1

## 环境配置
- Python: 3.13 (见 `.python-version`)
- 虚拟环境：`.venv/` (uv 管理)
- CST 库路径：`C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries`
- 材料定义：`.trae/skills/cst-overview/reference/Materials/*.mtd`

## 常用命令
```bash
# 激活虚拟环境
.venv\Scripts\activate

# 运行 MCP 建模服务
uv run advanced_mcp.py

# 运行 MCP 结果服务
uv run cst_results_mcp.py

# 运行原型优化器
uv run prototype_optimizer/app.py

# 杀 CST 进程
powershell -ExecutionPolicy Bypass -File tools/kill_cst.ps1

# 同步当前 Skill 到 opencode
powershell -ExecutionPolicy Bypass -File tools/sync_opencode_skills.ps1 -SkillName "cst-simulation-optimization"
```
