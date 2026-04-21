"""探查 modeler COM 对象是否有 results 接口"""
import sys
sys.path.insert(0, '.')
import cst.interface, cst.results

src = r'C:\Users\z1376\Documents\CST_MCP\prototype_optimizer\data\workspaces\quad_ridged_horn_v1\projects\source\quad_ridged_horn_v1_0.cst'
print('File:', src)

try:
    de = cst.interface.DesignEnvironment()
    modeler_proj = de.open_project(src)
    print('Modeler project type:', type(modeler_proj).__name__, modeler_proj.__class__.__module__)
    print('Has .results:', hasattr(modeler_proj, 'results'))
    if hasattr(modeler_proj, 'results'):
        r = modeler_proj.results
        print('results type:', type(r).__name__)
    print('Modeler attributes containing results:',
          [a for a in dir(modeler_proj) if 'result' in a.lower() or 'solver' in a.lower() or '3d' in a.lower()])
except Exception as e:
    print('Error:', e)
    import traceback; traceback.print_exc()
