# CST 建模与结果经验

> 本文档记录已验证的技术经验、背景解释和历史问题。  
> 全局规则以 `AGENTS.md` 为准；执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 建模经验
- 布尔运算实体名使用完整 `component:name` 格式更稳定
- Loft 放样顺序推荐 `pick_face` 先 top 再 bottom；完成后删除零厚度辅助 brick
- `transform_shape` 镜像不需要 `Angle`；旋转时 `repetitions=3` 会生成 4 个方位副本
- `define_port` 的坐标参数应传数值，不传参数表达式字符串
- 四脊脊片建模的已验证做法是：`define_analytical_curve` 与 `define_polygon_3d` 共用一个 curve 组，再用 `define_extrude_curve` 对整个 curve 组拉伸，之后再做合并与旋转复制
- 轮廓设计时，polygon 只补辅助边界，不直接把主曲线首尾用直线短接
- `define_extrude_curve` 的 `curve` 参数传曲线组名，如 `curve1`，不是单条曲线名
- 如果目标是修改现有项目里的真实几何，直接改磁盘上的 `ModelHistory.json` 往往不会让 GUI 同步；更稳妥的方式是删除旧实体后通过 MCP 重新建模
- 四脊标准命名经验：先形成种子脊并镜像合并，重命名为 `ridge_x-`；旋转复制后依次重命名为 `ridge_y-`、`ridge_x+`、`ridge_y+`
- `cst-modeler_list_entities` 在部分 session 中不稳定，验收时更适合结合 `delete_entity`、`rename_entity`、`transform_shape`、`boolean_add` 的返回结果一起判断

## 结果读取与导出经验
- 结果读取后不要保存工程，尤其是在 results 侧读取完成之后
- 常规 1D 结果优先直接通过接口读取，不先走额外导出
- 远场结果通常需要先从真实结果树定位 farfield 名称，再走导出链路
- 常见 farfield 名称格式形如 `farfield (f=10) [1]`，其中 `[1]` 更像端口后缀，不应当成通用编号假设
- 当前远场 ASCII 数据常见采样为：Theta 0-180、Phi 0-355、步进 5 度，共 2664 点
- `project.results` 不是可用的 CST COM API 对象
- `FarfieldPlot.Plot()` 与 ASCII 导出链路之间的激活关系容易踩坑，优先使用项目内已支持的导出工具链

## S11 与 Session 经验
- S11 原始数据是复数，转换到 dB 时应先取幅值，再取对数
- `advanced_mcp`（modeler）与 `cst_results_mcp`（results）是两个独立会话；仿真后 results 不会自动看到 modeler 的内存结果
- 当前更稳定的读取顺序是：modeler 仿真完成 -> `close_project(save=False)` 释放工程 -> results 侧 `close + reopen` -> 再读最新 `run_id`
- 如果某类任务的增益/方向图导出只对当前最新 `run_id` 可靠，且每一步都需要回看方向图变化，则更稳的做法是“一参数组合一个独立 run_xxx”，不要在同一工程里继续堆多个尝试

## 多 run 展示经验
- 多个 run 的展示页更适合拆成两层：主页面只负责指标折线和 run 总览；每个 run 的方向图单独生成子页面，再由主页面聚合
- 如果历史 run 已经只有 farfield TXT、而新 run 是 realized gain grid JSON，可先把两类产物统一解析成同一结构，再生成一致的方向图 cut 页面
- 对多 run 过程展示，flatness 变化更适合用“按频点分线、横轴为 run”的折线图；方向图变化则更适合直接展示 theta-cut，而不是把所有 run 压成一张热力图

## 历史问题与已验证 workaround
- 远场导出后再保存工程，曾导致项目损坏；当前稳定做法是把远场导出放到流程最后，并在导出后 `close(save=False)`
- 远场 VBA 导出前若 results 侧仍持有项目句柄，容易出现文件锁；关闭 results 上下文后再导出更稳定
- 仿真前的冗余 `save_project()` 曾与 orchestrator 逻辑冲突，移除后更稳定
- `quit_cst()` 关闭所有 `DesignEnvironment` 实例后，残留进程问题显著减少
- stdio 模式下向 stdout 输出启动提示会干扰本地 MCP 注册，启动日志更适合走 stderr 或日志系统
