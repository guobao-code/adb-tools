import requests
import re
import time
import json
import datetime
import logging
from pathlib import Path
from requests.exceptions import RequestException
import concurrent.futures
from threading import Lock, Thread
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ====================== 默认配置（与原脚本一致） ======================
DEFAULT_BACKUP_IP = "10.0.0.56:49000"
DEFAULT_START_DATETIME = datetime.datetime(2025, 10, 8, 10, 33, 00)
DEFAULT_END_DATETIME = datetime.datetime(2025, 10, 15, 23, 00, 00)
DEFAULT_DEVICE_API_URL = "http://192.168.2.240:8080/api/v1/data/score/qydate"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "REQUEST-WITHOUT-AUTHORIZE": "true",
    "Cookie": "JSESSIONID=8912734AF80096042E50B1962F7D623A"
}
DEFAULT_BASE_SAVE_DIR = "交互式视频下载"
DEFAULT_MAX_WORKERS = 5
SUPPORTED_TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d"
]
# =====================================================================

# 全局统计变量
global_stats = {
    'total': 0,
    'success': 0,
    'failed': 0,
    'skipped': 0
}
stats_lock = Lock()

# ====================== 原有核心业务函数（无需修改） ======================
def datetime_to_millisecond_ts(dt):
    return int(dt.timestamp() * 1000)

def parse_time_input(time_str):
    if not time_str.strip():
        raise ValueError("时间字符串不能为空")
    for fmt in SUPPORTED_TIME_FORMATS:
        try:
            return datetime.datetime.strptime(time_str.strip(), fmt)
        except (ValueError, TypeError):
            continue
    raise ValueError(f"时间格式不支持，请使用以下格式之一：{', '.join(SUPPORTED_TIME_FORMATS)}")

def extract_ip_port(url):
    if not isinstance(url, str):
        return None
    match = re.match(r'http[s]?://([\d.]+:\d+)/', url)
    return match.group(1) if match else None

def replace_ip_in_url(url, new_ip_port):
    if not isinstance(url, str) or not new_ip_port:
        return url
    original_ip_port = extract_ip_port(url)
    return url.replace(original_ip_port, new_ip_port) if original_ip_port else url

def extract_video_identifier(url):
    if not url or not isinstance(url, str):
        return ""
    url_without_ip = re.sub(r'http[s]?://[^/]+', '', url.split('?')[0])
    path_parts = url_without_ip.split('/')
    return path_parts[-1].lower() if path_parts and path_parts[-1] else ""

def global_remove_duplicates(all_video_urls):
    unique_videos = {}
    for url in all_video_urls:
        if url and isinstance(url, str) and url.startswith(("http://", "https://")):
            identifier = extract_video_identifier(url)
            if identifier not in unique_videos:
                unique_videos[identifier] = url
            else:
                logging.debug(f"发现重复视频：\n{unique_videos[identifier]}\n{url}")
    logging.info(f"全局去重：{len(all_video_urls)}个原始URL → 保留{len(unique_videos)}个唯一视频")
    return list(unique_videos.values())

def download_video(url, save_path, backup_ip, max_retries=2):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": url.split('/')[0] + "//" + url.split('/')[2],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    temp_path = save_path.with_suffix(save_path.suffix + ".part")
    # 原始URL重试
    for attempt in range(max_retries + 1):
        try:
            logging.info(f"下载尝试（{attempt + 1}/{max_retries + 1}）: {url}")
            if temp_path.exists():
                temp_path.unlink()
            with requests.get(
                    url,
                    stream=True,
                    timeout=60,
                    headers=headers
            ) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                temp_path.replace(save_path)
                logging.info(f"下载成功：{save_path.name}")
                return True
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logging.warning(f"原始URL尝试{attempt + 1}失败：{str(e)}")
            if attempt < max_retries:
                time.sleep(2)
    # 备用IP重试
    original_ip_port = extract_ip_port(url)
    if not original_ip_port:
        logging.error(f"无法提取IP，无法重试：{url}")
        return False
    modified_url = replace_ip_in_url(url, backup_ip)
    if modified_url == url:
        logging.error(f"替换IP后无变化，无法重试：{url}")
        return False
    for attempt in range(max_retries + 1):
        try:
            logging.info(f"备用IP尝试（{attempt + 1}/{max_retries + 1}）: {modified_url}")
            if temp_path.exists():
                temp_path.unlink()
            with requests.get(
                    modified_url,
                    stream=True,
                    timeout=60,
                    headers=headers
            ) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                temp_path.replace(save_path)
                logging.info(f"备用IP下载成功：{save_path.name}")
                return True
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logging.warning(f"备用IP尝试{attempt + 1}失败：{str(e)}")
            if attempt < max_retries:
                time.sleep(2)
    logging.error(f"所有尝试失败：{url}")
    return False

