# 任务卡模板

## 用途

用户给 agent 发送一个简短的任务卡（task card），agent 即可开始执行，**无需通读项目文档**。

agent 在收到任务卡后的标准回应：

```
当前 run: run_001
参数: {g: 25, thr: 12.5, ...}
目标指标: 9-11 GHz S11 mean = -18.3 dB
最优指标: -18.3 dB (run_001)
是否停止: 否，继续优化
停止原因: 目标值 ≤ -40 dB 未达到，轮次未超限
```

## 任务卡字段

| 字段 | 是否必填 | 格式示例 | 说明 |
|------|---------|---------|------|
| `task_id` | 必填 | `task_011_ref0_s11_optimization` | 目录名，小写加下划线 |
| `source_project` | 必填 | `ref/ref_model/ref_0/ref_0.cst` | 蓝本 CST 工程，只读 |
| `parameters` | 必填 | `[{"name":"g","min":20,"max":30,"step":0.5,"initial":25}]` | 变量名、范围、步进、初始值 |
| `target_metric` | 必填 | `"9-11 GHz S11 mean ≤ -40 dB"` | 定量停止条件 |
| `max_rounds` | 必填 | `15` | 不含 baseline |
| `farfield` | 可选 | `{"frequency":10, "cut_axis":"Phi", "plot_mode":"Realized Gain"}` | 末端验证 |
| `pipeline` | 可选 | `CLI` / `MCP` | 执行链路，默认 CLI |
| `stopping` | 可选 | `{"no_improvement_rounds":3, "target_value":-40}` | 早停参数，默认连续 3 轮无改善 |

## 任务卡 JSON 示例

```json
{
  "task_id": "task_011_ref0_s11_optimization",
  "source_project": "C:/path/to/ref/ref_model/ref_0/ref_0.cst",
  "parameters": [
    {"name": "g", "min": 20, "max": 30, "step": 0.5, "initial": 25},
    {"name": "thr", "min": 10, "max": 15, "step": 0.5, "initial": 12.5}
  ],
  "target_metric": "9-11 GHz S11 mean <= -40 dB",
  "max_rounds": 15,
  "farfield": {
    "frequency": 10,
    "plot_mode": "Realized Gain"
  },
  "pipeline": "CLI",
  "stopping": {
    "no_improvement_rounds": 3,
    "target_value": -40
  }
}
```

## agent 执行契约

1. 收到任务卡后，先创建 `tasks/task_id/` + `task.json`
2. 每个变量值只保存一次（初始值和最优点）；无需每轮记录全部历史
3. 每轮只用 `prepare-run` 创建新 run，不覆盖旧 run
4. 仿真→close(modeler, save=False)→results 刷新→读指标，作为一轮完整单位
5. 每轮输出一条摘要给用户

## 验收清单

- [ ] task.json 存在且字段完整
- [ ] baseline run 有 S11 JSON
- [ ] 每轮有独立的 run_xxx 目录
- [ ] status.json 标记为 validated
- [ ] 无 `.lok` 残留
- [ ] （可选）远场产物存在且 unit=dBi
- [ ] 项目已关闭、CST 进程已清理（残留只记录为 `nonblocking_access_denied_residual`）
