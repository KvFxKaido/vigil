@echo off
cd /d %~dp0
echo Installing Vigil dependencies...
echo.
pip install -r requirements.txt
echo.
if %ERRORLEVEL% EQU 0 (
    echo Setup complete. Run workspace.cmd to launch.
) else (
    echo.
    echo Something went wrong. Make sure Python and pip are installed.
)
echo.
pause
