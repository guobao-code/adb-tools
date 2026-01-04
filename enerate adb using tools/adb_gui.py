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
import re


class ADBGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB 工具 - 国保增强版")
        self.root.geometry("1000x750")
        self.root.minsize(800, 650)

        # 根窗口权重配置
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # 存储设备列表（新增设备详细信息）
        self.devices_list = []
        self.unauthorized_devices_list = []
        self.device_details = {}  # 存储设备详细信息 {device_id: {"model": "", "ip": "", "type": "wired/wireless"}}

        # 命令队列
        self.command_queue = queue.Queue()
        self.processing_command = False

        # 输出日志配置
        self.log_colors = {
            "INFO": "#000000",      # 普通信息-黑色
            "SUCCESS": "#008000",    # 成功-绿色
            "WARNING": "#FF8C00",    # 警告-橙色
            "ERROR": "#FF0000",      # 错误-红色
            "TIMESTAMP": "#808080"   # 时间戳-灰色
        }
        self.auto_scroll = tk.BooleanVar(value=True)  # 自动滚动开关
        self.filter_keyword = tk.StringVar(value="")  # 日志过滤关键词
        self.filter_level = tk.StringVar(value="ALL") # 日志级别过滤
        self.raw_logs = []  # 新增：维护原始日志列表，用于过滤恢复

        # 创建主框架（改用PanedWindow实现可拖拽调整区域大小）
        main_paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
        main_paned.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ========== 设备显示区域（优化核心） ==========
        device_frame = ttk.LabelFrame(main_paned, text="设备管理", padding="10")
        main_paned.add(device_frame, weight=1)  # 设备区权重1

        # 设备区顶部：操作栏 + 搜索过滤
        device_top_frame = ttk.Frame(device_frame)
        device_top_frame.pack(fill=tk.X, pady=(0, 10))
        device_top_frame.columnconfigure(0, weight=1)
        device_top_frame.columnconfigure(1, weight=0)

        # 设备操作按钮
        device_buttons_frame = ttk.Frame(device_top_frame)
        device_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for col in range(6):
            device_buttons_frame.columnconfigure(col, weight=1)

        ttk.Button(device_buttons_frame, text="刷新设备列表",
                   command=self.refresh_devices).grid(row=0, column=0, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="连接设备(IP)",
                   command=self.connect_device).grid(row=0, column=1, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="安装APK",
                   command=self.install_apk).grid(row=0, column=2, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="主板信息",
                   command=self.show_board_info).grid(row=0, column=3, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="一键息屏/亮屏",
                   command=self.toggle_screen).grid(row=0, column=4, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="重启ADB服务",
                   command=self.restart_adb_server).grid(row=0, column=5, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 设备搜索过滤
        device_filter_frame = ttk.Frame(device_top_frame)
        device_filter_frame.pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Label(device_filter_frame, text="搜索设备:").grid(row=0, column=0, padx=2, pady=2)
        self.device_search_var = tk.StringVar()
        self.device_search_var.trace_add("write", self.filter_devices_display)
        ttk.Entry(device_filter_frame, textvariable=self.device_search_var, width=20).grid(row=0, column=1, padx=2, pady=2)

        # 设备状态标签
        self.device_status_label = ttk.Label(device_frame, text="正在检测设备...", foreground="blue")
        self.device_status_label.pack(fill=tk.X, pady=(0, 5))

        # 设备列表容器（可滚动 + 自适应卡片布局）
        device_list_container = ttk.Frame(device_frame)
        device_list_container.pack(fill=tk.BOTH, expand=True)
        
        # 设备列表滚动区域
        self.device_canvas = tk.Canvas(device_list_container, bg="#f8f9fa", highlightthickness=0)
        device_scrollbar = ttk.Scrollbar(device_list_container, orient="vertical", command=self.device_canvas.yview)
        self.device_scrollable_frame = ttk.Frame(self.device_canvas, style="DeviceCard.TFrame")
        
        self.device_canvas.configure(yscrollcommand=device_scrollbar.set)
        self.device_canvas.bind("<Configure>", self.on_device_canvas_resize)
        self.device_scrollable_frame.bind("<Configure>", lambda e: self.device_canvas.configure(scrollregion=self.device_canvas.bbox("all")))
        
        canvas_window = self.device_canvas.create_window((0, 0), window=self.device_scrollable_frame, anchor="nw")
        self.device_canvas.bind("<Configure>", lambda e: self.device_canvas.itemconfig(canvas_window, width=e.width))
        
        self.device_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        device_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ========== 输出显示区域（优化核心） ==========
        output_frame = ttk.LabelFrame(main_paned, text="日志输出", padding="10")
        main_paned.add(output_frame, weight=2)  # 输出区权重2（更大空间）

        # 输出控制栏
        output_control_frame = ttk.Frame(output_frame)
        output_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 左侧控制：清空、保存、自动滚动
        output_left_control = ttk.Frame(output_control_frame)
        output_left_control.pack(side=tk.LEFT)
        
        ttk.Button(output_left_control, text="清空日志", command=self.clear_output).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(output_left_control, text="导出日志", command=self.export_log).grid(row=0, column=1, padx=2, pady=2)
        ttk.Checkbutton(output_left_control, text="自动滚动", variable=self.auto_scroll).grid(row=0, column=2, padx=8, pady=2)

        # 右侧控制：级别过滤 + 关键词过滤
        output_right_control = ttk.Frame(output_control_frame)
        output_right_control.pack(side=tk.RIGHT)
        
        ttk.Label(output_right_control, text="级别:").grid(row=0, column=0, padx=2, pady=2)
        level_combobox = ttk.Combobox(output_right_control, textvariable=self.filter_level, width=8, state="readonly")
        level_combobox['values'] = ["ALL", "INFO", "SUCCESS", "WARNING", "ERROR"]
        level_combobox.current(0)
        level_combobox.grid(row=0, column=1, padx=2, pady=2)
        level_combobox.bind("<<ComboboxSelected>>", self.filter_logs)
        
        ttk.Label(output_right_control, text="关键词:").grid(row=0, column=2, padx=8, pady=2)
        keyword_entry = ttk.Entry(output_right_control, textvariable=self.filter_keyword, width=15)
        keyword_entry.grid(row=0, column=3, padx=2, pady=2)
        keyword_entry.bind("<KeyRelease>", self.filter_logs)

        # 自定义ADB命令区（优化布局）
        cmd_frame = ttk.LabelFrame(output_frame, text="自定义ADB命令", padding="5")
        cmd_frame.pack(fill=tk.X, pady=(0, 10))
        cmd_frame.columnconfigure(1, weight=1)
        cmd_frame.columnconfigure(3, weight=3)

        ttk.Label(cmd_frame, text="目标设备:").grid(row=0, column=0, padx=2, pady=5, sticky=tk.W)
        self.cmd_device_var = tk.StringVar()
        self.cmd_device_combobox = ttk.Combobox(cmd_frame, textvariable=self.cmd_device_var, state="readonly", width=20)
        self.cmd_device_combobox.grid(row=0, column=1, padx=2, pady=5, sticky=(tk.W, tk.E))
        self.cmd_device_combobox['values'] = ["无可用设备"]
        self.cmd_device_combobox.current(0)
        self.cmd_device_combobox.config(state="disabled")

        ttk.Label(cmd_frame, text="命令:").grid(row=0, column=2, padx=8, pady=5, sticky=tk.W)
        self.cmd_input_var = tk.StringVar()
        self.cmd_input_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_input_var, font=("Consolas", 10))
        self.cmd_input_entry.grid(row=0, column=3, padx=2, pady=5, sticky=(tk.W, tk.E))
        self.cmd_input_entry.bind('<Return>', lambda e: self.execute_custom_adb_command())

        ttk.Button(cmd_frame, text="执行命令", command=self.execute_custom_adb_command).grid(row=0, column=4, padx=8, pady=5, sticky=(tk.W, tk.E))

        # 日志输出文本框（优化样式 + 语法高亮）
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#000000",
            relief=tk.FLAT,
            borderwidth=1
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 设置日志文本框标签（用于颜色高亮）
        for level, color in self.log_colors.items():
            self.output_text.tag_configure(level, foreground=color)
        self.output_text.tag_configure("LINE", foreground="#e0e0e0")  # 行号颜色
        self.output_text.tag_configure("TITLE", font=("Microsoft YaHei", 10, "bold"))  # 设备信息标题样式

        # 状态栏
        self.status_var = tk.StringVar(value="正在启动ADB服务...")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # 初始化样式
        self.setup_styles()
        
        # 初始化操作
        self.ensure_adb_server_running()
        self._start_command_processor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ========== 样式配置（设备卡片美化） ==========
    def setup_styles(self):
        """配置自定义样式"""
        style = ttk.Style()
        
        # 设备卡片样式
        style.configure("DeviceCard.TFrame", background="#ffffff", relief=tk.RAISED, borderwidth=1)
        # 补充悬停样式
        style.configure("Hover.TFrame", background="#e9f5ff", relief=tk.RAISED, borderwidth=2)
        
        style.configure("DeviceCard.TLabel", font=("Microsoft YaHei", 9))
        style.configure("DeviceStatus.Online.TLabel", foreground="#28a745")
        style.configure("DeviceStatus.Offline.TLabel", foreground="#dc3545")
        style.configure("DeviceStatus.Unauthorized.TLabel", foreground="#ffc107")
        
        # 按钮样式
        style.configure("Action.TButton", font=("Microsoft YaHei", 9), padding=2)

    # ========== 设备显示区域优化核心方法 ==========
    def on_device_canvas_resize(self, event):
        """设备画布大小变化时重新布局卡片"""
        self.refresh_devices_display(self.devices_list, self.unauthorized_devices_list)

    def filter_devices_display(self, *args):
        """过滤设备显示"""
        search_text = self.device_search_var.get().lower().strip()
        filtered_devices = []
        filtered_unauthorized = []
        
        if search_text:
            # 过滤已授权设备
            for device in self.devices_list:
                if search_text in device.lower() or (self.device_details.get(device, {}).get("model", "").lower().find(search_text) != -1):
                    filtered_devices.append(device)
            # 过滤未授权设备
            for device in self.unauthorized_devices_list:
                if search_text in device.lower():
                    filtered_unauthorized.append(device)
        else:
            filtered_devices = self.devices_list.copy()
            filtered_unauthorized = self.unauthorized_devices_list.copy()
        
        self.update_devices_display(filtered_devices, filtered_unauthorized)

    def refresh_devices_display(self, devices, unauthorized_devices):
        """刷新设备显示（自适应卡片布局）"""
        # 获取画布宽度，计算每行可显示的卡片数
        canvas_width = self.device_canvas.winfo_width()
        card_width = 280  # 每张卡片固定宽度
        cards_per_row = max(1, canvas_width // card_width) if canvas_width > 0 else 3
        
        # 更新设备显示
        self.update_devices_display(devices, unauthorized_devices, cards_per_row)

    def update_devices_display(self, devices, unauthorized_devices, cards_per_row=None):
        """更新设备卡片显示（核心优化）"""
        # 清空原有卡片
        for widget in self.device_scrollable_frame.winfo_children():
            widget.destroy()

        if cards_per_row is None:
            canvas_width = self.device_canvas.winfo_width()
            card_width = 280
            cards_per_row = max(1, canvas_width // card_width) if canvas_width > 0 else 3

        # 显示已授权设备
        if devices:
            self.device_status_label.config(text=f"已授权设备: {len(devices)} 个 | 未授权设备: {len(unauthorized_devices)} 个", foreground="#28a745")
            
            row = 0
            col = 0
            
            for idx, device_id in enumerate(devices):
                # 创建设备卡片（美化版）
                card_frame = ttk.Frame(self.device_scrollable_frame, style="DeviceCard.TFrame", padding="8")
                card_frame.grid(row=row, column=col, padx=8, pady=8, sticky=(tk.W, tk.E))
                card_frame.configure(width=260, height=180)
                card_frame.grid_propagate(False)  # 固定卡片大小
                
                # 卡片悬停效果（模拟）
                card_frame.bind("<Enter>", lambda e, cf=card_frame: cf.configure(style="Hover.TFrame"))
                card_frame.bind("<Leave>", lambda e, cf=card_frame: cf.configure(style="DeviceCard.TFrame"))

                # 设备ID（标题）
                device_id_label = ttk.Label(card_frame, text=device_id, font=("Microsoft YaHei", 10, "bold"), wraplength=240)
                device_id_label.pack(fill=tk.X, pady=(0, 5))

                # 设备类型（有线/无线）
                device_detail = self.device_details.get(device_id, {})
                dev_type = device_detail.get("type", "未知")
                dev_type_text = "📶 无线设备" if dev_type == "wireless" else "🔌 有线设备"
                type_label = ttk.Label(card_frame, text=dev_type_text, font=("Microsoft YaHei", 8), foreground="#6c757d")
                type_label.pack(fill=tk.X, pady=(0, 3))

                # 设备型号
                model = device_detail.get("model", "未知型号")
                model_label = ttk.Label(card_frame, text=f"型号: {model}", font=("Microsoft YaHei", 9), wraplength=240)
                model_label.pack(fill=tk.X, pady=(0, 3))

                # IP地址（仅无线设备）
                if dev_type == "wireless":
                    ip = device_detail.get("ip", "未知IP")
                    ip_label = ttk.Label(card_frame, text=f"IP: {ip}", font=("Microsoft YaHei", 9), foreground="#007bff")
                    ip_label.pack(fill=tk.X, pady=(0, 3))

                # 状态标签
                status_label = ttk.Label(card_frame, text="✅ 已授权", style="DeviceStatus.Online.TLabel", font=("Microsoft YaHei", 9))
                status_label.pack(fill=tk.X, pady=(0, 8))

                # 操作按钮区
                btn_frame = ttk.Frame(card_frame)
                btn_frame.pack(fill=tk.X, expand=True)
                for i in range(4):
                    btn_frame.columnconfigure(i, weight=1)

                # 操作按钮
                ttk.Button(btn_frame, text="断开", style="Action.TButton",
                           command=lambda d=device_id: self.disconnect_single_device(d)).grid(row=0, column=0, padx=2, pady=2, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="控制", style="Action.TButton",
                           command=lambda d=device_id: self.remote_control_device(d)).grid(row=0, column=1, padx=2, pady=2, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="文件", style="Action.TButton",
                           command=lambda d=device_id: self.show_file_manager(d)).grid(row=0, column=2, padx=2, pady=2, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="信息", style="Action.TButton",
                           command=lambda d=device_id: self.show_board_info_window(d)).grid(row=0, column=3, padx=2, pady=2, sticky=(tk.W, tk.E))

                # 更新行列位置
                col += 1
                if col >= cards_per_row:
                    col = 0
                    row += 1

        # 显示未授权设备
        if unauthorized_devices and (not devices or col != 0):
            if not devices:
                row = 0
                col = 0
            else:
                if col > 0:
                    row += 1
                col = 0

            # 未授权设备分组标题
            group_label = ttk.Label(self.device_scrollable_frame, text="未授权设备", font=("Microsoft YaHei", 10, "bold"), foreground="#ffc107")
            group_label.grid(row=row, column=0, columnspan=cards_per_row, sticky=tk.W, padx=8, pady=(15, 5))
            row += 1

            # 未授权设备卡片
            for idx, device_id in enumerate(unauthorized_devices):
                card_frame = ttk.Frame(self.device_scrollable_frame, style="DeviceCard.TFrame", padding="8")
                card_frame.grid(row=row, column=col, padx=8, pady=8, sticky=(tk.W, tk.E))
                card_frame.configure(width=260, height=120)
                card_frame.grid_propagate(False)

                # 设备ID
                device_id_label = ttk.Label(card_frame, text=device_id, font=("Microsoft YaHei", 10, "bold"), wraplength=240)
                device_id_label.pack(fill=tk.X, pady=(0, 5))

                # 状态标签
                status_label = ttk.Label(card_frame, text="⚠️ 未授权", style="DeviceStatus.Unauthorized.TLabel", font=("Microsoft YaHei", 9))
                status_label.pack(fill=tk.X, pady=(0, 8))

                # 提示信息
                tip_label = ttk.Label(card_frame, text="请在设备上允许USB调试授权", font=("Microsoft YaHei", 8), foreground="#6c757d", wraplength=240)
                tip_label.pack(fill=tk.X, pady=(0, 5))

                # 操作按钮
                btn_frame = ttk.Frame(card_frame)
                btn_frame.pack(fill=tk.X, expand=True)
                btn_frame.columnconfigure(0, weight=1)

                ttk.Button(btn_frame, text="断开", style="Action.TButton",
                           command=lambda d=device_id: self.disconnect_single_device(d)).grid(row=0, column=0, padx=2, pady=2, sticky=(tk.W, tk.E))

                # 更新行列位置
                col += 1
                if col >= cards_per_row:
                    col = 0
                    row += 1

        # 无设备时的提示
        if not devices and not unauthorized_devices:
            self.device_status_label.config(text="未检测到任何设备", foreground="#6c757d")
            empty_label = ttk.Label(self.device_scrollable_frame, text="📱 暂无设备连接\n\n请确保：\n1. 设备已开启USB调试\n2. 数据线已正确连接\n3. ADB服务正常运行", 
                                    font=("Microsoft YaHei", 12), foreground="#6c757d", justify=tk.CENTER)
            empty_label.pack(expand=True, pady=50)

        # 更新滚动区域
        self.device_scrollable_frame.update_idletasks()
        self.device_canvas.configure(scrollregion=self.device_canvas.bbox("all"))

    # ========== 输出区域优化核心方法 ==========
    def append_output(self, text, level="INFO"):
        """添加带级别和颜色的日志输出（优化：存入原始日志列表）"""
        # 格式化时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] {text}"
        # 存入原始日志列表
        self.raw_logs.append((log_line, level))
        # 主线程更新UI
        self.root.after(0, self._update_output_with_color, log_line + "\n", level)

    def _update_output_with_color(self, log_line, level):
        """带颜色更新输出文本"""
        # 插入时间戳（灰色）
        timestamp_end = log_line.find(']') + 1
        self.output_text.insert(tk.END, log_line[:timestamp_end], "TIMESTAMP")
        # 插入日志内容（对应级别颜色）
        self.output_text.insert(tk.END, log_line[timestamp_end:], level)
        
        # 自动滚动（如果开启）
        if self.auto_scroll.get():
            self.output_text.see(tk.END)
        
        # 刷新UI
        self.output_text.update_idletasks()

    def filter_logs(self, *args):
        """优化：基于原始日志列表过滤，支持恢复原始日志"""
        self.output_text.delete(1.0, tk.END)
        # 获取过滤条件
        level_filter = self.filter_level.get()
        keyword_filter = self.filter_keyword.get().lower()

        # 遍历原始日志，筛选符合条件的日志
        for log_line, level in self.raw_logs:
            if not log_line:
                continue

            # 级别过滤
            if level_filter != "ALL" and level != level_filter:
                continue

            # 关键词过滤
            if keyword_filter and keyword_filter not in log_line.lower():
                continue

            # 重新上色插入
            if "[" in log_line and "]" in log_line:
                timestamp_end = log_line.find(']') + 1
                self.output_text.insert(tk.END, log_line[:timestamp_end], "TIMESTAMP")
                self.output_text.insert(tk.END, log_line[timestamp_end:] + "\n", level)

        if self.auto_scroll.get():
            self.output_text.see(tk.END)

    def export_log(self):
        """导出日志到文件"""
        file_path = filedialog.asksaveasfilename(
            title="导出日志",
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.get(1.0, tk.END))
                self.append_output(f"日志已导出到: {file_path}", "SUCCESS")
            except Exception as e:
                self.append_output(f"日志导出失败: {str(e)}", "ERROR")

    def clear_output(self):
        """清空日志（带确认）"""
        if messagebox.askyesno("确认清空", "确定要清空所有日志吗？"):
            self.output_text.delete(1.0, tk.END)
            self.raw_logs.clear()  # 同时清空原始日志列表
            self.append_output("日志已清空", "INFO")

    # ========== 新增：全局主板信息查询入口（修复AttributeError） ==========
    def show_board_info(self):
        """全局主板信息查询（处理无设备/单个设备/多个设备场景）"""
        # 1. 无已授权设备时给出提示
        if not self.devices_list:
            messagebox.showinfo("提示", "没有已授权设备可查询主板信息！")
            return
        
        # 2. 单个设备直接查询
        if len(self.devices_list) == 1:
            device_id = self.devices_list[0]
            self.show_board_info_window(device_id)
            return
        
        # 3. 多个设备时弹出选择框，让用户选择要查询的设备
        device_id = self.ask_select_device()
        if device_id:  # 用户选择了设备才执行查询
            self.show_board_info_window(device_id)

    # ========== 原有核心功能（保留 + 优化） ==========
    def normalize_text(self, text):
        """中文标点转英文"""
        chinese_to_english = {
            '：': ':', '，': ',', '；': ';', '！': '!', '？': '?', '。': '.',
        }
        result = ""
        for char in text:
            result += chinese_to_english.get(char, char)
        return result

    def check_network_connectivity(self, ip, port):
        """检查网络连通性"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, int(port)))
            sock.close()
            return result == 0
        except ValueError:
            return False
        except Exception as e:
            self.append_output(f"网络检测警告: {str(e)}", "WARNING")
            return False

    def execute_adb_command(self, cmd, device_id=None, retry_count=2):
        """执行ADB命令"""
        if not cmd.strip().startswith('adb '):
            cmd = 'adb ' + cmd
        if device_id:
            cmd = cmd.replace('adb ', f'adb -s {device_id} ', 1)
        self.update_status(f"执行命令: {cmd}")
        self.command_queue.put((cmd, device_id, retry_count))

    def _run_adb_command(self, cmd, device_id=None, retry_count=2):
        """线程执行ADB命令"""
        device_prefix = f"[{device_id}] " if device_id else ""
        
        if "input keyevent 26" in cmd:
            self.append_output(f"{device_prefix}执行：屏幕状态切换命令", "INFO")
        else:
            self.append_output(f"{device_prefix}执行命令: {cmd}", "INFO")

        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.append_output(f"{device_prefix}{output.strip()}", "INFO")

            stderr = process.stderr.read()
            if stderr:
                self.append_output(f"{device_prefix}错误输出: {stderr.strip()}", "ERROR")

            return_code = process.poll()

            if return_code != 0 and retry_count > 0:
                self.append_output(f"{device_prefix}命令执行失败，重试({retry_count}次剩余)...", "WARNING")
                time.sleep(1)
                self._run_adb_command(cmd.split(' ', 1)[1] if cmd.startswith('adb ') else cmd, 
                                    device_id, retry_count-1)
                return

            if return_code == 0:
                self.append_output(f"{device_prefix}命令执行成功", "SUCCESS")
            else:
                self.append_output(f"{device_prefix}命令执行失败（退出码: {return_code}）", "ERROR")

            self.root.after(0, lambda: self.update_status(f"{device_prefix}命令执行完成"))

        except Exception as e:
            error_msg = f"{device_prefix}执行命令出错: {str(e)}"
            self.append_output(error_msg, "ERROR")
            self.root.after(0, lambda: self.update_status(f"错误: {str(e)}"))

    def update_status(self, message):
        """更新状态栏"""
        self.status_var.set(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def refresh_devices(self):
        """刷新设备列表（新增设备详细信息获取）"""
        def _refresh():
            self.update_status("正在刷新设备列表...")
            
            try:
                # 获取设备列表
                result = subprocess.run(
                    "adb devices -l",  # -l 参数获取详细信息
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                lines = result.stdout.strip().split('\n')

                devices = []
                unauthorized_devices = []
                self.device_details.clear()

                # 解析设备信息
                for line in lines[1:]:
                    if line.strip() and '\t' in line:
                        parts = line.strip().split('\t')
                        device_id = parts[0]
                        status_part = parts[1]
                        
                        # 解析状态
                        if 'device' in status_part:
                            devices.append(device_id)
                            
                            # 解析设备详细信息
                            detail_parts = status_part.split()
                            model = "未知"
                            dev_type = "wired"
                            ip = ""
                            
                            for part in detail_parts:
                                if part.startswith('model:'):
                                    model = part.split(':', 1)[1]
                                elif part.startswith('device:'):
                                    dev_type = "wireless" if 'tcp' in device_id else "wired"
                            
                            # 获取无线设备IP
                            if dev_type == "wireless":
                                ip = device_id.split(':')[0]
                            
                            self.device_details[device_id] = {
                                "model": model,
                                "type": dev_type,
                                "ip": ip
                            }
                            
                        elif 'unauthorized' in status_part:
                            unauthorized_devices.append(device_id)

                self.devices_list = devices
                self.unauthorized_devices_list = unauthorized_devices

                # 更新UI
                self.root.after(0, self.refresh_devices_display, devices, unauthorized_devices)
                self.root.after(0, self._update_cmd_device_combobox, devices)

                # 更新状态
                if devices:
                    self.update_status(f"找到 {len(devices)} 个已授权设备")
                elif unauthorized_devices:
                    self.update_status("设备未授权，请在设备上确认授权")
                else:
                    self.update_status("未找到任何设备")

            except subprocess.TimeoutExpired:
                self.update_status("设备检测超时")
                self.append_output("设备列表刷新超时", "WARNING")
            except Exception as e:
                self.update_status(f"刷新设备失败: {str(e)}")
                self.append_output(f"刷新设备列表出错: {str(e)}", "ERROR")

        thread = threading.Thread(target=_refresh)
        thread.daemon = True
        thread.start()

    def _update_cmd_device_combobox(self, devices):
        """更新命令设备下拉框"""
        if devices:
            self.cmd_device_combobox['values'] = ["所有设备（不指定）"] + devices
            self.cmd_device_combobox.current(0)
            self.cmd_device_combobox.config(state="readonly")
        else:
            self.cmd_device_combobox['values'] = ["无可用设备"]
            self.cmd_device_combobox.current(0)
            self.cmd_device_combobox.config(state="disabled")

    def connect_device(self):
        """IP连接设备（保留原有修复逻辑）"""
        self.ensure_adb_server_running()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("连接无线设备")
        dialog.geometry("480x500")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)

        # IP输入
        ttk.Label(main_frame, text="设备IP地址:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.W)
        ip_var = tk.StringVar()
        ip_entry = ttk.Entry(main_frame, textvariable=ip_var, font=("Microsoft YaHei", 10))
        ip_entry.grid(row=0, column=1, padx=5, pady=8, sticky=(tk.W, tk.E))
        ip_entry.focus()

        # 端口输入
        ttk.Label(main_frame, text="端口号:", font=("Microsoft YaHei", 10)).grid(row=1, column=0, padx=5, pady=8, sticky=tk.W)
        port_var = tk.StringVar(value="5555")
        port_entry = ttk.Entry(main_frame, textvariable=port_var, font=("Microsoft YaHei", 10), width=10)
        port_entry.grid(row=1, column=1, padx=5, pady=8, sticky=tk.W)
        ttk.Label(main_frame, text="默认5555，无需修改", font=("Microsoft YaHei", 8), foreground="#6c757d").grid(row=1, column=2, padx=5, pady=8, sticky=tk.W)

        # 常用IP预设（优化布局）
        preset_frame = ttk.LabelFrame(main_frame, text="常用IP地址", padding="8")
        preset_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky=(tk.W, tk.E))
        preset_frame.columnconfigure((0,1,2,3), weight=1)

        preset_ips = [
            "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5",
            "10.0.0.100", "192.168.1.100", "192.168.2.31", "192.168.123.1"
        ]
        for i, ip in enumerate(preset_ips):
            ttk.Button(preset_frame, text=ip, style="Action.TButton",
                       command=lambda ip=ip: (ip_var.set(ip), port_var.set("5555"))).grid(row=i//4, column=i%4, padx=3, pady=3, sticky=(tk.W, tk.E))

        # 连接提示
        tips_frame = ttk.LabelFrame(main_frame, text="连接提示", padding="8")
        tips_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=10, sticky=(tk.W, tk.E))
        tips = [
            "• 确保设备与电脑在同一局域网",
            "• 设备需先执行: adb tcpip 5555",
            "• 首次连接需通过USB授权",
            "• 防火墙可能会阻止无线ADB连接"
        ]
        for i, tip in enumerate(tips):
            ttk.Label(tips_frame, text=tip, font=("Microsoft YaHei", 9), foreground="#6c757d").grid(row=i, column=0, sticky=tk.W, padx=2, pady=1)

        # 操作按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=15, sticky=(tk.W, tk.E))
        btn_frame.columnconfigure((0,1), weight=1)

        def do_connect():
            ip = ip_var.get().strip()
            port = port_var.get().strip()

            if not ip:
                messagebox.showwarning("警告", "请输入设备IP地址！", parent=dialog)
                return

            if not port:
                port = "5555"
            address = f"{ip}:{port}"

            # 网络检测
            network_ok = False
            try:
                network_ok = self.check_network_connectivity(ip, port)
            except Exception as e:
                self.append_output(f"网络检测异常: {str(e)}", "WARNING")

            if not network_ok:
                result = messagebox.askyesno(
                    "网络检测提示",
                    f"未检测到 {ip}:{port} 的网络连接\n可能是防火墙/设备未就绪\n是否继续尝试连接？",
                    parent=dialog
                )
                if not result:
                    return

            # 执行连接命令
            adb_cmd = f"adb connect {address}"
            self.append_output(f"执行无线连接命令: {adb_cmd}", "INFO")

            def run_connect():
                try:
                    self.update_status(f"正在连接 {address}...")
                    process = subprocess.run(
                        adb_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=20
                    )
                    
                    # 输出结果
                    if process.stdout:
                        self.append_output(f"连接结果: {process.stdout.strip()}", "SUCCESS" if "connected" in process.stdout else "ERROR")
                    if process.stderr:
                        self.append_output(f"连接错误: {process.stderr.strip()}", "ERROR")
                    
                    # 结果判断
                    if process.returncode == 0 and "connected to" in process.stdout.lower():
                        self.update_status(f"成功连接到 {address}")
                        messagebox.showinfo("成功", f"已连接到设备 {address}", parent=dialog)
                        dialog.destroy()
                        self.root.after(1000, self.refresh_devices)
                    else:
                        self.update_status(f"连接 {address} 失败")
                        messagebox.showerror("失败", 
                            f"连接失败！\n命令: {adb_cmd}\n输出: {process.stdout}\n错误: {process.stderr}", 
                            parent=dialog)
                        
                except Exception as e:
                    error_msg = f"连接执行异常: {str(e)}"
                    self.append_output(error_msg, "ERROR")
                    self.update_status(f"连接失败: {str(e)}")
                    messagebox.showerror("错误", error_msg, parent=dialog)

            thread = threading.Thread(target=run_connect)
            thread.daemon = True
            thread.start()

        ttk.Button(btn_frame, text="立即连接", style="Action.TButton", command=do_connect).grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(btn_frame, text="取消", style="Action.TButton", command=dialog.destroy).grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

        # 回车触发连接
        dialog.bind('<Return>', lambda e: do_connect())

    def toggle_screen(self):
        """切换屏幕状态（息屏/亮屏）"""
        if not self.devices_list:
            messagebox.showinfo("提示", "没有已授权设备可操作")
            return
        
        confirm = messagebox.askyesno("确认操作", f"是否对 {len(self.devices_list)} 个设备执行屏幕状态切换？")
        if not confirm:
            return
        
        self.update_status(f"发送屏幕切换指令到 {len(self.devices_list)} 个设备...")
        self.append_output(f"批量切换 {len(self.devices_list)} 个设备屏幕状态", "INFO")
        
        for device_id in self.devices_list:
            self.execute_adb_command("shell input keyevent 26", device_id, retry_count=1)
        
        self.root.after(1000, lambda: self.update_status("屏幕切换指令发送完成"))

    # ========== 其他原有功能（简化保留） ==========
    def execute_custom_adb_command(self):
        """执行自定义命令"""
        custom_cmd = self.cmd_input_var.get().strip()
        if not custom_cmd:
            messagebox.showwarning("警告", "请输入ADB命令！")
            self.cmd_input_entry.focus()
            return

        selected_device = self.cmd_device_var.get()
        device_id = selected_device if selected_device != "所有设备（不指定）" else None

        final_cmd = f'adb {custom_cmd}' if not custom_cmd.startswith('adb ') else custom_cmd
        if device_id and '-s' not in final_cmd:
            final_cmd = final_cmd.replace('adb ', f'adb -s {device_id} ', 1)

        self.execute_adb_command(final_cmd, device_id)
        self.cmd_input_var.set("")
        self.cmd_input_entry.focus()

    def disconnect_single_device(self, device):
        """断开单个设备"""
        self.execute_adb_command(f"disconnect {device}")
        self.root.after(1000, self.refresh_devices)

    def remote_control_device(self, device):
        """远程控制"""
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            result = messagebox.askquestion(
                "scrcpy未安装",
                "未找到scrcpy，请先安装：\nWindows: 下载后添加到PATH\nmacOS: brew install scrcpy\nLinux: sudo apt install scrcpy\n\n是否打开下载页面？",
                icon='warning'
            )
            if result == 'yes':
                import webbrowser
                webbrowser.open("https://github.com/Genymobile/scrcpy")
            return

        def run_scrcpy():
            try:
                self.update_status(f"启动scrcpy控制设备: {device}")
                subprocess.run(f"scrcpy -s {device}", shell=True)
                self.update_status(f"scrcpy远程控制已结束: {device}")
            except Exception as e:
                self.append_output(f"启动scrcpy失败: {str(e)}", "ERROR")

        thread = threading.Thread(target=run_scrcpy)
        thread.daemon = True
        thread.start()

    def install_apk(self):
        """安装APK"""
        file_path = filedialog.askopenfilename(
            title="选择APK文件",
            filetypes=[("APK文件", "*.apk"), ("所有文件", "*.*")]
        )
        if file_path:
            file_path = self.normalize_text(file_path)
            self.execute_adb_command(f'install -r "{file_path}"')

    def show_board_info_window(self, device):
        """显示设备信息"""
        info_window = tk.Toplevel(self.root)
        info_window.title(f"设备信息 - {device}")
        info_window.geometry("700x600")
        info_window.minsize(600, 500)
        info_window.transient(self.root)

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - info_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - info_window.winfo_height()) // 2
        info_window.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(info_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 设备基本信息
        basic_frame = ttk.LabelFrame(main_frame, text="基本信息", padding="10")
        basic_frame.pack(fill=tk.X, pady=10)
        
        # 获取设备信息
        def get_device_info():
            info_text.delete(1.0, tk.END)
            info_text.insert(tk.END, "正在获取设备信息...\n")
            
            commands = {
                "设备ID": f"echo {device}",
                "设备型号": "getprop ro.product.model",
                "制造商": "getprop ro.product.manufacturer",
                "Android版本": "getprop ro.build.version.release",
                "SDK版本": "getprop ro.build.version.sdk",
                "内核版本": "cat /proc/version",
                "CPU信息": "cat /proc/cpuinfo | head -20",
                "内存信息": "cat /proc/meminfo | head -10"
            }
            
            for title, cmd in commands.items():
                info_text.insert(tk.END, f"\n{'='*40}\n{title}:\n{'='*40}\n", "TITLE")
                try:
                    result = subprocess.run(
                        f"adb -s {device} shell {cmd}",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=8
                    )
                    if result.returncode == 0:
                        info_text.insert(tk.END, result.stdout)
                    else:
                        info_text.insert(tk.END, f"获取失败: {result.stderr}", "ERROR")
                except Exception as e:
                    info_text.insert(tk.END, f"执行错误: {str(e)}", "ERROR")
            
            info_text.see(tk.END)

        # 信息显示区域
        info_text = scrolledtext.ScrolledText(main_frame, font=("Consolas", 10), wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True, pady=10)
        info_text.tag_configure("TITLE", font=("Microsoft YaHei", 10, "bold"))
        info_text.tag_configure("ERROR", foreground="#dc3545")

        # 操作按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="刷新信息", command=get_device_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出信息", command=lambda: self.export_device_info(info_text.get(1.0, tk.END), device)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=info_window.destroy).pack(side=tk.RIGHT, padx=5)

        # 初始获取信息
        threading.Thread(target=get_device_info, daemon=True).start()

    def export_device_info(self, info, device):
        """导出设备信息"""
        file_path = filedialog.asksaveasfilename(
            title="导出设备信息",
            defaultextension=".txt",
            initialfile=f"设备信息_{device}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(info)
                self.append_output(f"设备 {device} 信息已导出到: {file_path}", "SUCCESS")
            except Exception as e:
                self.append_output(f"导出设备信息失败: {str(e)}", "ERROR")

    def show_file_manager(self, device=None):
        """文件管理器（增强：支持双击进入文件夹）"""
        if not device:
            if not self.devices_list:
                messagebox.showwarning("警告", "无可用设备")
                return
            if len(self.devices_list) > 1:
                device = self.ask_select_device()
                if not device:
                    return
            else:
                device = self.devices_list[0]

        # 简化版文件管理器（保留核心功能）
        file_window = tk.Toplevel(self.root)
        file_window.title(f"文件管理器 - {device}")
        file_window.geometry("800x600")
        file_window.transient(self.root)

        main_frame = ttk.Frame(file_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 路径栏
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)
        self.current_path_var = tk.StringVar(value="/sdcard")
        ttk.Entry(path_frame, textvariable=self.current_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(path_frame, text="转到", command=lambda: self.browse_device_path(device, self.current_path_var.get(), file_list)).pack(side=tk.LEFT)

        # 文件列表
        file_list = ttk.Treeview(main_frame, columns=("名称", "大小", "类型"), show="headings")
        file_list.heading("名称", text="名称")
        file_list.heading("大小", text="大小")
        file_list.heading("类型", text="类型")
        file_list.column("名称", width=400)
        file_list.column("大小", width=100)
        file_list.column("类型", width=80)
        file_list.pack(fill=tk.BOTH, expand=True, pady=5)

        # 操作按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="上传文件", command=lambda: self.upload_file(device, self.current_path_var.get())).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="下载选中", command=lambda: self.download_selected(device, file_list)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="刷新", command=lambda: self.browse_device_path(device, self.current_path_var.get(), file_list)).pack(side=tk.LEFT, padx=2)

        # 绑定双击进入文件夹事件
        file_list.bind("<Double-1>", lambda e: self.enter_selected_folder(device, file_list))

        # 初始加载
        self.browse_device_path(device, "/sdcard", file_list)

    def enter_selected_folder(self, device, file_list):
        """双击进入选中文件夹"""
        selection = file_list.selection()
        if not selection:
            return
        item = file_list.item(selection[0])
        name = item['values'][0]
        ftype = item['values'][2]
        if ftype != "目录":
            return  # 非目录不处理
        # 拼接新路径
        current_path = self.current_path_var.get()
        new_path = os.path.join(current_path, name).replace('\\', '/')
        # 浏览新路径
        self.browse_device_path(device, new_path, file_list)

    def browse_device_path(self, device, path, file_list):
        """浏览设备路径"""
        for item in file_list.get_children():
            file_list.delete(item)
        
        self.current_path_var.set(path)
        
        def _get_files():
            try:
                result = subprocess.run(
                    f'adb -s {device} shell ls -la "{path}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line and not line.startswith('total'):
                            parts = line.split()
                            if len(parts) >= 9:
                                perm = parts[0]
                                size = parts[4]
                                name = ' '.join(parts[8:])
                                ftype = "目录" if perm.startswith('d') else "文件"
                                file_list.insert("", "end", values=(name, size, ftype))
            except Exception as e:
                self.append_output(f"获取文件列表失败: {str(e)}", "ERROR")
        
        threading.Thread(target=_get_files, daemon=True).start()

    def upload_file(self, device, dest_path):
        """上传文件"""
        file_path = filedialog.askopenfilename(title="选择文件")
        if file_path:
            dest = os.path.join(dest_path, os.path.basename(file_path)).replace('\\', '/')
            self.execute_adb_command(f'push "{file_path}" "{dest}"', device)

    def download_selected(self, device, file_list):
        """下载文件"""
        selection = file_list.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择文件")
            return
        
        item = file_list.item(selection[0])
        name = item['values'][0]
        path = os.path.join(self.current_path_var.get(), name).replace('\\', '/')
        
        save_path = filedialog.asksaveasfilename(initialfile=name)
        if save_path:
            self.execute_adb_command(f'pull "{path}" "{save_path}"', device)

    def ensure_adb_server_running(self):
        """确保ADB服务运行"""
        def _check():
            try:
                subprocess.run("adb devices", shell=True, capture_output=True, timeout=10)
                self.update_status("ADB服务正常运行")
                self.root.after(0, self.refresh_devices)
            except Exception:
                self.root.after(0, self._restart_adb_server)

        threading.Thread(target=_check, daemon=True).start()

    def _restart_adb_server(self):
        """重启ADB服务"""
        try:
            self.update_status("重启ADB服务...")
            subprocess.run(["adb", "kill-server"], timeout=5)
            time.sleep(1)
            result = subprocess.run(["adb", "start-server"], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.append_output("ADB服务重启成功", "SUCCESS")
                self.update_status("ADB服务重启成功")
                self.root.after(1000, self.refresh_devices)
            else:
                self.append_output(f"ADB服务启动失败: {result.stderr}", "ERROR")
                self.update_status("ADB服务启动失败")
                
        except Exception as e:
            self.append_output(f"重启ADB服务异常: {str(e)}", "ERROR")
            self.update_status(f"ADB服务重启失败: {str(e)}")

    def restart_adb_server(self):
        """用户触发重启ADB"""
        if messagebox.askyesno("确认", "确定要重启ADB服务吗？"):
            self._restart_adb_server()

    def ask_select_device(self):
        """选择设备对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择设备")
        dialog.geometry("350x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="请选择操作设备:", font=("Microsoft YaHei", 10)).pack(pady=10)

        listbox = tk.Listbox(main_frame, font=("Microsoft YaHei", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for device in self.devices_list:
            model = self.device_details.get(device, {}).get("model", "未知")
            listbox.insert(tk.END, f"{device} ({model})")

        selected = None
        def on_ok():
            nonlocal selected
            if listbox.curselection():
                selected = self.devices_list[listbox.curselection()[0]]
                dialog.destroy()
            else:
                messagebox.showwarning("警告", "请选择设备")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=5, expand=True)

        dialog.wait_window()
        return selected

    def _start_command_processor(self):
        """启动命令处理线程"""
        def process():
            while True:
                cmd, device_id, retry = self.command_queue.get()
                if cmd is None:
                    break
                self._run_adb_command(cmd, device_id, retry)
                self.command_queue.task_done()

        thread = threading.Thread(target=process, daemon=True)
        thread.start()

    def on_closing(self):
        """退出处理"""
        if messagebox.askokcancel("退出", "确定要退出ADB工具吗？"):
            self.command_queue.put((None, None, 0))
            self.root.destroy()


def main():
    """主函数"""
    # 检查ADB
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        result = messagebox.askquestion(
            "ADB未找到",
            "未检测到ADB，请确保已安装并添加到系统PATH\n是否继续运行？",
            icon='warning'
        )
        if result != 'yes':
            return

    # 启动GUI
    root = tk.Tk()
    app = ADBGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()