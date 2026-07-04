@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [*] 清理非核心文件（构建产物、缓存、运行数据）...

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist chrome_temp_profile rmdir /s /q chrome_temp_profile
if exist assets\app.png del /q assets\app.png
if exist app_config.json del /q app_config.json
if exist checker.log del /q checker.log
if exist crash.log del /q crash.log

if exist data (
    for %%f in (data\*) do (
        if /i not "%%~nxf"==".gitkeep" del /q "%%f" 2>nul
    )
)

echo [OK] 已清理，保留核心源码与配置
echo.
echo 保留: bilibili_uid_checker.py gui.py assets/ scripts/ requirements*.txt
pause
