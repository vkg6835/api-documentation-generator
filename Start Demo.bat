@echo off
cd /d "%~dp0"
py -3.13 run_demo.py
if errorlevel 1 pause