def save_api_response(response_data, base_path, start_ts, end_ts):
    try:
        api_data_dir = base_path / "api_responses"
        api_data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"api_response_{start_ts}_{end_ts}_{timestamp}.json"
        file_path = api_data_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)
        logging.info(f"API响应数据已保存: {file_path}")
        return True
    except Exception as e:
        logging.error(f"保存API响应数据失败: {str(e)}")
        return False

def fetch_tasks_from_device(start_ts, end_ts, base_save_dir):
    try:
        request_data = {"startTime": start_ts, "endTime": end_ts}
        logging.info(
            f"请求时间范围：{datetime.datetime.fromtimestamp(start_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')} 至 {datetime.datetime.fromtimestamp(end_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"使用API地址：{DEFAULT_DEVICE_API_URL}")
        response = requests.post(
            DEFAULT_DEVICE_API_URL,
            headers=DEFAULT_HEADERS,
            json=request_data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        save_api_response(result, Path(base_save_dir), start_ts, end_ts)
        if result.get("code") != 0:
            logging.error(f"接口错误：{result.get('message', '未知错误')}")
            return []
        tasks = []
        task_info_list = result.get("data", {}).get("taskInfoScoreList", [])
        if not isinstance(task_info_list, (list, tuple)):
            task_info_list = []
        for task_info in task_info_list:
            if not isinstance(task_info, dict):
                continue
            task_id = task_info.get("task_info", {}).get("task_id")
            if not task_id:
                continue
            video_urls = []
            score_info = task_info.get("score_info", {})
            for key in ["playback", "publicPlayback", "videoUrls"]:
                value = score_info.get(key, [])
                if isinstance(value, list):
                    video_urls.extend(value)
                elif isinstance(value, str):
                    video_urls.append(value)
            tasks.append({
                "task_id": task_id,
                "sport_name": task_info.get("sport_info", {}).get("sport_name", "未知项目"),
                "video_urls": video_urls,
                "raw_data": task_info
            })
        logging.info(f"获取到 {len(tasks)} 个任务")
        return tasks
    except Exception as e:
        logging.error(f"获取任务失败：{str(e)}")
        return []

def save_task_data(task, task_path):
    try:
        task_data_path = task_path / "task_data.json"
        with open(task_data_path, 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        logging.info(f"任务数据已保存: {task_data_path}")
        return True
    except Exception as e:
        logging.error(f"保存任务数据失败: {str(e)}")
        return False

def download_single_video(args):
    url, save_path, backup_ip = args
    with stats_lock:
        global_stats['total'] += 1
    if save_path.exists() and save_path.stat().st_size > 1024 * 10:
        with stats_lock:
            global_stats['skipped'] += 1
        logging.info(f"文件已存在，跳过：{save_path.name}")
        return True, save_path.name
    success = download_video(url, save_path, backup_ip)
    with stats_lock:
        if success:
            global_stats['success'] += 1
        else:
            global_stats['failed'] += 1
    return success, save_path.name

def download_tasks_videos(tasks, backup_ip, max_workers, gui_log_widget, progress_bar, progress_label):
    base_path = Path(DEFAULT_BASE_SAVE_DIR)
    base_path.mkdir(parents=True, exist_ok=True)
    logging.info(f"视频保存目录：{base_path.absolute()}（默认）")
    logging.info(f"使用 {max_workers} 个线程进行下载")

    # 任务排序
    def get_task_running_time(task):
        try:
            running_time_val = task.get("raw_data", {}).get("task_info", {}).get("task_running_time")
            if not running_time_val:
                logging.warning(f"任务 {task.get('task_id', '未知ID')} 缺失 task_running_time 字段，将排至末尾")
                return 0
            if isinstance(running_time_val, str):
                running_time_val = running_time_val.strip()
                running_time_ts = int(running_time_val)
            else:
                running_time_ts = int(running_time_val)
            if running_time_ts < 10000000000:
                running_time_ts *= 1000
            return running_time_ts
        except Exception as e:
            logging.warning(f"提取任务 {task.get('task_id', '未知ID')} 的 task_running_time 失败：{str(e)}，将排至末尾")
            return 0

    tasks.sort(key=get_task_running_time, reverse=False)
    logging.info("已按 task_running_time 时间戳完成任务排序")

    # 重置统计
    global global_stats
    global_stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    all_video_urls = []
    for task in tasks:
        all_video_urls.extend(task["video_urls"])
    unique_global_urls = global_remove_duplicates(all_video_urls)

    # 准备下载参数
    download_args = []
    for task_idx, task in enumerate(tasks, 1):
        task_id = task["task_id"]
        sport_name = task["sport_name"]
        task_folder = f"{task_idx:03d}_{re.sub(r'[<>:\"/\\\\|?*]', '_', sport_name)}_{task_id}"
        task_path = base_path / task_folder
        task_path.mkdir(parents=True, exist_ok=True)
        save_task_data(task, task_path)
        task_unique_urls = [url for url in unique_global_urls if url in task["video_urls"]]
        if not task_unique_urls:
            logging.info(f"任务 {task_id} 无有效视频URL")
            continue
        for vid_idx, url in enumerate(task_unique_urls, 1):
            identifier = extract_video_identifier(url)
            filename = identifier if identifier else f"video_{vid_idx}_{int(time.time())}.mp4"
            save_path = task_path / filename
            download_args.append((url, save_path, backup_ip))

    if not download_args:
        logging.info("没有需要下载的视频")
        gui_log_widget.after(0, lambda: messagebox.showinfo("提示", "没有需要下载的视频"))
        # 无任务时重置进度条
        progress_bar.after(0, lambda: progress_bar.config(value=0))
        progress_label.after(0, lambda: progress_label.config(text="0 / 0 个视频"))
        return

    # 设置进度条最大值
    total_videos = len(download_args)
    progress_bar.after(0, lambda: progress_bar.config(maximum=total_videos))
    progress_label.after(0, lambda: progress_label.config(text=f"0 / {total_videos} 个视频"))

    logging.info(f"总共需要下载 {len(download_args)} 个视频")
    start_time = time.time()

    # 已完成视频计数
    completed_count = 0
    completed_lock = Lock()

    # 多线程下载
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_single_video, args): args for args in download_args}
        for future in concurrent.futures.as_completed(future_to_url):
            args = future_to_url[future]
            try:
                success, filename = future.result()
                if not success:
                    logging.error(f"下载失败: {filename}")
            except Exception as exc:
                logging.error(f"下载异常: {args[0]}, 错误: {exc}")
                with stats_lock:
                    global_stats['failed'] += 1
            finally:
                # 更新进度
                with completed_lock:
                    completed_count += 1
                    current_count = completed_count
                # 线程安全更新GUI
                progress_bar.after(0, lambda: progress_bar.config(value=current_count))
                progress_label.after(0, lambda: progress_label.config(text=f"{current_count} / {total_videos} 个视频"))

    # 统计输出
    elapsed_time = time.time() - start_time
    stats_info = f"""
===== 下载统计 =====
总视频数: {global_stats['total']}
成功: {global_stats['success']}
失败: {global_stats['failed']}
跳过(已存在): {global_stats['skipped']}
耗时: {elapsed_time:.2f} 秒
平均速度: {global_stats['success']/elapsed_time:.2f} 个/秒
"""
    logging.info(stats_info)
    # GUI主线程弹出统计提示
    gui_log_widget.after(0, lambda: messagebox.showinfo("下载完成", stats_info.strip()))

    # 下载完成后重置进度条
    progress_bar.after(0, lambda: progress_bar.config(value=0))
    progress_label.after(0, lambda: progress_label.config(text="0 / 0 个视频"))

# ====================== Tkinter 图形化界面（含进度条） ======================
class VideoDownloadGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("视频批量下载工具")
        self.root.geometry("800x700")  # 适当放大窗口，容纳进度条

        # 1. 初始化控件
        self._init_widgets()
        # 2. 配置日志（输出到GUI文本框 + 文件）
        self._config_logging()

    def _init_widgets(self):
        # 整体框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 第一部分：参数配置区域
        config_frame = ttk.LabelFrame(main_frame, text="下载参数配置", padding="10")
        config_frame.pack(fill=tk.X, pady=10)  # 修正：mb→pady

        # 备用IP
        ttk.Label(config_frame, text="备用IP:端口:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.backup_ip_entry = ttk.Entry(config_frame, width=30)
        self.backup_ip_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.backup_ip_entry.insert(0, DEFAULT_BACKUP_IP)  # 默认值

        # 开始时间
        ttk.Label(config_frame, text="开始时间:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_time_entry = ttk.Entry(config_frame, width=30)
        self.start_time_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.start_time_entry.insert(0, DEFAULT_START_DATETIME.strftime("%Y-%m-%d %H:%M:%S"))
        ttk.Label(config_frame, text="(格式：YYYY-MM-DD HH:MM:SS)", foreground="gray").grid(row=1, column=2, sticky=tk.W, pady=5)

        # 结束时间
        ttk.Label(config_frame, text="结束时间:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_time_entry = ttk.Entry(config_frame, width=30)
        self.end_time_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.end_time_entry.insert(0, DEFAULT_END_DATETIME.strftime("%Y-%m-%d %H:%M:%S"))
        ttk.Label(config_frame, text="(格式：YYYY-MM-DD HH:MM:SS)", foreground="gray").grid(row=2, column=2, sticky=tk.W, pady=5)

        # 线程数
        ttk.Label(config_frame, text="下载线程数:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.worker_spinbox = ttk.Spinbox(config_frame, from_=1, to=20, width=10)
        self.worker_spinbox.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        self.worker_spinbox.delete(0, tk.END)
        self.worker_spinbox.insert(0, DEFAULT_MAX_WORKERS)
        ttk.Label(config_frame, text="(1-20之间)", foreground="gray").grid(row=3, column=2, sticky=tk.W, pady=5)

        # 第二部分：操作按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)  # 修正：mb→pady

        self.start_btn = ttk.Button(btn_frame, text="开始下载", command=self.start_download)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))  # 修正：mr→padx

        self.clear_log_btn = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.pack(side=tk.LEFT, padx=(0, 10))  # 修正：mr→padx

        self.quit_btn = ttk.Button(btn_frame, text="退出程序", command=self.root.quit)
        self.quit_btn.pack(side=tk.LEFT)

        # 第三部分：下载进度区域（新增）
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding="10")
        progress_frame.pack(fill=tk.X, pady=10)

        # 进度条控件
        self.download_progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            mode='determinate',
        )
        self.download_progress.pack(fill=tk.X, expand=True)

        # 进度文本提示
        self.progress_label = ttk.Label(progress_frame, text="0 / 0 个视频")
        self.progress_label.pack(pady=5)

        # 第四部分：实时日志区域
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, width=1, height=1, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _config_logging(self):
        # 自定义日志处理器：输出到GUI文本框
        class GuiLogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

            def emit(self, record):
                msg = self.format(record)
                # 非主线程中更新GUI，需用after()方法
                def append_msg():
                    self.text_widget.config(state=tk.NORMAL)
                    self.text_widget.insert(tk.END, msg + "\n")
                    self.text_widget.see(tk.END)  # 自动滚动到末尾
                    self.text_widget.config(state=tk.DISABLED)
                self.text_widget.after(0, append_msg)

        # 配置日志：文件 + GUI文本框
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("download_log.txt", encoding='utf-8'),
                GuiLogHandler(self.log_text)
            ]
        )

    def _get_valid_timestamp(self, time_str, default_dt):
        """验证时间输入并返回毫秒时间戳"""
        if not time_str.strip():
            return datetime_to_millisecond_ts(default_dt)
        # 尝试解析时间字符串
        try:
            user_dt = parse_time_input(time_str)
            return datetime_to_millisecond_ts(user_dt)
        except ValueError:
            # 尝试解析毫秒时间戳
            try:
                timestamp = int(time_str)
                datetime.datetime.fromtimestamp(timestamp / 1000)
                return timestamp
            except:
                return None
        except Exception:
            return None

    def start_download(self):
        """开始下载按钮点击事件"""
        # 1. 获取输入参数
        backup_ip = self.backup_ip_entry.get().strip() or DEFAULT_BACKUP_IP
        start_time_str = self.start_time_entry.get().strip()
        end_time_str = self.end_time_entry.get().strip()
        try:
            max_workers = int(self.worker_spinbox.get().strip())
        except:
            max_workers = DEFAULT_MAX_WORKERS

        # 2. 验证时间参数
        start_ts = self._get_valid_timestamp(start_time_str, DEFAULT_START_DATETIME)
        end_ts = self._get_valid_timestamp(end_time_str, DEFAULT_END_DATETIME)
        if not start_ts or not end_ts:
            messagebox.showerror("错误", "无效的时间格式！请按照提示格式输入")
            return
        if end_ts <= start_ts:
            messagebox.showerror("错误", "结束时间必须晚于开始时间！")
            return

        # 3. 验证线程数
        if not (1 <= max_workers <= 20):
            messagebox.showerror("错误", "线程数必须在1-20之间！")
            return

        # 4. 禁用开始按钮（防止重复点击）
        self.start_btn.config(state=tk.DISABLED)

        # 5. 初始化进度条
        self.download_progress["value"] = 0
        self.progress_label["text"] = "0 / 0 个视频"

        # 6. 开启子线程执行下载
        def download_task():
            try:
                # 获取任务
                tasks = fetch_tasks_from_device(start_ts, end_ts, DEFAULT_BASE_SAVE_DIR)
                if tasks:
                    # 下载视频：传递进度条参数
                    download_tasks_videos(tasks, backup_ip, max_workers, self.log_text, self.download_progress, self.progress_label)
                else:
                    self.log_text.after(0, lambda: messagebox.showwarning("提示", "未获取到有效下载任务"))
                    # 重置进度条
                    self.root.after(0, lambda: self.download_progress.config(value=0))
                    self.root.after(0, lambda: self.progress_label.config(text="0 / 0 个视频"))
            except Exception as e:
                logging.critical(f"程序出错：{str(e)}", exc_info=True)
                self.log_text.after(0, lambda: messagebox.showerror("错误", f"程序异常：{str(e)}\n日志文件：{Path('download_log.txt').absolute()}"))
                # 异常时重置进度条
                self.root.after(0, lambda: self.download_progress.config(value=0))
                self.root.after(0, lambda: self.progress_label.config(text="0 / 0 个视频"))
            finally:
                # 恢复开始按钮
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

        Thread(target=download_task, daemon=True).start()

    def clear_log(self):
        """清空日志按钮点击事件"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDownloadGUI(root)
    root.mainloop()
