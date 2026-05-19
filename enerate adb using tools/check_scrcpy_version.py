import subprocess
import requests
import re
import sys

def get_current_version():
    try:
        result = subprocess.run(["scrcpy", "--version"], capture_output=True, text=True, timeout=5)
        output = result.stdout.strip()
        match = re.search(r'scrcpy\s+([\d.]+)', output)
        if match:
            return match.group(1)
        else:
            print(f"无法解析scrcpy版本，输出: {output}")
            return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("scrcpy未安装，请先安装scrcpy")
        return None
    except Exception as e:
        print(f"检查scrcpy版本时出错: {str(e)}")
        return None

def get_latest_version():
    try:
        response = requests.get("https://api.github.com/repos/Genymobile/scrcpy/releases/latest", timeout=10)
        if response.status_code == 200:
            latest_version = response.json()["tag_name"]
            latest_version = latest_version.lstrip('v')
            return latest_version
        else:
            print(f"无法获取最新版本信息，HTTP状态码: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败，无法检查最新版本: {str(e)}")
        return None

def main():
    print("正在检查scrcpy版本...")
    current = get_current_version()
    if current is None:
        sys.exit(1)
    print(f"当前scrcpy版本: {current}")
    
    latest = get_latest_version()
    if latest is None:
        print("请手动检查 https://github.com/Genymobile/scrcpy/releases")
        sys.exit(1)
    print(f"最新scrcpy版本: {latest}")
    
    if current == latest:
        print("恭喜！您的scrcpy是最新版本。")
    else:
        print(f"您的scrcpy版本不是最新的。建议升级到版本 {latest}。")
        print("下载地址: https://github.com/Genymobile/scrcpy/releases")

if __name__ == "__main__":
    main()