# MCP/CLI Migration Status

Generated at: `2026-05-12T09:08:26+00:00`

This file is generated from the Phase 1 inventory script. It is a static
ledger only; it does not prove CST execution or production validation.

## Summary

- Total records: `113`
- MCP tools discovered: `95`
- CLI tools discovered: `84`
- Implemented or mapped to CLI: `87`
- Not migrated and needs design: `25`
- Disabled or blocked: `1`

## Not Pipeable Tools

- `activate_post_process_operation`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `add_to_history`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `boolean_add`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `boolean_insert`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `boolean_intersect`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `boolean_subtract`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `change_frequency_range`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `change_material`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `change_parameter`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `change_solver_type`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `close_project`: `not_pipeable_session`, risk `session`, retention `not_decided`
- `create_component`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `create_hollow_sweep`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `create_horn_segment`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `create_loft_sweep`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `create_mesh_group`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_analytical_curve`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_background`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_boundary`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_brick`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_cone`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_cylinder`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_extrude_curve`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_frequency_range`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_loft`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_material_from_mtd`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_mesh`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_monitor`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_polygon_3d`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_port`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_rectangle`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_solver`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `define_units`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `delete_entity`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `delete_monitor`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `delete_probe_by_id`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `export_e_field_data`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `export_surface_current_data`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `export_voltage_data`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `init_cst_project`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `open_project`: `not_pipeable_session`, risk `session`, retention `not_decided`
- `parameter_set`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `pause_simulation`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `pick_face`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `quit_cst`: `not_pipeable_destructive`, risk `process-control`, retention `mcp_preferred`
- `rename_entity`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `resume_simulation`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `set_background_with_space`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_efield_monitor`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_entity_color`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_farfield_monitor`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_farfield_plot_cuts`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_fdsolver_extrude_open_bc`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_field_monitor`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_mesh_fpbavoid_nonreg_unite`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_mesh_minimum_step_number`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_probe`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `set_solver_acceleration`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `show_bounding_box`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `start_simulation`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `start_simulation_async`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `stop_simulation`: `not_pipeable_session`, risk `session`, retention `mcp_preferred`
- `transform_curve`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `transform_shape`: `not_pipeable_destructive`, risk `write`, retention `mcp_preferred`
- `close_project`: `not_pipeable_session`, risk `session`, retention `not_decided`
- `export_existing_farfield_cut_fresh_session`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `export_farfield`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `export_farfield_fresh_session`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `open_project`: `not_pipeable_session`, risk `session`, retention `not_decided`
- `read_realized_gain_grid_fresh_session`: `not_pipeable_session`, risk `long-running`, retention `mcp_preferred`
- `activate-post-process`: `not_pipeable_destructive`, risk `write`, retention `cli_native`
- `create-blank-project`: `not_pipeable_destructive`, risk `write`, retention `cli_native`
- `cst-session-close`: `not_pipeable_session`, risk `session`, retention `cli_native`
- `cst-session-open`: `not_pipeable_session`, risk `session`, retention `cli_native`
- `cst-session-quit`: `not_pipeable_destructive`, risk `process-control`, retention `cli_native`
- `delete-probe`: `not_pipeable_destructive`, risk `write`, retention `cli_native`
- `wait-simulation`: `not_pipeable_session`, risk `long-running`, retention `cli_native`

## Disabled Or Blocked

- `export_s_parameter`: `disabled_with_replacement`, replacement `get-1d-result -> generate-s11-comparison`, reason `Production S11 CSV/export_s_parameter path is forbidden by AGENTS.md; use JSON result chain.`

## Not Migrated Needs Design

- `activate_post_process_operation` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `add_to_history` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `close_project` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `not_decided`
- `create_hollow_sweep` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `create_horn_segment` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `create_loft_sweep` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `define_analytical_curve` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `define_extrude_curve` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `define_loft` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `define_material_from_mtd` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `define_polygon_3d` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `delete_probe_by_id` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `export_e_field_data` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `mcp_preferred`
- `export_surface_current_data` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `mcp_preferred`
- `export_voltage_data` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `mcp_preferred`
- `init_cst_project` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `open_project` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `not_decided`
- `parameter_set` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `pause_simulation` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `mcp_preferred`
- `pick_face` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `resume_simulation` from `mcp/advanced_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `mcp_preferred`
- `transform_curve` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `transform_shape` from `mcp/advanced_mcp.py`: risk `write`, pipeline `not_pipeable_destructive`, MCP retention `mcp_preferred`
- `close_project` from `mcp/cst_results_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `not_decided`
- `open_project` from `mcp/cst_results_mcp.py`: risk `session`, pipeline `not_pipeable_session`, MCP retention `not_decided`
