import functools

def require_active_project():
    """Decorator factory to ensure an active CST project is loaded before a tool runs.

    Usage:
      @require_active_project()
      def some_tool(...):
          ...
    """
    def _decorator(fn):
        @functools.wraps(fn)
        def _wrapper(*args, **kwargs):
            try:
                from mcp.advanced_mcp import get_project_object
                proj = get_project_object()
                if not proj:
                    return {"status": "error", "message": "No active CST project or not connected"}
            except Exception as e:
                return {"status": "error", "message": f"Precheck failed: {e}"}
            return fn(*args, **kwargs)
        return _wrapper
    return _decorator
