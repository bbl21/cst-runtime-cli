import json
import math
import os

# 读取 S11 数据
export_path = "C:\\Users\\z1376\\Documents\\CST_MCP\\tasks\\task_006_ref_0_s11_optimization\\runs\\run_001\\exports\\s11_run2.json"

with open(export_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取数据
frequencies = data['xdata']
complex_data = data['ydata']
real_parts = [item['real'] for item in complex_data]
imag_parts = [item['imag'] for item in complex_data]

# 目标频率
target_freq = 10.0

# 查找目标频率附近的数据点
closest_index = min(range(len(frequencies)), key=lambda i: abs(frequencies[i] - target_freq))

# 获取对应的数据
freq = frequencies[closest_index]
real = real_parts[closest_index]
imag = imag_parts[closest_index]

# 计算 S11 dB
mag = math.hypot(real, imag)
s11_db = 20 * math.log10(max(mag, 1e-15))

# 输出结果
print(f"频率: {freq:.6f} GHz")
print(f"S11 (dB): {s11_db:.2f} dB")
print(f"参数组合: {data['parameter_combination']}")

# 保存结果到 summary.md
summary_path = "C:\\Users\\z1376\\Documents\\CST_MCP\\tasks\\task_006_ref_0_s11_optimization\\runs\\run_001\\summary.md"

with open(summary_path, 'w', encoding='utf-8') as f:
    f.write(f"# 优化结果\n\n")
    f.write(f"## 目标频点: 10 GHz\n\n")
    f.write(f"### 优化参数\n")
    f.write(f"- g: {data['parameter_combination']['g']}\n")
    f.write(f"- thr: {data['parameter_combination']['thr']}\n\n")
    f.write(f"### S11 指标\n")
    f.write(f"- 频率: {freq:.6f} GHz\n")
    f.write(f"- S11 (dB): {s11_db:.2f} dB\n\n")
    f.write(f"### 原始参数\n")
    f.write(f"- g: 25.0\n")
    f.write(f"- thr: 12.5\n\n")
    f.write(f"### 优化效果\n")
    f.write(f"S11 改善: 待计算\n")

print("结果已保存到 summary.md")
