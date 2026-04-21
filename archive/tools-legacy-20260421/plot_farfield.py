"""
解析CST远场数据并生成交互式HTML预览
诊断远场方向图绕极轴扭曲问题
"""
import json
import os

# 读取数据文件
file_path = r"C:\Users\z1376\Documents\CST_MCP\test\jazani2018_horn_mcp\jazani2018_horn_mcp_0\Model\3D\farfield_10GHz.txt"
output_path = r"c:\Users\z1376\Documents\CST_MCP\plot_previews\farfield_10GHz_jazani.html"

# 读取并解析数据（跳过前两行：标题和分隔符）
theta_list = []
phi_list = []
abs_e_list = []
abs_theta_list = []
phase_theta_list = []
abs_phi_list = []
phase_phi_list = []
ax_ratio_list = []

with open(file_path, 'r') as f:
    lines = f.readlines()

for line in lines[2:]:  # 跳过标题行和分隔符
    parts = line.split()
    if len(parts) >= 8:
        try:
            theta_list.append(float(parts[0]))
            phi_list.append(float(parts[1]))
            abs_e_list.append(float(parts[2]))
            abs_theta_list.append(float(parts[3]))
            phase_theta_list.append(float(parts[4]))
            abs_phi_list.append(float(parts[5]))
            phase_phi_list.append(float(parts[6]))
            ax_ratio_list.append(float(parts[7]))
        except ValueError:
            continue

print(f"读取数据点数: {len(theta_list)}")
print(f"Theta范围: {min(theta_list)} - {max(theta_list)}")
print(f"Phi范围: {min(phi_list)} - {max(phi_list)}")

# 计算主极化和交叉极化分量
# 对于线极化天线，主极化通常是 Abs(Theta) 或 Abs(Phi) 中的较大者
# 交叉极化是较小者
main_pol = []
cross_pol = []
for i in range(len(abs_theta_list)):
    at = abs_theta_list[i]
    ap = abs_phi_list[i]
    if at >= ap:
        main_pol.append(at)
        cross_pol.append(ap)
    else:
        main_pol.append(ap)
        cross_pol.append(at)

# 计算圆极化增益 (GCP = |E_theta + j*E_phi|)
# 但这里只有幅度和相位，需要复数计算
# E_total = E_theta * exp(j*phase_theta) + E_phi * exp(j*phase_phi) 对于圆极化

# 对于诊断，先用简单的方法：主极化分量画2D极坐标图

