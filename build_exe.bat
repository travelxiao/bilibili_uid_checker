@echo off
chcp 65001 >nul
echo ============================================
echo   Bilibili UID Checker — 构建 EXE
echo ============================================
echo.

cd /d "%~dp0"

echo [*] 安装依赖...
py -m pip install -r requirements-build.txt -q
if errorlevel 1 (
    echo [X] 依赖安装失败
    pause
    exit /b 1
)

echo [*] 生成 Bilibili 图标...
py scripts\build_icon.py
if errorlevel 1 (
    echo [X] 图标生成失败
    pause
    exit /b 1
)

echo [*] 开始打包（约 1~3 分钟）...
py -m PyInstaller --noconfirm --clean bilibili_uid_checker.spec
if errorlevel 1 (
    echo [X] 打包失败
    pause
    exit /b 1
)

if not exist "dist\assets" mkdir "dist\assets"
copy /y "assets\app.ico" "dist\assets\" >nul
copy /y "assets\app.ico" "dist\app.ico" >nul

if not exist "dist\start_chrome_windows.bat" (
    copy /y "scripts\start_chrome_windows.bat" "dist\" >nul
)

echo.
echo [OK] 构建完成！
echo.
echo 输出目录: dist\
echo   - BilibiliUIDChecker.exe   双击即可运行（自动启动 Chrome）
echo.
echo 使用: 双击 BilibiliUIDChecker.exe，配置后点击「开始检查」
echo 前提: 本机已安装 Google Chrome
echo.
pause
