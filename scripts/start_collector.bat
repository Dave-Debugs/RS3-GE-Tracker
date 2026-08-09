@echo off
REM Standalone collector - keeps gathering prices with the dashboard closed.
REM Run EITHER this OR start_backend.bat (the backend already collects).
cd /d "%~dp0.."
python scripts\run_collector.py
