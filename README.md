[English](README.en.md) | **中文**

# CST Runtime CLI

CST Studio Suite 自动化 CLI 工具链与 AI agent 基础设施。提供 113 个原子命令覆盖建模、仿真、结果读取、参数优化、远场导出全链路，统一的 JSON 契约接口，内建运行时守卫层拦截已知 CST 陷阱。

项目同时以 AI 工具 skill 形式发布，但工具链本身是通用设计——可独立使用、作为 skill 集成、或作为 Python 包二次开发。

---

## 核心能力

| 分类 | 工具数 | 代表工具 |
|------|-------|---------|
| **几何建模** | 42 | `define-brick`, `define-cylinder`, `boolean-subtract`, `change-material`, `transform-shape` |
| **工程操作** | 25 | `change-parameter`, `define-port`, `define-mesh`, `inspect-project`, `capture-3d-view` |
| **结果读取** | 11 | `get-1d-result`, `get-2d-result`, `export-run-results`, `list-run-ids`, `generate-report` |
| **优化** | 11 | `create-study`, `ask-study`, `tell-study`, `run-probe-phase`, `run-optimization-step` |
| **会话管理** | 7 | `cst-session-open`, `cst-session-close`, `cst-session-quit`, `create-blank-project`, `save-project` |
| **远场** | 4 | `export-farfield-grid`, `export-farfield-cut`, `inspect-farfield-monitors`, `inspect-model-view` |
| **工作区** | 4 | `init-workspace`, `init-task`, `health-check`, `install-cst-libraries` |
| **项目身份** | 4 | `verify-project-identity`, `infer-run-dir`, `wait-project-unlocked`, `list-open-projects` |
| **审计** | 3 | `record-stage`, `update-status`, `stage-evidence` |
| **DOE** | 2 | `design-probes`, `analyze-probes` |
| **运行** | 2 | `prepare-run`, `get-run-context` |

113 个工具各含 JSON Schema 定义，入参校验、输出格式统一。

---

## 架构

### 统一契约

所有命令的输入输出格式一致：

- **入参**：JSON Schema 校验，支持 `--args-file <json>`、`--args-json`、stdin、直接标志四种传参方式
- **返回值**：`{status: "success"|"error", message?, ...}` 字典结构，零异常控制流
- **审计落盘**：每次调用自动写入 `stages/` + `logs/production_chain.md`

### 双层命令

- **原子工具**（113 个）：单步操作，可独立调用。
- **管道**：编排示例，将原子工具组合为多步流程（如 `inspect-project`、`prepare-experiment`、`run-experiment`）。

管道仅为使用参考，用户可完全按自己的策略编排工作流。

### 守卫层（Gateway）

内建 10+ 个运行时安全护栏，拦截已知 CST 陷阱：

| 陷阱 | 表现 | 保护 |
|------|------|------|
| T2 | 改参后未重建模型直接仿真 | 拦截并提示 `next_action` |
| T3 | 远场导出后 save 损坏工程 | 强制 `save=False` |
| T4 | S11 复数据当 dB 用 | `20*log10(hypot(real,imag))` 转换 |
| T5 | modeler/results session 混用 | 拒绝跨 session 操作 |
| T8 | Abs(E) 当增益证据 | 拒绝非增益量 |
| T13 | `StoreDoubleParameter` 只改参数表不重建模型 | 操作成功但附加警告 |

每个 trap 触发时附带 `cst_raw` 上下文和 `next_action` 指导，帮助 agent 自动恢复。

> ⚠️ 守卫层基于已知模式设计，不能穷举所有 CST 异常。复杂工作流仍需在关键节点人工复核。

### 双 Session 模型

- **Modeler session**（COM 读写，`cst.interface`）：建模、仿真、参数变更
- **Results session**（只读，`cst.results`）：结果读取、S11/远场导出

严格隔离，禁止混用。仿真后关闭 modeler session，另开 results session 读取数据。

### 本地报告引擎

全内联 HTML/SVG/WebGL 报告，零 JS/CDN 外部依赖。支持 S11 多迹叠加折线图、3D 远场方向图（预计算顶点）、2D 热力图、迭代时间线、收敛分析。

---

## 扩展开发

当前 113 个工具不是能力上限。只要 CST VBA 或 COM API 可执行的操作，即可通过开发包扩展为 CLI 命令。

### 代码生成器路径（新 VBA 对象）

