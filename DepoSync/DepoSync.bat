@echo off
cd /d "%~dp0"
python deposync\ui\main.py
if errorlevel 1 pause
