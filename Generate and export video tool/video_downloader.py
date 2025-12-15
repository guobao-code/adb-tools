import requests
import re
import time
import json
import datetime
import logging
from pathlib import Path
from requests.exceptions import RequestException
import concurrent.futures
from threading import Lock
from tqdm import tqdm
import hashlib

# ====================== 默认配置 ======================
DEFAULT_BACKUP_IP = "10.0.0.56:49000"
DEFAULT_START_DATETIME = "2025-07-18 09:00:00"
DEFAULT_END_DATETIME = "2025-07-18 12:00:00"
DEFAULT_DEVICE_API_URL = "http://192.168.2.240:8080/api/v1/data/score/qydate"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "REQUEST-WITHOUT-AUTHORIZE": "true",
    "Cookie": "JSESSIONID=8912734AF80096042E50B1962F7D623A"
}
DEFAULT_BASE_SAVE_DIR = "交互式视频下载"
DEFAULT_MAX_WORKERS = 5

# 增强配置
ENHANCED_CONFIG = {
    "timeout": 60,
    "chunk_size": 8192,
    "max_retries": 3,
    "base_retry_delay": 2,
    "max_retry_delay": 60,
    "min_file_size": 10 * 1024,  # 10KB
    "enable_file_verification": True,
    "remove_corrupted_files": True
}
# =====================================================

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("download_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局统计变量
global_stats = {
    'total': 0,
    'success': 0,
    'failed': 0,
    'skipped': 0,
    'corrupted': 0,
    'retry_success': 0
}
stats_lock = Lock()

# 全局进度条变量
global_pbar = None
pbar_lock = Lock()


class SmartRetryStrategy:
    """智能重试策略类"""

    def __init__(self, max_retries=3, base_delay=2, max_delay=60):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def get_delay(self, attempt):
        """指数退避算法计算延迟时间"""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self, attempt, exception):
        """根据异常类型决定是否重试"""
        retryable_errors = (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.HTTPError
        )

        # 对于HTTP错误，只重试服务器错误(5xx)和部分客户端错误
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                status_code = exception.response.status_code
                # 重试服务器错误和429(太多请求)
                return status_code >= 500 or status_code == 429

        return attempt < self.max_retries and isinstance(exception, retryable_errors)


class FileIntegrityChecker:
    """文件完整性检查器"""

    # 常见视频文件格式的文件头签名
    VIDEO_SIGNATURES = {
        'mp4': [b'ftyp', b'iso', b'mp4'],
        'avi': [b'RIFF'],
        'mov': [b'ftypqt', b'moov'],
        'flv': [b'FLV'],
        'mkv': [b'\x1A\x45\xDF\xA3'],
        'webm': [b'\x1A\x45\xDF\xA3'],
        'wmv': [b'\x30\x26\xB2\x75\x8E\x66\xCF\x11'],
    }

    @staticmethod
    def verify_video_file(file_path, min_size=10240):
        """
        验证视频文件完整性
        返回: (is_valid, reason)
        """
        try:
            # 检查文件是否存在
            if not file_path.exists():
                return False, "文件不存在"

            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size < min_size:
                return False, f"文件过小 ({file_size} bytes)"

            # 检查文件头
            with open(file_path, 'rb') as f:
                header = f.read(16)  # 读取前16字节

                if len(header) < 8:
                    return False, "文件头过短"

                # 检查常见视频格式
                for format_name, signatures in FileIntegrityChecker.VIDEO_SIGNATURES.items():
                    for signature in signatures:
                        if header.startswith(signature):
                            return True, f"有效的 {format_name.upper()} 文件"

                # 如果没有匹配的签名，检查是否包含视频相关字节
                if b'mdat' in header or b'moov' in header or b'avi' in header:
                    return True, "疑似视频文件（包含视频标签）"

                # 检查是否为有效的二进制文件（不是文本文件）
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)) | set(range(0x80, 0x100)))
                is_binary = bool(header.translate(None, text_chars))

                if not is_binary:
                    return False, "文件可能是文本格式，不是视频"

                return True, "未知格式但可能是二进制文件"

        except Exception as e:
            return False, f"验证异常: {str(e)}"

    @staticmethod
    def calculate_file_hash(file_path, algorithm='md5', block_size=8192):
        """计算文件哈希值"""
        try:
            hash_func = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(block_size), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return None


