@echo off
setlocal
cd /d %~dp0

echo ================================================
echo            企业管理系统 一键启动
echo ================================================

rem ---------- 1) MySQL 连通性检查（仅提示，不代启） ----------
netstat -ano | findstr /c:":3306 " | findstr LISTENING >nul
if errorlevel 1 (
    echo [警告] 未检测到 MySQL 3306 端口在运行，后端可能启动失败，请先启动 MySQL 服务。
) else (
    echo [OK] MySQL 已在运行
)

rem ---------- 2) 后端 FastAPI :8000（先同步数据库迁移再启动） ----------
netstat -ano | findstr /c:":8000 " | findstr LISTENING >nul
if errorlevel 1 (
    echo [启动] 后端 http://127.0.0.1:8000 （独立窗口，含 --reload 热重载）...
    start "backend :8000" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m alembic upgrade head && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
) else (
    echo [跳过] 8000 端口已被占用，后端可能已在运行；如需重启请先运行 stop-all.bat
)

rem ---------- 3) 前端 Vite :5173 ----------
netstat -ano | findstr /c:":5173 " | findstr LISTENING >nul
if errorlevel 1 (
    echo [启动] 前端 http://localhost:5173 （独立窗口）...
    start "frontend :5173" cmd /k "cd /d %~dp0frontend && npm run dev"
) else (
    echo [跳过] 5173 端口已被占用，前端可能已在运行
)

rem ---------- 4) 等待就绪后打开浏览器（ping 充当延时，兼容性最好） ----------
echo 等待服务就绪，约 6 秒后打开浏览器...
ping -n 7 127.0.0.1 >nul
start http://localhost:5173

echo.
echo 完成：两个服务运行在各自的命令行窗口中，请保持窗口打开。
echo 后端接口文档：http://127.0.0.1:8000/docs
echo 停止服务：运行 stop-all.bat，或直接关闭对应命令行窗口。
pause
