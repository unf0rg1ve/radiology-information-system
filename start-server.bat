@echo off
chcp 65001 >nul 2>&1
title RIS Server - Auto-detect IP

echo ========================================
echo   RIS Server - Auto IP Detection
echo ========================================
echo.

:: Detect local IP
for /f "tokens=*" %%i in ('python detect_ip.py') do set LOCAL_IP=%%i

if "%LOCAL_IP%"=="127.0.0.1" (
    echo [ERROR] Cannot detect network IP. Check your network connection.
    pause
    exit /b 1
)

echo [OK] Detected IP: %LOCAL_IP%
echo.

:: Write .env file for docker-compose
echo HOST_IP=%LOCAL_IP%> .env
echo [OK] Written .env: HOST_IP=%LOCAL_IP%
echo.

:: Kill old proxy if running
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8043 " ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1

:: Start docker-compose
echo [..] Starting Docker containers...
docker compose up -d 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] docker compose failed
    pause
    exit /b 1
)
echo [OK] Docker containers started
echo.

:: Wait for backend to be ready
echo [..] Waiting for backend...
timeout /t 8 /nobreak >nul

:: Start proxy
echo [..] Starting Orthanc proxy on 0.0.0.0:8043...
start /B pythonw orthanc-proxy.py
timeout /t 2 /nobreak >nul

:: Verify proxy
netstat -ano | findstr ":8043 " | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Proxy running on port 8043
) else (
    echo [WARN] Proxy may not have started. Check proxy.log
)

echo.
echo ========================================
echo   Server is ready!
echo ========================================
echo.
echo   Frontend:   http://%LOCAL_IP%:3000
echo   Backend:    http://%LOCAL_IP%:8000
echo   Orthanc:    http://localhost:8042
echo   Proxy:      http://%LOCAL_IP%:8043
echo.
echo   Open http://%LOCAL_IP%:3000 in browser
echo ========================================
echo.
pause
