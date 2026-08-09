@echo off
REM One-click start: backend + frontend in separate windows, then open browser.
start "RS3 Tracker Backend" cmd /k "%~dp0start_backend.bat"
timeout /t 5 /nobreak >nul
start "RS3 Tracker Frontend" cmd /k "%~dp0start_frontend.bat"
timeout /t 5 /nobreak >nul
start http://localhost:5173
