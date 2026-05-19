import subprocess
import time
import logging
import datetime
import re
from pathlib import Path
import concurrent.futures
from threading import Lock, Thread
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

try:
    from tkcalendar import Calendar, DateEntry
    HAS_TKCALENDAR = True
except ImportError:
    HAS_TKCALENDAR = False

# ====================== 默认配置 ======================
DEFAULT_BASE_SAVE_DIR = "交互式视频下载"
DEFAULT_MAX_WORKERS = 3
# ADB 配置
DEFAULT_DEVICE_IP = "192.168.2.100"
DEFAULT_ADB_PORT = "5555"
DEFAULT_REMOTE_PATH = "/sdcard/Android/data/cn.aisports.app/files/recordings"
# 时间范围默认值
DEFAULT_START_DATETIME = datetime.datetime(2025, 1, 1, 0, 0, 0)
DEFAULT_END_DATETIME = datetime.datetime.now()
# =====================================================================

# 全局统计变量
global_stats = {
    'total': 0,
    'success': 0,
    'failed': 0,
    'skipped': 0
}
stats_lock = Lock()

# ====================== ADB 相关函数 ======================
def adb_connect(device_ip, device_port):
    """连接设备"""
    try:
        cmd = ["adb", "connect", f"{device_ip}:{device_port}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def adb_devices():
    """获取已连接设备列表"""
    try:
        cmd = ["adb", "devices"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行标题
        devices = []
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))  # (设备序列号, 状态)
        return devices
    except Exception as e:
        logging.error(f"获取设备列表失败：{str(e)}")
        return []

