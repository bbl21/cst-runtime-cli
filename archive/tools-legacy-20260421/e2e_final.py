"""端到端测试"""
from __future__ import annotations
import math, os, shutil, sys
sys.path.insert(0, "prototype_optimizer")
import advanced_mcp, cst_results_mcp

SRC = r"C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\workspaces\quad_ridged_horn_v1\projects\source\quad_ridged_horn_v1_0.cst"
DEST_DIR = r"C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\runs\test_final"
DEST = os.path.join(DEST_DIR, os.path.basename(SRC))
os.makedirs(DEST_DIR, exist_ok=True)
if os.path.exists(DEST):
    os.remove(DEST)
    folder = os.path.splitext(DEST)[0]
    if os.path.exists(folder):
        shutil.rmtree(folder)
shutil.copy2(SRC, DEST)
print("copy OK:", DEST)

print("1 modeler open")
r1 = advanced_mcp.open_project(DEST)
print("  ", r1.get("status"))

print("2 results open non-interactive")
r2 = cst_results_mcp.open_project(DEST, allow_interactive=False)
print("  ", r2.get("status"))

print("3 params + sim")
for n, v in [("g", 10.5), ("thr", 3.1), ("R", 0.011)]:
    advanced_mcp.change_parameter(n, v)
r3 = advanced_mcp.start_simulation()
print("  ", r3.get("status"))

print("4 results reload")
cst_results_mcp.close_project()
r4 = cst_results_mcp.open_project(DEST, allow_interactive=False)
print("  ", r4.get("status"))

print("5 get_1d_result")
r5 = cst_results_mcp.get_1d_result(
    treepath="1D Results\\S-Parameters\\S1,1",
    module_type="3d",
    run_id=1,
    load_impedances=True,
)
print("  status:", r5.get("status"))
if r5.get("status") == "success":
    y = r5.get("ydata", [])
    print("  points:", len(y))
    dbs = []
    for item in y:
        if isinstance(item, dict):
            mag = math.hypot(item.get("real", 0) or 0, item.get("imag", 0) or 0)
            dbs.append(20.0 * math.log10(max(mag, 1e-15)))
    print("  sample dB:", [round(v, 2) for v in dbs[:5]])
else:
    print("  ERROR:", r5.get("message"))

cst_results_mcp.close_project()
advanced_mcp.close_project()
print("DONE" if r5.get("status") == "success" else "FAILED")