def parse_task_datetime(task_data):
    """从任务数据中解析日期时间信息"""
    try:
        # 尝试从不同字段获取时间信息
        raw_data = task_data.get("raw_data", {})

        # 可能的日期时间字段（根据实际API响应调整）
        time_fields = [
            "create_time", "start_time", "timestamp", "record_time",
            "task_time", "video_time", "time"
        ]

        for field in time_fields:
            time_value = raw_data.get(field)
            if time_value:
                # 处理时间戳（毫秒或秒）
                if isinstance(time_value, (int, float)):
                    if time_value > 1e12:  # 毫秒时间戳
                        return datetime.datetime.fromtimestamp(time_value / 1000)
                    else:  # 秒时间戳
                        return datetime.datetime.fromtimestamp(time_value)

                # 处理字符串时间
                elif isinstance(time_value, str):
                    # 尝试多种日期格式
                    formats = [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y/%m/%d %H:%M:%S",
                        "%Y%m%d%H%M%S",
                        "%Y-%m-%d %H:%M:%S.%f"
                    ]

                    for fmt in formats:
                        try:
                            return datetime.datetime.strptime(time_value, fmt)
                        except ValueError:
                            continue

        # 如果无法解析，使用任务ID或默认时间
        task_id = task_data.get("task_id", "")
        if task_id:
            # 尝试从任务ID中提取时间信息
            match = re.search(r'(\d{8})[_-]?(\d{6})', task_id)
            if match:
                date_str = match.group(1)
                time_str = match.group(2) if match.group(2) else "000000"
                try:
                    return datetime.datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                except ValueError:
                    pass

        # 最后使用当前时间
        logger.warning(f"无法解析任务 {task_data.get('task_id')} 的时间，使用默认时间")
        return datetime.datetime.now()

    except Exception as e:
        logger.error(f"解析任务时间失败: {e}")
        return datetime.datetime.now()


def validate_time_sequence(tasks):
    """验证任务时间顺序"""
    if not tasks:
        return True

    timestamps = [task["timestamp"] for task in tasks]
    is_sorted = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))

    if is_sorted:
        logger.info("✓ 任务已按时间顺序正确排序")
    else:
        logger.warning("⚠ 任务时间顺序可能有问题")

    return is_sorted


def get_choice_input(prompt, min_val, max_val):
    """获取选择输入"""
    while True:
        try:
            choice = input(f"{prompt} ({min_val}-{max_val}): ").strip()
            if not choice:
                return min_val  # 默认选择第一个

            choice = int(choice)
            if min_val <= choice <= max_val:
                return choice
            else:
                print(f"❌ 请输入 {min_val}-{max_val} 的数字")
        except ValueError:
            print("❌ 请输入有效数字")


def get_datetime_input():
    """简单的日期时间输入选择"""
    print("\n📅 日期时间选择")
    print("=" * 40)

    # 日期选择
    print("请选择日期:")
    today = datetime.date.today()
    date_options = [
        f"1. 今天 ({today})",
        f"2. 昨天 ({today - datetime.timedelta(days=1)})",
        f"3. 前天 ({today - datetime.timedelta(days=2)})",
        f"4. 自定义日期"
    ]

    for option in date_options:
        print(option)

    date_choice = get_choice_input("日期", 1, 4)

    if date_choice == 1:
        selected_date = today
    elif date_choice == 2:
        selected_date = today - datetime.timedelta(days=1)
    elif date_choice == 3:
        selected_date = today - datetime.timedelta(days=2)
    else:
        # 自定义日期输入
        date_str = input("请输入日期 (YYYY-MM-DD): ").strip()
        try:
            selected_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print("❌ 日期格式错误，使用今天")
            selected_date = today

    # 时间选择
    print("\n🕐 请选择时间段:")
    time_options = [
        "1. 上午 (08:00-12:00)",
        "2. 下午 (12:00-18:00)",
        "3. 晚上 (18:00-24:00)",
        "4. 全天 (00:00-24:00)",
        "5. 自定义时间"
    ]

    for option in time_options:
        print(option)

    time_choice = get_choice_input("时间段", 1, 5)

    if time_choice == 1:
        start_time = datetime.time(8, 0)
        end_time = datetime.time(12, 0)
    elif time_choice == 2:
        start_time = datetime.time(12, 0)
        end_time = datetime.time(18, 0)
    elif time_choice == 3:
        start_time = datetime.time(18, 0)
        end_time = datetime.time(23, 59)
    elif time_choice == 4:
        start_time = datetime.time(0, 0)
        end_time = datetime.time(23, 59)
    else:
        # 自定义时间输入
        start_str = input("开始时间 (HH:MM): ").strip()
        end_str = input("结束时间 (HH:MM): ").strip()
        try:
            start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
        except ValueError:
            print("❌ 时间格式错误，使用全天")
            start_time = datetime.time(0, 0)
            end_time = datetime.time(23, 59)

    # 组合日期时间
    start_dt = datetime.datetime.combine(selected_date, start_time)
    end_dt = datetime.datetime.combine(selected_date, end_time)

    # 转换为时间戳
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    print(f"✅ 选择时间: {start_dt} 至 {end_dt}")
    return start_ts, end_ts