def list_remote_files(device_ip, device_port, remote_path):
    """列出设备上指定路径的所有视频文件（递归扫描子目录），返回 (文件路径, 修改时间戳) 列表"""
    try:
        # 先列出顶层目录
        cmd = ["adb", "-s", f"{device_ip}:{device_port}", "shell", "ls", "-lat", remote_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logging.error(f"列出远程文件失败：{result.stderr}")
            return []
        
        lines = result.stdout.strip().split('\n')
        
        # 收集所有子目录
        subdirs = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 6:
                # 检查是否为目录（以 d 开头）
                if parts[0].startswith('d'):
                    dirname = parts[-1]
                    # 跳过 . 和 ..
                    if dirname not in ('.', '..') and not dirname.startswith('.'):
                        subdirs.append(dirname)
        
        logging.info(f"发现 {len(subdirs)} 个子目录: {subdirs}")
        
        # 递归扫描子目录，收集所有 mp4 文件
        all_files = []
        for subdir in subdirs:
            # base_path 保持为 recordings 目录，subpath 从子目录名开始
            files = _scan_directory_recursive(device_ip, device_port, remote_path, subdir)
            all_files.extend(files)
        
        logging.info(f"共找到 {len(all_files)} 个视频文件")
        return all_files
    except Exception as e:
        logging.error(f"列出远程文件异常：{str(e)}")
        return []

def _scan_directory_recursive(device_ip, device_port, base_path, subpath):
    """递归扫描目录，查找 mp4 文件，返回 (文件相对路径, 修改时间戳) 列表"""
    current_path = f"{base_path}/{subpath}" if subpath else base_path
    
    try:
        cmd = ["adb", "-s", f"{device_ip}:{device_port}", "shell", "ls", "-lat", current_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logging.warning(f"扫描目录失败：{current_path} - {result.stderr}")
            return []
        
        lines = result.stdout.strip().split('\n')
        files = []
        
        for line in lines:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 6:
                filename = parts[-1]
                
                # 跳过 . 和 ..
                if filename in ('.', '..') or filename.startswith('.'):
                    continue
                
                if parts[0].startswith('d'):
                    # 是目录，递归扫描
                    new_subpath = f"{subpath}/{filename}" if subpath else filename
                    files.extend(_scan_directory_recursive(device_ip, device_port, base_path, new_subpath))
                elif filename.endswith('.mp4'):
                    # 是 mp4 文件，记录路径和时间
                    # ls -lat 输出格式: -rw-rw-rw- 1 user group size YYYY-MM-DD HH:MM filename
                    # parts[-1] = filename, parts[-2] = HH:MM, parts[-3] = YYYY-MM-DD
                    # 或者格式为: drwxrwxrwx 2 user group size YYYY-MM-DD HH:MM dirname
                    try:
                        if ':' in parts[-2]:
                            # 时间格式: "2026-05-18 15:30" 或 "May 18 15:30"
                            mtime_str = f"{parts[-3]} {parts[-2]}"
                        else:
                            # 只有日期
                            mtime_str = parts[-2]
                        mtime = parse_remote_time(mtime_str)
                    except Exception as e:
                        logging.warning(f"解析时间失败：{' '.join(parts[-3:])} - {e}")
                        mtime = None
                    
                    # 完整文件路径（相对于recordings目录）
                    full_path = f"{subpath}/{filename}" if subpath else filename
                    files.append((full_path, mtime))
        
        return files
    except Exception as e:
        logging.warning(f"递归扫描异常：{current_path} - {str(e)}")
        return []

def parse_remote_time(time_str):
    """解析远程文件的时间字符串，返回 datetime 对象"""
    time_str = time_str.strip()
    current_year = datetime.datetime.now().year
    
    # Android ls -lat 常见格式：
    # May 18 15:30        (今年的文件，只有时分)
    # May 18 15:30:00     (今年的文件，有时分秒)
    # May 18  2025        (非今年的文件)
    # 2025-05-18 15:30:00 (某些busybox版本)
    
    # 直接解析带年份的格式
    formats_with_year = [
        "%b %d %H:%M:%S %Y",   # May 18 14:30:00 2025
        "%b %d %H:%M %Y",      # May 18 14:30 2025
        "%b %d %Y",            # May 18 2025
        "%Y-%m-%d %H:%M:%S",   # 2025-05-18 14:30:00
        "%Y-%m-%d %H:%M",      # 2025-05-18 14:30
    ]
    
    for fmt in formats_with_year:
        try:
            return datetime.datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    # 手动解析没有年份的格式 (如 "May 18 14:30")
    import calendar
    months = {v: k for k, v in enumerate(calendar.month_abbr) if v}
    months.update({v: k for k, v in enumerate(calendar.month_name) if v})
    
    # 尝试匹配 "May 18 14:30" 或 "May 18 14:30:00" 格式
    match = re.match(r'([A-Za-z]+)\s+(\d+)\s+(\d{1,2}):(\d{2})(?::(\d{2}))?', time_str)
    if match:
        month_str, day, hour, minute = match.groups()[:4]
        second = match.groups()[4] or '0'
        month = months.get(month_str.title(), 0)
        if month > 0:
            return datetime.datetime(current_year, month, int(day), int(hour), int(minute), int(second))
    
    return None

def filter_files_by_time(files, start_time, end_time):
    """根据时间范围筛选文件，时间解析失败的保留以供下载
    返回 [(relative_path, mtime), ...] 格式
    """
    filtered = []
    unknown_time_count = 0
    for fpath, mtime in files:
        if mtime is None:
            # 时间解析失败的保留，让用户自行决定
            filtered.append((fpath, mtime))
            unknown_time_count += 1
        elif start_time <= mtime <= end_time:
            filtered.append((fpath, mtime))
    if unknown_time_count > 0:
        logging.info(f"有 {unknown_time_count} 个文件时间解析失败，已包含在下载列表中")
    return filtered

def pull_single_file(args):
    """使用 adb pull 拉取单个文件"""
    device_ip, device_port, remote_path, local_path, skip_existing = args
    
    with stats_lock:
        global_stats['total'] += 1
    
    # 确保本地父目录存在
    local_file = Path(local_path)
    local_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 检查本地文件是否已存在
    if skip_existing and local_file.exists():
        file_size = local_file.stat().st_size
        if file_size > 1024:  # 文件大于1KB认为是有效文件
            with stats_lock:
                global_stats['skipped'] += 1
            logging.info(f"文件已存在，跳过：{local_file.name}")
            return True, local_file.name
    
    try:
        cmd = ["adb", "-s", f"{device_ip}:{device_port}", "pull", remote_path, local_path]
        logging.info(f"拉取文件：{remote_path} -> {local_path}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        if result.returncode == 0:
            with stats_lock:
                global_stats['success'] += 1
            logging.info(f"拉取成功：{Path(local_path).name}")
            return True, Path(local_path).name
        else:
            with stats_lock:
                global_stats['failed'] += 1
            logging.error(f"拉取失败：{remote_path} - {result.stderr or result.stdout}")
            return False, Path(remote_path).name if '/' not in remote_path else remote_path.split('/')[-1]
            
    except subprocess.TimeoutExpired:
        with stats_lock:
            global_stats['failed'] += 1
        logging.error(f"拉取超时：{remote_path}")
        return False, remote_path.split('/')[-1] if '/' in remote_path else remote_path
    except Exception as e:
        with stats_lock:
            global_stats['failed'] += 1
        logging.error(f"拉取异常：{remote_path} - {str(e)}")
        return False, remote_path.split('/')[-1] if '/' in remote_path else remote_path

def pull_files_parallel(device_ip, device_port, remote_files, remote_base_path, local_base_path, 
                        max_workers, skip_existing, gui_log_widget, progress_bar, progress_label):
    """并行拉取多个文件
    remote_files: [(relative_path, mtime), ...] - 相对路径如 "E-1-10/2026-05-18/video.mp4"
    """
    base_path = Path(local_base_path)
    base_path.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"保存目录：{base_path.absolute()}")
    logging.info(f"设备：{device_ip}:{device_port}")
    logging.info(f"远程路径：{remote_base_path}")
    logging.info(f"并发数：{max_workers}")
    
    # 重置统计
    global global_stats
    global_stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
    
    if not remote_files:
        logging.info("没有文件需要下载")
        gui_log_widget.after(0, lambda: messagebox.showinfo("提示", "没有找到可下载的文件"))
        progress_bar.after(0, lambda: progress_bar.config(value=0))
        progress_label.after(0, lambda: progress_label.config(text="0 / 0 个文件"))
        return
    
    # 准备下载参数
    download_args = []
    for file_info in remote_files:
        if isinstance(file_info, tuple):
            relative_path = file_info[0]  # 如 "E-1-10/2026-05-18/video.mp4"
        else:
            relative_path = file_info
        
        # 远程文件完整路径
        remote_path = f"{remote_base_path}/{relative_path}"
        # 本地保存路径，保持子目录结构
        local_path = str(base_path / relative_path)
        download_args.append((device_ip, device_port, remote_path, local_path, skip_existing))
    
    # 设置进度条
    total_files = len(download_args)
    progress_bar.after(0, lambda: progress_bar.config(maximum=total_files))
    progress_label.after(0, lambda: progress_label.config(text=f"0 / {total_files} 个文件"))
    
    logging.info(f"总共需要拉取 {total_files} 个文件")
    start_time = time.time()
    
    completed_count = 0
    completed_lock = Lock()
    
    # 并行下载
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_args = {executor.submit(pull_single_file, args): args for args in download_args}
        for future in concurrent.futures.as_completed(future_to_args):
            args = future_to_args[future]
            try:
                success, filename = future.result()
                if not success:
                    logging.error(f"拉取失败: {filename}")
            except Exception as exc:
                logging.error(f"拉取异常: {args[0]}, 错误: {exc}")
                with stats_lock:
                    global_stats['failed'] += 1
            finally:
                with completed_lock:
                    completed_count += 1
                    current_count = completed_count
                progress_bar.after(0, lambda v=current_count: progress_bar.config(value=v))
                progress_label.after(0, lambda v=current_count, t=total_files: progress_label.config(text=f"{v} / {t} 个文件"))
    
    # 统计输出
    elapsed_time = time.time() - start_time
    stats_info = f"""
===== 拉取统计 =====
总文件数: {global_stats['total']}
成功: {global_stats['success']}
失败: {global_stats['failed']}
跳过(已存在): {global_stats['skipped']}
耗时: {elapsed_time:.2f} 秒
"""
    logging.info(stats_info)
    gui_log_widget.after(0, lambda: messagebox.showinfo("下载完成", stats_info.strip()))
    
    progress_bar.after(0, lambda: progress_bar.config(value=0))
    progress_label.after(0, lambda: progress_label.config(text="0 / 0 个文件"))

# ====================== Tkinter 图形化界面 ======================
class VideoDownloadGUI:
    def __init__(self, root):
        self.root = root
        self.embedded = not isinstance(root, (tk.Tk, tk.Toplevel))
        if not self.embedded:
            self.root.title("ADB 视频拉取工具")
            self.root.geometry("700x600")
        
        self._init_widgets()
        self._config_logging()
    
    def _init_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="ADB 配置", padding="10")
        config_frame.pack(fill=tk.X, pady=10)
        
        # 设备 IP
        ttk.Label(config_frame, text="设备 IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.device_ip_entry = ttk.Entry(config_frame, width=25)
        self.device_ip_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.device_ip_entry.insert(0, DEFAULT_DEVICE_IP)
        
        # 端口
        ttk.Label(config_frame, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 5))
        self.device_port_entry = ttk.Entry(config_frame, width=10)
        self.device_port_entry.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        self.device_port_entry.insert(0, DEFAULT_ADB_PORT)
        
        # 连接按钮
        self.connect_btn = ttk.Button(config_frame, text="连接设备", command=self._connect_device)
        self.connect_btn.grid(row=0, column=4, padx=10)
        
        # 远程路径
        ttk.Label(config_frame, text="远程路径:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.remote_path_entry = ttk.Entry(config_frame, width=50)
        self.remote_path_entry.grid(row=1, column=1, columnspan=4, sticky=tk.EW, pady=5, padx=5)
        self.remote_path_entry.insert(0, DEFAULT_REMOTE_PATH)
        
        # 本地保存路径
        ttk.Label(config_frame, text="本地路径:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.local_path_entry = ttk.Entry(config_frame, width=50)
        self.local_path_entry.grid(row=2, column=1, columnspan=4, sticky=tk.EW, pady=5, padx=5)
        self.local_path_entry.insert(0, str(Path.cwd() / DEFAULT_BASE_SAVE_DIR))
        
        # 时间范围区域
        time_frame = ttk.LabelFrame(main_frame, text="时间范围筛选", padding="10")
        time_frame.pack(fill=tk.X, pady=10)
        
        # 创建时间选择器
        self._create_datetime_pickers(time_frame)
        
        # 选项区域
        option_frame = ttk.Frame(main_frame)
        option_frame.pack(fill=tk.X, pady=5)
        
        # 线程数
        ttk.Label(option_frame, text="并发数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.worker_spinbox = ttk.Spinbox(option_frame, from_=1, to=10, width=10)
        self.worker_spinbox.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.worker_spinbox.delete(0, tk.END)
        self.worker_spinbox.insert(0, DEFAULT_MAX_WORKERS)
        
        # 跳过已存在文件
        self.skip_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(option_frame, text="跳过已存在的文件", variable=self.skip_existing_var).grid(
            row=0, column=2, sticky=tk.W, pady=5, padx=20)
        
        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(btn_frame, text="开始拉取", command=self.start_pull)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.refresh_btn = ttk.Button(btn_frame, text="刷新文件列表", command=self._refresh_file_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_log_btn = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.quit_btn = ttk.Button(btn_frame, text="退出程序", command=self.root.quit)
        self.quit_btn.pack(side=tk.LEFT)
        
        # 进度区域
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding="10")
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.download_progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.download_progress.pack(fill=tk.X, expand=True)
        
        self.progress_label = ttk.Label(progress_frame, text="0 / 0 个文件")
        self.progress_label.pack(pady=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=1, height=1, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def _create_datetime_pickers(self, parent):
        """创建日期时间选择器（使用日历控件直接点击选择）"""
        if not HAS_TKCALENDAR:
            messagebox.showwarning(
                "缺少组件",
                "请先安装 tkcalendar 库以使用日历功能：\n\npip install tkcalendar\n\n安装后请重新运行程序。",
                parent=parent
            )
            # 回退到简单的输入框方式
            self._create_simple_datetime_pickers(parent)
            return
        
        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]  # 每5分钟一个选项
        
        def create_calendar_picker(row, label_text, default_dt):
            """创建日历日期选择器和时分选择器"""
            frame = ttk.Frame(parent)
            frame.grid(row=row, column=0, columnspan=11, sticky=tk.W, pady=5)
            
            # 标签
            ttk.Label(frame, text=label_text, width=8).pack(side=tk.LEFT, padx=(0, 5))
            
            # 日期选择器（使用 DateEntry 带日历弹出）
            date_entry = DateEntry(
                frame, width=12, background='darkblue', foreground='white',
                borderwidth=2, year=default_dt.year, month=default_dt.month, day=default_dt.day,
                date_pattern='yyyy-mm-dd', showweeknumbers=False
            )
            date_entry.pack(side=tk.LEFT, padx=(0, 10))
            
            # 小时选择
            ttk.Label(frame, text="时:").pack(side=tk.LEFT, padx=(0, 2))
            hour_var = tk.StringVar(value=f"{default_dt.hour:02d}")
            hour_combo = ttk.Combobox(frame, textvariable=hour_var, values=hours, width=4, state="readonly")
            hour_combo.pack(side=tk.LEFT, padx=(0, 5))
            
            # 分钟选择
            ttk.Label(frame, text="分:").pack(side=tk.LEFT, padx=(0, 2))
            minute_var = tk.StringVar(value=f"{default_dt.minute // 5 * 5:02d}")
            minute_combo = ttk.Combobox(frame, textvariable=minute_var, values=minutes, width=4, state="readonly")
            minute_combo.pack(side=tk.LEFT, padx=(0, 5))
            
            # 快捷按钮框架
            quick_frame = ttk.Frame(frame)
            quick_frame.pack(side=tk.LEFT, padx=(10, 0))
            
            ttk.Label(quick_frame, text="快捷:").pack(side=tk.LEFT, padx=(0, 5))
            
            def set_today():
                now = datetime.datetime.now()
                date_entry.set_date(now.date())
                hour_var.set(f"{now.hour:02d}")
                minute_var.set(f"{now.minute // 5 * 5:02d}")
            
            def set_yesterday():
                yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
                date_entry.set_date(yesterday.date())
                hour_var.set("00")
                minute_var.set("00")
            
            def set_week_ago():
                week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
                date_entry.set_date(week_ago.date())
                hour_var.set("00")
                minute_var.set("00")
            
            btn_today = ttk.Button(quick_frame, text="今天", width=5, command=set_today)
            btn_today.pack(side=tk.LEFT, padx=2)
            
            btn_yesterday = ttk.Button(quick_frame, text="昨天", width=5, command=set_yesterday)
            btn_yesterday.pack(side=tk.LEFT, padx=2)
            
            btn_week = ttk.Button(quick_frame, text="一周前", width=6, command=set_week_ago)
            btn_week.pack(side=tk.LEFT, padx=2)
            
            return {
                'date_entry': date_entry, 
                'hour': hour_var, 
                'minute': minute_var
            }
        
        # 开始时间选择器
        self.start_picker = create_calendar_picker(0, "开始时间:", DEFAULT_START_DATETIME)
        
        # 结束时间选择器
        self.end_picker = create_calendar_picker(1, "结束时间:", DEFAULT_END_DATETIME)
    
    def _create_simple_datetime_pickers(self, parent):
        """简单的文本输入时间选择器（备用方案）"""
        def create_picker(row, label_text, default_dt):
            frame = ttk.Frame(parent)
            frame.grid(row=row, column=0, columnspan=11, sticky=tk.W, pady=5)
            
            ttk.Label(frame, text=label_text, width=8).pack(side=tk.LEFT, padx=(0, 5))
            
            # 日期输入框
            date_var = tk.StringVar(value=default_dt.strftime("%Y-%m-%d"))
            date_entry = ttk.Entry(frame, textvariable=date_var, width=12)
            date_entry.pack(side=tk.LEFT, padx=(0, 5))
            
            # 时分选择
            hours = [f"{h:02d}" for h in range(24)]
            minutes = [f"{m:02d}" for m in range(0, 60, 5)]
            
            ttk.Label(frame, text="时:").pack(side=tk.LEFT, padx=(0, 2))
            hour_var = tk.StringVar(value=f"{default_dt.hour:02d}")
            hour_combo = ttk.Combobox(frame, textvariable=hour_var, values=hours, width=4, state="readonly")
            hour_combo.pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Label(frame, text="分:").pack(side=tk.LEFT, padx=(0, 2))
            minute_var = tk.StringVar(value=f"{default_dt.minute // 5 * 5:02d}")
            minute_combo = ttk.Combobox(frame, textvariable=minute_var, values=minutes, width=4, state="readonly")
            minute_combo.pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Label(frame, text="(格式: YYYY-MM-DD)").pack(side=tk.LEFT, padx=(10, 0))
            
            return {
                'date_entry': date_var, 
                'hour': hour_var, 
                'minute': minute_var
            }
        
        self.start_picker = create_picker(0, "开始时间:", DEFAULT_START_DATETIME)
        self.end_picker = create_picker(1, "结束时间:", DEFAULT_END_DATETIME)
    
    def _get_datetime_from_picker(self, picker):
        """从选择器获取 datetime 对象"""
        try:
            if HAS_TKCALENDAR:
                # 日历控件模式
                date_value = picker['date_entry'].get_date()
                hour = int(picker['hour'].get())
                minute = int(picker['minute'].get())
                return datetime.datetime(date_value.year, date_value.month, date_value.day, hour, minute, 0)
            else:
                # 简单输入框模式
                date_str = picker['date_entry'].get()
                date_value = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                hour = int(picker['hour'].get())
                minute = int(picker['minute'].get())
                return datetime.datetime(date_value.year, date_value.month, date_value.day, hour, minute, 0)
        except (ValueError, AttributeError) as e:
            logging.warning(f"解析时间失败: {e}")
            return None
    
    def _config_logging(self):
        class GuiLogHandler(logging.Handler):
            def __init__(self, text_widget, source_path):
                super().__init__()
                self.text_widget = text_widget
                self.source_path = Path(source_path).resolve()
                self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            
            def emit(self, record):
                try:
                    if Path(record.pathname).resolve() != self.source_path:
                        return
                except Exception:
                    return

                msg = self.format(record)
                def append_msg():
                    self.text_widget.config(state=tk.NORMAL)
                    self.text_widget.insert(tk.END, msg + "\n")
                    self.text_widget.see(tk.END)
                    self.text_widget.config(state=tk.DISABLED)
                self.text_widget.after(0, append_msg)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        log_path = Path("download_log.txt").resolve()
        has_file_handler = any(
            isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename) == log_path
            for handler in root_logger.handlers
        )
        if not has_file_handler:
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        has_gui_handler = any(
            getattr(handler, "text_widget", None) is self.log_text
            for handler in root_logger.handlers
        )
        if not has_gui_handler:
            root_logger.addHandler(GuiLogHandler(self.log_text, __file__))
    
    def _connect_device(self):
        """连接设备"""
        device_ip = self.device_ip_entry.get().strip()
        device_port = self.device_port_entry.get().strip()
        
        if not device_ip or not device_port:
            messagebox.showwarning("警告", "请输入设备 IP 和端口")
            return
        
        def connect_task():
            self.connect_btn.config(state=tk.DISABLED)
            self.connect_btn.config(text="连接中...")
            
            success, msg = adb_connect(device_ip, device_port)
            
            self.root.after(0, lambda: self.connect_btn.config(state=tk.NORMAL, text="连接设备"))
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("成功", f"设备连接成功！\n\n{msg}"))
                logging.info(f"设备连接成功：{msg}")
            else:
                self.root.after(0, lambda: messagebox.showwarning("失败", f"设备连接失败！\n\n{msg}"))
                logging.error(f"设备连接失败：{msg}")
        
        Thread(target=connect_task, daemon=True).start()
    
    def _refresh_file_list(self):
        """刷新文件列表"""
        device_ip = self.device_ip_entry.get().strip()
        device_port = self.device_port_entry.get().strip()
        remote_path = self.remote_path_entry.get().strip()
        
        if not device_ip or not device_port:
            messagebox.showwarning("警告", "请输入设备 IP 和端口")
            return
        
        def refresh_task():
            self.refresh_btn.config(state=tk.DISABLED)
            self.refresh_btn.config(text="刷新中...")
            
            files = list_remote_files(device_ip, device_port, remote_path)
            
            self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL, text="刷新文件列表"))
            
            if files:
                # 获取时间范围
                start_time = self._get_datetime_from_picker(self.start_picker)
                end_time = self._get_datetime_from_picker(self.end_picker)
                if start_time is None:
                    start_time = DEFAULT_START_DATETIME
                if end_time is None:
                    end_time = DEFAULT_END_DATETIME
                
                # 筛选文件（现在 files 是 [(relative_path, mtime), ...]）
                filtered_files = filter_files_by_time(files, start_time, end_time)
                
                # filtered_files 是 [(relative_path, mtime), ...]，转换为集合方便查找
                filtered_set = set(fpath for fpath, _ in filtered_files)
                
                file_count = len(filtered_files)
                total_count = len(files)
                
                # 显示文件列表及时间
                file_list_str = []
                for fpath, ftime in files[:50]:
                    time_str = ftime.strftime("%Y-%m-%d %H:%M") if ftime else "未知时间"
                    marker = "✓" if fpath in filtered_set else "×"
                    file_list_str.append(f"{marker} {time_str} - {fpath}")
                
                msg = f"远程目录: {remote_path}\n"
                msg += f"总文件数: {total_count}\n"
                msg += f"时间范围内: {file_count}\n"
                msg += f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"
                msg += "文件列表 (✓=将下载, ×=不下载):\n"
                msg += "\n".join(file_list_str)
                if len(files) > 50:
                    msg += f"\n... 还有 {len(files) - 50} 个文件"
                
                self.root.after(0, lambda: messagebox.showinfo("文件列表", msg))
                logging.info(f"发现 {total_count} 个远程文件，其中 {file_count} 个在时间范围内")
            else:
                self.root.after(0, lambda: messagebox.showwarning("提示", f"在 {remote_path}\n未找到文件或路径无效"))
                logging.warning(f"未找到远程文件")
        
        Thread(target=refresh_task, daemon=True).start()
    
    def start_pull(self):
        """开始拉取"""
        device_ip = self.device_ip_entry.get().strip()
        device_port = self.device_port_entry.get().strip()
        remote_path = self.remote_path_entry.get().strip()
        local_path = self.local_path_entry.get().strip()
        
        if not device_ip or not device_port:
            messagebox.showerror("错误", "请输入设备 IP 和端口")
            return
        
        if not remote_path:
            messagebox.showerror("错误", "请输入远程路径")
            return
        
        if not local_path:
            messagebox.showerror("错误", "请输入本地保存路径")
            return
        
        try:
            max_workers = int(self.worker_spinbox.get().strip())
            if not (1 <= max_workers <= 10):
                raise ValueError()
        except:
            max_workers = DEFAULT_MAX_WORKERS
        
        # 获取时间范围
        start_time = self._get_datetime_from_picker(self.start_picker)
        end_time = self._get_datetime_from_picker(self.end_picker)
        if start_time is None:
            start_time = DEFAULT_START_DATETIME
        if end_time is None:
            end_time = DEFAULT_END_DATETIME
        
        if end_time <= start_time:
            messagebox.showerror("错误", "结束时间必须晚于开始时间！")
            return
        
        skip_existing = self.skip_existing_var.get()
        
        # 获取文件列表
        self.start_btn.config(state=tk.DISABLED)
        self.download_progress["value"] = 0
        self.progress_label["text"] = "正在获取文件列表..."
        
        def pull_task():
            try:
                # 获取远程文件列表（带时间戳）
                files = list_remote_files(device_ip, device_port, remote_path)
                
                if files:
                    # 按时间筛选
                    filtered_files = filter_files_by_time(files, start_time, end_time)
                    logging.info(f"时间范围 {start_time} ~ {end_time}，筛选后 {len(filtered_files)}/{len(files)} 个文件")
                    
                    if filtered_files:
                        pull_files_parallel(
                            device_ip, device_port, filtered_files, remote_path, local_path,
                            max_workers, skip_existing, self.log_text, 
                            self.download_progress, self.progress_label
                        )
                    else:
                        self.log_text.after(0, lambda: messagebox.showwarning("提示", 
                            f"在时间范围内未找到文件\n\n时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"))
                        self.root.after(0, lambda: self.download_progress.config(value=0))
                        self.root.after(0, lambda: self.progress_label.config(text="0 / 0 个文件"))
                else:
                    self.log_text.after(0, lambda: messagebox.showwarning("提示", "未找到可下载的文件"))
                    self.root.after(0, lambda: self.download_progress.config(value=0))
                    self.root.after(0, lambda: self.progress_label.config(text="0 / 0 个文件"))
            except Exception as e:
                logging.critical(f"程序出错：{str(e)}", exc_info=True)
                self.log_text.after(0, lambda: messagebox.showerror("错误", f"程序异常：{str(e)}"))
            finally:
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
        
        Thread(target=pull_task, daemon=True).start()
    
    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDownloadGUI(root)
    root.mainloop()
