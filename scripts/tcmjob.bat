@echo off
setlocal EnableExtensions
rem ============================================================
rem  tcmjob - Medical Job Workbench one-shot launcher
rem
rem  usage: type  tcmjob  in any cmd window
rem    - starts backend(8000) + frontend(5173), opens browser
rem    - Ctrl+C / Ctrl+Break / closing this window stops everything
rem      (a watchdog in its own minimized window watches a heartbeat
rem       file that this script refreshes every second; when this
rem       window dies the heartbeat goes stale and the watchdog
rem       runs tcmjob-stop. Do NOT watch window titles/PIDs: the
rem       title survives Ctrl+C in an interactive cmd, so it can
rem       never signal the death of the batch.)
rem    - tcmjob-stop also stops both services from anywhere
rem ============================================================

if "%TCM_HOME%"=="" set "TCM_HOME=D:\ó¦Ð·'s Projects\ó¦Ð·µÄ¼òÀú×«Ð´¹¤¾ß"

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "HB=%TCM_HOME%\logs\tcm-heartbeat.flag"

rem unique random window title so the windows are tellable apart
set "TCM_TITLE=tcmjob-%RANDOM%%RANDOM%"
title tcmjob %TCM_TITLE%

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
    echo pnpm dev --port %FRONTEND_PORT%^> "%TCM_HOME%\logs\tcm-frontend.log" 2^>^&1
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

rem ---- warm-up: dev server compiles on the first page hit, so fetch ----
rem ---- index once ourselves or the browser eats that cold compile ----
echo   [tcmjob] warming up frontend (first hit compiles, can take a bit)...
curl -s -o nul --max-time 60 http://127.0.0.1:%FRONTEND_PORT%/ 2>nul

start "" http://127.0.0.1:%FRONTEND_PORT%/

echo   ============================================================
echo    All services up. Press Ctrl+C here to stop everything.
echo   ============================================================
echo.

rem ---- watchdog: a separate minimized window checks the heartbeat ----
rem ---- file every ~3s; stale for 8s means THIS window died, and   ----
rem ---- then it stops both services and exits. goto-branching is   ----
rem ---- deliberate: `if x call y & exit` would run the exit on     ----
rem ---- EVERY beat (& is not bound to the if), killing the watchdog ----
rem ---- after one beat no matter what.                              ----
> "%TCM_HOME%\logs\tcm-watchdog.cmd" (
    echo @echo off
    echo set "HB=%HB%"
    echo :watch
    echo ping -n 3 127.0.0.1 ^>nul
    echo powershell -NoProfile -Command "if(((Get-Date)-[System.IO.File]::GetLastWriteTime($env:HB)).TotalSeconds -ge 8){exit 1}"
    echo if errorlevel 1 goto :stop
    echo goto :watch
    echo :stop
    echo call "%~d0%~p0tcmjob-stop.bat" ^>nul 2^>nul
    echo exit /b 0
)
start "tcmjob-watchdog" /min cmd /c ""%TCM_HOME%\logs\tcm-watchdog.cmd""

rem ---- foreground hold: refresh the heartbeat every ~1s while alive ----
rem ---- (echo writes real bytes; copy /b +,, and break> do NOT bump ----
rem ---- the mtime on this machine, the watchdog would see a stale   ----
rem ---- heartbeat and kill the stack while it is running)           ----
break>"%HB%"
:hold
ping -n 2 127.0.0.1 >nul
echo x>"%HB%"
goto :hold

:fail
exit /b 1

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
