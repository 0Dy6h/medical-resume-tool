@echo off
setlocal EnableExtensions
rem ============================================================
rem  tcmjob - Medical Job Workbench one-shot launcher
rem
rem  usage: type  tcmjob  in any cmd window
rem    - starts backend(8000) + frontend(5173), opens browser
rem    - Ctrl+C / Ctrl+Break / closing this window stops everything
rem      (a watchdog detects the window death and runs tcmjob-stop)
rem    - tcmjob-stop also stops both services from anywhere
rem ============================================================

if "%TCM_HOME%"=="" set "TCM_HOME=D:\ó¦Ð·'s Projects\ó¦Ð·µÄ¼òÀú×«Ð´¹¤¾ß"

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

rem unique window title: fixed prefix + random suffix (watchdog watches this)
set "TCM_TITLE=tcmjob-%RANDOM%%RANDOM%"
title "%TCM_TITLE%"

echo.
echo   [tcmjob] Medical Job Workbench
echo   [tcmjob] project: %TCM_HOME%
echo.

rem ---- port pre-check ----
set "portBusy=0"
for %%P in (%BACKEND_PORT% %FRONTEND_PORT%) do (
    netstat -ano | findstr /r /c:":%%P .*LISTENING" >nul 2>nul
    if not errorlevel 1 set "portBusy=1"
)
if "%portBusy%"=="1" (
    echo   [tcmjob] a service port is already in use - maybe already running.
    echo   [tcmjob] to restart: run tcmjob-stop first.
    goto :fail
)

if not exist "%TCM_HOME%\logs" mkdir "%TCM_HOME%\logs"

rem ---- helper scripts (avoids quote-nesting inside start) ----
> "%TCM_HOME%\logs\tcm-run-backend.cmd" (
    echo @echo off
    echo uv run --project "%TCM_HOME%\backend" --directory "%TCM_HOME%\backend" python -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%^> "%TCM_HOME%\logs\tcm-backend.log" 2^>^&1
)
> "%TCM_HOME%\logs\tcm-run-frontend.cmd" (
    echo @echo off
    echo set CI=true
    echo cd /d "%TCM_HOME%\frontend"
    echo pnpm dev --host 127.0.0.1 --port %FRONTEND_PORT%^> "%TCM_HOME%\logs\tcm-frontend.log" 2^>^&1
)

echo   [tcmjob] starting backend  http://127.0.0.1:%BACKEND_PORT% ...
start "tcmjob-backend" /min cmd /c ""%TCM_HOME%\logs\tcm-run-backend.cmd""

echo   [tcmjob] starting frontend http://127.0.0.1:%FRONTEND_PORT% ...
start "tcmjob-frontend" /min cmd /c ""%TCM_HOME%\logs\tcm-run-frontend.cmd""

rem ---- wait until both ports are listening (max ~90s) ----
set /a tries=0
:waitloop
ping -n 3 127.0.0.1 >nul
set /a tries+=1
set "backendUp=0"
set "frontendUp=0"
netstat -ano | findstr /r /c:":%BACKEND_PORT% .*LISTENING" >nul 2>nul && set "backendUp=1"
netstat -ano | findstr /r /c:":%FRONTEND_PORT% .*LISTENING" >nul 2>nul && set "frontendUp=1"
if "%backendUp%"=="1" if "%frontendUp%"=="1" goto :ready
if %tries% geq 45 (
    echo   [tcmjob] not ready in 90s - see logs\tcm-backend.log / tcm-frontend.log
    goto :cleanup
)
goto :waitloop

:ready
echo.
echo   [tcmjob] backend  ready  http://127.0.0.1:%BACKEND_PORT%
echo   [tcmjob] frontend ready  http://127.0.0.1:%FRONTEND_PORT%
echo   [tcmjob] logs            %TCM_HOME%\logs\tcm-*.log
echo.

start "" http://127.0.0.1:%FRONTEND_PORT%/

echo   ============================================================
echo    All services up. Press Ctrl+C here to stop everything.
echo   ============================================================
echo.

rem ---- watchdog: when THIS window dies (Ctrl+C / close), stop all ----
> "%TCM_HOME%\logs\tcm-watchdog.cmd" (
    echo @echo off
    echo :watch
    echo ping -n 3 127.0.0.1 ^>nul
    echo tasklist /V /FI "WINDOWTITLE eq %1" 2^>nul ^| findstr /i "cmd.exe" ^>nul 2^>nul
    echo if not errorlevel 1 goto :watch
    echo call "%~d0%~p0tcmjob-stop.bat" ^>nul 2^>nul
)
start "tcmjob-watchdog" /min cmd /c ""%TCM_HOME%\logs\tcm-watchdog.cmd"" "%TCM_TITLE%""

rem ---- foreground hold: Ctrl+C here = window dies = watchdog fires ----
pause >nul

rem ---- graceful path (user pressed a key instead of Ctrl+C) ----
echo.
echo   [tcmjob] stopping services...
call :stopport %FRONTEND_PORT% "frontend"
call :stopport %BACKEND_PORT% "backend"
echo   [tcmjob] all stopped.
ping -n 3 127.0.0.1 >nul
exit /b 0

:cleanup
echo.
echo   [tcmjob] stopping services (startup failed)...
call :stopport %FRONTEND_PORT% "frontend"
call :stopport %BACKEND_PORT% "backend"
ping -n 3 127.0.0.1 >nul
exit /b 1

:stopport
for /f "tokens=5" %%Q in ('netstat -ano ^| findstr /r /c:":%1 .*LISTENING"') do (
    if not "%%Q"=="0" (
        echo   [tcmjob]   stopping %2 (PID %%Q)
        taskkill /PID %%Q /T /F >nul 2>nul
    )
)
exit /b 0
