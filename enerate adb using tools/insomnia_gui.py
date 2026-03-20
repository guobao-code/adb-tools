#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Insomnia 工具模块
包含所有 Insomnia 相关的工具功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import json
import os
import threading
import subprocess
from datetime import datetime
import sys


class InsomniaGUI:
    """Insomnia 工具界面类"""
    
    def __init__(self, parent_root):
        """
        初始化 Insomnia GUI
        
        Args:
            parent_root: 父窗口根对象
        """
        self.parent_root = parent_root
        self.tools_dialog = None
        self.tools_text = None
        
        # 所有可用的 API 基础配置
        self.api_configs = {
            "默认配置 (192.168.77.2)": {
                "base_url": "http://192.168.77.2:8080/api/v1",
                "headers": {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'application/json'
                },
                "cookies": {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }
            },
            "配置 240 (192.168.2.240)": {
                "base_url": "http://192.168.2.240:8080/api/v1",
                "headers": {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'application/json'
                },
                "cookies": {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }
            },
            "配置 241 (192.168.2.241)": {
                "base_url": "http://192.168.2.241:8080/api/v1",
                "headers": {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true',
                    'Content-Type': 'application/json'
                },
                "cookies": {
                    'JSESSIONID': '73A83929AD7D9D49F37843960E088AB2'
                }
            }
        }
        
        # 当前选中的配置（默认使用第一个配置）
        self.current_config_name = list(self.api_configs.keys())[0]
        self.base_url = self.api_configs[self.current_config_name]["base_url"]
        self.default_headers = self.api_configs[self.current_config_name]["headers"]
        self.default_cookies = self.api_configs[self.current_config_name]["cookies"]
        
    def show_tools_window(self):
        """显示 Insomnia 工具窗口"""
        # 如果已存在未关闭的dialog，先关闭
        if hasattr(self, 'tools_dialog') and self.tools_dialog and self.tools_dialog.winfo_exists():
            try:
                self.tools_dialog.destroy()
            except:
                pass

        # 创建工具窗口
        self.tools_dialog = tk.Toplevel(self.parent_root)
        self.tools_dialog.title("Insomnia 工具")
        self.tools_dialog.geometry("1100x600")
        self.tools_dialog.resizable(True, True)
        self.tools_dialog.transient(self.parent_root)

        # 等待窗口创建完成后再计算居中位置
        self.tools_dialog.update_idletasks()

        # 居中显示
        x = self.parent_root.winfo_x() + (self.parent_root.winfo_width() - self.tools_dialog.winfo_width()) // 2
        y = self.parent_root.winfo_y() + (self.parent_root.winfo_height() - self.tools_dialog.winfo_height()) // 2
        self.tools_dialog.geometry(f"+{x}+{y}")

        # 主框架
        main_frame = ttk.Frame(self.tools_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置选择框架
        config_frame = ttk.LabelFrame(main_frame, text="API 配置选择", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 配置选择下拉框
        config_label = ttk.Label(config_frame, text="当前配置:", font=("Microsoft YaHei", 9))
        config_label.pack(side=tk.LEFT, padx=(0, 10))
        
        config_var = tk.StringVar(value=self.current_config_name)
        config_combo = ttk.Combobox(config_frame, textvariable=config_var, 
                                   values=list(self.api_configs.keys()),
                                   state="readonly", width=40, font=("Microsoft YaHei", 9))
        config_combo.pack(side=tk.LEFT)
        
        def update_config(event=None):
            """更新当前配置"""
            selected_config = config_var.get()
            if selected_config in self.api_configs:
                self.current_config_name = selected_config
                self.base_url = self.api_configs[selected_config]["base_url"]
                self.default_headers = self.api_configs[selected_config]["headers"]
                self.default_cookies = self.api_configs[selected_config]["cookies"]
                config_info_label.config(text=f"当前URL: {self.base_url}")
                # 更新文本框中的配置信息
                self._update_config_info()
        
        config_combo.bind("<<ComboboxSelected>>", update_config)
        
        # 配置信息显示
        config_info_label = ttk.Label(config_frame, 
                                     text=f"当前URL: {self.base_url}", 
                                     font=("Microsoft YaHei", 9, "italic"))
        config_info_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        # 所有按钮在一行显示
        for i in range(6):
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
        self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
        self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n")
        self.tools_text.insert(tk.END, "点击上方按钮获取信息...")
        self.tools_text.config(state=tk.DISABLED)

        # 关闭按钮
        ttk.Button(main_frame, text="关闭",
                   command=self.tools_dialog.destroy).pack(fill=tk.X, pady=(10, 0))

    def get_version_info(self):
        """获取版本信息"""
        self._set_text_state(True)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
        self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n\n")
        self.tools_text.insert(tk.END, "正在获取版本信息...\n")
        self.tools_text.update()

        try:
            url = f"{self.base_url}/ops/version"
            headers = self.default_headers.copy()
            cookies = self.default_cookies.copy()

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    version_data = data.get('data', {})
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

        self._set_text_state(False)

    def get_config_info(self):
        """获取配置信息"""
        self._set_text_state(True)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
        self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n\n")
        self.tools_text.insert(tk.END, "正在获取配置信息...\n")
        self.tools_text.update()

        try:
            url = f"{self.base_url}/ops/internal/training/sport/configs/8oHftycwh79693Jpq4TB"
            headers = self.default_headers.copy()
            cookies = self.default_cookies.copy()

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    config_data = data.get('data', {})
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

        self._set_text_state(False)

    def set_config_info(self):
        """设置配置信息"""
        # 读取默认配置文件
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
                url = f"{self.base_url}/ops/internal/training/sport/configs/8oHftycwh79693Jpq4TB"
                headers = self.default_headers.copy()
                cookies = self.default_cookies.copy()

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
                    messagebox.showerror("失败", f"配置设置失败: {result_json.get('message', '未知错误')}", parent=set_config_dialog)

            except requests.exceptions.Timeout:
                messagebox.showerror("错误", "请求超时，请检查网络连接", parent=set_config_dialog)
            except requests.exceptions.ConnectionError:
                messagebox.showerror("错误", "连接失败，请检查服务器地址和端口", parent=set_config_dialog)
            except Exception as e:
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=set_config_dialog)

        ttk.Button(btn_frame, text="确定", command=do_set_config).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(btn_frame, text="关闭", command=set_config_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def get_custom_info(self):
        """获取自定义信息"""
        self._set_text_state(True)
        self.tools_text.delete(1.0, tk.END)
        self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
        self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n\n")
        self.tools_text.insert(tk.END, "正在获取自定义信息...\n")
        self.tools_text.update()

        try:
            # 根据提供的curl命令更新API路径
            # 原始: /ops/internal/training/sport/customization/get/8oHftycwh79693Jpq4TB
            # 正确: /ops/training/sport/custom/get (根据curl命令)
            url = f"{self.base_url}/ops/training/sport/custom/get"
            headers = self.default_headers.copy()
            cookies = self.default_cookies.copy()
            
            # 显示请求信息用于调试
            self.tools_text.insert(tk.END, f"请求URL: {url}\n")
            self.tools_text.insert(tk.END, f"请求Headers: {headers}\n")
            self.tools_text.insert(tk.END, f"请求Cookies: {cookies}\n")
            self.tools_text.update()

            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            
            # 显示响应状态
            self.tools_text.insert(tk.END, f"\n响应状态: HTTP {response.status_code}\n")
            self.tools_text.update()

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    custom_data = data.get('data', {})
                    result = json.dumps(custom_data, indent=4, ensure_ascii=False)

                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, f"✅ 获取成功\n\n")
                    self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
                    self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n\n")
                    self.tools_text.insert(tk.END, result)
                else:
                    self.tools_text.delete(1.0, tk.END)
                    self.tools_text.insert(tk.END, f"❌ 获取失败: {data.get('message', '未知错误')}\n")
                    self.tools_text.insert(tk.END, f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            else:
                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, f"❌ 请求失败: HTTP {response.status_code}\n\n")
                self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
                self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n")
                self.tools_text.insert(tk.END, f"请求URL: {url}\n\n")
                
                # 尝试获取响应文本
                try:
                    error_text = response.text[:500]
                    self.tools_text.insert(tk.END, f"错误响应: {error_text}\n")
                except:
                    self.tools_text.insert(tk.END, "无法获取错误响应内容\n")

        except requests.exceptions.Timeout:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "⏱️ 请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, "🔌 连接失败，请检查服务器地址和端口")
        except Exception as e:
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, f"⚠️ 发生错误: {str(e)}")

        self._set_text_state(False)

    def set_custom_info(self):
        """设置自定义信息"""
        # 读取默认配置文件
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "设置自定义.json")

        default_content = ""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    default_content = f.read()
            except Exception as e:
                default_content = f"读取配置文件失败: {str(e)}"

        # 创建设置自定义窗口
        set_custom_dialog = tk.Toplevel(self.tools_dialog)
        set_custom_dialog.title("设置自定义")
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
        input_frame = ttk.LabelFrame(main_frame, text="自定义内容(JSON格式)", padding="10")
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
            """执行设置自定义"""
            custom_content = custom_text.get(1.0, tk.END).strip()

            if not custom_content:
                messagebox.showerror("错误", "请输入自定义内容", parent=set_custom_dialog)
                return

            # 验证JSON格式
            try:
                json_data = json.loads(custom_content)
            except json.JSONDecodeError as e:
                messagebox.showerror("错误", f"JSON格式错误: {str(e)}", parent=set_custom_dialog)
                return

            # 发送POST请求
            try:
                # 根据获取自定义的路径模式，更新设置自定义的路径
                # 原始: /ops/internal/training/sport/customization/set
                # 更新: /ops/training/sport/custom/set (根据获取自定义的路径模式)
                url = f"{self.base_url}/ops/training/sport/custom/set"
                headers = self.default_headers.copy()
                cookies = self.default_cookies.copy()
                
                # 显示调试信息
                custom_text.insert(tk.END, f"\n请求URL: {url}\n")
                custom_text.insert(tk.END, f"请求Headers: {headers}\n")
                custom_text.insert(tk.END, f"请求Cookies: {cookies}\n")
                custom_text.update()

                # 显示进度
                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, "正在设置自定义...\n")
                custom_text.insert(tk.END, f"目标URL: {url}\n\n")
                custom_text.update()

                response = requests.post(url, json=json_data, headers=headers, cookies=cookies, timeout=30)

                # 显示结果
                result_json = response.json()
                result_text = json.dumps(result_json, indent=4, ensure_ascii=False)

                custom_text.delete(1.0, tk.END)
                custom_text.insert(tk.END, f"HTTP响应状态: {response.status_code}\n\n")
                custom_text.insert(tk.END, result_text)

                # 显示成功提示
                if result_json.get('code') == 0:
                    messagebox.showinfo("成功", "自定义设置成功！", parent=set_custom_dialog)
                else:
                    messagebox.showerror("失败", f"自定义设置失败: {result_json.get('message', '未知错误')}", parent=set_custom_dialog)

            except requests.exceptions.Timeout:
                messagebox.showerror("错误", "请求超时，请检查网络连接", parent=set_custom_dialog)
            except requests.exceptions.ConnectionError:
                messagebox.showerror("错误", "连接失败，请检查服务器地址和端口", parent=set_custom_dialog)
            except Exception as e:
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=set_custom_dialog)

        ttk.Button(btn_frame, text="确定", command=do_set_custom).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(btn_frame, text="关闭", command=set_custom_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def ota_upgrade(self):
        """OTA升级"""
        # 检查工具对话框是否存在
        if not self.tools_dialog or not self.tools_dialog.winfo_exists():
            messagebox.showerror("错误", "请先打开Insomnia工具窗口", parent=self.parent_root)
            return
        
        # 创建OTA升级对话框
        ota_dialog = tk.Toplevel(self.tools_dialog)
        ota_dialog.title("OTA升级")
        ota_dialog.geometry("500x380")  # 增加高度以容纳更多内容
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

        # 描述信息
        description = """
⚠️ 警告：此操作将进行OTA固件升级

• 升级过程中设备将重启
• 请确保设备电量充足
• 升级过程不可中断
• 升级完成后设备将自动重启
        """

        ttk.Label(main_frame, text=description, font=("Microsoft YaHei", 9), justify=tk.LEFT).pack(pady=(0, 15))

        # IV输入框
        iv_frame = ttk.Frame(main_frame)
        iv_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(iv_frame, text="IV值:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 10))
        iv_var = tk.StringVar()
        iv_entry = ttk.Entry(iv_frame, textvariable=iv_var, font=("Microsoft YaHei", 9), width=40)
        iv_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Key输入框
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(key_frame, text="Key值:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 10))
        key_var = tk.StringVar()
        key_entry = ttk.Entry(key_frame, textvariable=key_var, font=("Microsoft YaHei", 9), width=40)
        key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 文件选择
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(file_frame, text="固件包路径:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 10))
        file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=file_var, font=("Microsoft YaHei", 9), width=30)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse_file():
            filename = filedialog.askopenfilename(
                title="选择固件包",
                filetypes=[("固件包", "*.zip *.tar *.gz *.ape"), ("所有文件", "*.*")]
            )
            if filename:
                file_var.set(filename)

        ttk.Button(file_frame, text="浏览", command=browse_file, width=8).pack(side=tk.LEFT, padx=(5, 0))

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)  # 添加第二列的权重配置

        def do_upgrade():
            # 获取输入值
            iv_value = iv_var.get().strip()
            key_value = key_var.get().strip()
            file_path = file_var.get().strip()
            
            # 验证输入
            if not iv_value:
                messagebox.showwarning("警告", "请输入IV值", parent=ota_dialog)
                return
                
            if not key_value:
                messagebox.showwarning("警告", "请输入Key值", parent=ota_dialog)
                return
                
            if not file_path:
                messagebox.showwarning("警告", "请先点击'浏览'按钮选择固件包文件", parent=ota_dialog)
                return

            if not os.path.exists(file_path):
                messagebox.showerror("错误", f"文件不存在: {file_path}\n请重新选择", parent=ota_dialog)
                return
            
            # 显示文件信息
            file_info = f"已选择文件: {os.path.basename(file_path)}\n"
            file_info += f"文件大小: {os.path.getsize(file_path) / (1024*1024):.2f} MB\n"
            file_info += f"文件路径: {file_path}\n\n"
            file_info += f"IV值: {iv_value}\n"
            file_info += f"Key值: {key_value}"
            
            # 确认升级
            confirm = messagebox.askyesno("确认升级", 
                                          f"{file_info}\n\n确定要开始OTA升级吗？\n此操作不可逆！", 
                                          parent=ota_dialog)
            if not confirm:
                return
            
            try:
                # 准备请求
                url = f"{self.base_url}/ops/ota"
                headers = {
                    'REQUEST-WITHOUT-AUTHORIZE': 'true, true',
                    'Content-Type': 'multipart/form-data'
                }
                cookies = self.default_cookies.copy()
                
                # 准备multipart/form-data数据
                files = {
                    'iv': (None, iv_value),
                    'key': (None, key_value),
                    'upgrade_package': (os.path.basename(file_path), open(file_path, 'rb'), 'application/octet-stream')
                }
                
                # 在主窗口显示进度信息
                self._set_text_state(True)
                self.tools_text.delete(1.0, tk.END)
                self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
                self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n\n")
                self.tools_text.insert(tk.END, "正在执行OTA升级...\n")
                self.tools_text.insert(tk.END, f"URL: {url}\n")
                self.tools_text.insert(tk.END, f"IV值: {iv_value}\n")
                self.tools_text.insert(tk.END, f"Key值: {key_value}\n")
                self.tools_text.insert(tk.END, f"文件: {os.path.basename(file_path)}\n")
                self.tools_text.update()
                
                # 发送请求（设置较长的超时时间，因为文件上传可能需要时间）
                response = requests.post(url, files=files, headers=headers, cookies=cookies, timeout=60)
                
                # 显示响应
                self.tools_text.insert(tk.END, f"\nHTTP响应状态: {response.status_code}\n")
                self.tools_text.update()
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        result_text = json.dumps(result, indent=4, ensure_ascii=False)
                        
                        self.tools_text.insert(tk.END, f"\n响应内容:\n{result_text}\n")
                        
                        if result.get('code') == 0:
                            messagebox.showinfo("成功", "OTA升级已开始！\n设备将在升级完成后自动重启。", parent=ota_dialog)
                            self.tools_text.insert(tk.END, "\n✅ OTA升级已开始！\n")
                        else:
                            messagebox.showerror("失败", f"OTA升级失败: {result.get('message', '未知错误')}", parent=ota_dialog)
                            self.tools_text.insert(tk.END, f"\n❌ OTA升级失败: {result.get('message', '未知错误')}\n")
                            
                    except:
                        # 如果响应不是JSON格式
                        self.tools_text.insert(tk.END, f"\n响应内容: {response.text[:500]}\n")
                        messagebox.showinfo("响应", f"升级请求已发送，响应:\n{response.text[:500]}", parent=ota_dialog)
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200] if response.text else '无响应内容'}"
                    self.tools_text.insert(tk.END, f"\n❌ 请求失败: {error_msg}\n")
                    messagebox.showerror("失败", f"OTA升级请求失败: {error_msg}", parent=ota_dialog)
                    
                self._set_text_state(False)
                
            except requests.exceptions.Timeout:
                self._set_text_state(True)
                self.tools_text.insert(tk.END, "\n⏱️ 请求超时，可能文件太大或网络连接慢\n")
                self._set_text_state(False)
                messagebox.showerror("超时", "请求超时，可能文件太大或网络连接慢\n请检查网络并重试", parent=ota_dialog)
            except requests.exceptions.ConnectionError:
                self._set_text_state(True)
                self.tools_text.insert(tk.END, "\n🔌 连接失败，请检查服务器地址和端口\n")
                self._set_text_state(False)
                messagebox.showerror("连接失败", "连接失败，请检查服务器地址和端口", parent=ota_dialog)
            except Exception as e:
                self._set_text_state(True)
                self.tools_text.insert(tk.END, f"\n⚠️ 发生错误: {str(e)}\n")
                self._set_text_state(False)
                messagebox.showerror("错误", f"发生错误: {str(e)}", parent=ota_dialog)
            finally:
                # 确保文件被关闭
                try:
                    files['upgrade_package'][1].close()
                except:
                    pass
                
                # 关闭对话框
                ota_dialog.destroy()

        ttk.Button(btn_frame, text="开始升级",
                   command=do_upgrade).grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))

        # 关闭按钮
        ttk.Button(btn_frame, text="关闭",
                   command=ota_dialog.destroy).grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

    def _set_text_state(self, enabled):
        """设置文本框状态"""
        if self.tools_text:
            if enabled:
                self.tools_text.config(state=tk.NORMAL)
            else:
                self.tools_text.config(state=tk.DISABLED)
    
    def _update_config_info(self):
        """更新文本框中的配置信息（当配置改变时）"""
        if self.tools_text:
            self._set_text_state(True)
            self.tools_text.delete(1.0, tk.END)
            self.tools_text.insert(tk.END, f"当前配置: {self.current_config_name}\n")
            self.tools_text.insert(tk.END, f"API地址: {self.base_url}\n")
            self.tools_text.insert(tk.END, "点击上方按钮获取信息...")
            self._set_text_state(False)


