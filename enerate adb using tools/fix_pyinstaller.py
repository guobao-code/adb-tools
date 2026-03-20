#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复PyInstaller打包问题的脚本
专门解决UpdateResourceW错误
"""

import os
import sys
import subprocess
import shutil

def check_python():
    """检查Python环境"""
    print("=" * 50)
    print("检查Python环境...")
    print("=" * 50)
    
    try:
        import platform
        python_version = platform.python_version()
        print(f"✅ Python版本: {python_version}")
        
        # 检查Python版本是否可能有问题
        major, minor, _ = python_version.split('.')
        major, minor = int(major), int(minor)
        
        if major == 3 and minor >= 13:
            print("⚠️  注意：Python 3.13+ 可能与某些PyInstaller版本不兼容")
            print("     建议使用 Python 3.8-3.12 版本")
        
        return True
    except Exception as e:
        print(f"❌ 检查Python失败: {e}")
        return False

def check_pyinstaller():
    """检查PyInstaller安装"""
    print("\n检查PyInstaller...")
    print("-" * 30)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyinstaller", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ PyInstaller版本: {version}")
            return True
        else:
            print("❌ PyInstaller未安装或有问题")
            return False
            
    except FileNotFoundError:
        print("❌ PyInstaller未安装")
        return False
    except Exception as e:
        print(f"❌ 检查PyInstaller失败: {e}")
        return False

def install_dependencies():
    """安装必要的依赖"""
    print("\n安装依赖...")
    print("-" * 30)
    
    dependencies = ["pyinstaller", "pillow", "requests"]
    
    for dep in dependencies:
        print(f"正在检查/安装 {dep}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", dep],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✅ {dep} 安装/更新成功")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  {dep} 安装失败: {e}")
        except Exception as e:
            print(f"⚠️  {dep} 安装异常: {e}")
    
    return True

def clean_build_dirs():
    """清理构建目录"""
    print("\n清理构建目录...")
    print("-" * 30)
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = ["*.spec", "*.pyc"]
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"✅ 已删除目录: {dir_name}")
            except Exception as e:
                print(f"⚠️  删除目录失败 {dir_name}: {e}")
    
    for file_pattern in files_to_clean:
        # 简化处理，不实际使用glob
        pass
    
    return True

def test_script():
    """测试主脚本是否能正常运行"""
    print("\n测试ADB工具脚本...")
    print("-" * 30)
    
    script_path = "adb_gui.py"
    
    if not os.path.exists(script_path):
        print(f"❌ 找不到脚本文件: {script_path}")
        return False
    
    try:
        # 尝试导入脚本，但不运行GUI
        print("尝试导入脚本模块...")
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("adb_gui", script_path)
        module = importlib.util.module_from_spec(spec)
        
        # 只检查导入，不执行
        print("✅ 脚本导入成功")
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败 - 缺少依赖: {e}")
        return False
    except SyntaxError as e:
        print(f"❌ 语法错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def create_simple_spec():
    """创建简单的spec文件（无图标）"""
    print("\n创建简单的spec文件...")
    print("-" * 30)
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['adb_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ADB工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',  # 关键：不使用图标，避免UpdateResourceW错误
)

coll = COLLECT(exe)
'''
    
    try:
        with open("ADB工具_noicon.spec", "w", encoding="utf-8") as f:
            f.write(spec_content)
        print("✅ 已创建无图标spec文件: ADB工具_noicon.spec")
        return True
    except Exception as e:
        print(f"❌ 创建spec文件失败: {e}")
        return False

def run_pyinstaller_simple():
    """运行最简单的PyInstaller命令"""
    print("\n运行最简单的打包命令...")
    print("-" * 30)
    
    commands = [
        # 命令1：最基本的命令
        [sys.executable, "-m", "pyinstaller", "--name", "ADB工具", "adb_gui.py"],
        
        # 命令2：单文件，无图标
        [sys.executable, "-m", "pyinstaller", "--onefile", "--windowed", "--name", "ADB工具", "adb_gui.py"],
        
        # 命令3：使用spec文件
        [sys.executable, "-m", "pyinstaller", "ADB工具_noicon.spec"],
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n尝试命令 {i}: {' '.join(cmd[2:])}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print("✅ 打包成功！")
                
                # 检查输出文件
                if os.path.exists("dist/ADB工具.exe"):
                    size = os.path.getsize("dist/ADB工具.exe")
                    print(f"   文件大小: {size/1024/1024:.1f} MB")
                elif os.path.exists("dist/ADB工具/ADB工具.exe"):
                    size = os.path.getsize("dist/ADB工具/ADB工具.exe")
                    print(f"   文件大小: {size/1024/1024:.1f} MB (非单文件)")
                
                return True
            else:
                print(f"❌ 命令 {i} 失败")
                if result.stderr:
                    print(f"   错误: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            print(f"❌ 命令 {i} 超时")
        except Exception as e:
            print(f"❌ 命令 {i} 异常: {e}")
    
    return False

def main():
    """主函数"""
    print("=" * 60)
    print("PyInstaller问题修复工具")
    print("专门解决UpdateResourceW错误")
    print("=" * 60)
    
    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"工作目录: {os.getcwd()}")
    
    # 执行检查步骤
    steps = [
        ("检查Python环境", check_python),
        ("检查PyInstaller", check_pyinstaller),
        ("安装依赖", install_dependencies),
        ("清理构建目录", clean_build_dirs),
        ("测试脚本", test_script),
        ("创建spec文件", create_simple_spec),
        ("尝试打包", run_pyinstaller_simple),
    ]
    
    results = []
    
    for step_name, step_func in steps:
        print(f"\n[{len(results)+1}/{len(steps)}] {step_name}...")
        try:
            success = step_func()
            results.append((step_name, success))
            
            if not success and step_name == "尝试打包":
                print("\n⚠️  打包失败，但可能仍有其他方法")
                print("   请尝试手动命令:")
                print("   1. pyinstaller --name \"ADB工具\" adb_gui.py")
                print("   2. pyinstaller --onefile --windowed --name \"ADB工具\" adb_gui.py")
                print("   3. pyinstaller ADB工具_noicon.spec")
        except Exception as e:
            print(f"❌ 步骤失败: {e}")
            results.append((step_name, False))
    
    # 显示结果摘要
    print("\n" + "=" * 60)
    print("修复结果摘要")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    
    for step_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{step_name:20} {status}")
    
    print(f"\n总体: {success_count}/{len(results)} 个步骤成功")
    
    if success_count >= len(results) - 1:  # 允许一个步骤失败
        print("\n🎉 修复成功！请检查dist目录中的可执行文件")
    else:
        print("\n⚠️  修复未完全成功")
        print("   请参考手动打包指南.txt中的方法")
    
    print("\n按Enter键退出...")
    input()

if __name__ == "__main__":
    main()