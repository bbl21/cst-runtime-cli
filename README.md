[English](README.en.md) | **中文**

# CST Runtime CLI

CST Studio Suite 的 AI 自动化交互工具链。通过统一 CLI 入口提供建模、仿真、参数优化、结果读取和远场导出能力，让 AI agent 能够可靠地操作 CST 完成电磁仿真任务。

仓库包含两个 skill：

- **`cst-runtime-cli`** — 基础设施 skill，提供 CLI 工具实现（session 管理、建模、仿真、结果读取、远场导出等），是直接与 CST 交互的底层层。
- **`cst-runtime-optimization`** — 优化 skill，专注参数优化闭环，依赖 `cst-runtime-cli` 执行 CLI 调用，自身仅包含 SKILL.md 定义的流程逻辑。

---

## 前置条件

| 依赖 | 说明 |
|---|---|
| CST Studio Suite 2026 | **必须手动安装**，安装时勾选 "Python libraries" 组件 |
| Python 3.12+ | health-check 可自动安装 |
| uv | health-check 可自动安装 |

> 完整的环境初始化指引（包括 bootstrap、Python 手动安装、常见问题排查）见 [`skills/cst-runtime-cli/references/setup_guide.md`](skills/cst-runtime-cli/references/setup_guide.md)。

## 安装 Skill

仓库包含两个 skill，需分别安装：

### 方式 A：Release 下载（仅 skill 结构，推荐）

从 [Releases](https://github.com/anomalyco/cst-runtime-cli/releases) 下载最新版压缩包，解压到对应工具的 skills 目录：

| AI 工具 | Skills 目录 |
|---------|-------------|
| OpenCode | `%USERPROFILE%\.config\opencode\skills\` |
| Claude Code | `%USERPROFILE%\.claude\skills\` |
| Cursor | `%USERPROFILE%\.cursor\skills\` |
| Trae / Codex | `%USERPROFILE%\.trae\skills\` |
| 通用 | 在工具配置中将 skills 目录指向解压路径 |

解压后结构：
```
skills\
├── cst-runtime-cli\
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── tests/
└── cst-runtime-optimization\
    └── SKILL.md
```

Windows 下也可用符号链接指向解压目录：
```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.config\opencode\skills\cst-runtime-cli" -Target "解压路径\skills\cst-runtime-cli"
```

### 方式 B：Clone 完整仓库

```powershell
git clone https://github.com/anomalyco/cst-runtime-cli.git
```

创建符号链接到对应工具的 skills 目录：

```powershell
# 基础设施 skill（OpenCode 示例，其他工具替换路径前缀）
New-Item -ItemType Junction -Path "%USERPROFILE%\.config\opencode\skills\cst-runtime-cli" -Target ".\skills\cst-runtime-cli"

# 优化 skill
New-Item -ItemType Junction -Path "%USERPROFILE%\.config\opencode\skills\cst-runtime-optimization" -Target ".\skills\cst-runtime-optimization"
```

> 方式 B 适合需要同时修改 skill 源码的场景。

重启 AI 工具或开始新会话后，skill 即生效。

## 快速开始

### 第一步：环境初始化

直接告诉 agent：

> 帮我初始化 CST 运行环境，创建 workspace，完成后告诉我。

agent 会自动完成：`health-check --auto-fix true` → `uv sync` → `doctor` 确认。

**auto-fix 完成后，所有后续命令必须使用 `uv run` 模式**，不可再走系统 Python，否则可能出现库冲突等不可预期结果。

首次使用细节见 [`skills/cst-runtime-cli/references/setup_guide.md`](skills/cst-runtime-cli/references/setup_guide.md)。

### 第二步：告诉 agent 你的需求

```
源工程: C:\path\to\your_project.cst
优化目标: 例如 9-11 GHz S11 ≤ -40 dB
可调参数: 例如 g (20-30, 步进0.5)
```

如果不确定参数名称，agent 会先读取工程参数列表让你确认。

### 常见场景

| 场景 | 需求示例 |
|---|---|
| 优化 S11 | 源工程在 `C:\antennas\my_horn.cst`，优化 9-11 GHz S11 ≤ -40 dB |
| 跑一次仿真 | 帮我跑一下 `C:\antennas\my_horn.cst` 的仿真，看 S11 曲线 |
| 导出远场 | 帮我导出 10 GHz 的远场方向图，Realized Gain |
| 对比 S11 | 两个 run 的 S11 结果，帮我做个对比页面 |

---

## 项目结构

```
cst-runtime-cli/                          # 完整仓库
├── README.md                             # 本文件
├── README.en.md                          # 英文版
├── LICENSE
├── pyproject.toml                        # 根项目（可选）
├── uv.lock
├── .gitignore
│
├── skills/
│   ├── cst-runtime-cli/                  # ← 基础设施 skill（即 release 内容）
│   │   ├── SKILL.md                      # Agent 执行手册
│   │   ├── scripts/
│   │   │   ├── cst_runtime_cli.py        # CLI 入口（bootstrap 用）
│   │   │   ├── pyproject.toml            # cst-runtime 包定义
│   │   │   └── cst_runtime/              # 所有工具实现
│   │   ├── references/
│   │   │   ├── setup_guide.md            # 首次初始化完整手册
│   │   │   ├── task_card_template.md
│   │   │   ├── pipeline_mode_guide.md
│   │   │   └── materials_name_list.txt
│   │   └── tests/
│   │
│   └── cst-runtime-optimization/         # ← 优化 skill
│       └── SKILL.md                      # 优化闭环流程定义
│
└── tests/                                # 集成测试
```

## License

MIT