# 测试代码
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Insomnia GUI 测试 - 已新增两个API配置")
    root.geometry("900x500")
    
    insomnia = InsomniaGUI(root)
    
    # 显示配置信息
    info_frame = ttk.LabelFrame(root, text="API配置信息", padding="20")
    info_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
    
    info_text = tk.Text(info_frame, height=12, width=60, wrap=tk.WORD, font=("Microsoft YaHei", 9))
    info_text.pack(fill=tk.BOTH, expand=True)
    
    info_text.insert(tk.END, "✅ 新增的两个API配置已成功添加：\n\n")
    info_text.insert(tk.END, "1. 配置 240 (192.168.2.240)\n")
    info_text.insert(tk.END, "   URL: http://192.168.2.240:8080/api/v1\n\n")
    info_text.insert(tk.END, "2. 配置 241 (192.168.2.241)\n")
    info_text.insert(tk.END, "   URL: http://192.168.2.241:8080/api/v1\n\n")
    info_text.insert(tk.END, "当前可用配置：\n")
    for i, config_name in enumerate(insomnia.api_configs.keys(), 1):
        url = insomnia.api_configs[config_name]["base_url"]
        info_text.insert(tk.END, f"  {i}. {config_name}: {url}\n")
    
    info_text.config(state=tk.DISABLED)
    
    test_button = ttk.Button(root, text="打开 Insomnia 工具窗口", 
                           command=insomnia.show_tools_window,
                           style="Accent.TButton")
    test_button.pack(pady=20)
    
    # 创建现代样式
    style = ttk.Style()
    style.configure("Accent.TButton", font=("Microsoft YaHei", 10), 
                   padding=10, background="#4CAF50", foreground="white")
    
    root.mainloop()