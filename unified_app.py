# -*- coding: utf-8 -*-
"""统一工具入口：左侧菜单切换三个已有 Tkinter 功能页。"""

from __future__ import annotations

import importlib.util
import os
import sys
import tkinter as tk
import traceback
from dataclasses import dataclass
from pathlib import Path
from tkinter import scrolledtext, ttk
from typing import Dict, Optional


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PageDefinition:
    key: str
    label: str
    title: str
    subtitle: str
    module_path: Path
    class_name: str


PAGES = [
    PageDefinition(
        key="video_download",
        label="老版本视频下载",
        title="视频批量下载工具",
        subtitle="从接口任务中批量获取并下载比赛视频",
        module_path=BASE_DIR / "Generate and export video tool" / "video_downloader.py",
        class_name="VideoDownloadGUI",
    ),
    PageDefinition(
        key="adb_video_pull",
        label="立方眼视频下载",
        title="ADB 视频拉取工具",
        subtitle="按时间范围扫描设备录像目录并拉取本地",
        module_path=BASE_DIR / "New-Sport2.0-videos" / "video2.0_downloader.py",
        class_name="VideoDownloadGUI",
    ),
    PageDefinition(
        key="adb_tools",
        label="ADB 设备工具",
        title="ADB 设备工具",
        subtitle="设备管理、无线连接、日志导出、安装软件等常用 ADB 操作",
        module_path=BASE_DIR / "enerate adb using tools" / "adb_gui.py",
        class_name="ADBGUI",
    ),
]


def load_page_module(page: PageDefinition):
    module_name = f"unified_page_{page.key}"
    if module_name in sys.modules:
        return sys.modules[module_name]

    if not page.module_path.exists():
        raise FileNotFoundError(f"找不到页面文件：{page.module_path}")

    module_dir = str(page.module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    spec = importlib.util.spec_from_file_location(module_name, page.module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块：{page.module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class UnifiedToolboxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("国保的体育工具箱")
        self.root.geometry("1280x820")
        self.root.minsize(1080, 680)

        self.current_key: Optional[str] = None
        self.page_state: Dict[str, Dict[str, object]] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}

        self._configure_styles()
        self._init_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_page(PAGES[0].key)

    def _configure_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background="#f4f6f8")
        style.configure("Header.TFrame", background="#f4f6f8")
        style.configure("Content.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f4f6f8", foreground="#111827", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background="#f4f6f8", foreground="#5f6b7a", font=("Microsoft YaHei UI", 10))

    def _init_layout(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = tk.Frame(self.root, width=220, bg="#202631")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        brand = tk.Label(
            sidebar,
            text="体育工具箱",
            bg="#202631",
            fg="#f8fafc",
            font=("Microsoft YaHei UI", 16, "bold"),
            anchor="w",
            padx=18,
            pady=18,
        )
        brand.pack(fill=tk.X)

        nav = tk.Frame(sidebar, bg="#202631")
        nav.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        for page in PAGES:
            btn = tk.Button(
                nav,
                text=page.label,
                anchor="w",
                padx=14,
                pady=12,
                bd=0,
                relief=tk.FLAT,
                cursor="hand2",
                bg="#202631",
                fg="#d6dde8",
                activebackground="#2e3746",
                activeforeground="#ffffff",
                font=("Microsoft YaHei UI", 10),
                command=lambda key=page.key: self.show_page(key),
            )
            btn.pack(fill=tk.X, pady=3)
            self.nav_buttons[page.key] = btn

        exit_btn = tk.Button(
            sidebar,
            text="退出",
            anchor="w",
            padx=24,
            pady=12,
            bd=0,
            relief=tk.FLAT,
            cursor="hand2",
            bg="#202631",
            fg="#cbd5e1",
            activebackground="#2e3746",
            activeforeground="#ffffff",
            font=("Microsoft YaHei UI", 10),
            command=self.on_close,
        )
        exit_btn.pack(fill=tk.X, padx=10, pady=(0, 14))

        main = ttk.Frame(self.root, style="App.TFrame", padding=(18, 16, 18, 18))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main, style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(header, style="Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ttk.Label(header, style="Subtitle.TLabel")
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.content_body = ttk.Frame(main, style="Content.TFrame")
        self.content_body.grid(row=1, column=0, sticky="nsew")
        self.content_body.columnconfigure(0, weight=1)
        self.content_body.rowconfigure(0, weight=1)

    def show_page(self, key: str):
        page = self._get_page(key)

        for state in self.page_state.values():
            frame = state.get("frame")
            if isinstance(frame, tk.Widget):
                frame.grid_remove()

        state = self._ensure_page(page)
        frame = state["frame"]
        if isinstance(frame, tk.Widget):
            frame.grid(row=0, column=0, sticky="nsew")

        self.current_key = key
        self.title_label.config(text=page.title)
        self.subtitle_label.config(text=page.subtitle)
        self._update_nav()

    def _ensure_page(self, page: PageDefinition) -> dict[str, object]:
        if page.key in self.page_state:
            return self.page_state[page.key]

        frame = ttk.Frame(self.content_body, style="Content.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        state: Dict[str, object] = {"frame": frame, "instance": None}
        self.page_state[page.key] = state

        try:
            module = load_page_module(page)
            page_class = getattr(module, page.class_name)
            state["instance"] = page_class(frame)
        except Exception:
            self._render_load_error(frame, page)

        return state

    def _render_load_error(self, frame: ttk.Frame, page: PageDefinition):
        error_frame = ttk.Frame(frame, padding=18)
        error_frame.grid(row=0, column=0, sticky="nsew")
        error_frame.columnconfigure(0, weight=1)
        error_frame.rowconfigure(1, weight=1)

        ttk.Label(
            error_frame,
            text=f"{page.label} 加载失败",
            font=("Microsoft YaHei UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        text = scrolledtext.ScrolledText(error_frame, wrap=tk.WORD, height=10)
        text.grid(row=1, column=0, sticky="nsew")
        text.insert(tk.END, traceback.format_exc())
        text.config(state=tk.DISABLED)

    def _get_page(self, key: str) -> PageDefinition:
        for page in PAGES:
            if page.key == key:
                return page
        raise KeyError(f"未知页面：{key}")

    def _update_nav(self):
        for key, button in self.nav_buttons.items():
            if key == self.current_key:
                button.config(bg="#3b82f6", fg="#ffffff", activebackground="#2563eb")
            else:
                button.config(bg="#202631", fg="#d6dde8", activebackground="#2e3746")

    def on_close(self):
        for state in self.page_state.values():
            instance = state.get("instance")
            shutdown = getattr(instance, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    pass
        self.root.destroy()


def main():
    os.chdir(BASE_DIR)
    root = tk.Tk()
    UnifiedToolboxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
