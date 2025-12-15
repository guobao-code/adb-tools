@echo off
chcp 65001
echo 正在打包程序，请稍候...
pyinstaller --onefile --console --name "视频下载工具" --clean video_downloader.py
echo.
echo ✅ 打包完成！
echo 📁 可执行文件位置: dist\视频下载工具.exe
echo.
echo 🎯 使用说明：
echo    双击运行 "视频下载工具.exe"
echo    按照提示输入参数即可下载视频
echo.
pause
