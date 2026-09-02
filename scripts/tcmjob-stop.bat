@echo off
rem tcmjob-stop - 停止 tcmjob 启动的服务（按端口找 PID 终止进程树）
setlocal EnableExtensions
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
call :stopport %FRONTEND_PORT% "前端"
call :stopport %BACKEND_PORT% "后端"
exit /b 0

:stopport
set "found=0"
for /f "tokens=5" %%Q in ('netstat -ano ^| findstr /r /c:":%1 .*LISTENING"') do (
    if not "%%Q"=="0" (
        set "found=1"
        echo   [tcmjob-stop] 停止 %~2 (PID %%Q)
        taskkill /PID %%Q /T /F >nul 2>nul
    )
)
if "%found%"=="0" echo   [tcmjob-stop] %~2 未在运行
exit /b 0
