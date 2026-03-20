@echo off
chcp 65001 >nul
echo ADB工具打包 - 无图标版（解决UpdateResourceW错误）
echo ==================================================
echo.

:: 进入脚本所在目录
cd /d "%~dp0"

echo 正在清理旧文件...
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul

echo.
echo 开始打包（无图标）...
echo 正在执行命令：pyinstaller --onefile --windowed --name "ADB工具" adb_gui.py
echo.

pyinstaller --onefile --windowed --name "ADB工具" adb_gui.py

if errorlevel 1 (
    echo.
    echo 打包失败！尝试替代方案...
    echo.
    echo 尝试简单打包命令...
    pyinstaller --name "ADB工具" adb_gui.py
    
    if errorlevel 1 (
        echo.
        echo ❌ 打包失败！
        echo.
        echo 建议：
        echo 1. 手动运行命令查看详细错误
        echo 2. 打开CMD，进入此目录，运行：python adb_gui.py 测试脚本
        echo 3. 安装依赖：pip install pillow requests
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ✅ 打包完成！
echo.
echo 输出文件在：dist\ADB工具.exe
echo.
echo 注意：此版本没有图标
echo 如需添加图标，请参考"手动打包指南.txt"
echo.
pause