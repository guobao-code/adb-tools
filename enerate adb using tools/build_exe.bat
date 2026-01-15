@echo off
chcp 65001 >nul
echo ========================================
echo ADB工具打包脚本
echo ========================================
echo.

:: 检查是否安装了PyInstaller
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到PyInstaller，正在安装...
    pip install pyinstaller
    echo.
)

echo [1/4] 清理旧文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo [完成] 清理完成
echo.

echo [2/4] 开始打包ADB工具...
echo.

:: 使用PyInstaller打包
pyinstaller --onefile --windowed --name "ADB工具" ^
    --add-data "adb_gui.py;." ^
    --icon=NONE ^
    --noconfirm ^
    adb_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo [3/4] 复制说明文档...
if not exist "dist\说明.txt" (
    echo ADB工具使用说明 > "dist\说明.txt"
    echo ================= >> "dist\说明.txt"
    echo. >> "dist\说明.txt"
    echo 1. 确保已安装Android SDK Platform-Tools >> "dist\说明.txt"
    echo 2. 将adb.exe所在目录添加到系统PATH环境变量 >> "dist\说明.txt"
    echo 3. 双击运行 ADB工具.exe >> "dist\说明.txt"
    echo. >> "dist\说明.txt"
    echo 常见问题: >> "dist\说明.txt"
    echo - 提示"未检测到ADB": 请检查是否已安装ADB并配置PATH >> "dist\说明.txt"
    echo - 设备未显示: 请检查USB调试是否开启，数据线是否正常 >> "dist\说明.txt"
    echo - 无线连接失败: 请确保设备和电脑在同一局域网 >> "dist\说明.txt"
)

echo [完成] 说明文档已创建
echo.

echo [4/4] 打包结果...
echo.
echo ========================================
echo 打包成功！
echo ========================================
echo 输出文件位置: dist\ADB工具.exe
echo 文件大小:
dir "dist\ADB工具.exe" | find "ADB工具.exe"
echo.
echo 提示:
echo - 可执行文件已生成在 dist 目录
echo - 建议将 adb.exe 与 ADB工具.exe 放在同一目录
echo - 首次运行请关闭杀毒软件防止误杀
echo ========================================
echo.
pause
