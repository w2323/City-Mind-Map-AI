@echo off
title CityMind Operations Center
echo ===================================================
echo   CityMind - Starting Backend and 2D Pygame UI
echo ===================================================

echo Starting Backend API (Uvicorn) in a separate window...
start "CityMind Backend" cmd /k "python -m uvicorn backend.api.main:app --port 8000"

echo Waiting 4 seconds for Backend to initialize...
timeout /t 4 /nobreak >nul

echo Starting 2D Pygame Desktop Application...
python frontend-2d-pygame/main.py
