@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [*] 清理构建产物与缓存...

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist assets\app.png del /q assets\app.png
if exist checker.log del /q checker.log
if exist crash.log del /q crash.log

echo [OK] 已清理 dist/ build/ __pycache__/ assets/app.png 及日志
echo 提示: data/ 运行数据目录未删除
pause