def show_time_summary(start_ts, end_ts):
    """显示时间范围摘要"""
    start_dt = datetime.datetime.fromtimestamp(start_ts / 1000)
    end_dt = datetime.datetime.fromtimestamp(end_ts / 1000)
    duration = end_dt - start_dt

    print(f"\n📊 时间范围摘要:")
    print(f"  开始: {start_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  结束: {end_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  时长: {duration}")

    hours = duration.total_seconds() / 3600
    if hours > 24:
        print(f"  约 {int(hours / 24)} 天 {int(hours % 24)} 小时")
    elif hours >= 1:
        print(f"  约 {hours:.1f} 小时")
    else:
        print(f"  约 {int(duration.total_seconds() / 60)} 分钟")


def get_user_input():
    """简化版用户输入函数"""
    print("\n===== 下载参数配置 =====")

    # 1. 备用IP（保持简单输入）
    backup_ip = input(f"备用IP:端口（回车使用默认 {DEFAULT_BACKUP_IP}）: ").strip()
    backup_ip = backup_ip if backup_ip else DEFAULT_BACKUP_IP

    # 2. 时间范围选择（弹出式选择）
    print("\n--- 时间范围配置 ---")
    start_timestamp, end_timestamp = get_datetime_input()

    # 3. 线程数选择（简单选择）
    print("\n--- 下载设置 ---")
    print("下载线程数:")
    print("1. 低速 (1线程)")
    print("2. 标准 (3线程)")
    print("3. 快速 (5线程)")
    print("4. 高速 (10线程)")

    thread_choice = get_choice_input("选择速度", 1, 4)
    thread_map = {1: 1, 2: 3, 3: 5, 4: 10}
    max_workers = thread_map[thread_choice]

    # 显示配置摘要
    print("\n" + "=" * 40)
    print("✅ 配置确认")
    print("=" * 40)
    print(f"备用IP: {backup_ip}")
    print(f"时间范围: {datetime.datetime.fromtimestamp(start_timestamp / 1000)}")
    print(f"         至 {datetime.datetime.fromtimestamp(end_timestamp / 1000)}")
    print(f"下载线程: {max_workers}")
    print("=" * 40)

    return {
        "backup_ip": backup_ip,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "max_workers": max_workers
    }


def extract_ip_port(url):
    """从URL中提取IP和端口"""
    if not isinstance(url, str):
        return None
    match = re.match(r'http[s]?://([\d.]+:\d+)/', url)
    return match.group(1) if match else None


def replace_ip_in_url(url, new_ip_port):
    """替换URL中的IP和端口"""
    if not isinstance(url, str) or not new_ip_port:
        return url
    original_ip_port = extract_ip_port(url)
    return url.replace(original_ip_port, new_ip_port) if original_ip_port else url


def extract_video_identifier(url):
    """提取视频唯一标识用于去重"""
    if not url or not isinstance(url, str):
        return ""
    url_without_ip = re.sub(r'http[s]?://[^/]+', '', url.split('?')[0])
    path_parts = url_without_ip.split('/')
    return path_parts[-1].lower() if path_parts and path_parts[-1] else ""


def global_remove_duplicates(all_video_urls):
    """全局去重"""
    unique_videos = {}
    for url in all_video_urls:
        if url and isinstance(url, str) and url.startswith(("http://", "https://")):
            identifier = extract_video_identifier(url)
            if identifier not in unique_videos:
                unique_videos[identifier] = url
            else:
                logger.debug(f"发现重复视频：\n{unique_videos[identifier]}\n{url}")

    logger.info(f"全局去重：{len(all_video_urls)}个原始URL → 保留{len(unique_videos)}个唯一视频")
    return list(unique_videos.values())


