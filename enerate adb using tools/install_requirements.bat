@echo off
chcp 65001 >nul
echo ========================================
echo ADB工具依赖安装脚本
echo ========================================
echo.
echo 正在安装打包所需的依赖库...
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo.
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检查并安装PyInstaller...
python -m pip install --upgrade pip >nul 2>&1
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller安装失败
        pause
        exit /b 1
    )
    echo [完成] PyInstaller已安装
) else (
    echo [跳过] PyInstaller已安装
)

echo.
echo [2/4] 检查并安装Pillow(图标生成库)...
python -c "import PIL; print('PIL available')" >nul 2>&1
if errorlevel 1 (
    echo 正在安装Pillow...
    pip install pillow
    if errorlevel 1 (
        echo [警告] Pillow安装失败，图标生成将使用简单方法
        echo 可以手动安装: pip install pillow
    ) else (
        echo [完成] Pillow已安装
    )
) else (
    echo [跳过] Pillow已安装
)

echo.
echo [3/4] 检查其他依赖...
echo 正在检查Tkinter...
python -c "import tkinter; print('Tkinter available')" >nul 2>&1
if errorlevel 1 (
    echo [警告] Tkinter未安装，请确保Python安装时包含了Tkinter
) else (
    echo [完成] Tkinter可用
)

echo.
echo [4/4] 创建测试脚本...
echo 创建测试脚本以验证环境...
(
echo import tkinter
echo import requests
echo try:
echo     from PIL import Image
echo     print("✅ PIL/Image 可用")
echo except ImportError:
echo     print("⚠️  PIL/Image 不可用（图标生成功能受限）")
echo 
echo try:
echo     import pyinstaller
echo     print("✅ PyInstaller 可用")
echo except ImportError:
echo     print("❌ PyInstaller 不可用")
echo 
echo print("="^ * 40)
echo "环境检查完成"
) > test_env.py

python test_env.py
del test_env.py >nul 2>&1

echo.
echo ========================================
echo 依赖安装完成！
echo ========================================
echo.
echo 现在可以:
echo 1. 正式版打包: 双击 build_exe.bat
echo 2. 调试版打包: 双击 build_exe_debug.bat
echo.
echo 注意事项:
echo - 如果Pillow安装失败，图标将使用简单样式
echo - 首次打包可能需要几分钟时间
echo - 杀毒软件可能会误报，请添加到白名单
echo ========================================
echo.
pause