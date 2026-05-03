# CLI 工具开发规则

> 目标：将 CLI 当作稳定的软件接口来设计，而不是临时脚本。  
> 一个合格的 CLI 应该同时服务于人类用户、脚本、CI/CD、自动化系统和 agent。

---

## 1. 总体原则

### 1.1 CLI 是稳定 API

CLI 命令一旦发布，就应视为对外接口。

要求：

- 命令、参数、输出格式应保持稳定。
- 破坏性变更必须走版本升级和迁移说明。
- 不允许随意修改已有命令语义。
- 废弃命令应保留一段兼容期，并给出 deprecation warning。

### 1.2 优先保证确定性

CLI 的行为应可预测、可复现。

要求：

- 相同输入应产生相同结构的输出。
- 输出字段名、文件格式、退出码不能随机变化。
- 不依赖隐式 GUI 状态、当前目录副作用或上一次运行状态。
- 所有关键输入必须显式传入或来自清晰的配置来源。

### 1.3 同时面向人和机器

CLI 默认输出应适合人阅读，同时必须提供机器可读模式。

要求：

- 人类模式：简洁、清楚、可读。
- 机器模式：使用 `--json` 或 `--format json`。
- 自动化场景不能依赖解析自然语言文本。

---

## 2. 命令结构规则

### 2.1 命令格式

推荐结构：

```bash
tool <command> <subcommand> [arguments] [options]
```

示例：

```bash
mytool project create demo
mytool project delete demo --force
mytool run start --config config.yaml
mytool result export --format json --output result.json
```

### 2.2 命令语义

命令应遵守以下原则：

- 一个命令只做一件明确的事。
- 命令名使用动词或资源名时，整个工具内必须统一。
- 不应出现多个命令做同一件事但语义不一致。
- 不应把复杂流程隐藏在含糊命令里。

推荐：

```bash
mytool build
mytool test
mytool deploy
mytool export
mytool inspect
```

避免：

```bash
mytool do
mytool process
mytool magic
mytool run-everything
```

### 2.3 子命令分组

当功能较多时，应按资源或动作分组。

示例：

```bash
mytool config get
mytool config set
mytool config list

mytool project create
mytool project inspect
mytool project delete

mytool run start
mytool run status
mytool run cancel
```

---

## 3. 参数规则

### 3.1 常用参数命名

应优先使用通用约定：

```bash
-h, --help
-v, --version
-o, --output
-f, --force
-y, --yes
-q, --quiet
--verbose
--debug
--config
--format
--json
--dry-run
--overwrite
--no-color
```

### 3.2 长短参数

规则：

- 常用选项可提供短参数。
- 低频或危险选项只提供长参数。
- 短参数必须避免冲突。
- 长参数应语义清晰。

推荐：

```bash
mytool export input.txt -o output.json
mytool export input.txt --output output.json
```

### 3.3 参数必须显式

关键输入必须显式传入，不应依赖猜测。

推荐：

```bash
mytool export --input data.csv --output result.json --format json
```

避免：

```bash
mytool export
```

除非工具有明确、可解释、可查看的默认值。

### 3.4 参数校验

CLI 必须在执行前校验参数。

要求：

- 缺少必填参数时给出明确错误。
- 参数类型错误时给出正确格式示例。
- 文件不存在、权限不足、格式不合法时应提前失败。
- 多个参数冲突时应明确指出冲突项。

示例：

```text
Error: --output is required.

Usage:
  mytool export INPUT --output OUTPUT
```

---

## 4. 帮助与文档规则

### 4.1 必须支持帮助命令

每个 CLI 必须支持：

```bash
mytool --help
mytool --version
mytool <command> --help
```

### 4.2 Help 内容要求

`--help` 应包含：

- Usage
- Commands
- Arguments
- Options
- Examples
- Exit codes
- Environment variables
- Config file location

示例：

```text
Usage:
  mytool export INPUT --output OUTPUT [--format json|csv]

Arguments:
  INPUT                  Input file path

Options:
  -o, --output PATH       Output file path
      --format FORMAT     Output format: json, csv
      --overwrite         Overwrite existing output
      --dry-run           Show actions without writing files
  -h, --help              Show help

Examples:
  mytool export data.csv -o result.json --format json
```

### 4.3 示例优先

每个核心命令都应至少提供 2 个示例：

- 最小可用示例
- 常见真实场景示例

---

## 5. 输出规则

### 5.1 stdout 与 stderr 分离

必须遵守：

- `stdout`：命令的主要结果。
- `stderr`：日志、警告、进度、错误信息。

错误示例：

