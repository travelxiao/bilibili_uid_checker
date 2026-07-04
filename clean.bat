@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [*] 清理构建缓存...
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"

echo [OK] 已清理 build/ 与 __pycache__/
echo 提示: dist/ 未删除，如需清理请手动删除 dist 文件夹
pause
