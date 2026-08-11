@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" toss_display_ads_bot.py >> toss_display_ads.log 2>&1