```bash
mytool run --json > result.json
```

如果 `result.json` 中混入进度条、warning、debug log，则不合格。

### 5.2 机器可读输出

涉及状态、结果、查询、导出、诊断的命令，应支持 JSON 输出。

推荐：

```bash
mytool status --json
mytool result inspect --format json
```

JSON 输出应稳定：

```json
{
  "ok": true,
  "status": "completed",
  "output": "result.json"
}
```

### 5.3 输出字段稳定

禁止随意改动 JSON 字段名。

错误：

```json
{ "name": "demo" }
```

下一版变成：

```json
{ "project_name": "demo" }
```

除非这是明确的 breaking change。

### 5.4 颜色输出

规则：

- 彩色输出只能用于人类模式。
- JSON / CSV / pipe 模式禁止颜色控制字符。
- 应支持 `--no-color`。
- 检测到非 TTY 输出时，默认关闭颜色。

---

## 6. 错误处理规则

### 6.1 错误信息必须可诊断

错误信息应包含：

- 发生了什么。
- 为什么失败。
- 用户可以如何修复。
- 必要的上下文信息。

推荐：

```text
Error: output file already exists: result.json

Use --overwrite to replace it, or choose another path with --output.
```

避免：

```text
Error.
Failed.
Unknown problem.
```

### 6.2 机器模式错误

当启用 `--json` 时，错误也应尽量以 JSON 输出。

示例：

```json
{
  "ok": false,
  "error_code": "OUTPUT_EXISTS",
  "message": "Output file already exists: result.json",
  "suggestion": "Use --overwrite or choose another output path."
}
```

### 6.3 Exit Code

必须使用稳定退出码。

推荐：

```text
0    success
1    general error
2    invalid usage or bad arguments
126  permission problem
127  command not found or dependency missing
130  interrupted by Ctrl-C
```

项目可以扩展自定义退出码，但必须文档化。

---

## 7. 自动化规则

### 7.1 不强制交互

CLI 必须支持非交互运行。

不合格：

```bash
mytool deploy
Are you sure? [y/N]
```

如果没有非交互参数，则不适合 CI/CD。

推荐：

```bash
mytool deploy --yes
mytool deploy --dry-run
mytool deploy --non-interactive
```

### 7.2 Prompt 只能作为辅助

交互式 prompt 可以提升体验，但不能成为唯一入口。

要求：

- 所有 prompt 都应能通过参数跳过。
- CI 环境下应自动禁用交互，或要求显式 `--interactive`。
- 缺少必要输入时，非交互模式应直接失败并提示所需参数。

### 7.3 支持 dry-run

涉及写入、删除、部署、发布、远端修改的命令，必须支持：

```bash
--dry-run
```

dry-run 应展示将要执行的动作，并保证不产生实际修改。

---

## 8. 危险操作规则

### 8.1 破坏性操作必须显式

危险操作包括：

- 删除文件或远端资源。
- 覆盖已有结果。
- 发布到生产环境。
- 修改数据库或远端状态。
- 产生费用的操作。

必须提供保护机制：

```bash
--force
--yes
--overwrite
--confirm NAME
--backup
--dry-run
```

### 8.2 默认安全

规则：

- 读操作默认安全。
- 写操作必须明确。
- 删除和覆盖必须二次确认或显式 flag。
- 默认不应删除用户数据。
- 默认不应修改远端生产环境。

### 8.3 覆盖文件规则

当输出文件已存在时，应采用以下策略之一：

- 默认失败，提示使用 `--overwrite`。
- 自动备份，且明确告知备份路径。
- 显式通过 `--output` 指定新路径。

禁止静默覆盖重要文件。

---

## 9. 配置规则

### 9.1 配置优先级

推荐优先级：

```text
命令行参数 > 环境变量 > 配置文件 > 默认值
```

示例：

```bash
mytool run --config ./config.yaml
MYTOOL_TOKEN=xxx mytool run
```

### 9.2 配置位置

配置文件位置必须明确。

推荐：

```text
Linux/macOS: ~/.config/mytool/config.toml
Windows: %APPDATA%\mytool\config.toml
Project: ./mytool.toml
```

### 9.3 配置检查

推荐提供：

```bash
mytool config list
mytool config get KEY
mytool config set KEY VALUE
mytool config path
mytool doctor
```

### 9.4 Secret 管理

禁止：

- 默认把 token 打印到日志。
- 把密码写进 shell history。
- 在错误信息中暴露密钥。
- 在 debug 日志中输出完整 credential。

推荐：

- 使用系统 keychain 或 credential store。
- 显示 secret 时做脱敏。
- 配置文件权限限制为当前用户可读写。

