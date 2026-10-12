@echo off
cd /d "%~dp0..\frontend"
call npm run build

cd /d "%~dp0..\backend"
python -m PyInstaller RS3Tracker.spec --noconfirm

cd /d "%~dp0.."
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
) else (
    iscc installer.iss
)
