@echo off
rem Launch wrapper: delegates to scripts\start-local.ps1 (install deps + start backend/frontend + health check + open browser)
rem Usage: start.bat [-NoBrowser]  (extra args are passed through)
title Medical Job Workbench - Starting
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1" %*
)
echo.
pause
