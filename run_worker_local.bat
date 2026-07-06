@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Toss re-collection worker (this window = running)
echo   Close this window to stop the worker.
echo ============================================
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" _launch_worker.py
pause
