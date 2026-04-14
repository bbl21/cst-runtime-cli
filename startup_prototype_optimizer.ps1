$root = "C:\Users\z1376\Documents\CST_MCP"
Set-Location $root
$env:PYTHONPATH = $root

Write-Host "Starting Prototype Optimizer UI..." -ForegroundColor Cyan

& uv run streamlit run prototype_optimizer/app.py --server.headless true
