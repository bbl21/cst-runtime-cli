import json
import os
import sys


def extract_data_from_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    params = data.get("parameter_combination", {})
    xdata = data.get("xdata", [])
    raw_ydata = data.get("ydata", [])

    complex_data = []
    for item in raw_ydata:
        if isinstance(item, dict):
            complex_data.append(complex(item.get("real", 0), item.get("imag", 0)))
        elif isinstance(item, str):
            complex_data.append(eval(item.replace("j", "j")))
        else:
            complex_data.append(complex(0, 0))

    return params, xdata, complex_data


def find_data_files(exports_dir, prefix="s11_run"):
    files = []
    if os.path.isdir(exports_dir):
        for f in sorted(os.listdir(exports_dir)):
            if f.startswith(prefix) and f.endswith(".json"):
                files.append(os.path.join(exports_dir, f))
    return files


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Generate interactive comparison HTML")
    parser.add_argument(
        "exports_dir", nargs="?", help="Directory containing JSON data files"
    )
    parser.add_argument(
        "--prefix", default="s11_run", help="File prefix to match (default: s11_run)"
    )
    parser.add_argument(
        "--title", default="", help="Chart title (default: auto from files)"
    )
    parser.add_argument(
        "--params", default="", help="Comma-separated params to display (default: all)"
    )
    parser.add_argument("--xlabel", default="Frequency", help="X-axis label")
    parser.add_argument("--ylabel", default="S11 (dB)", help="Y-axis label")
    return parser.parse_args()


args = parse_args()

if args.exports_dir:
    exports_dir = args.exports_dir
else:
    exports_dir = r"C:\Users\z1376\Documents\CST_MCP\tasks\task_001_ref_10ghz_match\runs\run_004\exports"

files = find_data_files(exports_dir, args.prefix)

if not files:
    print(f"No files found with prefix '{args.prefix}' in {exports_dir}")
    sys.exit(1)

print(f"Loading data from: {exports_dir}")
print(f"Found {len(files)} data files")

all_runs = []
for fp in files:
    try:
        params, xdata, ydata = extract_data_from_file(fp)
        filename = os.path.basename(fp)
        if filename.startswith(args.prefix):
            run_num = int(filename[len(args.prefix) : filename.rfind(".json")])
        else:
            run_num = len(all_runs) + 1
        all_runs.append(
            {"run_id": run_num, "params": params, "xdata": xdata, "ydata": ydata}
        )
        print(f"Run {run_num}: {len(ydata)} points")
    except Exception as e:
        print(f"Error loading {fp}: {e}")

if not all_runs:
    print("No valid data loaded")
    sys.exit(1)

# Auto-detect frequency range
xdata = all_runs[0]["xdata"]
freq_min = min(xdata)
freq_max = max(xdata)

# Determine which params to display
all_params = all_runs[0]["params"]
if args.params:
    display_params = [p.strip() for p in args.params.split(",")]
else:
    display_params = list(all_params.keys())

# Build title
if args.title:
    title = args.title
else:
    title = f"Comparison - {len(all_runs)} Runs"