---

## 10. 日志规则

### 10.1 日志等级

应支持：

```bash
--quiet
--verbose
--debug
--log-file PATH
```

推荐日志等级：

```text
quiet
normal
verbose
debug
```

### 10.2 默认输出克制

默认模式不应刷屏。

默认输出只显示：

- 当前关键状态。
- 最终结果。
- 重要警告。
- 明确错误。

详细信息放入：

```bash
--verbose
--debug
--log-file
```

### 10.3 日志不得污染结果

当用户重定向 stdout 时，日志必须进入 stderr 或日志文件。

---

## 11. 状态与文件规则

### 11.1 输出文件结构明确

涉及生成文件的命令，应明确输出位置。

推荐：

```bash
mytool run --output-dir runs/run_001
```

输出目录示例：

```text
runs/run_001/
  command.json
  status.json
  stdout.log
  stderr.log
  artifacts/
  summary.json
```

### 11.2 状态文件

长任务应生成状态文件。

示例：

```json
{
  "run_id": "run_001",
  "status": "success",
  "started_at": "2026-05-03T10:00:00Z",
  "finished_at": "2026-05-03T10:03:20Z",
  "artifacts": [
    "artifacts/result.json"
  ]
}
```

### 11.3 幂等性

重复运行同一命令不应造成不可控副作用。

要求：

- 重复执行要么安全覆盖。
- 要么明确失败。
- 要么跳过已完成步骤。
- 行为必须文档化。

---

## 12. 兼容性规则

### 12.1 版本号

必须支持：

```bash
mytool --version
```

推荐输出：

```text
mytool 1.4.2
```

机器模式：

```bash
mytool version --json
```

```json
{
  "name": "mytool",
  "version": "1.4.2",
  "commit": "abc1234",
  "build_time": "2026-05-03T10:00:00Z"
}
```

### 12.2 破坏性变更

破坏性变更包括：

- 删除命令。
- 修改参数含义。
- 修改默认行为。
- 修改 JSON 输出结构。
- 修改退出码语义。

破坏性变更必须：

- 提升主版本号。
- 写入 changelog。
- 提供迁移说明。
- 尽量保留兼容期。

### 12.3 废弃机制

废弃命令应输出 warning：

```text
Warning: `mytool old-command` is deprecated and will be removed in v2.0.
Use `mytool new-command` instead.
```

---

## 13. 跨平台规则

### 13.1 路径兼容

必须兼容：

- Windows
- macOS
- Linux

要求：

- 不硬编码 `/`。
- 正确处理空格路径。
- 正确处理 Unicode 路径。
- 正确处理相对路径和绝对路径。
- 文档中给出 Windows 和 Unix 示例。

### 13.2 Shell 兼容

注意不同 shell 的差异：

- bash
- zsh
- fish
- PowerShell
- cmd.exe

尤其注意：

- 引号规则。
- 环境变量写法。
- 路径转义。
- 换行符。

### 13.3 终端能力检测

CLI 应检测是否运行在 TTY 中。

规则：

- 非 TTY 下关闭 spinner。
- 非 TTY 下关闭颜色。
- 非 TTY 下避免交互 prompt。
- CI 环境下默认更适合机器读取。

---

## 14. 可发现性规则

### 14.1 自动补全

推荐支持：

```bash
mytool completion bash
mytool completion zsh
mytool completion fish
mytool completion powershell
```

### 14.2 doctor 命令

推荐提供：

```bash
mytool doctor
```

检查内容：

- 依赖是否安装。
- 配置是否有效。
- 认证是否成功。
- 权限是否足够。
- 版本是否兼容。
- 网络或远端服务是否可用。

### 14.3 list / inspect 命令

复杂工具应提供可发现命令：

```bash
mytool list
mytool inspect
mytool status
mytool config list
```

---

## 15. 测试规则

### 15.1 必须测试 CLI 行为

不能只测试内部函数，也要测试命令行入口。

测试内容：

- 参数解析。
- help 输出。
- version 输出。
- 正常命令执行。
- 错误输入。
- stdout / stderr 分离。
- exit code。
- JSON 输出格式。
- 文件生成。
- dry-run 不产生副作用。
- 跨平台路径。

### 15.2 Golden Test

对稳定输出建议使用 snapshot / golden test。

示例：

```bash
mytool status --json
```

应验证：

- JSON 合法。
- 字段存在。
- 字段类型正确。
- 不包含多余日志文本。

### 15.3 CI 测试

CI 中至少覆盖：

- Linux
- Windows
- macOS，若项目需要
- 最低支持版本
- 当前主流版本

