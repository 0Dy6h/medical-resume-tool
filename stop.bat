@echo off
rem Stop wrapper: stops backend/frontend by PID file with port-based fallback
title Medical Job Workbench - Stopping
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1" -Stop
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1" -Stop
)
echo.
pause
