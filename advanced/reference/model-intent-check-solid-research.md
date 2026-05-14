# LEAM 调研与 Check Solid 设计结论

> 本文是一次研究结论沉淀，不是全局规则源。  
> 全局红线仍以 `AGENTS.md` 为准；正式执行流程仍以当前维护的执行 Skill 和对应 MCP/runtime 文档为准。

## 状态

- 日期：2026-05-02
- 状态：`reference`
- 主题：LEAM 论文代码调研、CST_MCP 建模工具复用、Check Solid / model intent validator 设计
- 适用范围：讨论“自然语言需求 -> 建模意图 -> CST 建模 -> 仿真优化”闭环时，判断当前最该补哪一层

## 结论摘要

这次调研确认：LEAM 当前开源代码的主要价值不是优化器，而是一个把 LLM 建模过程拆成多个受控阶段的建模工作流。

对 CST_MCP 来说，当前真正缺少的不是建模工具，也不是优化框架，而是位于两者之间的 **Check Solid / model intent validator**：

```text
自然语言需求
  -> LLM 生成结构化 model_intent
  -> Check Solid 做准入校验、问题归因、修复路由
  -> MCP 建模工具按结构化输入执行
  -> CST_MCP 优化框架执行仿真、指标读取、参数探索
```

因此，后续不应回到“让 LLM 直接调用建模工具一口气建完整模型”的路线。更稳的路线是让 LLM 输出可检查的结构化意图，由 Check Solid 先挡住几何、材料、参数、布尔关系和仿真设置中的明显错误，再交给现有 MCP 建模工具执行。

## LEAM 源码调研结论

LEAM 不是训练代码，也不是完整论文优化链的开源实现。它更像一个 LLM 驱动的天线建模工作台：

- 通过 desktop workflow 组织 CST/HFSS 建模步骤
- 通过 LLM caller 调 OpenAI Responses API 生成结构化 JSON 或脚本
- 通过 backend generator 生成 CST VBA 或 HFSS/PyAEDT 脚本
- 通过 artifacts/workspace/session store 保存中间产物
- 通过 Check Solid 对 solids、parameters、materials 等结构化产物做局部一致性检查

LEAM 代码中能看到参数生成、材料生成、solids 生成、尺寸推断、3D/2.5D 建模脚本、布尔运算、桌面流程编排和执行 runner。

但在当前开源仓库中，没有看到论文描述的完整优化链：

- 没有可用的 `ParaControl` 优化参数控制模块
- 没有可用的 `Interface` 优化接口文件生成模块
- 没有可用的 `ConfigOpt` 优化配置模块
- 没有可用的 `SB-SADEA` 优化器实现
- 没有完整的“建模完成后自动进入代理模型辅助差分进化优化”的生产代码路径

所以 LEAM 对 CST_MCP 的直接参考价值集中在“建模前置结构化”和“Check Solid 校验”，不是优化执行。

## 对 CST_MCP 的重新定位

结合当前 CST_MCP 现状，应把系统分成四层：

| 层次 | 责任 | 当前判断 |
| --- | --- | --- |
| LLM 需求理解层 | 把自然语言需求转成结构化建模意图和优化约束 | 可以做，但必须输出可检查结构 |
| Check Solid 准入层 | 校验建模意图能否安全交给 CST 建模工具 | 当前关键缺口 |
| MCP 建模工具层 | 执行确定性的 CST 建模、材料、布尔、端口等操作 | 用户确认已有完整工具，应复用 |
| CST_MCP 优化层 | 正式 task/run、仿真、结果读取、指标计算、参数优化 | 当前已有优化框架，应继续作为主链 |

这意味着：建模工具之前被弃用，不是因为 MCP 工具本身没有价值，而是因为 LLM 直接建模的上游输入不可靠。把 LLM 直接放到工具调用层，会把空间几何错误、参数引用错误、材料缺失、布尔顺序错误和仿真设置遗漏一次性放大。

正确切入点不是重写建模工具，而是新增一层明确的、可审计的准入检查。

## 建议的 model_intent 结构

