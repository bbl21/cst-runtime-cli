"""诊断：CST results ProjectFile 仿真后是否需要显式刷新"""
import sys
sys.path.insert(0, '.')

import cst.interface, cst.results

src = r'C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\workspaces\quad_ridged_horn_v1\projects\source\quad_ridged_horn_v1_0.cst'
print('File:', src)

# 1. Open via modeler
de = cst.interface.DesignEnvironment()
modeler_proj = de.open_project(src)
print('Modeler open OK')

# 2. Apply param + simulate
modeler_proj.store_double_parameter('g', 10.5)
modeler_proj.modeler.add_to_history('p', 'StoreDoubleParameter "g", 10.5')
modeler_proj.modeler.run_simulation()
print('Sim done')

# 3. Get results via modeler.results
results_proj = modeler_proj.results
print('results type:', type(results_proj).__name__, type(results_proj).__module__)
mod3d = results_proj.get_3d()
print('get_3d OK')

# 4. Try to read S11
try:
    item = mod3d.get_result_item('1D Results\\S-Parameters\\S1,1', run_id=1, load_impedances=True)
    print('get_result_item OK')
    y = item.get_ydata()
    print('ydata count:', len(y))
    vals = y[:3]
    import math
    dbs = [round(20 * math.log10(max(math.hypot(v.get('real', 0), v.get('imag', 0))) for v in vals]
    print('dB:', dbs)
except Exception as e:
    print('ERROR:', e)
    import traceback; traceback.print_exc()