```powershell
# 1. 在 devkit/tools/vba_defs/ 写 TOML 定义
# 2. 运行生成器
uv run python devkit/tools/generate_tools.py
# 3. 产出 gen_<object>.py，在真实 CST 上验证
# 4. 注册到 CLI
```

TOML 定义参考：`devkit/tools/vba_defs/`（10 个参考实现）。

### 手工增强路径（现有工具修改）

改函数签名 + 同步 JSON Schema。新参数带默认值，向后兼容。

### 开发参考

`devkit/references/` 包含完整的 VBA 官方 API 参考（1890 行）、CST Python API 参考（1377 行）、开发流程指南和测试体系说明。

---

## 快速开始

前置条件：CST Studio Suite 2026、Python 3.13+、uv。完整环境初始化见 `skills/cst-runtime-cli/references/setup_guide.md`。

```powershell
# 部署到工作区（一次性）
python bootstrap.py --skill-path <skill-root>\scripts
uv run python -m cst_runtime health-check --auto-fix

# 查看所有可用工具
uv run python -m cst_runtime list-tools

# 了解工程
uv run python -m cst_runtime inspect-project --project-path <project.cst>

# 自行编排工作流
uv run python -m cst_runtime change-parameter --project-path <p.cst> --name g --value 25.0
uv run python -m cst_runtime prepare-experiment --args-file <args.json>
uv run python -m cst_runtime run-experiment --args-file <args.json>
uv run python -m cst_runtime export-run-results --args-file <args.json>
```

---

## 参考工程

`skills/cst-runtime-cli/tests/refs/ref_0/ref_0.cst` — 四脊喇叭天线，8-12 GHz，含完整建模历史（VBA 737 行）。用于在真实 CST 上验证工具和管道。不含仿真结果缓存，可仿真生成或从工作区获取缓存。

---

## 安装与集成

### 方式 A：AI 工具 skill

解压到对应工具的 skills 目录：

| AI 工具 | 路径 |
|---------|------|
| OpenCode / Cursor / Claude Code | `%USERPROFILE%\.config\opencode\skills\`（或其他工具对应路径） |

解压后结构需包含 `skills/cst-runtime-cli/` 和 `skills/cst-runtime-optimization/`。

### 方式 B：直接 CLI 使用

```powershell
git clone https://github.com/bbl21/cst-runtime-cli.git
cd cst-runtime-cli
python skills/cst-runtime-cli/scripts/bootstrap.py --skill-path skills/cst-runtime-cli/scripts
uv run python -m cst_runtime list-tools
```

### 方式 C：Python 包

```python
from cst_runtime.core.session import open_project, close_project
from cst_runtime.core.results import get_1d_result
```

---

## 项目结构

```
cst-runtime-cli/
├── devkit/                              # 扩展开发工具包
│   ├── references/                      # VBA/CST API 官方参考、开发流程指南、测试体系文档
│   └── tools/
│       ├── generate_tools.py            # 代码生成器：TOML → Python
│       ├── vba_defs/                    # TOML 定义（10 个参考实现）
│       └── generated/                   # 生成器输出（不入 git）
│
├── skills/
│   ├── cst-runtime-cli/                 # 基础设施 skill
│   │   ├── SKILL.md                     # Agent 执行手册
│   │   ├── scripts/
│   │   │   ├── bootstrap.py             # 部署引导
│   │   │   ├── pyproject.toml           # 包定义
│   │   │   └── cst_runtime/             # 全部源码
│   │   │       ├── cli/                 # 分发层（dispatch + pipeline 编排）
│   │   │       ├── core/                # 核心模块（session/建模/仿真/结果/远场/守卫/审计/工作区等 20 模块）
│   │   │       ├── tools/               # 工具层（10 模块，113 命令）
│   │   │       ├── render/              # 自包含 HTML/SVG/WebGL 报告
│   │   │       └── analysis/            # 远场解析与平坦度分析
│   │   ├── references/                  # 用户文档
│   │   └── tests/
│   │       ├── refs/ref_0/              # 参考工程（四脊喇叭天线，8-12 GHz）
│   │       └── ...                      # 合约测试、架构不变式、管道合约
│   │
│   └── cst-runtime-optimization/        # 优化 skill（仅 SKILL.md，不含代码）
│       └── SKILL.md
│
└── docs/                                # 设计文档
```

## License

MIT
