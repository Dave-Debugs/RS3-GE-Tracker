@echo off
REM First-time setup: installs backend and frontend dependencies.
cd /d "%~dp0..\backend"
pip install -r requirements.txt
cd /d "%~dp0..\frontend"
call npm install
echo.
echo Setup complete. Run scripts\start_all.bat to launch the tracker.