def download_video_with_retry(url, save_path, backup_ip, retry_strategy, max_retries=2):
    """
    下载视频（带智能重试和文件验证）
    返回: (success, file_valid, retry_count)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": url.split('/')[0] + "//" + url.split('/')[2],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    def attempt_download(download_url, attempt_description):
        """单次下载尝试"""
        try:
            with requests.get(
                    download_url,
                    stream=True,
                    timeout=ENHANCED_CONFIG["timeout"],
                    headers=headers
            ) as response:
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))

                with tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=attempt_description,
                        leave=False
                ) as pbar:

                    with open(save_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=ENHANCED_CONFIG["chunk_size"]):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))

                return True, None

        except Exception as e:
            return False, e

    # 尝试原始URL（带智能重试）
    for attempt in range(max_retries + 1):
        description = f"原始URL尝试{attempt + 1}"
        success, error = attempt_download(url, description)

        if success:
            # 下载成功，验证文件完整性
            if ENHANCED_CONFIG["enable_file_verification"]:
                is_valid, reason = FileIntegrityChecker.verify_video_file(
                    save_path,
                    ENHANCED_CONFIG["min_file_size"]
                )
                if is_valid:
                    logger.info(f"✓ 下载成功且文件验证通过：{save_path.name} - {reason}")
                    return True, True, attempt
                else:
                    logger.warning(f"⚠ 下载成功但文件验证失败：{save_path.name} - {reason}")
                    if ENHANCED_CONFIG["remove_corrupted_files"]:
                        try:
                            save_path.unlink()
                            logger.info(f"已删除损坏文件：{save_path.name}")
                        except Exception as e:
                            logger.error(f"删除损坏文件失败：{e}")

                    # 文件验证失败，继续重试
                    if attempt < max_retries:
                        delay = retry_strategy.get_delay(attempt)
                        logger.info(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
                        continue
                    else:
                        return True, False, attempt
            else:
                # 不验证文件完整性
                logger.info(f"✓ 下载成功：{save_path.name}")
                return True, True, attempt
        else:
            # 下载失败
            if retry_strategy.should_retry(attempt, error):
                delay = retry_strategy.get_delay(attempt)
                logger.warning(f"下载失败，{delay}秒后重试：{error}")
                time.sleep(delay)
            else:
                break

    # 尝试备用IP（带智能重试）
    original_ip_port = extract_ip_port(url)
    if not original_ip_port:
        logger.error(f"无法提取IP，无法重试：{url}")
        return False, False, max_retries

    modified_url = replace_ip_in_url(url, backup_ip)
    if modified_url == url:
        logger.error(f"替换IP后无变化，无法重试：{url}")
        return False, False, max_retries

    for attempt in range(max_retries + 1):
        description = f"备用IP尝试{attempt + 1}"
        success, error = attempt_download(modified_url, description)

        if success:
            # 下载成功，验证文件完整性
            if ENHANCED_CONFIG["enable_file_verification"]:
                is_valid, reason = FileIntegrityChecker.verify_video_file(
                    save_path,
                    ENHANCED_CONFIG["min_file_size"]
                )
                if is_valid:
                    logger.info(f"✓ 备用IP下载成功且文件验证通过：{save_path.name} - {reason}")
                    return True, True, attempt + max_retries + 1
                else:
                    logger.warning(f"⚠ 备用IP下载成功但文件验证失败：{save_path.name} - {reason}")
                    if ENHANCED_CONFIG["remove_corrupted_files"]:
                        try:
                            save_path.unlink()
                            logger.info(f"已删除损坏文件：{save_path.name}")
                        except Exception as e:
                            logger.error(f"删除损坏文件失败：{e}")

                    # 文件验证失败，继续重试
                    if attempt < max_retries:
                        delay = retry_strategy.get_delay(attempt)
                        logger.info(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
                        continue
                    else:
                        return True, False, attempt + max_retries + 1
            else:
                # 不验证文件完整性
                logger.info(f"✓ 备用IP下载成功：{save_path.name}")
                return True, True, attempt + max_retries + 1
        else:
            # 下载失败
            if retry_strategy.should_retry(attempt, error):
                delay = retry_strategy.get_delay(attempt)
                logger.warning(f"备用IP下载失败，{delay}秒后重试：{error}")
                time.sleep(delay)
            else:
                break

    logger.error(f"❌ 所有尝试失败：{url}")
    return False, False, max_retries * 2 + 1


def save_api_response(response_data, base_path, start_ts, end_ts):
    """保存API响应数据到JSON文件"""
    try:
        api_data_dir = base_path / "api_responses"
        api_data_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"api_response_{start_ts}_{end_ts}_{timestamp}.json"
        file_path = api_data_dir / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

        logger.info(f"API响应数据已保存: {file_path}")
        return True
    except Exception as e:
        logger.error(f"保存API响应数据失败: {str(e)}")
        return False


def fetch_tasks_from_device(start_ts, end_ts, base_save_dir):
    """从默认API获取任务数据并保存响应，并按时间排序"""
    try:
        request_data = {"startTime": start_ts, "endTime": end_ts}
        logger.info(
            f"请求时间范围：{datetime.datetime.fromtimestamp(start_ts / 1000)} 至 {datetime.datetime.fromtimestamp(end_ts / 1000)}")
        logger.info(f"使用API地址：{DEFAULT_DEVICE_API_URL}")

        with tqdm(desc="获取任务数据", unit="request", leave=False) as pbar:
            response = requests.post(
                DEFAULT_DEVICE_API_URL,
                headers=DEFAULT_HEADERS,
                json=request_data,
                timeout=30
            )
            pbar.update(1)

        response.raise_for_status()
        result = response.json()

        save_api_response(result, Path(base_save_dir), start_ts, end_ts)

        if result.get("code") != 0:
            logger.error(f"接口错误：{result.get('message', '未知错误')}")
            return []

        tasks = []
        task_info_list = result.get("data", {}).get("taskInfoScoreList", [])
        if not isinstance(task_info_list, (list, tuple)):
            task_info_list = []

        for task_info in tqdm(task_info_list, desc="处理任务数据", leave=False):
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

            task_data = {
                "task_id": task_id,
                "sport_name": task_info.get("sport_info", {}).get("sport_name", "未知项目"),
                "video_urls": video_urls,
                "raw_data": task_info
            }

            # 解析任务时间
            task_datetime = parse_task_datetime(task_data)
            task_data["parsed_datetime"] = task_datetime
            task_data["timestamp"] = int(task_datetime.timestamp() * 1000)

            tasks.append(task_data)

        # 按时间排序任务（从早到晚）
        tasks.sort(key=lambda x: x["timestamp"])

        logger.info(f"获取到 {len(tasks)} 个任务，已按时间排序")

        # 输出时间范围
        if tasks:
            start_time = datetime.datetime.fromtimestamp(tasks[0]["timestamp"] / 1000)
            end_time = datetime.datetime.fromtimestamp(tasks[-1]["timestamp"] / 1000)
            logger.info(f"任务时间范围: {start_time} 至 {end_time}")

        return tasks
    except Exception as e:
        logger.error(f"获取任务失败：{str(e)}")
        return []


def save_task_data(task, task_path):
    """保存任务数据到JSON文件，包含时间信息"""
    try:
        # 添加格式化时间信息
        task_with_time = task.copy()
        if "parsed_datetime" in task:
            task_with_time["formatted_datetime"] = task["parsed_datetime"].strftime("%Y-%m-%d %H:%M:%S")

        task_data_path = task_path / "task_data.json"
        with open(task_data_path, 'w', encoding='utf-8') as f:
            json.dump(task_with_time, f, ensure_ascii=False, indent=2)
        logger.info(f"任务数据已保存: {task_data_path}")
        return True
    except Exception as e:
        logger.error(f"保存任务数据失败: {str(e)}")
        return False


def download_single_video(args):
    """下载单个视频（用于多线程）"""
    url, save_path, backup_ip, retry_strategy = args

    # 检查文件是否已存在且有效
    if save_path.exists():
        if ENHANCED_CONFIG["enable_file_verification"]:
            is_valid, reason = FileIntegrityChecker.verify_video_file(
                save_path,
                ENHANCED_CONFIG["min_file_size"]
            )
            if is_valid:
                with stats_lock:
                    global_stats['skipped'] += 1
                logger.info(f"✓ 文件已存在且验证通过，跳过：{save_path.name}")
                return True, save_path.name, 0
            else:
                logger.warning(f"⚠ 文件已存在但验证失败，重新下载：{save_path.name} - {reason}")
                try:
                    save_path.unlink()
                    logger.info(f"已删除损坏文件：{save_path.name}")
                except Exception as e:
                    logger.error(f"删除损坏文件失败：{e}")
        else:
            # 不验证完整性，只检查大小
            if save_path.stat().st_size > ENHANCED_CONFIG["min_file_size"]:
                with stats_lock:
                    global_stats['skipped'] += 1
                logger.info(f"文件已存在，跳过：{save_path.name}")
                return True, save_path.name, 0

    # 尝试下载（使用增强的下载函数）
    success, file_valid, retry_count = download_video_with_retry(
        url, save_path, backup_ip, retry_strategy, ENHANCED_CONFIG["max_retries"]
    )

    with stats_lock:
        global_stats['total'] += 1
        if success and file_valid:
            global_stats['success'] += 1
            if retry_count > 0:
                global_stats['retry_success'] += 1
        elif success and not file_valid:
            global_stats['corrupted'] += 1
        else:
            global_stats['failed'] += 1

    result_status = "成功" if success and file_valid else "损坏" if success and not file_valid else "失败"
    return success and file_valid, save_path.name, retry_count


def init_global_progress(total):
    """初始化全局进度条"""
    global global_pbar
    global_pbar = tqdm(
        total=total,
        unit='file',
        desc="总体进度",
        position=0,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
    )


def update_global_progress():
    """更新全局进度条"""
    global global_pbar
    if global_pbar:
        with pbar_lock:
            global_pbar.update(1)


def close_global_progress():
    """关闭全局进度条"""
    global global_pbar
    if global_pbar:
        global_pbar.close()
        global_pbar = None


def download_tasks_videos(tasks, backup_ip, max_workers):
    """使用多线程下载所有任务的视频，按时间顺序处理"""
    base_path = Path(DEFAULT_BASE_SAVE_DIR)
    base_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"视频保存目录：{base_path.absolute()}（默认）")
    logger.info(f"使用 {max_workers} 个线程进行下载")
    logger.info(f"文件完整性验证：{'启用' if ENHANCED_CONFIG['enable_file_verification'] else '禁用'}")
    logger.info(f"智能重试策略：最大{ENHANCED_CONFIG['max_retries']}次重试")

    # 初始化智能重试策略
    retry_strategy = SmartRetryStrategy(
        max_retries=ENHANCED_CONFIG["max_retries"],
        base_delay=ENHANCED_CONFIG["base_retry_delay"],
        max_delay=ENHANCED_CONFIG["max_retry_delay"]
    )

    # 重置全局统计
    global global_stats
    global_stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'corrupted': 0, 'retry_success': 0}

    # 收集所有视频URL用于全局去重
    all_video_urls = []
    for task in tasks:
        all_video_urls.extend(task["video_urls"])
    unique_global_urls = global_remove_duplicates(all_video_urls)

    # 准备所有下载任务（按时间顺序）
    download_args = []

    # 首先输出任务时间顺序
    logger.info("任务按时间顺序排列:")
    for task_idx, task in enumerate(tasks, 1):
        task_time = datetime.datetime.fromtimestamp(task["timestamp"] / 1000)
        logger.info(f"  {task_idx:02d}. {task_time} - {task['sport_name']} (ID: {task['task_id']})")

    for task_idx, task in enumerate(tasks, 1):
        task_id = task["task_id"]
        sport_name = task["sport_name"]
        task_time = datetime.datetime.fromtimestamp(task["timestamp"] / 1000)

        # 创建按时间命名的文件夹
        time_str = task_time.strftime("%Y%m%d_%H%M%S")
        task_folder = f"{task_idx:03d}_{time_str}_{re.sub(r'[<>:\"/\\\\|?*]', '_', sport_name)}_{task_id}"
        task_path = base_path / task_folder
        task_path.mkdir(parents=True, exist_ok=True)

        # 保存任务数据到JSON文件（包含解析的时间信息）
        save_task_data(task, task_path)

        task_unique_urls = [url for url in unique_global_urls if url in task["video_urls"]]
        if not task_unique_urls:
            logger.info(f"任务 {task_id} 无有效视频URL")
            continue

        for vid_idx, url in enumerate(task_unique_urls, 1):
            identifier = extract_video_identifier(url)
            filename = identifier if identifier else f"video_{vid_idx:03d}.mp4"
            save_path = task_path / filename
            download_args.append((url, save_path, backup_ip, retry_strategy))

    if not download_args:
        logger.info("没有需要下载的视频")
        return

    logger.info(f"总共需要下载 {len(download_args)} 个视频，按时间顺序处理")

    # 初始化全局进度条
    init_global_progress(len(download_args))

    # 使用线程池执行下载（但保持任务顺序）
    start_time = time.time()

    # 为了保持时间顺序，我们按批次处理（每个任务一个批次）
    task_batches = []
    current_batch = []
    current_task_id = None

    for args in download_args:
        # 从保存路径中提取任务信息来判断是否属于同一任务
        task_info = args[1].parent.name
        if task_info != current_task_id:
            if current_batch:
                task_batches.append(current_batch)
            current_batch = [args]
            current_task_id = task_info
        else:
            current_batch.append(args)

    if current_batch:
        task_batches.append(current_batch)

    logger.info(f"按任务分成 {len(task_batches)} 个批次处理")

    # 按批次顺序处理（保持时间顺序）
    for batch_idx, batch in enumerate(task_batches, 1):
        task_name = batch[0][1].parent.name
        logger.info(f"处理批次 {batch_idx}/{len(task_batches)}: {task_name} ({len(batch)} 个视频)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(download_single_video, args): args for args in batch}

            for future in concurrent.futures.as_completed(future_to_url):
                args = future_to_url[future]
                try:
                    success, filename, retry_count = future.result()
                    update_global_progress()
                    if not success:
                        logger.error(f"下载失败: {filename}")
                    elif retry_count > 0:
                        logger.info(f"重试后下载成功: {filename} (重试{retry_count}次)")
                except Exception as exc:
                    logger.error(f"下载异常: {args[0]}, 错误: {exc}")
                    with stats_lock:
                        global_stats['failed'] += 1
                    update_global_progress()

    # 关闭全局进度条
    close_global_progress()

    # 输出增强的下载统计
    elapsed_time = time.time() - start_time
    logger.info(f"\n===== 下载统计 =====")
    logger.info(f"总视频数: {global_stats['total']}")
    logger.info(f"✅ 成功: {global_stats['success']}")
    logger.info(f"❌ 失败: {global_stats['failed']}")
    logger.info(f"⚠️  损坏: {global_stats['corrupted']}")
    logger.info(f"⏭️  跳过: {global_stats['skipped']}")
    if global_stats['retry_success'] > 0:
        logger.info(f"🔄 重试成功: {global_stats['retry_success']}")
    logger.info(f"⏱️  耗时: {elapsed_time:.2f} 秒")

    if elapsed_time > 0:
        success_rate = (global_stats['success'] / global_stats['total']) * 100 if global_stats['total'] > 0 else 0
        logger.info(f"📊 成功率: {success_rate:.1f}%")
        logger.info(f"🚀 平均速度: {global_stats['success'] / elapsed_time:.2f} 个/秒")


def main():
    """使用简单选择的主函数"""
    print("🚀 交互式视频下载工具 - 国保定制版")
    print("=" * 50)

    try:
        # 获取配置
        config = get_user_input()

        # 显示时间摘要
        show_time_summary(config["start_timestamp"], config["end_timestamp"])

        # 确认开始
        confirm = input("\n开始下载？(Y/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print("操作取消")
            return

        # 获取任务数据
        print("\n📡 正在获取任务数据...")
        tasks = fetch_tasks_from_device(
            start_ts=config["start_timestamp"],
            end_ts=config["end_timestamp"],
            base_save_dir=DEFAULT_BASE_SAVE_DIR
        )

        if tasks:
            validate_time_sequence(tasks)
            print(f"\n🎯 开始下载 {len(tasks)} 个任务的视频...")
            download_tasks_videos(
                tasks=tasks,
                backup_ip=config["backup_ip"],
                max_workers=config["max_workers"]
            )
        else:
            print("❌ 未获取到任务数据")

        print("\n✅ 操作完成")

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        logger.error(f"程序错误: {e}")
        print("❌ 程序执行出错")


if __name__ == "__main__":
    main()