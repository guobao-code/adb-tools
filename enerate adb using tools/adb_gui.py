import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import subprocess
import threading
import os
from datetime import datetime
import queue
import socket
import time
import sys
##123

class ADBGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB 工具 - 国保版")
        self.root.geometry("570x700")  # 增加窗口高度以容纳新功能
        self.root.minsize(470, 600)

        # 存储设备列表
        self.devices_list = []
        self.unauthorized_devices_list = []

        # 命令队列
        self.command_queue = queue.Queue()
        self.processing_command = False

        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 设备信息区域
        device_frame = ttk.LabelFrame(main_frame, text="设备信息", padding="5")
        device_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        # 设备操作按钮（调整为两行显示）
        device_buttons_frame = ttk.Frame(device_frame)
        device_buttons_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))

        # ===================== 第一行按钮 =====================
        ttk.Button(device_buttons_frame, text="刷新设备列表",
                   command=self.refresh_devices).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="连接设备",
                   command=self.connect_device).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="安装APK",
                   command=self.install_apk).grid(row=0, column=2, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="主板信息",
                   command=self.show_board_info).grid(row=0, column=3, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="一键断开所有",
                   command=self.disconnect_all_devices).grid(row=0, column=4, padx=2, pady=2)

        # ===================== 第二行按钮 =====================
        ttk.Button(device_buttons_frame, text="筛选异常设备",
                   command=self.filter_abnormal_devices).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="重启ADB服务",
                   command=self.restart_adb_server).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="一键息屏",
                   command=self.onekey_screen_off).grid(row=1, column=2, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="一键亮屏",
                   command=self.onekey_screen_on).grid(row=1, column=3, padx=2, pady=2)
        ttk.Button(device_buttons_frame, text="文件传输",
                   command=self.show_file_manager).grid(row=1, column=4, padx=2, pady=2)

        # 设备列表显示区域
        devices_list_frame = ttk.Frame(device_frame)
        devices_list_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))

        # 设备列表标签
        ttk.Label(devices_list_frame, text="已连接设备:", font=("", 9, "bold")).grid(row=0, column=0, sticky=tk.W,
                                                                                     pady=(0, 5))

        # 创建设备列表容器（使用Canvas和Frame实现滚动）
        self.devices_canvas = tk.Canvas(devices_list_frame, height=80, bg="white")
        self.devices_canvas.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # 添加滚动条
        scrollbar = ttk.Scrollbar(devices_list_frame, orient="vertical", command=self.devices_canvas.yview)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.devices_canvas.configure(yscrollcommand=scrollbar.set)

        # 设备列表框架
        self.devices_frame = ttk.Frame(self.devices_canvas)
        self.devices_canvas_window = self.devices_canvas.create_window((0, 0), window=self.devices_frame, anchor="nw")

        # 绑定事件以确保正确滚动
        self.devices_frame.bind("<Configure>", self.on_devices_frame_configure)
        self.devices_canvas.bind("<Configure>", self.on_devices_canvas_configure)

        # 状态标签
        self.device_status_label = ttk.Label(device_frame, text="正在检测设备...", foreground="blue")
        self.device_status_label.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        device_frame.columnconfigure(0, weight=1)

        # 输出区域
        output_frame = ttk.LabelFrame(main_frame, text="输出", padding="5")
        output_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 输出控制按钮
        output_control_frame = ttk.Frame(output_frame)
        output_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Button(output_control_frame, text="清除输出",
                   command=self.clear_output).pack(side=tk.LEFT, padx=2)

        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            width=80,
            height=20,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        self.output_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)

        self.status_label = ttk.Label(status_frame, text="正在启动ADB服务...")
        self.status_label.pack(side=tk.LEFT)

        # 配置权重使布局可扩展
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        device_frame.columnconfigure(0, weight=1)
        devices_list_frame.columnconfigure(0, weight=1)

        # 启动ADB服务
        self.ensure_adb_server_running()

        # 启动命令处理线程
        self._start_command_processor()

        # 添加退出时的清理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def ensure_adb_server_running(self):
        """确保ADB服务正在运行"""
        def _check_adb_server():
            try:
                # 尝试列出设备来检查ADB服务状态
                result = subprocess.run(
                    "adb devices",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # 如果命令执行成功，说明ADB服务正常
                if result.returncode == 0:
                    self.root.after(0, lambda: self.update_status("ADB服务正常运行"))
                    self.root.after(0, self.refresh_devices)
                else:
                    self.root.after(0, self._restart_adb_server)
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                self.root.after(0, lambda: self._restart_adb_server())

        thread = threading.Thread(target=_check_adb_server)
        thread.daemon = True
        thread.start()

    def _restart_adb_server(self):
        """重启ADB服务（内部方法）"""
        try:
            self.update_status("正在重启ADB服务...")
            
            # 杀死现有ADB服务
            subprocess.run(["adb", "kill-server"], 
                          capture_output=True, 
                          timeout=5)
            
            # 等待一段时间
            time.sleep(2)
            
            # 启动新ADB服务
            result = subprocess.run(["adb", "start-server"], 
                                  capture_output=True, 
                                  text=True,
                                  timeout=10)
            
            if result.returncode == 0:
                self.update_status("ADB服务重启成功")
                # 重启后刷新设备列表
                self.root.after(1000, self.refresh_devices)
            else:
                self.update_status("ADB服务启动失败")
                messagebox.showerror("错误", 
                    "ADB服务启动失败！\n\n"
                    "请检查：\n"
                    "1. ADB是否正确安装\n"
                    "2. ADB是否添加到系统PATH\n"
                    "3. 端口5037是否被占用")
                
        except subprocess.TimeoutExpired:
            self.update_status("ADB服务启动超时")
            messagebox.showwarning("警告", "ADB服务启动超时，但可能仍在启动中")
        except Exception as e:
            self.update_status(f"ADB服务重启失败: {str(e)}")
            messagebox.showerror("错误", 
                f"ADB服务启动失败:\n{str(e)}\n\n"
                "请检查ADB是否安装并配置到系统PATH中")

    def restart_adb_server(self):
        """重启ADB服务（用户调用）"""
        if messagebox.askyesno("确认", "确定要重启ADB服务吗？"):
            self._restart_adb_server()

    def _start_command_processor(self):
        """启动命令处理线程"""

        def process_commands():
            while True:
                cmd, device_id, retry_count = self.command_queue.get()
                if cmd is None:  # 停止信号
                    break
                self._run_adb_command(cmd, device_id, retry_count)
                self.command_queue.task_done()

        self.command_processor = threading.Thread(target=process_commands)
        self.command_processor.daemon = True
        self.command_processor.start()

    def on_devices_frame_configure(self, event):
        """更新设备列表滚动区域"""
        self.devices_canvas.configure(scrollregion=self.devices_canvas.bbox("all"))

    def on_devices_canvas_configure(self, event):
        """调整设备列表框架宽度以适应画布"""
        self.devices_canvas.itemconfig(self.devices_canvas_window, width=event.width)

    def normalize_text(self, text):
        """将中文标点符号转换为英文标点符号"""
        # 定义中英文标点符号映射
        chinese_to_english = {
            '：': ':',  # 中文冒号转英文冒号
            '，': ',',  # 中文逗号转英文逗号
            '；': ';',  # 中文分号转英文分号
            '！': '!',  # 中文感叹号转英文感叹号
            '？': '?',  # 中文问号转英文问号
            '。': '.',  # 中文句号转英文句号
        }

        # 替换所有中文标点符号
        result = ""
        for char in text:
            if char in chinese_to_english:
                result += chinese_to_english[char]
            else:
                result += char

        return result

    def check_network_connectivity(self, ip, port):
        """检查网络连通性"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, int(port)))
            sock.close()
            return result == 0
        except:
            return False

    def execute_adb_command(self, cmd, device_id=None, retry_count=2):
        """执行ADB命令"""
        # 如果命令不是以adb开头，则加上adb
        if not cmd.strip().startswith('adb '):
            cmd = 'adb ' + cmd

        # 如果指定了设备ID，则添加设备选择参数
        if device_id:
            cmd = cmd.replace('adb ', f'adb -s {device_id} ', 1)

        self.update_status(f"执行命令: {cmd}")
        self.command_queue.put((cmd, device_id, retry_count))

    def _run_adb_command(self, cmd, device_id=None, retry_count=2):
        """在新线程中运行ADB命令"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device_prefix = f"[{device_id}] " if device_id else ""
        
        # 优化息屏/亮屏命令的输出提示
        if "input keyevent 26" in cmd:
            if "一键亮屏" in self.status_label.cget("text"):
                self.append_output(f"[{timestamp}] {device_prefix}执行：一键亮屏命令\n")
            else:
                self.append_output(f"[{timestamp}] {device_prefix}执行：一键息屏命令\n")
        else:
            self.append_output(f"[{timestamp}] {device_prefix}执行: {cmd}\n")

        try:
            # 执行命令
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.append_output(f"{device_prefix}{output}")

            # 获取错误输出
            stderr = process.stderr.read()
            if stderr:
                self.append_output(f"{device_prefix}错误: {stderr}")

            return_code = process.poll()

            # 如果命令失败且还有重试次数，自动重试
            if return_code != 0 and retry_count > 0:
                self.append_output(f"{device_prefix}命令执行失败，正在重试... ({retry_count}次剩余)\n")
                time.sleep(1)
                self._run_adb_command(cmd.split(' ', 1)[1] if cmd.startswith('adb ') else cmd, 
                                    device_id, retry_count-1)
                return

            status_msg = f"{device_prefix}命令执行成功" if return_code == 0 else f"{device_prefix}命令执行失败，退出码: {return_code}"
            self.append_output(f"\n{status_msg}\n")
            self.append_output("=" * 60 + "\n")

            self.root.after(0, lambda: self.update_status(status_msg))

        except Exception as e:
            error_msg = f"{device_prefix}执行命令时出错: {str(e)}\n"
            self.append_output(error_msg)
            self.root.after(0, lambda: self.update_status(f"错误: {str(e)}"))

    def append_output(self, text):
        """在输出区域追加文本"""
        self.root.after(0, self._update_output, text)

    def _update_output(self, text):
        """更新输出区域（在主线程中执行）"""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.update_idletasks()

    def clear_output(self):
        """清除输出区域"""
        self.output_text.delete(1.0, tk.END)
        self.update_status("输出已清除")

    def update_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=message)

    def refresh_devices(self):
        """刷新设备列表"""

        def _refresh():
            self.root.after(0, lambda: self.update_status("正在刷新设备列表..."))
            self.root.after(0, lambda: self.device_status_label.config(text="正在检测设备..."))

            try:
                result = subprocess.run(
                    "adb devices",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                lines = result.stdout.strip().split('\n')

                devices = []
                unauthorized_devices = []

                for line in lines[1:]:
                    if line.strip() and '\t' in line:
                        device_id, status = line.strip().split('\t')
                        if status == 'device':
                            devices.append(device_id)
                        elif status == 'unauthorized':
                            unauthorized_devices.append(device_id)

                # 更新设备列表
                self.devices_list = devices
                self.unauthorized_devices_list = unauthorized_devices

                # 更新设备列表显示
                self.root.after(0, self.update_devices_display, devices, unauthorized_devices)

                if devices:
                    self.root.after(0, lambda: self.update_status(f"找到 {len(devices)} 个设备"))
                elif unauthorized_devices:
                    self.root.after(0, lambda: self.update_status("设备未授权，请检查设备授权提示"))
                else:
                    self.root.after(0, lambda: self.update_status("未找到设备"))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self.device_status_label.config(text="设备检测超时"))
                self.root.after(0, lambda: self.update_status("设备检测超时"))
            except Exception as e:
                self.root.after(0, lambda: self.device_status_label.config(text=f"刷新失败: {str(e)}"))
                self.root.after(0, lambda: self.update_status(f"刷新失败: {str(e)}"))

        thread = threading.Thread(target=_refresh)
        thread.daemon = True
        thread.start()

    def update_devices_display(self, devices, unauthorized_devices):
        """更新设备列表显示"""
        # 清除现有设备显示
        for widget in self.devices_frame.winfo_children():
            widget.destroy()

        # 显示已授权设备
        if devices:
            self.device_status_label.config(text=f"找到 {len(devices)} 个已授权设备")

            # 计算每行显示的设备数量
            devices_per_row = 3
            row = 0
            col = 0

            for i, device in enumerate(devices):
                # 创建设备标签框架
                device_frame = ttk.Frame(self.devices_frame, relief="solid", borderwidth=1)
                device_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))

                # 设备ID标签
                device_label = ttk.Label(device_frame, text=device, font=("Consolas", 9))
                device_label.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

                # 状态标签
                status_label = ttk.Label(device_frame, text="已授权", foreground="green", font=("", 8))
                status_label.grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)

                # 设备操作按钮
                button_frame = ttk.Frame(device_frame)
                button_frame.grid(row=2, column=0, padx=5, pady=2)

                # 断开此设备按钮
                ttk.Button(button_frame, text="断开",
                           command=lambda d=device: self.disconnect_single_device(d),
                           width=6).pack(side=tk.LEFT, padx=2)

                # 远程控制此设备按钮
                ttk.Button(button_frame, text="控制",
                           command=lambda d=device: self.remote_control_device(d),
                           width=6).pack(side=tk.LEFT, padx=2)

                # 文件管理按钮
                ttk.Button(button_frame, text="文件",
                           command=lambda d=device: self.show_file_manager(d),
                           width=6).pack(side=tk.LEFT, padx=2)

                # 更新行列位置
                col += 1
                if col >= devices_per_row:
                    col = 0
                    row += 1
        elif unauthorized_devices:
            self.device_status_label.config(text=f"找到 {len(unauthorized_devices)} 个未授权设备")

            # 显示未授权设备
            row = 0
            col = 0
            devices_per_row = 3

            for i, device in enumerate(unauthorized_devices):
                # 创建设备标签框架
                device_frame = ttk.Frame(self.devices_frame, relief="solid", borderwidth=1)
                device_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))

                # 设备ID标签
                device_label = ttk.Label(device_frame, text=device, font=("Consolas", 9))
                device_label.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

                # 状态标签
                status_label = ttk.Label(device_frame, text="未授权", foreground="red", font=("", 8))
                status_label.grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)

                # 更新行列位置
                col += 1
                if col >= devices_per_row:
                    col = 0
                    row += 1
        else:
            self.device_status_label.config(text="未检测到设备")

            # 显示无设备提示
            no_device_label = ttk.Label(self.devices_frame, text="无设备连接", foreground="gray")
            no_device_label.grid(row=0, column=0, padx=5, pady=5)

        # 更新滚动区域
        self.devices_frame.update_idletasks()
        self.devices_canvas.configure(scrollregion=self.devices_canvas.bbox("all"))

    def disconnect_single_device(self, device):
        """断开单个设备连接"""
        self.execute_adb_command(f"disconnect {device}")
        self.root.after(2000, self.refresh_devices)

    def remote_control_device(self, device):
        """远程控制指定设备"""
        # 检查scrcpy是否可用
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            result = messagebox.askquestion(
                "scrcpy未安装",
                "未找到scrcpy命令，是否要安装scrcpy？\n\n安装方法：\n"
                "Windows: 下载scrcpy并添加到PATH\n"
                "macOS: brew install scrcpy\n"
                "Linux: sudo apt install scrcpy",
                icon='warning'
            )
            if result == 'yes':
                # 打开浏览器到scrcpy GitHub页面
                import webbrowser
                webbrowser.open("https://github.com/Genymobile/scrcpy")
            return

        # 启动scrcpy并指定设备
        cmd = f"scrcpy -s {device}"

        # 在新线程中启动scrcpy
        def run_scrcpy():
            try:
                self.update_status(f"启动scrcpy远程控制设备: {device}")
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # 等待进程结束
                process.wait()
                self.update_status(f"设备 {device} 的scrcpy远程控制已结束")
            except Exception as e:
                self.update_status(f"启动scrcpy失败: {str(e)}")
                messagebox.showerror("错误", f"启动scrcpy失败: {str(e)}")

        thread = threading.Thread(target=run_scrcpy)
        thread.daemon = True
        thread.start()

    def disconnect_all_devices(self):
        """一键断开所有已连接的设备"""
        if not self.devices_list and not self.unauthorized_devices_list:
            messagebox.showinfo("提示", "当前没有已连接的设备")
            return

        if messagebox.askyesno("确认", "确定要断开所有已连接的设备吗？"):
            # 断开所有已授权设备
            for device in self.devices_list:
                self.execute_adb_command(f"disconnect {device}")

            # 断开所有未授权设备
            for device in self.unauthorized_devices_list:
                self.execute_adb_command(f"disconnect {device}")

            self.update_status("正在断开所有设备连接...")
            self.root.after(2000, self.refresh_devices)

    # ========== 一键息屏核心方法 ==========
    def onekey_screen_off(self):
        """一键息屏所有已授权设备"""
        # 检查是否有已授权设备
        if not self.devices_list:
            messagebox.showinfo("提示", "当前没有已授权的设备可执行息屏操作！")
            return
        
        # 弹出确认框，避免误操作
        confirm = messagebox.askyesno(
            "确认息屏", 
            f"检测到 {len(self.devices_list)} 个已授权设备，\n是否确认对所有设备执行一键息屏？"
        )
        if not confirm:
            return
        
        # 更新状态栏，提示用户操作开始
        self.update_status(f"正在向 {len(self.devices_list)} 个设备发送息屏指令...")
        # 输出区添加操作日志
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_output(f"\n[{timestamp}] 开始执行批量息屏操作\n")
        self.append_output(f"目标设备数量：{len(self.devices_list)}\n")
        self.append_output("-" * 50 + "\n")
        
        # 遍历所有已授权设备，逐个发送息屏命令
        for device_id in self.devices_list:
            # ADB息屏核心命令：模拟电源键事件（keyevent 26 = 电源键）
            adb_cmd = "shell input keyevent 26"
            # 调用原有命令执行方法，自动加入队列（重试1次即可，避免重复亮屏）
            self.execute_adb_command(adb_cmd, device_id=device_id, retry_count=1)
        
        # 操作完成后更新状态（延迟1秒确保命令都已发送）
        def finish_tip():
            self.update_status(f"息屏指令已发送完毕（共 {len(self.devices_list)} 个设备）")
            self.append_output(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 批量息屏指令发送完成\n")
            self.append_output("=" * 50 + "\n")
        
        self.root.after(1000, finish_tip)

    # ========== 一键亮屏核心方法 ==========
    def onekey_screen_on(self):
        """一键亮屏所有已授权设备"""
        # 检查是否有已授权设备
        if not self.devices_list:
            messagebox.showinfo("提示", "当前没有已授权的设备可执行亮屏操作！")
            return
        
        # 弹出确认框，避免误操作
        confirm = messagebox.askyesno(
            "确认亮屏", 
            f"检测到 {len(self.devices_list)} 个已授权设备，\n是否确认对所有设备执行一键亮屏？"
        )
        if not confirm:
            return
        
        # 更新状态栏，提示用户操作开始
        self.update_status(f"正在向 {len(self.devices_list)} 个设备发送亮屏指令...")
        # 输出区添加操作日志
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_output(f"\n[{timestamp}] 开始执行批量亮屏操作\n")
        self.append_output(f"目标设备数量：{len(self.devices_list)}\n")
        self.append_output("-" * 50 + "\n")
        
        # 遍历所有已授权设备，逐个发送亮屏命令
        for device_id in self.devices_list:
            # 亮屏核心命令：再次模拟电源键（息屏状态下按电源键=亮屏）
            adb_cmd = "shell input keyevent 26"
            # 备选方案（部分设备支持）：直接点亮屏幕
            # adb_cmd = "shell input keyevent 82"  # 模拟解锁键
            self.execute_adb_command(adb_cmd, device_id=device_id, retry_count=1)
        
        # 操作完成后更新状态（延迟1秒确保命令都已发送）
        def finish_tip():
            self.update_status(f"亮屏指令已发送完毕（共 {len(self.devices_list)} 个设备）")
            self.append_output(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 批量亮屏指令发送完成\n")
            self.append_output("=" * 50 + "\n")
        
        self.root.after(1000, finish_tip)

    def filter_abnormal_devices(self):
        """筛选已不存在或不正常连接的设备"""

        def _check_devices():
            self.update_status("正在检测设备连接状态...")

            abnormal_devices = []

            # 检查已授权设备
            for device in self.devices_list:
                try:
                    # 尝试执行一个简单的命令来检查设备是否响应
                    result = subprocess.run(
                        f"adb -s {device} shell echo test",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # 如果命令执行失败，说明设备连接异常
                    if result.returncode != 0:
                        abnormal_devices.append((device, "连接异常"))
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
                    abnormal_devices.append((device, "连接超时或无响应"))

            # 检查未授权设备
            for device in self.unauthorized_devices_list:
                abnormal_devices.append((device, "未授权"))

            # 更新显示
            self.root.after(0, self.update_abnormal_devices_display, abnormal_devices)

            if abnormal_devices:
                self.root.after(0, lambda: self.update_status(f"找到 {len(abnormal_devices)} 个异常设备"))
            else:
                self.root.after(0, lambda: self.update_status("未找到异常设备"))
                self.root.after(0, lambda: messagebox.showinfo("提示", "未找到异常设备"))

        thread = threading.Thread(target=_check_devices)
        thread.daemon = True
        thread.start()

    def update_abnormal_devices_display(self, abnormal_devices):
        """更新异常设备列表显示"""
        # 清除现有设备显示
        for widget in self.devices_frame.winfo_children():
            widget.destroy()

        if abnormal_devices:
            self.device_status_label.config(text=f"找到 {len(abnormal_devices)} 个异常设备")

            # 计算每行显示的设备数量
            devices_per_row = 3
            row = 0
            col = 0

            for i, (device, status) in enumerate(abnormal_devices):
                # 创建设备标签框架
                device_frame = ttk.Frame(self.devices_frame, relief="solid", borderwidth=1)
                device_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))

                # 设备ID标签
                device_label = ttk.Label(device_frame, text=device, font=("Consolas", 9))
                device_label.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

                # 状态标签
                if status == "未授权":
                    status_label = ttk.Label(device_frame, text=status, foreground="red", font=("", 8))
                else:
                    status_label = ttk.Label(device_frame, text=status, foreground="orange", font=("", 8))
                status_label.grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)

                # 设备操作按钮
                button_frame = ttk.Frame(device_frame)
                button_frame.grid(row=2, column=0, padx=5, pady=2)

                # 断开此设备按钮
                ttk.Button(button_frame, text="断开",
                           command=lambda d=device: self.disconnect_single_device(d),
                           width=6).pack(side=tk.LEFT, padx=2)

                # 更新行列位置
                col += 1
                if col >= devices_per_row:
                    col = 0
                    row += 1
        else:
            self.device_status_label.config(text="未找到异常设备")

            # 显示无异常设备提示
            no_device_label = ttk.Label(self.devices_frame, text="无异常设备", foreground="gray")
            no_device_label.grid(row=0, column=0, padx=5, pady=5)

        # 更新滚动区域
        self.devices_frame.update_idletasks()
        self.devices_canvas.configure(scrollregion=self.devices_canvas.bbox("all"))

    def connect_device(self):
        """连接设备通过IP地址"""
        # 先确保ADB服务运行
        self.ensure_adb_server_running()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("连接设备")
        dialog.geometry("450x460")  # 调整对话框高度以容纳提示信息
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示对话框
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # 主框架，用于更好的布局管理
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # IP地址输入
        ip_frame = ttk.Frame(main_frame)
        ip_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ip_frame, text="IP地址:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ip_var = tk.StringVar()
        ip_entry = ttk.Entry(ip_frame, textvariable=ip_var, width=20)
        ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ip_entry.focus()
        ip_frame.columnconfigure(1, weight=1)

        # 端口输入
        port_frame = ttk.Frame(main_frame)
        port_frame.pack(fill=tk.X, pady=5)

        ttk.Label(port_frame, text="端口:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        port_var = tk.StringVar(value="5555")
        port_entry = ttk.Entry(port_frame, textvariable=port_var, width=10)
        port_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        port_frame.columnconfigure(1, weight=1)

        # 预设IP地址区域
        preset_frame = ttk.LabelFrame(main_frame, text="常用IP地址", padding="5")
        preset_frame.pack(fill=tk.X, pady=10)

        # 创建预设按钮网格
        preset_ips = [
            "10.0.0.2", "10.0.0.3", "10.0.0.4",
            "10.0.0.5", "10.0.0.6", "10.0.0.7",
            "10.0.0.8", "10.0.0.9", "10.0.0.100",
            "10.0.0.200", "192.168.2.31", "192.168.123.1"
        ]

        # 3列布局
        for i, ip in enumerate(preset_ips):
            row = i // 3
            col = i % 3
            ttk.Button(
                preset_frame, 
                text=ip, 
                width=15,
                command=lambda ip=ip: self._set_ip_address(ip_var, port_var, ip)
            ).grid(row=row, column=col, padx=2, pady=2, sticky=tk.W+tk.E)

        # 连接提示信息
        tips_frame = ttk.LabelFrame(main_frame, text="连接提示", padding="5")
        tips_frame.pack(fill=tk.X, pady=10)

        tips = [
            "• 确保设备已开启USB调试",
            "• 首次使用需先用USB连接授权",
            "• 设备需执行: adb tcpip 5555",
            "• 确保设备和电脑在同一网络",
            "• 防火墙可能阻止连接，请检查防火墙设置"
        ]

        for tip in tips:
            ttk.Label(tips_frame, text=tip, font=("", 8), foreground="gray").pack(anchor=tk.W)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)

        def do_connect():
            ip = ip_var.get().strip()
            port = port_var.get().strip()

            # 应用符号转换
            ip = self.normalize_text(ip)
            port = self.normalize_text(port)

            if not ip:
                messagebox.showwarning("警告", "请输入IP地址", parent=dialog)
                return

            # 检查网络连通性
            if not self.check_network_connectivity(ip, port):
                result = messagebox.askyesno(
                    "网络连接问题",
                    f"无法连接到 {ip}:{port}\n\n"
                    f"可能的原因:\n"
                    f"• 设备未开启网络ADB调试\n"
                    f"• 防火墙阻止连接\n"
                    f"• 设备和电脑不在同一网络\n"
                    f"• 端口号不正确\n\n"
                    f"是否仍然尝试连接?",
                    parent=dialog
                )
                if not result:
                    return

            # 显示转换后的地址
            address = f"{ip}:{port}" if port else ip
            self.append_output(f"转换后的地址: {address}\n")

            self.execute_adb_command(f"connect {address}", retry_count=3)
            dialog.destroy()
            self.root.after(2000, self.refresh_devices)

        def do_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="连接", command=do_connect, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=do_cancel, width=10).pack(side=tk.LEFT, padx=10)

        # 添加弹性空间使按钮居中
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(3, weight=1)

        dialog.bind('<Return>', lambda e: do_connect())

    def _set_ip_address(self, ip_var, port_var, ip):
        """设置IP地址到输入框"""
        ip_var.set(ip)
        port_var.set("5555")  # 同时设置默认端口

    def install_apk(self):
        """安装APK文件"""
        file_path = filedialog.askopenfilename(
            title="选择APK文件",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")]
        )
        if file_path:
            # 对文件路径也应用符号转换，以防路径中包含中文符号
            file_path = self.normalize_text(file_path)
            self.execute_adb_command(f'install -r "{file_path}"')

    def show_board_info(self):
        """显示主板信息"""
        if not self.devices_list:
            messagebox.showwarning("警告", "没有可用的设备")
            return

        # 如果有多个设备，让用户选择
        device = None
        if len(self.devices_list) > 1:
            device = self.ask_select_device()
            if not device:
                return
        else:
            device = self.devices_list[0]

        # 在新窗口中显示主板信息
        self.show_board_info_window(device)

    def ask_select_device(self):
        """弹出设备选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择设备")
        dialog.geometry("300x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示对话框
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="请选择设备:").pack(pady=10)

        # 设备列表
        device_var = tk.StringVar()
        device_listbox = tk.Listbox(main_frame, height=6)
        for device in self.devices_list:
            device_listbox.insert(tk.END, device)
        device_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        selected_device = None

        def do_ok():
            nonlocal selected_device
            selection = device_listbox.curselection()
            if selection:
                selected_device = device_listbox.get(selection[0])
                dialog.destroy()
            else:
                messagebox.showwarning("警告", "请选择一个设备", parent=dialog)

        def do_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="确定", command=do_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=do_cancel).pack(side=tk.LEFT, padx=10)

        dialog.wait_window()
        return selected_device

    def show_board_info_window(self, device):
        """显示主板信息窗口"""
        info_window = tk.Toplevel(self.root)
        info_window.title(f"设备 {device} 主板信息")
        info_window.geometry("600x500")
        info_window.minsize(500, 400)

        # 居中显示窗口
        info_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - info_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - info_window.winfo_height()) // 2
        info_window.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(info_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 设备ID显示
        device_frame = ttk.Frame(main_frame)
        device_frame.pack(fill=tk.X, pady=5)
        ttk.Label(device_frame, text=f"设备: {device}", font=("", 10, "bold")).pack(side=tk.LEFT)

        # 信息显示区域
        info_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        info_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="刷新", 
                  command=lambda: self.refresh_board_info(device, info_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="关闭", 
                  command=info_window.destroy).pack(side=tk.LEFT, padx=5)

        # 初始加载信息
        self.refresh_board_info(device, info_text)

    def refresh_board_info(self, device, info_text):
        """刷新主板信息"""
        info_text.delete(1.0, tk.END)
        info_text.insert(tk.END, "正在获取设备信息...\n\n")
        info_text.update_idletasks()

        # 在新线程中获取信息
        def _get_board_info():
            try:
                # 获取设备基本信息
                info_text.delete(1.0, tk.END)
                info_text.insert(tk.END, f"设备IP: {device}\n")
                info_text.insert(tk.END, "=" * 50 + "\n\n")

                # 获取各种硬件信息
                commands = {
                    "设备型号": "getprop ro.product.model",
                    "制造商": "getprop ro.product.manufacturer",
                    "品牌": "getprop ro.product.brand",
                    "设备名称": "getprop ro.product.name",
                    "主板平台": "getprop ro.board.platform",
                    "硬件": "getprop ro.hardware",
                    "CPU ABI": "getprop ro.product.cpu.abi",
                    "Android版本": "getprop ro.build.version.release",
                    "内核版本": "cat /proc/version",
                    "CPU信息": "cat /proc/cpuinfo"
                }

                for title, cmd in commands.items():
                    info_text.insert(tk.END, f"{title}:\n")
                    info_text.insert(tk.END, "-" * 30 + "\n")
                    
                    try:
                        result = subprocess.run(
                            f"adb -s {device} shell {cmd}",
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if result.returncode == 0:
                            output = result.stdout.strip()
                            if output:
                                info_text.insert(tk.END, f"{output}\n")
                            else:
                                info_text.insert(tk.END, "无信息\n")
                        else:
                            info_text.insert(tk.END, f"获取失败: {result.stderr}\n")
                    except Exception as e:
                        info_text.insert(tk.END, f"执行错误: {str(e)}\n")
                    
                    info_text.insert(tk.END, "\n")

            except Exception as e:
                info_text.insert(tk.END, f"获取设备信息时出错: {str(e)}")

        thread = threading.Thread(target=_get_board_info)
        thread.daemon = True
        thread.start()

    def show_file_manager(self, device=None):
        """显示文件管理器窗口"""
        if not device:
            if not self.devices_list:
                messagebox.showwarning("警告", "没有可用的设备")
                return
            
            # 如果有多个设备，让用户选择
            if len(self.devices_list) > 1:
                device = self.ask_select_device()
                if not device:
                    return
            else:
                device = self.devices_list[0]

        # 创建文件管理器窗口
        file_window = tk.Toplevel(self.root)
        file_window.title(f"文件管理器 - {device}")
        file_window.geometry("800x600")
        file_window.minsize(700, 500)

        # 居中显示窗口
        file_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - file_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - file_window.winfo_height()) // 2
        file_window.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(file_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 设备信息
        device_frame = ttk.Frame(main_frame)
        device_frame.pack(fill=tk.X, pady=5)
        ttk.Label(device_frame, text=f"设备: {device}", font=("", 10, "bold")).pack(side=tk.LEFT)

        # 路径导航
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)

        ttk.Label(path_frame, text="当前路径:").pack(side=tk.LEFT)
        self.current_path_var = tk.StringVar(value="/sdcard")
        path_entry = ttk.Entry(path_frame, textvariable=self.current_path_var, width=50)
        path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(path_frame, text="转到", 
                  command=lambda: self.browse_device_path(device, self.current_path_var.get(), file_list)).pack(side=tk.LEFT, padx=2)
        ttk.Button(path_frame, text="上级目录", 
                  command=lambda: self.go_parent_directory(device, file_list)).pack(side=tk.LEFT, padx=2)
        ttk.Button(path_frame, text="刷新", 
                  command=lambda: self.browse_device_path(device, self.current_path_var.get(), file_list)).pack(side=tk.LEFT, padx=2)

        # 文件列表
        file_list_frame = ttk.LabelFrame(main_frame, text="文件列表", padding="5")
        file_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 创建文件列表
        columns = ("名称", "大小", "权限", "类型")
        file_list = ttk.Treeview(file_list_frame, columns=columns, show="headings", height=15)
        
        # 设置列标题
        for col in columns:
            file_list.heading(col, text=col)
            file_list.column(col, width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(file_list_frame, orient="vertical", command=file_list.yview)
        file_list.configure(yscrollcommand=scrollbar.set)
        
        file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文件操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="上传文件", 
                  command=lambda: self.upload_file(device, self.current_path_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="上传文件夹", 
                  command=lambda: self.upload_folder(device, self.current_path_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="下载选中", 
                  command=lambda: self.download_selected(device, file_list)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除选中", 
                  command=lambda: self.delete_selected(device, file_list)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="新建文件夹", 
                  command=lambda: self.create_folder(device, self.current_path_var.get())).pack(side=tk.LEFT, padx=5)

        # 绑定双击事件
        file_list.bind("<Double-1>", lambda e: self.on_file_double_click(device, file_list))

        # 初始加载文件列表
        self.browse_device_path(device, "/sdcard", file_list)

    def browse_device_path(self, device, path, file_list):
        """浏览设备路径"""
        # 清空文件列表
        for item in file_list.get_children():
            file_list.delete(item)
        
        # 更新当前路径
        self.current_path_var.set(path)
        
        # 获取文件列表
        def _get_file_list():
            try:
                # 执行ls命令获取文件列表
                cmd = f'adb -s {device} shell ls -la "{path}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    
                    # 解析文件列表
                    for line in lines:
                        if line and not line.startswith('total'):
                            parts = line.split()
                            if len(parts) >= 9:
                                # 解析权限、大小、名称等信息
                                permissions = parts[0]
                                size = parts[4]
                                name = ' '.join(parts[8:])
                                
                                # 判断是文件还是目录
                                file_type = "目录" if permissions.startswith('d') else "文件"
                                
                                # 添加到文件列表
                                file_list.insert("", "end", values=(name, size, permissions, file_type))
                else:
                    messagebox.showerror("错误", f"无法访问路径: {path}")
                    
            except Exception as e:
                messagebox.showerror("错误", f"获取文件列表失败: {str(e)}")
        
        thread = threading.Thread(target=_get_file_list)
        thread.daemon = True
        thread.start()

    def go_parent_directory(self, device, file_list):
        """返回上级目录"""
        current_path = self.current_path_var.get()
        if current_path != "/":
            parent_path = os.path.dirname(current_path)
            if not parent_path:
                parent_path = "/"
            self.browse_device_path(device, parent_path, file_list)

    def on_file_double_click(self, device, file_list):
        """文件双击事件"""
        selection = file_list.selection()
        if selection:
            item = file_list.item(selection[0])
            values = item['values']
            if values and values[3] == "目录":  # 如果是目录
                current_path = self.current_path_var.get()
                new_path = os.path.join(current_path, values[0]).replace('\\', '/')
                self.browse_device_path(device, new_path, file_list)

    def upload_file(self, device, dest_path):
        """上传文件到设备"""
        file_path = filedialog.askopenfilename(title="选择要上传的文件")
        if file_path:
            # 对文件路径应用符号转换
            file_path = self.normalize_text(file_path)
            dest_file = os.path.join(dest_path, os.path.basename(file_path)).replace('\\', '/')
            
            # 执行上传命令
            cmd = f'adb -s {device} push "{file_path}" "{dest_file}"'
            self.execute_adb_command(cmd, device)
            
            # 上传完成后刷新文件列表
            self.root.after(2000, lambda: self.browse_device_path(device, dest_path, None))

    def upload_folder(self, device, dest_path):
        """上传文件夹到设备"""
        folder_path = filedialog.askdirectory(title="选择要上传的文件夹")
        if folder_path:
            # 对文件夹路径应用符号转换
            folder_path = self.normalize_text(folder_path)
            dest_folder = os.path.join(dest_path, os.path.basename(folder_path)).replace('\\', '/')
            
            # 执行上传命令
            cmd = f'adb -s {device} push "{folder_path}" "{dest_folder}"'
            self.execute_adb_command(cmd, device)
            
            # 上传完成后刷新文件列表
            self.root.after(2000, lambda: self.browse_device_path(device, dest_path, None))

    def download_selected(self, device, file_list):
        """下载选中的文件或文件夹"""
        selection = file_list.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要下载的文件或文件夹")
            return
            
        item = file_list.item(selection[0])
        values = item['values']
        if not values:
            return
            
        file_name = values[0]
        current_path = self.current_path_var.get()
        remote_path = os.path.join(current_path, file_name).replace('\\', '/')
        
        # 选择本地保存位置
        if values[3] == "目录":  # 如果是目录
            local_path = filedialog.askdirectory(title="选择保存位置")
            if local_path:
                # 执行下载命令
                cmd = f'adb -s {device} pull "{remote_path}" "{local_path}"'
                self.execute_adb_command(cmd, device)
        else:  # 如果是文件
            local_path = filedialog.asksaveasfilename(
                title="选择保存位置",
                initialfile=file_name
            )
            if local_path:
                # 执行下载命令
                cmd = f'adb -s {device} pull "{remote_path}" "{local_path}"'
                self.execute_adb_command(cmd, device)

    def delete_selected(self, device, file_list):
        """删除选中的文件或文件夹"""
        selection = file_list.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的文件或文件夹")
            return
            
        item = file_list.item(selection[0])
        values = item['values']
        if not values:
            return
            
        file_name = values[0]
        current_path = self.current_path_var.get()
        remote_path = os.path.join(current_path, file_name).replace('\\', '/')
        
        if messagebox.askyesno("确认删除", f"确定要删除 {file_name} 吗？"):
            # 执行删除命令
            if values[3] == "目录":  # 如果是目录
                cmd = f'adb -s {device} shell rm -rf "{remote_path}"'
            else:  # 如果是文件
                cmd = f'adb -s {device} shell rm -f "{remote_path}"'
                
            self.execute_adb_command(cmd, device)
            
            # 删除完成后刷新文件列表
            self.root.after(1000, lambda: self.browse_device_path(device, current_path, file_list))

    def create_folder(self, device, parent_path):
        """在设备上创建新文件夹"""
        folder_name = simpledialog.askstring("新建文件夹", "请输入文件夹名称:")
        if folder_name:
            folder_path = os.path.join(parent_path, folder_name).replace('\\', '/')
            cmd = f'adb -s {device} shell mkdir "{folder_path}"'
            self.execute_adb_command(cmd, device)
            
            # 创建完成后刷新文件列表
            self.root.after(1000, lambda: self.browse_device_path(device, parent_path, None))

    def on_closing(self):
        """关闭程序时的处理"""
        if messagebox.askokcancel("退出", "确定要退出ADB工具吗?"):
            # 停止命令处理线程
            self.command_queue.put((None, None, 0))
            self.root.destroy()


def main():
    """主函数"""
    # 检查ADB是否可用
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        result = messagebox.askquestion(
            "ADB未找到",
            "未找到ADB命令，请确保ADB已安装并添加到系统PATH中。\n是否继续?",
            icon='warning'
        )
        if result != 'yes':
            return

    # 启动ADB服务
    try:
        print("正在启动ADB服务...")
        result = subprocess.run(
            ["adb", "start-server"], 
            capture_output=True, 
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            print("ADB服务启动成功")
        else:
            print(f"ADB服务启动返回码: {result.returncode}")
            print(f"错误输出: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("ADB服务启动超时，但可能仍在启动中")
    except Exception as e:
        print(f"ADB服务启动异常: {e}")
        messagebox.showwarning("警告", f"ADB服务启动异常: {e}\n程序将继续运行，但可能无法正常使用。")

    root = tk.Tk()
    app = ADBGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()