---

## 16. 发布规则

### 16.1 安装方式

应至少提供一种稳定安装方式。

常见方式：

```text
Homebrew
apt / yum / dnf
winget
scoop
pip
npm
cargo
go install
standalone binary
Docker image
```

### 16.2 Release 内容

每次 release 应包含：

- 版本号。
- changelog。
- 安装方式。
- 升级说明。
- breaking changes。
- checksum，若发布二进制文件。
- 平台兼容说明。

### 16.3 可回滚

涉及生产环境的 CLI，应考虑：

- 版本固定。
- 旧版本下载。
- 配置迁移。
- 回滚说明。

---

## 17. 安全规则

### 17.1 最小权限

CLI 应只请求完成任务所需权限。

禁止：

- 默认使用管理员权限。
- 默认访问无关目录。
- 默认上传用户文件。
- 默认修改全局系统配置。

### 17.2 敏感信息脱敏

日志中必须脱敏：

- API Key
- Token
- Password
- Cookie
- Private key
- 个人敏感信息

示例：

```text
Token: sk-****abcd
```

### 17.3 网络请求透明

如果 CLI 会访问网络，应明确说明：

- 请求目标。
- 是否上传文件。
- 是否发送匿名统计。
- 如何关闭遥测。

推荐：

```bash
--offline
--no-telemetry
```

---

## 18. Agent / 自动化友好规则

### 18.1 明确机器接口

面向 agent 或自动化系统时，应优先提供：

```bash
--json
--non-interactive
--dry-run
--output
--log-file
```

### 18.2 状态可查询

长流程不应只能看终端输出。

推荐：

```bash
mytool run start --json
mytool run status RUN_ID --json
mytool run logs RUN_ID
mytool run cancel RUN_ID
```

### 18.3 错误可恢复

错误输出应让自动化系统能够判断下一步。

示例：

```json
{
  "ok": false,
  "error_code": "MISSING_CONFIG",
  "recoverable": true,
  "required_action": "set_config",
  "message": "Missing required config: api_key"
}
```

---

## 19. 最低合格标准

一个 CLI 工具达到最低可发布质量，应满足：

```text
[ ] 有清晰 command / subcommand 结构
[ ] 支持 --help
[ ] 支持 --version
[ ] 参数命名符合常见习惯
[ ] stdout / stderr 分离
[ ] 有稳定 exit code
[ ] 错误信息可诊断
[ ] 支持非交互运行
[ ] 危险操作需要显式确认
[ ] 涉及结果查询时支持 --json
[ ] 配置优先级明确
[ ] 不泄露 secret
[ ] 核心 CLI 行为有测试
[ ] 文档中有真实示例
```

---

## 20. 推荐命令模板

### 20.1 基础模板

```bash
mytool --help
mytool --version
mytool doctor

mytool config list
mytool config get KEY
mytool config set KEY VALUE

mytool run start --config config.yaml --output-dir runs/run_001
mytool run status RUN_ID --json
mytool run logs RUN_ID
mytool run cancel RUN_ID

mytool result inspect RUN_ID --json
mytool result export RUN_ID --output result.json --format json
```

### 20.2 危险命令模板

```bash
mytool delete RESOURCE
mytool delete RESOURCE --dry-run
mytool delete RESOURCE --confirm RESOURCE
mytool delete RESOURCE --force
```

### 20.3 输出命令模板

```bash
mytool export INPUT --output OUTPUT
mytool export INPUT --output OUTPUT --overwrite
mytool export INPUT --output OUTPUT --format json
```

---

## 21. 反模式清单

应避免：

```text
[ ] 命令名含糊，例如 do、magic、process-all
[ ] 默认执行破坏性操作
[ ] 静默覆盖用户文件
[ ] 错误信息只有 Failed
[ ] --json 输出混入日志
[ ] 所有日志都打到 stdout
[ ] 强制用户交互确认
[ ] CI 中无法运行
[ ] 参数依赖隐式状态
[ ] 输出格式随版本随机变化
[ ] 没有 --help
[ ] 没有 --version
[ ] 没有测试命令行入口
[ ] debug 日志泄露 token
[ ] 改命令不写 changelog
```

---

## 22. 一句话标准

> 好的 CLI 是稳定、清晰、可组合、可自动化、可诊断、可维护的软件接口。

开发时应始终问：

```text
新手能不能通过 --help 用起来？
熟手能不能高效调用？
脚本能不能稳定解析？
CI 能不能非交互运行？
失败时能不能判断原因并恢复？
未来版本能不能保持兼容？
```
