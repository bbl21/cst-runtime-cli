# 首次初始化手册

安装 Skill 后，agent 自动执行以下流程使环境就绪。

## 自动流程

```powershell
# 1. 全量自检 + 自动修复
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true

# 2. 安装依赖到虚拟环境
uv sync

# 3. 确认就绪
uv run python -m cst_runtime doctor
```

`health-check --auto-fix true` 自动诊断并修复：
- Python 版本（≥3.12）
- uv 包管理器
- 工作区初始化（`init-workspace`）
- CST 安装扫描 + pyproject.toml 配置
- Python 导入验证

`health-check` 返回 `overall=blocked` 时 agent 停止，展示 `user_instructions`。

`health-check` + `uv sync` 通过后执行：
```powershell
# 发现工具和管道
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
```

## 入口模式

| 模式 | 命令 | 条件 |
|---|---|---|
| 引导 | `python <skill-root>\scripts\cst_runtime_cli.py` | 首次运行，无包依赖 |
| 生产 | `uv run python -m cst_runtime` | `uv sync` 后 |

## 上下游工具安装

### Python 3.12+

```powershell
# 静默安装（仅当前用户）
python-3.12.7-amd64.exe /quiet InstallAllUsers=0 PrependPath=1
```

Python 安装后若 `python` 仍不可用，注销重登录或手动刷新 PATH。

### uv 包管理器

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### CST Studio Suite 2026

需 GUI 安装 + 商业许可。安装后确认 `python_cst_libraries` 目录存在于：
```
C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries
```

## 常见问题

### health-check 报 Python 版本不足
运行 `python --version` 确认。如果版本 < 3.12，安装 Python 3.12+。

### pyproject.toml 创建失败
检查工作区目录写权限，或手动创建空 `pyproject.toml` 后重试。

### CST 导入验证失败
确认 CST Studio Suite 2026 已安装，`python_cst_libraries` 路径正确。
可指定自定义路径：
```powershell
python <skill-root>\scripts\cst_runtime_cli.py install-cst-libraries --cst-path "D:\CST\AMD64\python_cst_libraries"
```

### uv sync 失败
确认 `pyproject.toml` 存在、Python ≥3.12、网络正常。
