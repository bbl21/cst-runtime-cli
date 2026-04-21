"""端到端真实测试：modeler open -> params -> sim -> results reload -> read S11"""
import sys, os, shutil, math
sys.path.insert(0, "prototype_optimizer")
import advanced_mcp, cst_results_mcp

SRC = r"C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\workspaces\quad_ridged_horn_v1\projects\source\quad_ridged_horn_v1_0.cst"
OUT_DIR = r"C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\runs\test_scripts"
COPY_DIR = os.path.join(OUT_DIR, "projects")
os.makedirs(COPY_DIR, exist_ok=True)
DEST = os.path.join(COPY_DIR, os.path.basename(SRC))
if os.path.exists(DEST):
    shutil.rmtree(os.path.splitext(DEST)[0])
    os.remove(DEST)
shutil.copy2(SRC, DEST)
print("Copy:", DEST, "exists:", os.path.exists(DEST))

print("1 modeler open")
r1 = advanced_mcp.open_project(DEST)
print("  status:", r1.get("status"))
print("2 results open (non-interactive)")
r2 = cst_results_mcp.open_project(DEST, allow_interactive=False)
print("  status:", r2.get("status"))
print("3 params + sim")
for n, v in [("g", 10.5), ("thr", 3.1), ("R", 0.011)]:
    advanced_mcp.change_parameter(n, v)
r3 = advanced_mcp.start_simulation()
print("  sim status:", r3.get("status"))
print("4 results reload (non-interactive)")
cst_results_mcp.close_project()
r4 = cst_results_mcp.open_project(DEST, allow_interactive=False)
print("  reload status:", r4.get("status"))
print("5 read S11")
r5 = cst_results_mcp.get_1d_result(
    treepath="1D Results\\S-Parameters\\S1,1",
    module_type="3d", run_id=1, load_impedances=True
)
print("  S11 status:", r5.get("status"))
if r5.get("status") == "success":
    y = r5.get("ydata", [])
    dB = [20 * math.log10(math.hypot(v["real"], v["imag"])) for v in y[:3]]
    print("  dB sample:", [round(x, 2) for x in dB])
    print("  count:", len(y))
else:
    print("  ERROR:", r5.get("message"))
cst_results_mcp.close_project()
advanced_mcp.close_project()
advanced_mcp.close_project()
print("DONE" if r5.get("status") == "success" else "FAILED")
