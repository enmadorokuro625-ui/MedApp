@echo off
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python and add it to PATH.
    pause
    exit /b
)

echo Updating pip...
python -m pip install --upgrade pip

echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Errors occurred during installation.
    pause
    exit /b
)

echo Installation complete.
pause