Check Solid 不应直接吃自由文本，也不应只检查最终 CST 工程。它应优先检查一个稳定的中间结构，例如：

```json
{
  "device_type": "antenna",
  "coordinate_system": {
    "unit": "mm",
    "origin": "center"
  },
  "parameters": [
    {
      "name": "patch_w",
      "value": 28.0,
      "unit": "mm",
      "role": "geometry",
      "bounds": [20.0, 40.0]
    }
  ],
  "materials": [
    {
      "name": "Rogers RT5880",
      "role": "substrate",
      "required_properties": ["epsilon_r", "loss_tangent"]
    }
  ],
  "solids": [
    {
      "name": "patch",
      "component": "antenna",
      "kind": "brick",
      "material": "copper",
      "parameters_used": ["patch_w"],
      "bbox": {
        "xmin": "-patch_w/2",
        "xmax": "patch_w/2",
        "ymin": "-patch_l/2",
        "ymax": "patch_l/2",
        "zmin": "sub_h",
        "zmax": "sub_h + copper_t"
      }
    }
  ],
  "boolean_operations": [
    {
      "operation": "subtract",
      "target": "antenna:patch",
      "tool": "antenna:slot_1"
    }
  ],
  "simulation_setup": {
    "ports": [],
    "boundaries": {},
    "frequency_range_ghz": [3.1, 10.6],
    "monitors": []
  },
  "optimization_contract": {
    "variables": [],
    "objectives": [],
    "constraints": []
  }
}
```

这个结构不是最终格式，只是建议方向。关键是：LLM 输出的东西必须能被程序逐项验证、逐项路由、逐项修复，而不是只能在 CST 报错后倒查。

## Check Solid 应检查什么

第一版 Check Solid 建议从确定性检查开始，不急于加入新的 LLM 评审。

### 1. Schema 与命名完整性

- 必填字段是否存在
- entity/component/material/parameter 名称是否唯一
- entity 引用是否都能解析到定义
- component:name 是否满足现有建模工具的命名约定
- JSON 是否能稳定序列化并写入 run 目录

### 2. 参数契约

- 所有表达式引用的参数是否已定义
- 参数单位是否一致
- 参数 bounds 是否存在明显反常，例如下界大于上界
- 优化变量是否确实映射到几何或仿真设置
- 只读参数、派生参数、优化变量是否分层清楚

### 3. 材料契约

- 每个 solid 的 material 是否存在
- 材料是否能映射到 CST 库材料或项目自定义材料
- 关键材料属性是否齐全
- PEC、copper、substrate、vacuum/air 等角色是否明确

### 4. 几何实体检查

- bbox 是否有正体积或符合 2.5D 零厚度约定
- xmin/xmax、ymin/ymax、zmin/zmax 是否顺序正确
- 尺寸是否明显违反物理尺度
- 关键实体是否重叠、悬空、穿透或缺少接触关系
- 天线常见结构是否缺少 substrate、ground、radiator、feed 等核心部件

### 5. 布尔操作检查

- target/tool 是否存在
- 布尔顺序是否依赖尚未创建的实体
- subtract tool 是否与 target 有交集
- add/merge 后的命名是否可追踪
- 会被删除或合并的临时实体是否标记为临时对象

### 6. 仿真设置检查

- 频段是否存在且单位明确
- 端口、边界、激励、monitor 是否与器件类型匹配
- 优化所需的 S 参数、farfield、gain、directivity 等结果是否有对应读取路径
- 若约束使用 dBi 增益，必须声明使用 `Realized Gain`、`Gain` 或 `Directivity`，不能把 `Abs(E)` 当成 dBi

### 7. 优化准入检查

- 优化变量是否有明确 bounds 和初始值
- 目标函数是否能从已有 results 工具读取
- 约束是否能计算，并能写入 run 的 analysis/stages
- baseline 是否可跑通
- 每次候选参数变更后是否能读回参数并确认 project identity

## 问题路由格式

Check Solid 的输出不应只是 pass/fail。它应该返回可执行的问题列表：

