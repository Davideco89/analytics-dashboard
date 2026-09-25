@echo off
setlocal

pushd "%~dp0" || exit /b 1

py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.13 is required. Install it and retry.
    goto :failed
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.13 virtual environment...
    py -3.13 -m venv .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))"
if errorlevel 1 (
    echo [ERROR] The existing .venv is not Python 3.13.
    goto :failed
)

if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    if errorlevel 1 goto :failed
)

echo Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo Checking the project environment...
".venv\Scripts\python.exe" test_setup.py
if errorlevel 1 goto :failed

echo Running offline Python tests...
".venv\Scripts\python.exe" -m unittest discover -s tests/python -v
if errorlevel 1 goto :failed

echo Checking Docker Compose configuration...
docker compose config --quiet
if errorlevel 1 goto :failed

echo [OK] Setup checks passed. Build Metabase and run the data refresh as described in README.md.
popd
exit /b 0

:failed
echo [ERROR] Setup failed. See the command output above.
popd
exit /b 1
