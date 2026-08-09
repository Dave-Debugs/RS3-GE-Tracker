@echo off
REM Starts the React dev server on http://localhost:5173
cd /d "%~dp0..\frontend"
call npm run dev
