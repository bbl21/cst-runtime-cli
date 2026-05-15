[English](README.en.md) | **中文**

# cst-runtime-cli

CST Studio Suite CLI 基础设施层。通过统一 CLI 入口提供建模、仿真、结果读取和远场工具。

```powershell
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true
python <skill-root>\scripts\cst_runtime_cli.py list-tools
```

## 快速开始

需要 **Python 3.13+**、**uv** 和 **CST Studio Suite 2026**。

```powershell
# 自动检测并配置 CST Python 库
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true

# 发现可用工具
python <skill-root>\scripts\cst_runtime_cli.py list-tools
python <skill-root>\scripts\cst_runtime_cli.py list-pipelines
python <skill-root>\scripts\cst_runtime_cli.py describe-tool --tool change-parameter
```

完整文档见 [`skills/cst-runtime-cli/SKILL.md`](skills/cst-runtime-cli/SKILL.md)。

## 包含内容

- **105 个 CLI 工具**：session 管理、建模、仿真、结果、远场
- **自检**：`health-check` 诊断环境，`install-cst-libraries` 配置 CST
- **证据捕获**：`stage-evidence` 捕获操作前后快照用于验证
- **39 个合约测试**：不启动 CST 即可验证 JSON 输出格式

## License

MIT License. 详见 [LICENSE](LICENSE)。
