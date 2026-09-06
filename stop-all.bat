@echo off
setlocal
cd /d %~dp0

echo ================================================
echo            企业管理系统 一键停止
echo ================================================
echo 将强制结束占用 8000（后端）与 5173（前端）端口的进程。

set FOUND=0

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c:":8000 " ^| findstr LISTENING') do (
    echo [停止] 后端进程 PID=%%p
    taskkill /F /T /PID %%p >nul 2>&1
    set FOUND=1
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c:":5173 " ^| findstr LISTENING') do (
    echo [停止] 前端进程 PID=%%p
    taskkill /F /T /PID %%p >nul 2>&1
    set FOUND=1
)

if "%FOUND%"=="0" echo 两个服务当前均未在运行。
echo 完成。
pause
