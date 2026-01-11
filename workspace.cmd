@echo off
REM Unified Terminal Workspace Launcher
REM Double-click or pin to taskbar to launch

cd /d %~dp0
powershell -ExecutionPolicy Bypass -File "%~dp0workspace.ps1" %*