```json
{
  "status": "blocked",
  "issues": [
    {
      "id": "SOLID_BBOX_001",
      "severity": "error",
      "category": "solids",
      "entity": "antenna:patch",
      "message": "xmax must be greater than xmin after expression evaluation",
      "route_to": "dimensions",
      "suggested_action": "revise parameter expressions for patch_w"
    }
  ],
  "summary": {
    "errors": 1,
    "warnings": 0,
    "ready_for_modeling": false,
    "ready_for_optimization": false
  }
}
```

建议的 `category` / `route_to`：

- `parameters`
- `materials`
- `solids`
- `dimensions`
- `boolean_operations`
- `simulation_setup`
- `optimization_contract`
- `cst_project`
- `results_contract`

这样 agent 可以按类别回到对应生成阶段修复，而不是重新生成整套模型。

## 与现有正式 run 的关系

Check Solid 应接入正式 task/run，而不是形成新的旁路链。

建议落盘位置：

```text
tasks/task_xxx_slug/runs/run_xxx/
  stages/
    model_intent.json
    check_solid_report.json
  logs/
    check_solid.log
  analysis/
    check_solid_summary.md
```

建议状态语义：

- `pass`：可交给 MCP 建模工具执行
- `warning`：可执行，但必须记录非阻塞风险
- `blocked`：不得进入 CST 建模或仿真
- `needs_review`：确定性检查无法判断，需要人工或 LLM 语义评审

## 最小验收标准

第一版 Check Solid 不需要解决所有几何智能问题，但至少应满足：

- 能读取一个 `model_intent.json`
- 能输出结构化 `check_solid_report.json`
- 能发现未定义参数、缺失材料、非法 bbox、错误实体引用、布尔引用缺失
- 能区分 `error`、`warning`、`info`
- 能给出 `route_to`
- 能在正式 run 的 `stages/`、`logs/`、`analysis/` 中落盘
- 在 `blocked` 时阻止后续建模工具执行
- 在 `pass` 时把明确的建模输入交给现有 MCP 建模工具

## 后续实施顺序

### Phase 1：确定性 model_intent 检查

先实现纯 Python 检查器，不调用 CST，不调用 LLM。

重点是把输入结构、问题格式、落盘位置和阻断语义稳定下来。

### Phase 2：接入 MCP 建模工具前的准入门

把 Check Solid 放到建模工具调用之前。只有 `pass` 或允许的 `warning` 才继续执行建模。

此阶段要验证：LLM 生成的 model_intent 经修复后，能稳定驱动已有 MCP 建模工具，而不是让 LLM 直接调用建模原语。

### Phase 3：接入 CST 工程与结果契约检查

在几何 intent 通过后，补充 CST 项目级检查：

- 工程能否打开
- project identity 是否清楚
- 参数能否 list/read/write/readback
- baseline 是否能启动
- results 侧是否能刷新并读取目标指标
- 远场或增益指标是否走真实 gain/dBi 路径

### Phase 4：可选 LLM 语义评审

只有在确定性检查稳定后，再考虑加入 LLM 作为语义 reviewer。

LLM reviewer 的输入应是 `model_intent.json` 和确定性检查报告，输出仍应是结构化 issues，而不是自由文本建议。

## 明确不做

- 不恢复“LLM 直接调用 CST 建模工具生成完整模型”的路线
- 不把 LEAM 代码当作可直接替换 CST_MCP 优化框架的实现
- 不在 Check Solid 尚未通过时启动仿真或优化
- 不把字段强行做成黑盒长流程，关键判断点仍应返回结构化事实
- 不把 `Abs(E)` 当成 dBi 增益验收依据
- 不把本地调研路径或个人环境信息写入公开文档

## 一句话判断

LEAM 给出的启发是：LLM 建模不能靠一次性生成 CST 脚本硬冲，而要通过结构化中间层和 Check Solid 把错误挡在建模执行之前。

CST_MCP 当前最值得补的就是这层准入门：它把已有建模工具重新纳入系统，同时保护已经成型的优化主链不被不可靠建模输入污染。