# Generate HTML with dynamic ranges and params
html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        :root {{
            --bg: #f3f7fb;
            --panel: #ffffff;
            --ink: #132133;
            --muted: #54657a;
            --accent: #0b9e8a;
            --accent-soft: #d4f4ee;
            --line: #dce5ef;
            --shadow: 0 10px 30px rgba(17, 37, 63, 0.08);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            color: var(--ink);
            background:
                radial-gradient(circle at 15% 10%, #e3eef9 0%, rgba(227, 238, 249, 0) 45%),
                radial-gradient(circle at 85% 0%, #d8f5ef 0%, rgba(216, 245, 239, 0) 42%),
                var(--bg);
            font-family: "Segoe UI Variable Display", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        }}
        .container {{
            max-width: 1280px;
            margin: 24px auto;
            padding: 0 16px 24px;
        }}
        .hero {{
            background: linear-gradient(140deg, #ffffff 0%, #f8fcff 65%, #f1fff9 100%);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 20px 22px 16px;
            box-shadow: var(--shadow);
            margin-bottom: 16px;
        }}
        .title {{
            margin: 0;
            font-size: clamp(22px, 2.2vw, 32px);
            letter-spacing: 0.4px;
        }}
        .meta {{
            margin-top: 8px;
            color: var(--muted);
            font-size: 14px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px 14px;
        }}
        .chip {{
            display: inline-flex;
            align-items: center;
            border: 1px solid #cae5df;
            background: var(--accent-soft);
            color: #0c6c5f;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        .controls {{
            margin-bottom: 16px;
            padding: 16px 18px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            box-shadow: var(--shadow);
        }}
        .control-group {{
            display: grid;
            grid-template-columns: auto 1fr auto auto;
            gap: 12px;
            align-items: center;
        }}
        .control-label {{
            font-weight: 700;
            color: #334a64;
            white-space: nowrap;
        }}
        input[type="range"] {{
            width: 100%;
            accent-color: var(--accent);
        }}
        .freq-display {{
            min-width: 84px;
            text-align: right;
            font-weight: 800;
            color: #0e7f70;
            font-variant-numeric: tabular-nums;
        }}
        .unit {{
            font-size: 12px;
            color: var(--muted);
            font-weight: 600;
        }}
        .chart-card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            box-shadow: var(--shadow);
            padding: 10px 10px 2px;
            margin-bottom: 14px;
        }}
        #chart1 {{ height: 520px; }}
        #chart2 {{ height: 320px; }}
        @media (max-width: 860px) {{
            .container {{ margin: 14px auto; padding: 0 10px 16px; }}
            .hero {{ border-radius: 14px; padding: 14px 14px 12px; }}
            .controls {{ border-radius: 12px; padding: 12px; }}
            .control-group {{
                grid-template-columns: 1fr;
                gap: 8px;
                justify-items: start;
            }}
            .freq-display {{ text-align: left; }}
            #chart1 {{ height: 440px; }}
            #chart2 {{ height: 300px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <section class="hero">
            <h1 class="title">{title}</h1>
            <div class="meta">
                <span>范围: {freq_min:.2f} - {freq_max:.2f} {args.xlabel}</span>
                <span>共 {len(all_runs)} 组数据</span>
                <span class="chip">{args.ylabel}</span>
            </div>
        </section>

        <div class="controls">
            <div class="control-group">
                <span class="control-label">{args.xlabel}</span>
                <input type="range" id="freqSlider" min="0" max="{len(xdata) - 1}" value="{max(0, min(len(xdata) - 1, len(xdata) // 2))}">
                <span class="freq-display" id="freqValue">{xdata[max(0, min(len(xdata) - 1, len(xdata) // 2))]:.2f}</span>
                <span class="unit">GHz</span>
            </div>
        </div>

        <div class="chart-card">
            <div id="chart1"></div>
        </div>
        <div class="chart-card">
            <div id="chart2"></div>
        </div>
    </div>

    <script>
        const runData = DATA_PLACEHOLDER;
        const displayParams = {json.dumps(display_params)};
        const theme = {{
            paper: 'rgba(0,0,0,0)',
            plot: '#ffffff',
            grid: '#e7eef6',
            tick: '#5e738d',
            title: '#1c2f46',
            marker: '#0b9e8a',
            cross: '#f66a3a'
        }};

        // Convert complex to dB
        function toDb(complex) {{
            const mag = Math.sqrt(complex.real * complex.real + complex.imag * complex.imag);
            return 20 * Math.log10(mag + 1e-10);
        }}

        function formatParamValue(v) {{
            if (typeof v === 'number') {{
                return Number.isInteger(v) ? v.toString() : v.toFixed(3);
            }}
            return String(v);
        }}

        function getValueAtX(runIndex, xIndex) {{
            const y = runData[runIndex].ydata[xIndex];
            return toDb(y);
        }}

        const midIndex = Math.max(0, Math.min(runData[0].xdata.length - 1, Math.floor(runData[0].xdata.length / 2)));
        let currentXIndex = midIndex;

        function baseLayout() {{
            return {{
                paper_bgcolor: theme.paper,
                plot_bgcolor: theme.plot,
                margin: {{ l: 70, r: 28, t: 52, b: 56 }},
                font: {{ family: '"Segoe UI Variable Display", "Segoe UI", "PingFang SC", sans-serif', color: theme.tick, size: 13 }},
                hoverlabel: {{
                    bgcolor: '#18212c',
                    bordercolor: '#18212c',
                    font: {{ color: '#eef4fb', size: 12 }}
                }},
                legend: {{
                    bgcolor: 'rgba(255,255,255,0.9)',
                    bordercolor: '#dde8f2',
                    borderwidth: 1,
                    x: 1,
                    xanchor: 'right',
                    y: 1
                }}
            }};
        }}

        function createChart1() {{
            let minVal = 0;
            for (let i = 0; i < runData.length; i++) {{
                for (let j = 0; j < runData[i].ydata.length; j++) {{
                    const v = toDb(runData[i].ydata[j]);
                    if (v < minVal) minVal = v;
                }}
            }}
            const yMin = Math.floor(minVal - 5);
            
            const traces = [];
            for (let i = 0; i < runData.length; i++) {{
                const values = runData[i].ydata.map(y => toDb(y));
                let label = 'Run ' + runData[i].run_id;
                for (let p of displayParams) {{
                    if (runData[i].params[p] !== undefined) {{
                        label += ', ' + p + '=' + formatParamValue(runData[i].params[p]);
                    }}
                }}
                traces.push({{
                    x: runData[i].xdata,
                    y: values,
                    type: 'scatter',
                    mode: 'lines',
                    name: label,
                    line: {{ width: 2.3 }},
                    hovertemplate: '%{{x:.3f}} GHz<br>%{{y:.2f}} dB<extra>' + label + '</extra>'
                }});
            }}

            const currentX = runData[0].xdata[currentXIndex];

            const layout = Object.assign(baseLayout(), {{
                title: {{ text: '全频段对比', font: {{ size: 20, color: theme.title }} }},
                xaxis: {{
                    title: '{args.xlabel}',
                    range: [{freq_min}, {freq_max}],
                    gridcolor: theme.grid,
                    linecolor: '#d3dfeb',
                    zeroline: false
                }},
                yaxis: {{
                    title: '{args.ylabel}',
                    range: [yMin, 0],
                    gridcolor: theme.grid,
                    linecolor: '#d3dfeb',
                    zeroline: false
                }},
                shapes: [{{
                    type: 'line',
                    x0: currentX, x1: currentX,
                    y0: yMin, y1: 0,
                    line: {{ color: theme.cross, width: 2, dash: 'dot' }}
                }}]
            }});

            Plotly.newPlot('chart1', traces, layout, {{ responsive: true, displaylogo: false }});
        }}

        function createChart2() {{
            const xValues = [];
            const yValues = [];

            for (let i = 0; i < runData.length; i++) {{
                xValues.push(runData[i].run_id);
                yValues.push(getValueAtX(i, currentXIndex));
            }}

            const trace = {{
                x: xValues,
                y: yValues,
                type: 'scatter',
                mode: 'lines+markers',
                marker: {{ size: 9, color: theme.marker, line: {{ width: 1, color: '#ffffff' }} }},
                line: {{ width: 2.3, color: '#1b8abf' }},
                hovertemplate: 'Run %{{x}}<br>%{{y:.2f}} dB<extra></extra>'
            }};

            const currentX = runData[0].xdata[currentXIndex];
            const yMin = Math.min(...yValues) - 1.5;
            const yMax = Math.max(...yValues) + 1.5;

            const layout = Object.assign(baseLayout(), {{
                title: {{ text: currentX.toFixed(2) + ' GHz 截面对比', font: {{ size: 18, color: theme.title }} }},
                xaxis: {{
                    title: 'Run ID',
                    tickmode: 'linear',
                    dtick: 1,
                    gridcolor: theme.grid,
                    linecolor: '#d3dfeb',
                    zeroline: false
                }},
                yaxis: {{
                    title: '{args.ylabel}',
                    range: [yMin, yMax],
                    gridcolor: theme.grid,
                    linecolor: '#d3dfeb',
                    zeroline: false
                }}
            }});

            Plotly.newPlot('chart2', [trace], layout, {{ responsive: true, displaylogo: false }});
        }}

        document.getElementById('freqSlider').addEventListener('input', function() {{
            currentXIndex = parseInt(this.value);
            const x = runData[0].xdata[currentXIndex];
            document.getElementById('freqValue').textContent = x.toFixed(2);
            createChart1();
            createChart2();
        }});

        createChart1();
        createChart2();
    </script>
</body>
</html>"""

# Prepare data
data_for_js = []
for run in all_runs:
    ydata_list = []
    for y in run["ydata"]:
        ydata_list.append({"real": y.real, "imag": y.imag})
    data_for_js.append(
        {
            "run_id": run["run_id"],
            "params": run["params"],
            "xdata": run["xdata"],
            "ydata": ydata_list,
        }
    )

html_content = html_template.replace("DATA_PLACEHOLDER", json.dumps(data_for_js))

output_path = os.path.join(exports_dir, "interactive_comparison.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\nHTML saved to: {output_path}")
