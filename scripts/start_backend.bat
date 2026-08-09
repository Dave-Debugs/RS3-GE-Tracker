@echo off
REM Starts the FastAPI backend (includes the background price collector).
cd /d "%~dp0..\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
