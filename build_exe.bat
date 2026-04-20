@echo off
setlocal
:: zaimanhua-desktop-suite/build_exe.bat
echo [1/4] Building Frontend...
cd "ui_web\frontend" || goto :error
call npm install || goto :error
call npm run build || goto :error
cd "..\.." || goto :error

echo [2/4] Setting up Python Environment...
if not exist "venv" python -m venv "venv" || goto :error
set PYTHON_EXE=.\venv\Scripts\python.exe
%PYTHON_EXE% -m pip install -r "requirements-desktop.txt" || goto :error

echo [3/4] Packaging EXE...
set ICON_CMD=
set ICON_DATA_CMD=
if exist "app.ico" (
    set ICON_CMD=--icon="app.ico"
    set ICON_DATA_CMD=--add-data "app.ico;."
    echo [Info] Icon found! Adding to EXE and copying for runtime...
    copy /Y "app.ico" "favicon.ico" >nul || goto :error
)

:: Clean up old builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: --- Professional Layout: Use --onedir with --contents-directory ---
:: This puts all DLLs and messy files into "internal/" subfolder.
:: Root folder will only have: hugo-zaimanhua.exe, internal/, and your data folders.
%PYTHON_EXE% -m PyInstaller --name "hugo-zaimanhua" ^
    --specpath "build" ^
    --onedir ^
    --windowed ^
    --contents-directory "internal" ^
    %ICON_CMD% ^
    %ICON_DATA_CMD% ^
    --add-data "manga_list.txt;." ^
    --add-data "zaimanhua;zaimanhua" ^
    --add-data "ui_web/frontend/dist;ui_web/frontend/dist" ^
    --add-data "favicon.ico;." ^
    main_desktop.py || goto :error

copy /Y "manga_list.txt" "dist\hugo-zaimanhua\manga_list.txt" >nul || goto :error

echo [4/4] Done! 
echo Check your clean executable folder in: zaimanhua-desktop-suite\dist\hugo-zaimanhua\
exit /b 0

:error
echo [Error] Build failed with exit code %errorlevel%.
exit /b %errorlevel%
