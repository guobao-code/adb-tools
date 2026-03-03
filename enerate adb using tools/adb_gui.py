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
        self.root.geometry("1100x700")
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
        for col in range(7):
            device_buttons_frame.columnconfigure(col, weight=1)

        ttk.Button(device_buttons_frame, text="刷新设备列表",
                   command=self.refresh_devices).grid(row=0, column=0, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="连接设备(IP)",
                   command=self.connect_device).grid(row=0, column=1, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="insomnia工具",
                   command=self.show_tools_window).grid(row=0, column=2, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="息屏",
                   command=lambda: self.toggle_screen("off")).grid(row=0, column=3, padx=2, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(device_buttons_frame, text="亮屏",
                   command=lambda: self.toggle_screen("on")).grid(row=0, column=4, padx=2, pady=2, sticky=(tk.W, tk.E))
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
        self.device_scrollable_frame.bind("<Configure>", lambda e: self.device_canvas.configure(scrollregion=self.device_canvas.bbox("all")))

        canvas_window = self.device_canvas.create_window((0, 0), window=self.device_scrollable_frame, anchor="nw")
        self.device_canvas.bind("<Configure>", lambda e: self.device_canvas.itemconfig(canvas_window, width=e.width))

        # 添加鼠标滚轮支持（Windows）
        self.device_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # 添加鼠标滚轮支持（Linux）
        self.device_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.device_canvas.bind_all("<Button-5>", self._on_mousewheel)

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
        
        ttk.Label(output_right_control, text="日志分类:").grid(row=0, column=0, padx=2, pady=2)
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
        self._start_command_processor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 延迟启动ADB检查，确保GUI完全加载
        self.root.after(500, self.ensure_adb_server_running)

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

    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件"""
        # Windows系统使用 MouseWheel 事件，event.delta 为正负值
        if event.num == 4 or event.delta > 0:
            self.device_canvas.yview_scroll(-1, "units")  # 向上滚动
        elif event.num == 5 or event.delta < 0:
            self.device_canvas.yview_scroll(1, "units")   # 向下滚动

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

        self.root.after(100, self.update_devices_display, filtered_devices, filtered_unauthorized)

    def refresh_devices_display(self, devices, unauthorized_devices):
        """刷新设备显示（每行最多5个卡片）"""
        self.update_devices_display(devices, unauthorized_devices)

    def update_devices_display(self, devices, unauthorized_devices, cards_per_row=5):
        """更新设备卡片显示（每行最多5个卡片，多余下排）"""
        # 清空原有卡片（彻底清空）
        self.device_scrollable_frame.destroy()
        self.device_scrollable_frame = ttk.Frame(self.device_canvas, style="DeviceCard.TFrame")
        canvas_window = self.device_canvas.create_window((0, 0), window=self.device_scrollable_frame, anchor="nw")

        # 重新绑定 Configure 事件
        self.device_scrollable_frame.bind("<Configure>", lambda e: self.device_canvas.configure(scrollregion=self.device_canvas.bbox("all")))

        # 获取画布宽度
        canvas_width = self.device_canvas.winfo_width()

        # 如果画布尺寸未准备好，使用默认值
        if canvas_width <= 1:
            canvas_width = 1000

        # 计算卡片尺寸（每行5个卡片）
        cards_per_row = 5
        padding = 2  # 每个卡片左右各1px的padding
        card_width = (canvas_width - (padding * cards_per_row)) / cards_per_row
        # 限制最小和最大宽度
        card_width = max(200, min(card_width, 350))

        # 根据卡片宽度动态调整字体大小
        if card_width < 220:
            font_size_title = 9
            font_size_normal = 7
            font_size_small = 7
            font_size_btn = 7
            pady_text = (0, 2)
            pady_btn = 0
            card_height = card_width * 1.1
        elif card_width < 260:
            font_size_title = 9
            font_size_normal = 8
            font_size_small = 7
            font_size_btn = 7
            pady_text = (0, 3)
            pady_btn = 0
            card_height = card_width * 1.05
        else:
            font_size_title = 10
            font_size_normal = 9
            font_size_small = 8
            font_size_btn = 8
            pady_text = (0, 3)
            pady_btn = 1
            card_height = card_width * 0.95

        # 显示已授权设备
        if devices:
            self.device_status_label.config(text=f"已授权设备: {len(devices)} 个 | 未授权设备: {len(unauthorized_devices)} 个", foreground="#28a745")

            row = 0
            col = 0

            for idx, device_id in enumerate(devices):
                # 创建设备卡片（美化版）
                card_frame = ttk.Frame(self.device_scrollable_frame, style="DeviceCard.TFrame", padding="6")
                card_frame.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
                card_frame.configure(width=int(card_width), height=int(card_height))
                card_frame.grid_propagate(False)  # 固定卡片大小

                # 卡片悬停效果（模拟）
                card_frame.bind("<Enter>", lambda e, cf=card_frame: cf.configure(style="Hover.TFrame"))
                card_frame.bind("<Leave>", lambda e, cf=card_frame: cf.configure(style="DeviceCard.TFrame"))

                # 设备ID（标题）
                device_id_label = ttk.Label(card_frame, text=device_id, font=("Microsoft YaHei", font_size_title, "bold"), wraplength=int(card_width * 0.9))
                device_id_label.pack(fill=tk.X, pady=pady_text)

                # 设备类型（有线/无线）
                device_detail = self.device_details.get(device_id, {})
                dev_type = device_detail.get("type", "未知")
                dev_type_text = "📶 无线" if dev_type == "wireless" else "🔌 有线"
                type_label = ttk.Label(card_frame, text=dev_type_text, font=("Microsoft YaHei", font_size_small), foreground="#6c757d")
                type_label.pack(fill=tk.X, pady=pady_text)

                # 设备型号
                model = device_detail.get("model", "未知型号")
                model_label = ttk.Label(card_frame, text=f"型号: {model}", font=("Microsoft YaHei", font_size_normal), wraplength=int(card_width * 0.9))
                model_label.pack(fill=tk.X, pady=pady_text)

                # IP地址（仅无线设备）
                if dev_type == "wireless":
                    ip = device_detail.get("ip", "未知IP")
                    ip_label = ttk.Label(card_frame, text=f"IP: {ip}", font=("Microsoft YaHei", font_size_normal), foreground="#007bff")
                    ip_label.pack(fill=tk.X, pady=pady_text)

                # 状态标签
                status_label = ttk.Label(card_frame, text="✅ 已授权", style="DeviceStatus.Online.TLabel", font=("Microsoft YaHei", font_size_normal))
                status_label.pack(fill=tk.X, pady=(0, 5))

                # 操作按钮区
                btn_frame = ttk.Frame(card_frame)
                btn_frame.pack(fill=tk.X, expand=True)
                for i in range(5):  # 5列布局
                    btn_frame.columnconfigure(i, weight=1)

                # 动态创建按钮字体样式
                style = ttk.Style()
                btn_font = ("Microsoft YaHei", font_size_btn)
                style.configure("DynamicAction.TButton", font=btn_font, padding=1)

                # 操作按钮（三行布局）
                # 第一行
                ttk.Button(btn_frame, text="断开", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.disconnect_single_device(d)).grid(row=0, column=0, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="控制", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.remote_control_device(d)).grid(row=0, column=1, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="APK", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.install_apk(d)).grid(row=0, column=2, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                # 第二行
                ttk.Button(btn_frame, text="文件", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.show_file_manager(d)).grid(row=1, column=0, columnspan=2, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="信息", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.show_board_info_window(d)).grid(row=1, column=2, columnspan=3, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                # 第三行
                ttk.Button(btn_frame, text="日志", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.pull_device_logs(d)).grid(row=2, column=0, columnspan=2, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))
                ttk.Button(btn_frame, text="改IP", style="DynamicAction.TButton",
                           command=lambda d=device_id: self.modify_device_ip(d)).grid(row=2, column=2, columnspan=3, padx=0, pady=pady_btn, sticky=(tk.W, tk.E))

                # 更新行列位置（每行最多5个）
                col += 1
                if col >= cards_per_row:
                    col = 0
                    row += 1

        # 显示未授权设备（如果有）
        if unauthorized_devices:
            # 未授权设备从新行开始
            if devices and col != 0:
                row += 1
                col = 0

            for idx, device_id in enumerate(unauthorized_devices):
                card_frame = ttk.Frame(self.device_scrollable_frame, style="DeviceCard.TFrame", padding="8")
                card_frame.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
                card_frame.configure(width=int(card_width), height=int(card_height * 0.52))  # 未授权设备卡片稍矮
                card_frame.grid_propagate(False)

                # 设备ID
                device_id_label = ttk.Label(card_frame, text=device_id, font=("Microsoft YaHei", 10, "bold"), wraplength=int(card_width * 0.9))
                device_id_label.pack(fill=tk.X, pady=(0, 5))

                # 状态标签
                status_label = ttk.Label(card_frame, text="⚠️ 未授权", style="DeviceStatus.Unauthorized.TLabel", font=("Microsoft YaHei", 9))
                status_label.pack(fill=tk.X, pady=(0, 8))

                # 提示信息
                tip_label = ttk.Label(card_frame, text="请在设备上允许USB调试授权", font=("Microsoft YaHei", 8), foreground="#6c757d", wraplength=int(card_width * 0.9))
                tip_label.pack(fill=tk.X, pady=(0, 5))

                # 操作按钮
                btn_frame = ttk.Frame(card_frame)
                btn_frame.pack(fill=tk.X, expand=True)
                btn_frame.columnconfigure(0, weight=1)

                ttk.Button(btn_frame, text="断开", style="Action.TButton",
                           command=lambda d=device_id: self.disconnect_single_device(d)).grid(row=0, column=0, padx=1, pady=1, sticky=(tk.W, tk.E))

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
        self.append_output(f"加入命令队列: {cmd}", "INFO")  # 添加调试日志
        self.command_queue.put((cmd, device_id, retry_count))

    def _run_adb_command(self, cmd, device_id=None, retry_count=2):
        """线程执行ADB命令"""
        device_prefix = f"[{device_id}] " if device_id else ""
        self.append_output(f"[DEBUG] _run_adb_command 被调用", "INFO")  # 调试日志
        self.append_output(f"[DEBUG] cmd参数: '{cmd}'", "INFO")  # 调试日志
        self.append_output(f"[DEBUG] device_id参数: '{device_id}'", "INFO")  # 调试日志
        self.append_output(f"[DEBUG] retry_count参数: {retry_count}", "INFO")  # 调试日志

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
            self.append_output("开始扫描设备...", "INFO")
            
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
                
                self.append_output(f"ADB命令输出: {result.stdout}", "INFO")

                devices = []
                unauthorized_devices = []
                self.device_details.clear()

                # 解析设备信息
                for line in lines[1:]:
                    if line.strip():
                        # 支持制表符或空格分隔
                        if '\t' in line:
                            parts = line.strip().split('\t')
                        else:
                            # 使用正则表达式分割多个空格
                            parts = re.split(r'\s{2,}', line.strip())

                        if len(parts) >= 2:
                            device_id = parts[0]
                            status_part = parts[1]
                        
                        self.append_output(f"解析设备: {device_id}, 状态: {status_part}", "INFO")
                        
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
                            
                            self.append_output(f"设备详情: {device_id} - {model} ({dev_type})", "SUCCESS")
                            
                        elif 'unauthorized' in status_part:
                            unauthorized_devices.append(device_id)
                            self.append_output(f"未授权设备: {device_id}", "WARNING")

                self.devices_list = devices
                self.unauthorized_devices_list = unauthorized_devices

                # 更新UI（延迟执行，确保画布尺寸已初始化）
                self.root.after(100, self.refresh_devices_display, devices, unauthorized_devices)
                self.root.after(0, self._update_cmd_device_combobox, devices)

                # 更新状态
                if devices:
                    self.update_status(f"找到 {len(devices)} 个已授权设备")
                    self.append_output(f"成功扫描到 {len(devices)} 个设备", "SUCCESS")
                elif unauthorized_devices:
                    self.update_status("设备未授权，请在设备上确认授权")
                    self.append_output(f"发现 {len(unauthorized_devices)} 个未授权设备，请在设备上确认", "WARNING")
                else:
                    self.update_status("未找到任何设备")
                    self.append_output("未检测到任何设备", "WARNING")

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

    def show_tools_window(self):
        """显示工具窗口"""
        # 如果已存在未关闭的dialog，先关闭
        if hasattr(self, 'tools_dialog') and self.tools_dialog and self.tools_dialog.winfo_exists():
            try:
                self.tools_dialog.destroy()
            except:
                pass

        # 创建工具窗口
        self.tools_dialog = tk.Toplevel(self.root)
        self.tools_dialog.title("工具")
        self.tools_dialog.geometry("1000x600")
        self.tools_dialog.resizable(True, True)
        self.tools_dialog.transient(self.root)

        # 等待窗口创建完成后再计算居中位置
        self.tools_dialog.update_idletasks()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - self.tools_dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - self.tools_dialog.winfo_height()) // 2
        self.tools_dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(self.tools_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        # 所有按钮在一行显示
        for i in range(5):
            btn_frame.columnconfigure(i, weight=1)

        # 版本按钮
        ttk.Button(btn_frame, text="版本",
                   command=lambda: self.get_version_info()).grid(row=0, column=0, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 获取配置按钮
        ttk.Button(btn_frame, text="获取配置",
                   command=lambda: self.get_config_info()).grid(row=0, column=1, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 设置配置按钮
        ttk.Button(btn_frame, text="设置配置",
                   command=lambda: self.set_config_info()).grid(row=0, column=2, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 获取自定义按钮
        ttk.Button(btn_frame, text="获取自定义",
                   command=lambda: self.get_custom_info()).grid(row=0, column=3, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 设置自定义按钮
        ttk.Button(btn_frame, text="设置自定义",
                   command=lambda: self.set_custom_info()).grid(row=0, column=4, padx=2, pady=2, sticky=(tk.W, tk.E))

        # OTA升级按钮
        ttk.Button(btn_frame, text="OTA升级",
                   command=lambda: self.ota_upgrade()).grid(row=0, column=5, padx=2, pady=2, sticky=(tk.W, tk.E))

        # 信息显示区域
        info_frame = ttk.LabelFrame(main_frame, text="信息显示", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True)

        # 创建文本框显示信息
        self.tools_text = tk.Text(info_frame, height=20, width=50, wrap=tk.WORD)
        self.tools_text.pack(fill=tk.BOTH, expand=True)
        self.tools_text.insert(tk.END, "点击上方按钮获取信息...")
        self.tools_text.config(state=tk.DISABLED)

        # 关闭按钮
        ttk.Button(main_frame, text="关闭",
                   command=self.tools_dialog.destroy).pack(fill=tk.X, pady=(10, 0))

    def get_version_info(self):
        """获取版本信息"""
        self.tools_text.config(state=tk.NORMAL)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, "正在获取版本信息...\n")
        self.tools_text.update()

        try:
            import requests

            url = "http://192.168.77.2:8080/api/v1/ops/version"
            headers = {
                'REQUEST-WITHOUT-AUTHORIZE': 'true'
            }
            cookies = {
                'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
            }

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    version_data = data.get('data', {})

                    # Display as JSON format with proper formatting
                    import json
                    result = json.dumps(version_data, indent=4, ensure_ascii=False)

                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, result)
                else:
                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, f"获取失败: {data.get('message', '未知错误')}")
            else:
                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, f"请求失败: HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "连接失败，请检查服务器地址和端口")
        except Exception as e:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, f"发生错误: {str(e)}")

        self.tools_text.config(state=tk.DISABLED)

    def get_config_info(self):
        """获取配置信息"""
        self.tools_text.config(state=tk.NORMAL)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, "正在获取配置信息...\n")
        self.tools_text.update()

        try:
            import requests

            url = "http://192.168.77.2:8080/api/v1/ops/internal/training/sport/configs/8oHftycwh79693Jpq4TB"
            headers = {
                'REQUEST-WITHOUT-AUTHORIZE': 'true'
            }
            cookies = {
                'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
            }

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    config_data = data.get('data', {})

                    # Display as JSON format with proper formatting
                    import json
                    result = json.dumps(config_data, indent=4, ensure_ascii=False)

                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, result)
                else:
                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, f"获取失败: {data.get('message', '未知错误')}")
            else:
                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, f"请求失败: HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "连接失败，请检查服务器地址和端口")
        except Exception as e:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, f"发生错误: {str(e)}")

        self.tools_text.config(state=tk.DISABLED)

    def set_config_info(self):
        """设置配置信息"""
        # 读取默认配置文件
        import json
        import os

        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "设置json.json")

        default_content = ""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    default_content = f.read()
            except Exception as e:
                default_content = f"读取配置文件失败: {str(e)}"

        # 创建设置配置窗口
        set_config_dialog = tk.Toplevel(self.tools_dialog)
        set_config_dialog.title("设置配置")
        set_config_dialog.geometry("900x600")
        set_config_dialog.resizable(True, True)
        set_config_dialog.transient(self.tools_dialog)

        # 居中显示
        set_config_dialog.update_idletasks()
        x = self.tools_dialog.winfo_x() + (self.tools_dialog.winfo_width() - set_config_dialog.winfo_width()) // 2
        y = self.tools_dialog.winfo_y() + (self.tools_dialog.winfo_height() - set_config_dialog.winfo_height()) // 2
        set_config_dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(set_config_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 输入框框架
        input_frame = ttk.LabelFrame(main_frame, text="配置内容(JSON格式)", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True)

        # 创建文本编辑框
        config_text = tk.Text(input_frame, height=25, wrap=tk.WORD)
        config_text.pack(fill=tk.BOTH, expand=True)
        if default_content:
            config_text.insert(tk.END, default_content)

        # 滚动条
        scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=config_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        config_text.configure(yscrollcommand=scrollbar.set)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        def do_set_config():
            """执行设置配置"""
            config_content = config_text.get(1.0, tk.END).strip()

            if not config_content:
                messagebox.showerror("错误", "请输入配置内容", parent=set_config_dialog)
                return

            # 验证JSON格式
            try:
                json_data = json.loads(config_content)
            except json.JSONDecodeError as e:
                messagebox.showerror("错误", f"JSON格式错误: {str(e)}", parent=set_config_dialog)
                return

            # 发送POST请求
            try:
                import requests

                url = "http://192.168.77.2:8080/api/v1/ops/internal/training/sport/configs/8oHftycwh79693Jpq4TB"
                headers = {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'application/json'
                }
                cookies = {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }

                # 显示进度
                config_text.delete(1.0, tk.END)
                config_text.insert(tk.END, "正在设置配置...\n")
                config_text.update()

                response = requests.post(url, json=json_data, headers=headers, cookies=cookies, timeout=30)

                # 显示结果
                result_json = response.json()
                result_text = json.dumps(result_json, indent=4, ensure_ascii=False)

                config_text.delete(1.0, tk.END)
                config_text.insert(tk.END, result_text)

                # 显示成功提示
                if result_json.get('code') == 0:
                    messagebox.showinfo("成功", "配置设置成功！", parent=set_config_dialog)
                else:
                    messagebox.showwarning("警告", f"设置失败: {result_json.get('message', '未知错误')}", parent=set_config_dialog)

            except requests.exceptions.Timeout:
                messagebox.showerror("错误", "请求超时，请检查网络连接", parent=set_config_dialog)
                config_text.delete(1.0, tk.END)
                config_text.insert(tk.END, "请求超时")
            except requests.exceptions.ConnectionError:
                messagebox.showerror("错误", "连接失败，请检查服务器地址和端口", parent=set_config_dialog)
                config_text.delete(1.0, tk.END)
                config_text.insert(tk.END, "连接失败")
            except Exception as e:
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=set_config_dialog)
                config_text.delete(1.0, tk.END)
                config_text.insert(tk.END, f"错误: {str(e)}")

        # 设置按钮
        ttk.Button(btn_frame, text="设置",
                   command=do_set_config).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))

        # 关闭按钮
        ttk.Button(btn_frame, text="关闭",
                   command=set_config_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def get_custom_info(self):
        """获取自定义配置信息"""
        self.tools_text.config(state=tk.NORMAL)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, "正在获取自定义配置信息...\n")
        self.tools_text.update()

        try:
            import requests

            url = "http://192.168.77.2:8080/api/v1/ops/training/sport/custom/get"
            headers = {
                'REQUEST-WITHOUT-AUTHORIZE': 'true'
            }
            cookies = {
                'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
            }

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Display as JSON format with proper formatting
                import json
                result = json.dumps(data, indent=4, ensure_ascii=False)

                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, result)
            else:
                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, f"请求失败: HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "连接失败，请检查服务器地址和端口")
        except Exception as e:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, f"发生错误: {str(e)}")

        self.tools_text.config(state=tk.DISABLED)

    def set_custom_info(self):
        """设置自定义配置信息"""
        # 读取默认配置文件
        import json
        import os

        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "设置自定义.json")

        default_content = ""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    # 读取JSON data部分（去除curl命令部分）
                    content = f.read()
                    # 查找第一个{的位置
                    start_idx = content.find('{')
                    if start_idx != -1:
                        # 提取JSON部分
                        json_content = content[start_idx:].strip()
                        # 去除末尾的单引号（如果有）
                        if json_content.endswith("'"):
                            json_content = json_content[:-1]
                        default_content = json_content
                    else:
                        default_content = f"读取配置文件失败: 未找到JSON数据"
            except Exception as e:
                default_content = f"读取配置文件失败: {str(e)}"

        # 创建设置自定义配置窗口
        set_custom_dialog = tk.Toplevel(self.tools_dialog)
        set_custom_dialog.title("设置自定义配置")
        set_custom_dialog.geometry("900x600")
        set_custom_dialog.resizable(True, True)
        set_custom_dialog.transient(self.tools_dialog)

        # 居中显示
        set_custom_dialog.update_idletasks()
        x = self.tools_dialog.winfo_x() + (self.tools_dialog.winfo_width() - set_custom_dialog.winfo_width()) // 2
        y = self.tools_dialog.winfo_y() + (self.tools_dialog.winfo_height() - set_custom_dialog.winfo_height()) // 2
        set_custom_dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(set_custom_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 输入框框架
        input_frame = ttk.LabelFrame(main_frame, text="自定义配置内容(JSON格式)", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True)

        # 创建文本编辑框
        custom_text = tk.Text(input_frame, height=25, wrap=tk.WORD)
        custom_text.pack(fill=tk.BOTH, expand=True)
        if default_content:
            custom_text.insert(tk.END, default_content)

        # 滚动条
        scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=custom_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        custom_text.configure(yscrollcommand=scrollbar.set)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        def do_set_custom():
            """执行设置自定义配置"""
            config_content = custom_text.get(1.0, tk.END).strip()

            if not config_content:
                messagebox.showerror("错误", "请输入自定义配置内容", parent=set_custom_dialog)
                return

            # 验证JSON格式
            try:
                json_data = json.loads(config_content)
            except json.JSONDecodeError as e:
                messagebox.showerror("错误", f"JSON格式错误: {str(e)}", parent=set_custom_dialog)
                return

            # 发送POST请求
            try:
                import requests

                url = "http://192.168.77.2:8080/api/v1/ops/training/sport/custom/set?="
                headers = {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'application/json'
                }
                cookies = {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }

                # 显示进度
                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, "正在设置自定义配置...\n")
                custom_text.update()

                response = requests.post(url, json=json_data, headers=headers, cookies=cookies, timeout=30)

                # 显示结果
                result_json = response.json()
                result_text = json.dumps(result_json, indent=4, ensure_ascii=False)

                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, result_text)

                # 显示成功提示
                if result_json.get('code') == 0:
                    messagebox.showinfo("成功", "自定义配置设置成功！", parent=set_custom_dialog)
                else:
                    messagebox.showwarning("警告", f"设置失败: {result_json.get('message', '未知错误')}", parent=set_custom_dialog)

            except requests.exceptions.Timeout:
                messagebox.showerror("错误", "请求超时，请检查网络连接", parent=set_custom_dialog)
                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, "请求超时")
            except requests.exceptions.ConnectionError:
                messagebox.showerror("错误", "连接失败，请检查服务器地址和端口", parent=set_custom_dialog)
                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, "连接失败")
            except Exception as e:
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=set_custom_dialog)
                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, f"错误: {str(e)}")

        # 设置按钮
        ttk.Button(btn_frame, text="设置",
                   command=do_set_custom).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))

        # 关闭按钮
        ttk.Button(btn_frame, text="关闭",
                   command=set_custom_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def ota_upgrade(self):
        """OTA升级功能"""
        # 创建OTA升级窗口
        ota_dialog = tk.Toplevel(self.tools_dialog)
        ota_dialog.title("OTA升级")
        ota_dialog.geometry("600x400")
        ota_dialog.resizable(False, False)
        ota_dialog.transient(self.tools_dialog)

        # 居中显示
        ota_dialog.update_idletasks()
        x = self.tools_dialog.winfo_x() + (self.tools_dialog.winfo_width() - ota_dialog.winfo_width()) // 2
        y = self.tools_dialog.winfo_y() + (self.tools_dialog.winfo_height() - ota_dialog.winfo_height()) // 2
        ota_dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(ota_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # IV输入框
        ttk.Label(main_frame, text="IV:").grid(row=0, column=0, sticky=tk.W, pady=5)
        iv_var = tk.StringVar()
        iv_entry = ttk.Entry(main_frame, textvariable=iv_var, width=50)
        iv_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        # Key输入框
        ttk.Label(main_frame, text="Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        key_var = tk.StringVar()
        key_entry = ttk.Entry(main_frame, textvariable=key_var, width=50)
        key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        # 升级包文件选择框
        ttk.Label(main_frame, text="升级包文件:").grid(row=2, column=0, sticky=tk.W, pady=5)

        package_frame = ttk.Frame(main_frame)
        package_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        package_frame.columnconfigure(0, weight=1)

        package_var = tk.StringVar()
        package_entry = ttk.Entry(package_frame, textvariable=package_var, width=40)
        package_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse_file():
            from tkinter import filedialog
            filename = filedialog.askopenfilename(
                title="选择升级包文件",
                filetypes=[("Upgrade Package", "*"), ("All Files", "*.*")]
            )
            if filename:
                package_var.set(filename)

        ttk.Button(package_frame, text="浏览...",
                   command=browse_file).pack(side=tk.LEFT, padx=(5, 0))

        main_frame.columnconfigure(1, weight=1)

        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="升级结果", padding="10")
        result_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
        result_frame.columnconfigure(0, weight=1)

        result_text = tk.Text(result_frame, height=8, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)
        result_text.insert(tk.END, "等待升级...")
        result_text.config(state=tk.DISABLED)

        # 滚动条
        result_scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=result_text.yview)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        result_text.configure(yscrollcommand=result_scrollbar.set)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(15, 0), sticky=(tk.W, tk.E))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        def do_upgrade():
            """执行OTA升级"""
            iv = iv_var.get().strip()
            key = key_var.get().strip()
            package_path = package_var.get().strip()

            if not iv or not key:
                messagebox.showerror("错误", "请输入IV和Key", parent=ota_dialog)
                return

            if not package_path:
                messagebox.showerror("错误", "请选择升级包文件", parent=ota_dialog)
                return

            # 检查文件是否存在
            import os
            if not os.path.exists(package_path):
                messagebox.showerror("错误", "升级包文件不存在", parent=ota_dialog)
                return

            # 读取文件内容
            try:
                with open(package_path, 'rb') as f:
                    file_content = f.read()
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败: {str(e)}", parent=ota_dialog)
                return

            # 显示进度
            result_text.config(state=tk.NORMAL)
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "正在执行OTA升级...\n")
            result_text.insert(tk.END, f"IV: {iv}\n")
            result_text.insert(tk.END, f"Key: {key}\n")
            result_text.insert(tk.END, f"文件: {os.path.basename(package_path)}\n")
            result_text.insert(tk.END, f"文件大小: {len(file_content)} 字节\n\n")
            result_text.config(state=tk.DISABLED)
            result_text.update()

            # 发送升级请求
            try:
                import requests

                # 使用正确的URL格式
                url = "http://192.168.77.2:8080/api/v1/ops/ota/upgrade"
                headers = {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'multipart/form-data'
                }
                cookies = {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }

                # 准备文件和数据
                files = {
                    'upgrade_package': (os.path.basename(package_path), file_content, 'application/octet-stream')
                }
                data = {
                    'iv': iv,
                    'key': key
                }

                # 更新显示
                result_text.config(state=tk.NORMAL)
                result_text.insert(tk.END, "正在发送升级请求...\n")
                result_text.config(state=tk.DISABLED)
                result_text.update()

                # 发送请求
                response = requests.post(url, files=files, data=data, headers=headers, cookies=cookies, timeout=300)

                # 显示结果
                result_json = response.json()
                result_text.config(state=tk.NORMAL)
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, "OTA升级完成\n\n")
                result_text.insert(tk.END, json.dumps(result_json, indent=4, ensure_ascii=False))
                result_text.config(state=tk.DISABLED)

                # 显示成功提示
                if result_json.get('code') == 0:
                    messagebox.showinfo("成功", "OTA升级成功！", parent=ota_dialog)
                else:
                    messagebox.showwarning("警告", f"OTA升级失败: {result_json.get('message', '未知错误')}", parent=ota_dialog)

            except requests.exceptions.Timeout:
                result_text.config(state=tk.NORMAL)
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, "请求超时，请检查网络连接")
                result_text.config(state=tk.DISABLED)
                messagebox.showerror("错误", "请求超时，请检查网络连接", parent=ota_dialog)
            except requests.exceptions.ConnectionError:
                result_text.config(state=tk.NORMAL)
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, "连接失败，请检查服务器地址和端口")
                result_text.config(state=tk.DISABLED)
                messagebox.showerror("错误", "连接失败，请检查服务器地址和端口", parent=ota_dialog)
            except Exception as e:
                result_text.config(state=tk.NORMAL)
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, f"错误: {str(e)}")
                result_text.config(state=tk.DISABLED)
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=ota_dialog)

        # 升级按钮
        ttk.Button(btn_frame, text="升级",
                   command=do_upgrade).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))

        # 关闭按钮
        ttk.Button(btn_frame, text="关闭",
                   command=ota_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def connect_device(self):
        """IP连接设备（保留原有修复逻辑）"""
        self.ensure_adb_server_running()

        # 如果已存在未关闭的dialog，先关闭
        if hasattr(self, 'connect_dialog') and self.connect_dialog and self.connect_dialog.winfo_exists():
            try:
                self.connect_dialog.destroy()
            except:
                pass

        # 创建新的dialog
        self.connect_dialog = tk.Toplevel(self.root)
        self.connect_dialog.title("连接无线设备")
        self.connect_dialog.geometry("480x500")
        self.connect_dialog.resizable(True, True)
        self.connect_dialog.transient(self.root)

        # 先更新窗口以确保尺寸信息正确
        self.connect_dialog.update_idletasks()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - self.connect_dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - self.connect_dialog.winfo_height()) // 2
        self.connect_dialog.geometry(f"+{x}+{y}")

        # 暂时注释掉 grab_set，测试是否阻止了关闭
        # self.connect_dialog.grab_set()

        main_frame = ttk.Frame(self.connect_dialog, padding="15")
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
            "10.0.0.2", "10.0.0.3", "10.0.0.4", "192.168.77.1",
            "10.0.0.100", "192.168.1.100", "192.168.2.31", "192.168.123.1"
        ]

        # 显示预设IP
        for i, ip in enumerate(preset_ips):
            ttk.Button(preset_frame, text=ip, style="Action.TButton",
                       command=lambda ip=ip: (ip_var.set(ip), port_var.set("5555"))).grid(row=0 + i//4, column=i%4, padx=3, pady=3, sticky=(tk.W, tk.E))

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
                messagebox.showwarning("警告", "请输入设备IP地址！", parent=self.connect_dialog)
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
                    parent=self.connect_dialog
                )
                if not result:
                    return

            # 执行连接命令
            adb_cmd = f"adb connect {address}"
            self.append_output(f"执行无线连接命令: {adb_cmd}", "INFO")

            def run_connect():
                try:
                    self.update_status(f"正在连接 {address}...")
                    self.append_output(f"执行连接命令: {adb_cmd}", "INFO")

                    # 第一步：执行连接命令
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
                    if process.returncode == 0 and ("connected" in process.stdout.lower() or "already connected" in process.stdout.lower()):
                        self.update_status(f"连接命令执行成功，检查设备状态...")

                        # 等待2秒让设备连接稳定
                        time.sleep(2)

                        # 第二步：检查设备是否真的连接成功
                        check_result = subprocess.run("adb devices -l", shell=True, capture_output=True, text=True, timeout=5)
                        self.append_output(f"设备列表检查: {check_result.stdout}", "INFO")

                        # 检查设备是否在列表中
                        if address in check_result.stdout:
                            self.append_output(f"[DEBUG] 设备 {address} 在列表中找到，检查状态...", "INFO")
                            # 检查设备状态
                            lines = check_result.stdout.strip().split('\n')
                            device_found = False
                            device_unauthorized = False

                            for line in lines[1:]:
                                if line.strip():
                                    # 尝试用制表符分割，如果没有则用空格分割
                                    if '\t' in line:
                                        parts = line.strip().split('\t')
                                    else:
                                        parts = line.strip().split()
                                    self.append_output(f"[DEBUG] 解析行: {line[:80]}", "INFO")
                                    self.append_output(f"[DEBUG] parts[0]={parts[0]}, parts[1]={parts[1] if len(parts) > 1 else 'N/A'}", "INFO")
                                    if parts[0] == address:
                                        device_found = True
                                        self.append_output(f"[DEBUG] 设备状态: {parts[1]}", "INFO")
                                        if len(parts) > 1 and 'unauthorized' in parts[1]:
                                            device_unauthorized = True
                                        break
                            self.append_output(f"[DEBUG] device_found={device_found}, device_unauthorized={device_unauthorized}", "INFO")

                            if device_unauthorized:
                                self.update_status(f"设备 {address} 已连接但未授权")
                                # 直接在主线程关闭弹窗
                                self.root.after(0, self.connect_dialog.destroy)
                                # 显示授权提示
                                self.root.after(100, lambda: messagebox.showwarning(
                                    "需要授权",
                                    f"设备 {address} 已连接，但需要在设备上手动授权！\n\n请在设备上点击'允许USB调试'，然后点击刷新设备列表。",
                                    parent=self.root
                                ))
                                self.root.after(200, self.refresh_devices)
                            elif device_found:
                                self.update_status(f"成功连接到 {address}")
                                # 调试日志
                                self.append_output(f"[DEBUG] 准备关闭弹窗，dialog对象: {self.connect_dialog}", "INFO")
                                self.append_output(f"[DEBUG] dialog是否存活: {self.connect_dialog.winfo_exists()}", "INFO")

                                # 直接在主线程关闭弹窗
                                def close_dialog_and_refresh():
                                    try:
                                        self.append_output(f"[DEBUG] 开始关闭弹窗", "INFO")
                                        self.connect_dialog.destroy()
                                        self.append_output(f"[DEBUG] 弹窗已关闭", "SUCCESS")
                                    except Exception as e:
                                        self.append_output(f"[DEBUG] 关闭弹窗失败: {str(e)}", "ERROR")

                                self.root.after(0, close_dialog_and_refresh)
                                # 刷新设备列表
                                self.root.after(100, self.refresh_devices)
                                # 显示成功提示
                                self.root.after(300, lambda: messagebox.showinfo("成功", f"已连接到设备 {address}", parent=self.root))
                                return
                        else:
                            self.update_status(f"设备 {address} 未在列表中")
                            # 直接在主线程关闭弹窗
                            self.root.after(0, self.connect_dialog.destroy)
                            # 延迟显示错误提示
                            self.root.after(100, lambda: messagebox.showerror(
                                "连接失败",
                                f"设备 {address} 连接命令执行成功，但未在设备列表中找到！\n\n可能原因:\n1. 设备防火墙阻止\n2. 设备IP地址变更\n3. 设备未开启ADB调试\n\n当前设备列表:\n{check_result.stdout}",
                                parent=self.root
                            ))
                            return
                    else:
                        self.update_status(f"连接 {address} 失败")
                        # 直接在主线程关闭弹窗
                        self.root.after(0, self.connect_dialog.destroy)
                        # 延迟显示错误提示
                        self.root.after(100, lambda: messagebox.showerror("失败",
                            f"连接失败！\n命令: {adb_cmd}\n输出: {process.stdout}\n错误: {process.stderr}",
                            parent=self.root))
                        return

                except Exception as e:
                    error_msg = f"连接执行异常: {str(e)}"
                    self.append_output(error_msg, "ERROR")
                    self.update_status(f"连接失败: {str(e)}")
                    # 直接在主线程关闭弹窗
                    self.root.after(0, self.connect_dialog.destroy)
                    # 延迟显示错误提示
                    self.root.after(100, lambda: messagebox.showerror("错误", error_msg, parent=self.root))
                    return

            thread = threading.Thread(target=run_connect)
            thread.daemon = True
            thread.start()

        ttk.Button(btn_frame, text="立即连接", style="Action.TButton", command=do_connect).grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(btn_frame, text="取消", style="Action.TButton", command=self.connect_dialog.destroy).grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

        # 回车触发连接
        self.connect_dialog.bind('<Return>', lambda e: do_connect())

        # 绑定窗口关闭事件，清理引用
        def on_dialog_close():
            try:
                self.connect_dialog.destroy()
            except:
                pass
        self.connect_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

    def toggle_screen(self, action=None):
        """切换屏幕状态（息屏/亮屏）"""
        if not self.devices_list:
            messagebox.showinfo("提示", "没有已授权设备可操作")
            return

        # 如果没有指定操作，使用原来的切换逻辑
        if action is None:
            confirm = messagebox.askyesno("确认操作", f"是否对 {len(self.devices_list)} 个设备执行屏幕状态切换？")
            if not confirm:
                return

            self.update_status(f"发送屏幕切换指令到 {len(self.devices_list)} 个设备...")
            self.append_output(f"批量切换 {len(self.devices_list)} 个设备屏幕状态", "INFO")

            for device_id in self.devices_list:
                self.execute_adb_command("shell input keyevent 26", device_id, retry_count=1)

            self.root.after(1000, lambda: self.update_status("屏幕切换指令发送完成"))
        else:
            # 指定操作：息屏或亮屏
            if action == "off":
                action_name = "息屏"
                confirm = messagebox.askyesno("确认操作", f"是否对 {len(self.devices_list)} 个设备执行息屏操作？")
            else:  # action == "on"
                action_name = "亮屏"
                confirm = messagebox.askyesno("确认操作", f"是否对 {len(self.devices_list)} 个设备执行亮屏操作？")

            if not confirm:
                return

            self.update_status(f"发送{action_name}指令到 {len(self.devices_list)} 个设备...")
            self.append_output(f"批量{action_name} {len(self.devices_list)} 个设备", "INFO")

            for device_id in self.devices_list:
                if action == "off":
                    # 息屏：先按电源键关闭屏幕
                    self.execute_adb_command("shell input keyevent 26", device_id, retry_count=1)
                else:  # action == "on"
                    # 亮屏：先按电源键唤醒屏幕
                    self.execute_adb_command("shell input keyevent 26", device_id, retry_count=1)

            self.root.after(1000, lambda: self.update_status(f"{action_name}指令发送完成"))

    # ========== 其他原有功能（简化保留） ==========
    def execute_custom_adb_command(self):
        """执行自定义命令"""
        custom_cmd = self.cmd_input_var.get().strip()
        self.append_output(f"[DEBUG] 获取到的命令: '{custom_cmd}'", "INFO")  # 调试日志

        if not custom_cmd:
            messagebox.showwarning("警告", "请输入ADB命令！")
            self.cmd_input_entry.focus()
            return

        selected_device = self.cmd_device_var.get()
        self.append_output(f"[DEBUG] 选中的设备: '{selected_device}'", "INFO")  # 调试日志

        device_id = selected_device if selected_device != "所有设备（不指定）" else None

        final_cmd = f'adb {custom_cmd}' if not custom_cmd.startswith('adb ') else custom_cmd
        if device_id and '-s' not in final_cmd:
            final_cmd = final_cmd.replace('adb ', f'adb -s {device_id} ', 1)

        self.append_output(f"[DEBUG] 最终命令: '{final_cmd}'", "INFO")  # 调试日志
        self.append_output(f"[DEBUG] device_id参数: '{device_id}'", "INFO")  # 调试日志

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

    def install_apk(self, device=None):
        """安装APK（支持单个设备或所有设备）"""
        # 选择要安装的设备
        if not device:
            if not self.devices_list:
                messagebox.showinfo("提示", "没有已授权设备可操作")
                return

            # 多个设备时选择目标设备
            if len(self.devices_list) > 1:
                device = self.ask_select_device()
                if not device:
                    return  # 用户取消选择
            else:
                device = self.devices_list[0]

        # 选择APK文件
        file_path = filedialog.askopenfilename(
            title="选择APK文件",
            filetypes=[("APK文件", "*.apk"), ("所有文件", "*.*")]
        )
        if file_path:
            file_path = self.normalize_text(file_path)
            self.append_output(f"准备为设备 {device} 安装APK: {file_path}", "INFO")
            self.execute_adb_command(f'install -r "{file_path}"', device)

    def show_board_info_window(self, device):
        """显示设备信息"""
        info_window = tk.Toplevel(self.root)
        info_window.title(f"设备信息 - {device}")
        info_window.geometry("700x600")
        info_window.minsize(600, 500)
        info_window.transient(self.root)

        # 更新窗口以确保尺寸信息正确
        info_window.update_idletasks()

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
                "CPU信息": "cat /proc/cpuinfo",
                "内存信息": "cat /proc/meminfo"
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
                        # 根据标题截取输出内容
                        lines = result.stdout.split('\n')
                        if title == "CPU信息":
                            info_text.insert(tk.END, '\n'.join(lines[:30]))  # 只显示前30行
                        elif title == "内存信息":
                            info_text.insert(tk.END, '\n'.join(lines[:15]))  # 只显示前15行
                        else:
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

        # 更新窗口以确保尺寸信息正确
        file_window.update_idletasks()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - file_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - file_window.winfo_height()) // 2
        file_window.geometry(f"+{x}+{y}")

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

    def pull_device_logs(self, device):
        """获取设备当天日志"""
        # 选择保存目录
        save_dir = filedialog.askdirectory(title="选择日志保存目录")
        if not save_dir:
            return

        # 执行拉取日志命令
        log_path = "/sdcard/Android/data/cn.aisports.app/files/logs"
        self.append_output(f"开始从设备 {device} 拉取日志: {log_path}", "INFO")
        self.append_output(f"保存到: {save_dir}", "INFO")

        # 正确的命令格式: adb -s device_id pull source destination
        cmd = f'adb -s {device} pull "{log_path}" .'
        # 在子进程中切换到目标目录再执行
        import os
        if os.name == 'nt':  # Windows
            cmd = f'cd /d "{save_dir}" && adb -s {device} pull "{log_path}" .'
        else:  # Linux/Mac
            cmd = f'cd "{save_dir}" && adb -s {device} pull "{log_path}" .'

        self.update_status(f"执行命令: {cmd}")
        self.command_queue.put((cmd, None, 2))

    def modify_device_ip(self, device):
        """修改设备的固定IP地址"""
        device_detail = self.device_details.get(device, {})
        dev_type = device_detail.get("type", "wired")
        current_ip = device_detail.get("ip", "未知") if dev_type == "wireless" else "未知（有线设备）"

        # 创建IP修改对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"修改设备IP - {device}")
        dialog.geometry("450x320")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        # 更新窗口以确保尺寸信息正确
        dialog.update_idletasks()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 当前IP信息
        ttk.Label(main_frame, text="当前IP地址:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        current_ip_label = ttk.Label(main_frame, text=current_ip, font=("Microsoft YaHei", 11, "bold"), foreground="#007bff")
        current_ip_label.grid(row=0, column=1, sticky=tk.W, pady=(0, 5))

        # 设备类型提示
        dev_type_text = "📶 无线设备" if dev_type == "wireless" else "🔌 有线设备"
        ttk.Label(main_frame, text=f"设备类型: {dev_type_text}", font=("Microsoft YaHei", 9), foreground="#6c757d").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        # 新IP输入
        ttk.Label(main_frame, text="新IP地址:", font=("Microsoft YaHei", 10)).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        new_ip_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=new_ip_var, font=("Microsoft YaHei", 10)).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        # 子网掩码
        ttk.Label(main_frame, text="子网掩码:", font=("Microsoft YaHei", 10)).grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        netmask_var = tk.StringVar(value="255.255.255.0")
        ttk.Entry(main_frame, textvariable=netmask_var, font=("Microsoft YaHei", 10)).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        # 网关
        ttk.Label(main_frame, text="网关:", font=("Microsoft YaHei", 10)).grid(row=4, column=0, sticky=tk.W, pady=(0, 5))
        gateway_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=gateway_var, font=("Microsoft YaHei", 10)).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

        # 网络接口选择（有线设备需要）
        if dev_type == "wired":
            ttk.Label(main_frame, text="网络接口:", font=("Microsoft YaHei", 10)).grid(row=5, column=0, sticky=tk.W, pady=(0, 5))
            interface_var = tk.StringVar(value="eth0")
            interface_combobox = ttk.Combobox(main_frame, textvariable=interface_var, values=["eth0", "eth1"], width=15)
            interface_combobox.grid(row=5, column=1, sticky=tk.W, pady=(0, 5))

        # 操作按钮
        btn_frame = ttk.Frame(main_frame)
        row_offset = 6 if dev_type == "wired" else 6
        btn_frame.grid(row=row_offset, column=0, columnspan=2, pady=(20, 0), sticky=(tk.W, tk.E))
        btn_frame.columnconfigure((0, 1), weight=1)

        def on_confirm():
            new_ip = new_ip_var.get().strip()
            netmask = netmask_var.get().strip()
            gateway = gateway_var.get().strip()

            if not new_ip:
                messagebox.showwarning("警告", "请输入新的IP地址", parent=dialog)
                return

            if not netmask:
                messagebox.showwarning("警告", "请输入子网掩码", parent=dialog)
                return

            # 根据设备类型执行不同的操作
            if dev_type == "wireless":
                # 无线设备：断开ADB连接后重新连接到新IP
                new_address = f"{new_ip}:5555"
                self.append_output(f"断开设备 {device} 的连接...", "INFO")
                self.execute_adb_command(f"disconnect {device}")

                def reconnect():
                    self.append_output(f"尝试连接到新IP: {new_address}", "INFO")
                    self.execute_adb_command(f"connect {new_address}")

                self.root.after(2000, reconnect)
                self.root.after(3000, self.refresh_devices)
            else:
                # 有线设备：在设备内部修改网络配置
                interface = interface_var.get()
                self.append_output(f"为设备 {device} 修改网络配置...", "INFO")
                self.append_output(f"接口: {interface}, IP: {new_ip}, 掩码: {netmask}, 网关: {gateway}", "INFO")

                # 构建修改IP的命令（需要root权限）
                set_ip_cmd = f"shell su -c 'ifconfig {interface} {new_ip} netmask {netmask}'"
                if gateway:
                    set_ip_cmd = f"shell su -c 'ifconfig {interface} {new_ip} netmask {netmask} && route add default gw {gateway}'"

                self.append_output(f"执行命令: adb -s {device} {set_ip_cmd}", "INFO")

                # 执行修改IP命令
                def run_set_ip():
                    try:
                        # 1. 检查是否有root权限
                        check_root = subprocess.run(
                            f"adb -s {device} shell su -c 'id'",
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )

                        if "uid=0" not in check_root.stdout:
                            self.root.after(0, lambda: messagebox.showerror(
                                "权限错误",
                                f"设备 {device} 未获取root权限！\n\n修改IP需要root权限，请先对设备进行root操作。",
                                parent=self.root
                            ))
                            self.root.after(100, dialog.destroy)
                            return

                        # 2. 执行修改IP命令
                        result = subprocess.run(
                            f"adb -s {device} {set_ip_cmd}",
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        if result.returncode == 0:
                            self.root.after(0, lambda: messagebox.showinfo(
                                "修改成功",
                                f"已成功为设备 {device} 设置IP地址\n\n新IP: {new_ip}\n子网掩码: {netmask}\n网关: {gateway if gateway else '未设置'}\n\n注意：此修改是临时的，设备重启后会恢复",
                                parent=self.root
                            ))
                            self.append_output(f"设备 {device} IP修改成功", "SUCCESS")
                        else:
                            error_msg = result.stderr if result.stderr else result.stdout
                            self.root.after(0, lambda: messagebox.showerror(
                                "修改失败",
                                f"修改IP失败！\n\n错误信息: {error_msg}",
                                parent=self.root
                            ))
                            self.append_output(f"设备 {device} IP修改失败: {error_msg}", "ERROR")

                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror(
                            "执行错误",
                            f"执行修改IP命令时出错: {str(e)}",
                            parent=self.root
                        ))
                        self.append_output(f"设备 {device} IP修改异常: {str(e)}", "ERROR")

                threading.Thread(target=run_set_ip, daemon=True).start()

            dialog.destroy()

        ttk.Button(btn_frame, text="确认修改", command=on_confirm).grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))

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

        # 更新窗口以确保尺寸信息正确
        dialog.update_idletasks()

        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

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
