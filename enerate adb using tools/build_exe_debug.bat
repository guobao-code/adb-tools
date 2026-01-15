@echo off
chcp 65001 >nul
echo ========================================
echo ADB工具调试模式打包脚本
echo ========================================
echo.

:: 检查是否安装了PyInstaller
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到PyInstaller，正在安装...
    pip install pyinstaller
    echo.
)

echo [1/3] 清理旧文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo [完成] 清理完成
echo.

echo [2/3] 开始打包ADB工具(调试模式)...
echo.
echo 注意: 调试模式会显示控制台窗口，便于查看日志和错误信息
echo.

:: 使用PyInstaller打包(带控制台)
pyinstaller --onefile --name "ADB工具_调试版" ^
    --add-data "adb_gui.py;." ^
    --icon=NONE ^
    --noconfirm ^
    --console ^
    adb_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 打包结果...
echo.
echo ========================================
echo 调试版打包成功！
echo ========================================
echo 输出文件位置: dist\ADB工具_调试版.exe
echo 文件大小:
dir "dist\ADB工具_调试版.exe" | find "ADB工具_调试版.exe"
echo.
echo 说明:
echo - 调试版会显示控制台窗口，可以实时查看日志
echo - 适合开发和测试阶段使用
echo - 发布时请使用 build_exe.bat 打包无控制台版本
echo ========================================
echo.
pause
