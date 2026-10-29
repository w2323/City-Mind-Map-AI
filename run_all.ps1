# run_all.ps1 — Launch CityMind Backend and 2D Pygame Frontend
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  CityMind — Starting Backend and 2D Pygame UI" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Launch backend in a new PowerShell process
Write-Host "Starting Backend API in a separate window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn backend.api.main:app --port 8000"

# Wait for backend initialization
Write-Host "Waiting for backend to bind to port 8000..." -ForegroundColor Yellow
Start-Sleep -Seconds 4

# Launch Pygame desktop
Write-Host "Launching 2D Pygame Operations Center..." -ForegroundColor Green
python frontend-2d-pygame/main.py
