# 体育视频获取工具集

本项目是一套用于体育视频获取、设备管理和名称生成的工具集合，包含三个主要功能模块。

## 目录

- [项目概述](#项目概述)
- [功能模块](#功能模块)
- [快速开始](#快速开始)
- [详细使用说明](#详细使用说明)
- [技术栈](#技术栈)
- [常见问题](#常见问题)

## 项目概述

本工具集主要用于：
- 通过 ADB 管理和操作 Android 设备
- 批量下载体育比赛视频
- 生成测试用的中文和英文人名

## 功能模块

### 1. ADB 工具 (enerate adb using tools/)

基于 Python + Tkinter 开发的 Android Debug Bridge 图形化管理工具，提供便捷的设备管理功能。

**核心功能：**
- 📱 设备自动检测与管理（支持有线和无线连接）
- 🌐 无线设备连接（通过 IP 地址）
- 🔍 设备信息展示（型号、IP 地址、连接类型）
- 📺 屏幕控制（息屏/亮屏）
- 🛠️ 常用 ADB 工具集
- 📝 实时日志输出与过滤
- ⚡ 命令队列管理

**文件结构：**
```
enerate adb using tools/
├── adb_gui.py              # 主程序源代码
├── ADB工具.spec            # PyInstaller 配置文件
├── build_exe.bat           # 打包脚本（正式版）
├── build_exe_debug.bat     # 打包脚本（调试版）
├── 打包说明.md             # 详细打包文档
├── 设置json.json           # 工具配置文件
├── 获取自定义.json         # 自定义配置
├── 设置自定义.json         # 自定义设置
├── build/                  # 构建临时目录
└── dist/                   # 打包输出目录
    └── ADB工具.exe         # 可执行文件
```

### 2. 视频下载工具 (Generate and export video tool/)

基于 Python 的体育视频批量下载工具，支持多线程并发下载和断点续传。

**核心功能：**
- 🎥 批量下载体育比赛视频
- ⏰ 时间范围筛选
- 🔄 支持多线程并发下载（可配置线程数）
- 💾 自动去重和跳过已下载文件
- 📊 实时下载进度显示
- 🛡️ 备用 IP 地址切换（主 IP 失败时自动切换）
- 💾 保存任务数据为 JSON 格式
- 🖥️ 图形界面操作

**默认配置：**
```python
设备 API 地址: http://192.168.2.240:8080/api/v1/data/score/qydate
备份 IP 地址: 10.0.0.56:49000
默认保存目录: 交互式视频下载/
最大并发线程数: 5
```

**文件结构：**
```
Generate and export video tool/
├── video_downloader.py     # 主程序源代码
├── build.bat               # 打包脚本
└── 运行前查看！！！         # 使用说明
```

### 3. 名称生成器 (name-generator/)

基于 Web 的随机人名生成工具，支持中文和英文人名生成。

**核心功能：**
- 🎲 中文人名生成（支持 2-4 个字）
- 🎲 英文人名生成（支持传统/现代/独特风格）
- ⚧ 性别筛选（随机/男性/女性）
- 📋 一键复制结果
- 🌙 深色/浅色主题切换
- 📱 响应式设计，支持移动端

**技术特点：**
- 纯前端实现，无需后端
- 现代化 UI 设计
- 动画效果增强用户体验

**文件结构：**
```
name-generator/
├── index.html              # 主页面
├── script.js               # JavaScript 逻辑
└── style.css               # 样式表
```

## 快速开始

### 环境要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows
- **ADB**: Android SDK Platform-Tools（用于 ADB 工具）

### ADB 工具使用

#### 方式 1：直接运行源代码

```bash
cd "d:\git-warehouse\obtain-sports-videos\enerate adb using tools"
python adb_gui.py
```

#### 方式 2：运行打包好的程序

1. 双击运行 `dist\ADB工具.exe`
2. 确保 `adb.exe` 与 `ADB工具.exe` 在同一目录，或已添加到系统 PATH

### 视频下载工具使用

```bash
cd "d:\git-warehouse\obtain-sports-videos\Generate and export video tool"
python video_downloader.py
```

按照图形界面提示：
1. 设置开始时间和结束时间
2. 配置设备 API 地址（如需修改）
3. 设置备份 IP 地址
4. 选择并发线程数
5. 点击开始下载

### 名称生成器使用

直接在浏览器中打开 `name-generator/index.html` 文件即可使用。

## 详细使用说明

### ADB 工具打包

如需打包 ADB 工具为可执行文件：

```bash
cd "d:\git-warehouse\obtain-sports-videos\enerate adb using tools"

# 正式版本（无控制台窗口）
双击运行: build_exe.bat

# 调试版本（带控制台窗口）
双击运行: build_exe_debug.bat
```

打包完成后，可执行文件位于 `dist\ADB工具.exe`。

详细打包说明请参考：[打包说明.md](enerate%20adb%20using%20tools/打包说明.md)

### 视频下载工具打包

```bash
cd "d:\git-warehouse\obtain-sports-videos\Generate and export video tool"

# 双击运行 build.bat 进行打包
```

打包完成后，可执行文件位于 `dist\视频下载工具.exe`。

## 技术栈

### ADB 工具
- **语言**: Python 3.x
- **GUI 框架**: Tkinter + ttk
- **并发处理**: threading, queue
- **打包工具**: PyInstaller

### 视频下载工具
- **语言**: Python 3.x
- **网络请求**: requests
- **GUI 框架**: Tkinter + ttk
- **并发处理**: concurrent.futures, threading
- **数据处理**: json, re, datetime

### 名称生成器
- **前端技术**: HTML5, CSS3, JavaScript (ES6+)
- **UI 设计**: 现代化响应式设计
- **主题**: 深色/浅色主题切换

## 常见问题

### ADB 工具

**Q: 提示"未检测到ADB"？**
A: 确保 adb.exe 已安装并添加到系统 PATH，或将 adb.exe 与程序放在同一目录。

**Q: 设备未显示？**
A: 
1. 检查手机是否开启 USB 调试
2. 尝试更换 USB 端口或数据线
3. 点击"重启ADB服务"按钮

**Q: 杀毒软件误报？**
A: 将程序添加到白名单，或使用调试版本查看具体错误。

### 视频下载工具

**Q: 下载速度慢？**
A: 调整并发线程数（默认 5），可根据网络情况适当增加或减少。

**Q: 视频下载失败？**
A: 
1. 检查网络连接
2. 确认设备 API 地址正确
3. 查看日志输出了解具体错误

**Q: 如何更改默认配置？**
A: 修改 `video_downloader.py` 顶部的 `DEFAULT_*` 配置变量。

### 名称生成器

**Q: 如何在本地部署？**
A: 直接打开 `index.html` 文件即可，无需服务器。

**Q: 支持自定义人名字库吗？**
A: 可以修改 `script.js` 中的字库数组来添加自定义内容。

## 许可证

本项目仅供学习和个人使用。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进本项目。

---

**提示**: 首次使用前请仔细阅读各模块的使用说明文档，确保环境配置正确。
