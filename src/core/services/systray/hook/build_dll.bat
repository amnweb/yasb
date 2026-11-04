@echo off
setlocal

cd /d %~dp0

:: Build x64
echo.
echo Building for x64...
cmake -A x64 -B build_x64
if %errorlevel% neq 0 exit /b %errorlevel%
cmake --build build_x64 --config Release
if %errorlevel% neq 0 exit /b %errorlevel%

:: Build ARM64
echo.
echo Building for ARM64...
cmake -A ARM64 -B build_arm64
if %errorlevel% neq 0 exit /b %errorlevel%
cmake --build build_arm64 --config Release
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo ========================================
echo Build process completed successfully.
echo ========================================
pause
