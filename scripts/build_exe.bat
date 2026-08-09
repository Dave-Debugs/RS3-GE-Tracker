@echo off
echo Building frontend...
cd /d "%~dp0..\frontend"
call npm run build

echo Obfuscating backend...
cd /d "%~dp0..\backend"
if exist dist_obf rmdir /s /q dist_obf
python -m pyarmor.cli gen -O dist_obf -r app

echo Copying launcher...
copy run_app.py dist_obf\

echo Packaging executable...
cd dist_obf
python -m PyInstaller --name RS3Tracker ^
  --icon="..\..\icon.ico" ^
  --add-data "..\..\icon.ico;." ^
  --add-data "..\..\frontend\dist;frontend\dist" ^
  --add-data "app;app" ^
  --add-data "pyarmor_runtime_000000;pyarmor_runtime_000000" ^
  --hidden-import fastapi ^
  --hidden-import fastapi.middleware.cors ^
  --hidden-import fastapi.staticfiles ^
  --hidden-import fastapi.responses ^
  --hidden-import uvicorn ^
  --hidden-import httpx ^
  --hidden-import pydantic ^
  --hidden-import sqlite3 ^
  --hidden-import logging ^
  --hidden-import contextlib ^
  --hidden-import math ^
  --hidden-import typing ^
  --hidden-import pystray ^
  --windowed ^
  --noconsole ^
  --onefile run_app.py

echo Done! Executable is in backend\dist_obf\dist\RS3Tracker.exe
