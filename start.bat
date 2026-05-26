@echo off
chcp 65001 >nul
title QuantA-Share
setlocal enabledelayedexpansion

set PG_BIN=C:\Program Files\PostgreSQL\17\bin
set PG_DATA=C:\Program Files\PostgreSQL\17\data
set VENV_PYTHON=%~dp0backend\.venv\Scripts\python.exe
set VENV_PIP=%~dp0backend\.venv\Scripts\pip.exe
set VENV_UVICORN=%~dp0backend\.venv\Scripts\uvicorn.exe
set BACKEND_DIR=%~dp0backend
set DEPS_FLAG=%BACKEND_DIR%\.deps_installed

echo ============================================
echo   QuantA-Share ^|  http://localhost:8000
echo ============================================

:: ── 1. PostgreSQL ──
echo [1/3] PostgreSQL...
netstat -ano 2>nul | findstr ":5432.*LISTENING" >nul
if %errorlevel% neq 0 (
    >nul 2>&1 "%PG_BIN%\pg_ctl.exe" start -D "%PG_DATA%" -w -t 10
    if %errorlevel% neq 0 (
        echo   [FAIL] 请手动启动 PostgreSQL 服务或检查安装路径
        echo         pg_ctl: %PG_BIN%\pg_ctl.exe
        pause & exit /b 1
    )
)
echo   [OK] PostgreSQL 就绪

:: ── 2. Python 依赖（仅首次/更新后安装） ──
echo [2/3] Python 依赖...
if not exist "%DEPS_FLAG%" (
    "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt" akshare -q 2>nul
    if %errorlevel% equ 0 (
        type nul > "%DEPS_FLAG%"
        echo   [OK] 依赖已安装 ^(已记录^)
    ) else (
        echo   [FAIL] 依赖安装失败，请检查网络或手动安装
        pause & exit /b 1
    )
) else (
    echo   [OK] 依赖已就绪 ^(跳过安装^)
)

:: ── 3. 数据库 + 启动 ──
echo [3/3] 启动后端...
echo.
set SKIP_INITIAL_SCAN=0
set SCANNER_FIRST_DELAY_SECONDS=10
cd /d "%BACKEND_DIR%"
"%VENV_UVICORN%" app.main:app --host 0.0.0.0 --port 8000 --reload

pause