# 生成HTML
html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Farfield 10GHz - Jazani2018 Horn</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: white; }}
        .container {{ display: flex; flex-wrap: wrap; gap: 20px; }}
        .plot {{ flex: 1; min-width: 400px; height: 500px; }}
        .info {{ width: 100%; background: #16213e; padding: 15px; border-radius: 8px; }}
        h1 {{ color: #e94560; }}
        h3 {{ color: #0f3460; background: #e94560; padding: 5px 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>Farfield Analysis - 10 GHz (Jazani2018 Horn)</h1>

    <div class="info">
        <h3>Data Summary</h3>
        <p>Total points: {len(theta_list)}</p>
        <p>Theta range: {min(theta_list):.1f}° - {max(theta_list):.1f}°</p>
        <p>Phi range: {min(phi_list):.1f}° - {max(phi_list):.1f}°</p>
    </div>

    <div class="container">
        <div id="plot1" class="plot"></div>
        <div id="plot2" class="plot"></div>
    </div>
    <div class="container">
        <div id="plot3" class="plot"></div>
        <div id="plot4" class="plot"></div>
    </div>
    <div class="container">
        <div id="plot5" class="plot"></div>
    </div>

    <script>
    // 数据准备
    const theta = {json.dumps(theta_list)};
    const phi = {json.dumps(phi_list)};
    const absE = {json.dumps(abs_e_list)};
    const absTheta = {json.dumps(abs_theta_list)};
    const phaseTheta = {json.dumps(phase_theta_list)};
    const absPhi = {json.dumps(abs_phi_list)};
    const phasePhi = {json.dumps(phase_phi_list)};
    const axRatio = {json.dumps(ax_ratio_list)};
    const mainPol = {json.dumps(main_pol)};
    const crossPol = {json.dumps(cross_pol)};

    // 1. Abs(E) 3D surface
    Plotly.newPlot('plot1', [{{
        x: phi,
        y: theta,
        z: absE.map(v => 20 * Math.log10(v + 1e-10)),
        type: 'surface',
        colorscale: 'Jet',
        colorbar: {{title: '|E| (dB)'}}
    }}], {{
        title: 'Total Field |E| (dB)',
        scene: {{ xaxis: {{title: 'Phi (deg)'}}, yaxis: {{title: 'Theta (deg)'}}, zaxis: {{title: 'dB'}} }}
    }});

    // 2. Main Polarization component 3D surface
    Plotly.newPlot('plot2', [{{
        x: phi,
        y: theta,
        z: mainPol.map(v => 20 * Math.log10(v + 1e-10)),
        type: 'surface',
        colorscale: 'Jet',
        colorbar: {{title: 'Main Pol (dB)'}}
    }}], {{
        title: 'Main Polarization (dB)',
        scene: {{ xaxis: {{title: 'Phi (deg)'}}, yaxis: {{title: 'Theta (deg)'}}, zaxis: {{title: 'dB'}} }}
    }});

    // 3. 2D polar plot at principal cuts (Phi=0 and Phi=90)
    // Phi=0 cut
    let phi0_theta = [], phi0_val = [];
    for(let i=0; i<theta.length; i++) {{
        if(Math.abs(phi[i] - 0) < 1) {{
            phi0_theta.push(theta[i]);
            phi0_val.push(20 * Math.log10(absE[i] + 1e-10));
        }}
    }}

    // Phi=90 cut
    let phi90_theta = [], phi90_val = [];
    for(let i=0; i<theta.length; i++) {{
        if(Math.abs(phi[i] - 90) < 1) {{
            phi90_theta.push(theta[i]);
            phi90_val.push(20 * Math.log10(absE[i] + 1e-10));
        }}
    }}

    Plotly.newPlot('plot3', [
        {{
            x: phi0_theta,
            y: phi0_val,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Phi=0°',
            line: {{color: 'blue'}}
        }},
        {{
            x: phi90_theta,
            y: phi90_val,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Phi=90°',
            line: {{color: 'red'}}
        }}
    ], {{
        title: 'Principal Cuts - |E| (dB)',
        xaxis: {{title: 'Theta (deg)'}},
        yaxis: {{title: '|E| (dB)'}},
        legend: {{x: 0.9, y: 1}},
        hovermode: 'closest'
    }});

    // 4. Theta and Phi components at Phi=0 cut
    let phi0_absTheta = [], phi0_absPhi = [];
    for(let i=0; i<theta.length; i++) {{
        if(Math.abs(phi[i] - 0) < 1) {{
            phi0_absTheta.push(20 * Math.log10(absTheta[i] + 1e-10));
            phi0_absPhi.push(20 * Math.log10(absPhi[i] + 1e-10));
        }}
    }}

    Plotly.newPlot('plot4', [
        {{
            x: phi0_theta,
            y: phi0_absTheta,
            type: 'scatter',
            mode: 'lines+markers',
            name: '|E_Theta|',
            line: {{color: 'cyan'}}
        }},
        {{
            x: phi0_theta,
            y: phi0_absPhi,
            type: 'scatter',
            mode: 'lines+markers',
            name: '|E_Phi|',
            line: {{color: 'magenta'}}
        }}
    ], {{
        title: 'Phi=0 Cut - Theta/Phi Components (dB)',
        xaxis: {{title: 'Theta (deg)'}},
        yaxis: {{title: 'Component (dB)'}},
        legend: {{x: 0.9, y: 1}},
        hovermode: 'closest'
    }});

    // 5. Axial Ratio 3D
    Plotly.newPlot('plot5', [{{
        x: phi,
        y: theta,
        z: axRatio.map(v => Math.min(v, 30)), // clamp large values
        type: 'surface',
        colorscale: [[0, 'blue'], [0.5, 'green'], [1, 'red']],
        colorbar: {{title: 'Ax.Ratio'}},
        zsmooth: 'best'
    }}], {{
        title: 'Axial Ratio (clamped to 30)',
        scene: {{ xaxis: {{title: 'Phi (deg)'}}, yaxis: {{title: 'Theta (deg)'}}, zaxis: {{title: 'Ratio'}} }}
    }});

    </script>
</body>
</html>'''

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"HTML saved to: {output_path}")
