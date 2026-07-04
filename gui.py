"""
Bilibili UID 检查器 — GUI 界面
"""

import os
import queue
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from typing import Dict, List, Optional, Tuple

import bilibili_uid_checker as core
from bilibili_uid_checker import (
    APP_DIR,
    DEFAULT_DATA_DIR,
    MIN_UID_LENGTH,
    MAX_UID_LENGTH,
    DEFAULT_MIN_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_REST_EVERY_N,
    DEFAULT_REST_MIN,
    DEFAULT_REST_MAX,
    DEFAULT_MAX_CONSECUTIVE_ERRORS,
    ABSOLUTE_MIN_DELAY,
    CheckRecord,
    CheckerConfig,
    CheckerRunner,
    CheckerStats,
    RecordStore,
    validate_config,
    ensure_chrome_debug,
    configure_storage,
    save_storage_config,
    read_storage_config,
    validate_storage_path,
    clear_storage_config,
    get_data_dir,
    get_app_icon_path,
)

FONT_UI = ("Microsoft YaHei UI", 9)
FONT_UI_BOLD = ("Microsoft YaHei UI", 9, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 11, "bold")
FONT_STAT = ("Microsoft YaHei UI", 16, "bold")
FONT_MONO = ("Consolas", 10)

COLORS = {
    "bg": "#eef1f6",
    "panel": "#ffffff",
    "accent": "#00a1d6",
    "accent_dark": "#0088b5",
    "hit_fg": "#0a7c42",
    "hit_bg": "#e3f6ec",
    "hit_alt": "#f0faf4",
    "lv0_fg": "#1565c0",
    "lv0_bg": "#e3f0fb",
    "lv0_alt": "#f0f7ff",
    "error_fg": "#c0392b",
    "error_bg": "#fdecea",
    "skip_fg": "#6c7a89",
    "skip_bg": "#f4f5f6",
    "rest_fg": "#d35400",
    "muted": "#7a8699",
    "border": "#d8dee9",
    "header_bg": "#f7f9fc",
    "row_alt": "#f8fafc",
}

STATUS_FILTER_MAP = {
    "全部": None,
    "Lv0": "lv0",
    "命中": "hit",
    "不符合": "normal",
    "跳过": "skipped",
    "访问失败": "fetch_failed",
    "解析错误": "error",
}

RECORD_TAG_MAP = {
    "hit": "hit",
    "lv0": "lv0",
    "normal": "normal",
    "skipped": "skipped",
    "fetch_failed": "error",
    "error": "error",
}

COLUMN_LABELS = {
    "seq": "序号",
    "date": "日期",
    "time": "时间",
    "uid": "UID",
    "username": "用户名",
    "level": "等级",
    "score": "乱码评分",
    "gibberish": "乱码名",
    "status": "状态",
    "detail": "判定详情",
    "link": "空间",
    "url": "空间链接",
}


def apply_window_icon(window: tk.Misc):
    icon = get_app_icon_path()
    if not icon:
        return
    try:
        window.iconbitmap(default=icon)
    except tk.TclError:
        try:
            window.iconbitmap(icon)
        except tk.TclError:
            pass


def _center_window(window: tk.Misc, width: int, height: int):
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = max((sw - width) // 2, 0)
    y = max((sh - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


class StorageSetupDialog(tk.Toplevel):
    """启动时选择数据存储目录。"""

    def __init__(
        self,
        parent: tk.Tk,
        initial_dir: str,
        *,
        required: bool = True,
        missing_path: Optional[str] = None,
    ):
        super().__init__(parent)
        self.title("选择数据存储位置")
        self.resizable(True, False)
        self.minsize(520, 260)
        self.result: Optional[str] = None
        self._required = required

        apply_window_icon(self)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="数据存储位置",
            font=FONT_TITLE,
        ).grid(row=0, column=0, sticky=tk.W)

        if missing_path:
            warn = ttk.Label(
                frame,
                text=f"之前保存的目录已不存在：\n{missing_path}\n请重新选择。",
                foreground=COLORS["error_fg"],
                font=FONT_UI,
                wraplength=460,
            )
            warn.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
            hint_row = 2
        else:
            hint_row = 1

        ttk.Label(
            frame,
            text="记录文件将保存在此目录，选择后会记住，下次启动无需重复选择。",
            foreground=COLORS["muted"],
            font=FONT_UI,
            wraplength=460,
        ).grid(row=hint_row, column=0, sticky=tk.W, pady=(8, 12))

        path_row = hint_row + 1
        path_wrap = ttk.LabelFrame(frame, text="目录路径", padding=(10, 8))
        path_wrap.grid(row=path_row, column=0, sticky=tk.EW, pady=(0, 14))
        path_wrap.columnconfigure(0, weight=1)

        self.path_var = tk.StringVar(value=initial_dir)
        entry = ttk.Entry(path_wrap, textvariable=self.path_var, font=FONT_UI)
        entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(path_wrap, text="浏览…", command=self._browse).grid(row=0, column=1)

        btn_row = path_row + 1
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=btn_row, column=0, sticky=tk.E)
        if not required:
            ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(btn_frame, text="确定并保存", command=self._confirm, style="Accent.TButton").pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Return>", lambda e: self._confirm())
        entry.focus_set()
        entry.select_range(0, tk.END)

        _center_window(self, 540, 280)
        self.lift(parent)
        self.attributes("-topmost", True)
        self.update()
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _browse(self):
        folder = filedialog.askdirectory(
            title="选择数据存储目录",
            initialdir=self.path_var.get() or APP_DIR,
            parent=self,
        )
        if folder:
            self.path_var.set(folder)

    def _confirm(self):
        path = self.path_var.get().strip()
        valid, err = validate_storage_path(path)
        if not valid:
            messagebox.showerror("目录无效", err, parent=self)
            return
        self.result = os.path.normpath(os.path.abspath(path))
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()

    def _on_close(self):
        if self._required:
            if not messagebox.askyesno(
                "确认退出",
                "未选择存储目录，程序将退出。是否退出？",
                parent=self,
            ):
                return
        self._cancel()


class CheckerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bilibili UID 检查器")
        self.root.minsize(1024, 720)
        self.root.geometry("1180x820")
        self.root.configure(bg=COLORS["bg"])
        apply_window_icon(self.root)

        self.runner: Optional[CheckerRunner] = None
        self.config_frame: Optional[ttk.LabelFrame] = None
        self.safety_frame: Optional[ttk.LabelFrame] = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.record_queue: queue.Queue[CheckRecord] = queue.Queue()
        self.display_records: List[CheckRecord] = []
        self.lv0_records: List[CheckRecord] = []
        self.hit_records: List[CheckRecord] = []
        self._copy_hint_after: Optional[str] = None
        self.lv0_newest_first = tk.BooleanVar(value=True)
        self.hit_newest_first = tk.BooleanVar(value=True)
        self.all_newest_first = tk.BooleanVar(value=True)

        self._setup_styles()
        self._build_menubar()
        self._build_ui()
        self.root.update_idletasks()
        self._poll_queues()
        self.root.after(10, self._load_history_records)
        self.root.after(1200, self._start_chrome_background)

    def _start_chrome_background(self):
        threading.Thread(target=self._auto_start_chrome, daemon=True).start()

    def _auto_start_chrome(self):
        ok, err = ensure_chrome_debug(on_log=lambda msg: self.log_queue.put(msg))
        if not ok:
            self.log_queue.put(f"Chrome 自动启动失败: {err}")

    def _setup_styles(self):
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Header.TFrame", background=COLORS["header_bg"])
        style.configure("TLabelframe", background=COLORS["panel"], borderwidth=1, relief="solid")
        style.configure(
            "TLabelframe.Label",
            background=COLORS["panel"],
            foreground=COLORS["accent_dark"],
            font=FONT_UI_BOLD,
        )
        style.configure("TLabel", background=COLORS["bg"])
        style.configure("Panel.TLabel", background=COLORS["panel"])
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONT_UI)
        style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=FONT_UI)
        style.configure("Title.TLabel", background=COLORS["header_bg"], font=FONT_TITLE, foreground="#1a1a2e")
        style.configure("SubTitle.TLabel", background=COLORS["header_bg"], foreground=COLORS["muted"], font=FONT_UI)
        style.configure(
            "Card.TFrame",
            background=COLORS["panel"],
            relief="solid",
            borderwidth=1,
        )
        style.configure("CardTitle.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=FONT_UI)
        style.configure("CardValue.TLabel", background=COLORS["panel"], font=FONT_STAT)
        style.configure("StatusBar.TLabel", background=COLORS["header_bg"], foreground=COLORS["muted"], font=FONT_UI)
        style.configure("CopyHint.TLabel", background=COLORS["header_bg"], foreground=COLORS["accent"], font=FONT_UI)
        style.configure("Rest.TLabel", background=COLORS["bg"], foreground=COLORS["rest_fg"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Accent.TButton", font=FONT_UI_BOLD)
        style.configure("Treeview", rowheight=30, font=FONT_UI, background=COLORS["panel"])
        style.configure("Treeview.Heading", font=FONT_UI_BOLD, background=COLORS["header_bg"])
        style.map("Treeview", background=[("selected", "#cce8f4")], foreground=[("selected", "#1a1a2e")])

    def _build_menubar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开 lv0.json", command=lambda: self._open_file(core.LV0_FILE))
        file_menu.add_command(label="打开 hits.json", command=lambda: self._open_file(core.HITS_FILE))
        file_menu.add_command(label="打开 records.json", command=lambda: self._open_file(core.RECORDS_FILE))
        file_menu.add_command(label="打开 lv0.txt", command=lambda: self._open_file(core.LV0_OUTPUT_FILE))
        file_menu.add_command(label="打开 result.txt", command=lambda: self._open_file(core.OUTPUT_FILE))
        file_menu.add_separator()
        file_menu.add_command(label="更改数据存储位置…", command=self._change_storage_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.destroy)

        lv0_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Lv0 账号", menu=lv0_menu)
        lv0_menu.add_command(label="显示 Lv0 列表", command=self._show_lv0_tab)
        lv0_menu.add_command(label="刷新 Lv0 列表", command=self._reload_lv0_records)
        lv0_menu.add_separator()
        lv0_menu.add_command(label="复制全部 UID", command=self._copy_all_lv0_uids)
        lv0_menu.add_command(label="复制 UID + 用户名", command=self._copy_lv0_uid_names)
        lv0_menu.add_command(label="导出 Lv0 列表为文本…", command=self._export_lv0_txt)
        lv0_menu.add_separator()
        lv0_menu.add_command(label="在浏览器打开选中账号", command=lambda: self._open_selected_in_browser(self.lv0_tree, self.lv0_records))
        lv0_menu.add_command(label="打开 lv0.json", command=lambda: self._open_file(core.LV0_FILE))

        hit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="命中账号", menu=hit_menu)
        hit_menu.add_command(label="显示命中列表", command=self._show_hit_tab)
        hit_menu.add_command(label="刷新命中列表", command=self._reload_hit_records)
        hit_menu.add_separator()
        hit_menu.add_command(label="复制全部 UID", command=self._copy_all_hit_uids)
        hit_menu.add_command(label="复制 UID + 用户名", command=self._copy_hit_uid_names)
        hit_menu.add_command(label="导出命中列表为文本…", command=self._export_hit_txt)
        hit_menu.add_separator()
        hit_menu.add_command(label="在浏览器打开选中账号", command=lambda: self._open_selected_in_browser(self.hit_tree, self.hit_records))
        hit_menu.add_command(label="打开 hits.json", command=lambda: self._open_file(core.HITS_FILE))

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="查看", menu=view_menu)
        view_menu.add_command(label="Lv0 账号", command=self._show_lv0_tab)
        view_menu.add_command(label="命中账号", command=self._show_hit_tab)
        view_menu.add_command(label="全部记录", command=self._show_all_tab)
        view_menu.add_command(label="运行日志", command=self._show_log_tab)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self._show_help)

    def _build_ui(self):
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=(12, 10, 12, 8))
        root_frame.pack(fill=tk.BOTH, expand=True)
        root_frame.rowconfigure(2, weight=1)
        root_frame.columnconfigure(0, weight=1)

        self._build_header(root_frame)
        self._build_config_row(root_frame)
        self._build_toolbar_stats(root_frame)
        self._build_notebook(root_frame)
        self._build_status_bar(root_frame)

        self._append_log("就绪。程序将自动启动 Chrome，无需手动配置。")
        self._append_log(f"数据目录: {get_data_dir()}")
        self._append_log(f"Lv0 数据: {core.LV0_FILE} | 命中数据: {core.HITS_FILE}")

    def _update_data_dir_label(self):
        self.data_dir_label.config(text=f"数据存储: {get_data_dir()}")

    def _change_storage_dir(self):
        if self.runner and self.runner.is_running:
            messagebox.showwarning("提示", "请先停止检查，再更改存储目录。")
            return
        saved_path, _ = read_storage_config()
        dlg = StorageSetupDialog(
            self.root,
            get_data_dir(),
            required=False,
            missing_path=saved_path if saved_path and not os.path.isdir(saved_path) else None,
        )
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        try:
            configure_storage(dlg.result)
        except ValueError as e:
            messagebox.showerror("错误", str(e))
            return
        save_storage_config(dlg.result)
        self._update_data_dir_label()
        self._load_history_records()
        self._append_log(f"已切换数据目录: {dlg.result}")

    def _build_header(self, parent):
        header = ttk.Frame(parent, style="Header.TFrame", padding=(12, 10))
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Bilibili UID 检查器", style="Title.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(
            header,
            text="双击 exe 即可使用 · 程序会自动启动 Chrome · Lv0 与命中分开记录",
            style="SubTitle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        self.data_dir_label = ttk.Label(
            header,
            text="",
            style="SubTitle.TLabel",
            foreground=COLORS["lv0_fg"],
        )
        self.data_dir_label.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))
        ttk.Button(
            header,
            text="更改",
            command=self._change_storage_dir,
            width=6,
        ).grid(row=2, column=1, sticky=tk.E, padx=(8, 0))
        self._update_data_dir_label()

    def _build_config_row(self, parent):
        config_row = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        config_row.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))

        self.config_frame = ttk.LabelFrame(config_row, text="基础配置", padding=(12, 10))
        self.safety_frame = ttk.LabelFrame(config_row, text="安全限速 · 防封禁", padding=(12, 10))
        config_row.add(self.config_frame, weight=3)
        config_row.add(self.safety_frame, weight=2)

        self._build_basic_config(self.config_frame)
        self._build_safety_config(self.safety_frame)

    def _build_basic_config(self, cfg):
        cfg.columnconfigure(1, weight=1)

        fields = [
            ("UID 前缀", "prefix_var", "5", "纯数字，不以 0 开头"),
            ("UID 总长度", "length_var", "7", f"{MIN_UID_LENGTH}~{MAX_UID_LENGTH} 位"),
            ("运行时长(分)", "time_limit_var", "0", "0 = 不限"),
            ("最大检查数", "max_checks_var", "0", "0 = 不限，建议 ≤500"),
        ]
        for row, (label, attr, default, hint) in enumerate(fields):
            ttk.Label(cfg, text=label, style="Panel.TLabel").grid(
                row=row, column=0, sticky=tk.W, padx=(0, 10), pady=3
            )
            setattr(self, attr, tk.StringVar(value=default))
            ttk.Entry(cfg, textvariable=getattr(self, attr), width=12).grid(
                row=row, column=1, sticky=tk.W, pady=3
            )
            ttk.Label(cfg, text=hint, style="PanelMuted.TLabel").grid(
                row=row, column=2, sticky=tk.W, padx=(10, 0), pady=3
            )

        ttk.Label(cfg, text="请求间隔(秒)", style="Panel.TLabel").grid(row=4, column=0, sticky=tk.W, pady=3)
        interval_frame = ttk.Frame(cfg, style="Panel.TFrame")
        interval_frame.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=3)
        self.min_delay_var = tk.StringVar(value=str(DEFAULT_MIN_DELAY))
        self.max_delay_var = tk.StringVar(value=str(DEFAULT_MAX_DELAY))
        ttk.Entry(interval_frame, textvariable=self.min_delay_var, width=7).pack(side=tk.LEFT)
        ttk.Label(interval_frame, text=" ~ ", style="Panel.TLabel").pack(side=tk.LEFT)
        ttk.Entry(interval_frame, textvariable=self.max_delay_var, width=7).pack(side=tk.LEFT)
        ttk.Label(
            interval_frame,
            text=f"  最低 {ABSOLUTE_MIN_DELAY}s",
            style="PanelMuted.TLabel",
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _build_safety_config(self, saf):
        saf.columnconfigure(1, weight=1)

        safety_fields = [
            ("每 N 次休息", "rest_every_var", str(DEFAULT_REST_EVERY_N), "0 = 关闭"),
            ("休息最短(秒)", "rest_min_var", str(int(DEFAULT_REST_MIN)), ""),
            ("休息最长(秒)", "rest_max_var", str(int(DEFAULT_REST_MAX)), ""),
            ("连续错误阈值", "max_consec_errors_var", str(DEFAULT_MAX_CONSECUTIVE_ERRORS), "触发长休息"),
            ("长休息(秒)", "long_rest_var", "180", "连续错误后冷却"),
        ]
        for row, (label, attr, default, hint) in enumerate(safety_fields):
            ttk.Label(saf, text=label, style="Panel.TLabel").grid(
                row=row, column=0, sticky=tk.W, padx=(0, 10), pady=3
            )
            setattr(self, attr, tk.StringVar(value=default))
            ttk.Entry(saf, textvariable=getattr(self, attr), width=10).grid(
                row=row, column=1, sticky=tk.W, pady=3
            )
            if hint:
                ttk.Label(saf, text=hint, style="PanelMuted.TLabel").grid(
                    row=row, column=2, sticky=tk.W, padx=(10, 0), pady=3
                )

    def _build_toolbar_stats(self, parent):
        block = ttk.Frame(parent, style="App.TFrame")
        block.grid(row=2, column=0, sticky=tk.NSEW, pady=(0, 8))
        block.rowconfigure(2, weight=0)
        block.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(block, style="App.TFrame")
        toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))

        self.start_btn = ttk.Button(toolbar, text="▶ 开始检查", style="Accent.TButton", command=self._on_start)
        self.start_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(toolbar, text="■ 停止", command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=2)
        ttk.Button(toolbar, text="Lv0 列表", command=self._show_lv0_tab).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="命中列表", command=self._show_hit_tab).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="刷新", command=self._reload_all_lists).pack(side=tk.LEFT, padx=(6, 0))

        stats_frame = ttk.Frame(block, style="App.TFrame")
        stats_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        self.stat_value_labels: Dict[str, ttk.Label] = {}
        stat_defs = [
            ("checked", "已检查", COLORS["accent"]),
            ("lv0", "Lv0 账号", COLORS["lv0_fg"]),
            ("found", "命中账号", COLORS["hit_fg"]),
            ("skipped", "跳过", COLORS["skip_fg"]),
            ("errors", "错误", COLORS["error_fg"]),
            ("elapsed", "已运行", "#2c3e50"),
        ]
        for i, (key, title, color) in enumerate(stat_defs):
            card = ttk.Frame(stats_frame, style="Card.TFrame", padding=(12, 8))
            card.grid(row=0, column=i, padx=(0 if i == 0 else 6, 0), sticky=tk.NSEW)
            stats_frame.columnconfigure(i, weight=1)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor=tk.W)
            val = ttk.Label(card, text="—", style="CardValue.TLabel", foreground=color)
            val.pack(anchor=tk.W, pady=(2, 0))
            self.stat_value_labels[key] = val

        progress_row = ttk.Frame(block, style="App.TFrame")
        progress_row.grid(row=2, column=0, sticky=tk.EW)
        progress_row.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky=tk.EW)
        self.rest_status_label = ttk.Label(progress_row, text="", style="Rest.TLabel")
        self.rest_status_label.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))

        parent.rowconfigure(2, weight=0)

    def _build_notebook(self, parent):
        notebook_wrap = ttk.Frame(parent, style="App.TFrame")
        notebook_wrap.grid(row=3, column=0, sticky=tk.NSEW)
        notebook_wrap.rowconfigure(0, weight=1)
        notebook_wrap.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        notebook = ttk.Notebook(notebook_wrap)
        notebook.grid(row=0, column=0, sticky=tk.NSEW)
        self.notebook = notebook

        lv0_tab = ttk.Frame(notebook, padding=8)
        notebook.add(lv0_tab, text="  Lv0 账号  ")
        self._build_lv0_tab(lv0_tab)

        hit_tab = ttk.Frame(notebook, padding=8)
        notebook.add(hit_tab, text="  ★ 命中账号  ")
        self._build_hit_tab(hit_tab)

        all_tab = ttk.Frame(notebook, padding=8)
        notebook.add(all_tab, text="  全部记录  ")
        self._build_all_tab(all_tab)

        log_tab = ttk.Frame(notebook, padding=8)
        notebook.add(log_tab, text="  运行日志  ")
        self._build_log_tab(log_tab)

    def _build_lv0_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent, style="App.TFrame")
        toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="搜索", style="Muted.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.lv0_search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.lv0_search_var, width=22).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 12)
        )
        self.lv0_search_var.trace_add("write", lambda *_: self._refresh_lv0_table(scroll_to_end=False))

        ttk.Checkbutton(
            toolbar,
            text="最新优先",
            variable=self.lv0_newest_first,
            command=lambda: self._refresh_lv0_table(scroll_to_end=False),
        ).grid(row=0, column=2, sticky=tk.W, padx=(0, 12))

        ttk.Button(toolbar, text="复制 UID", command=self._copy_all_lv0_uids).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(toolbar, text="复制 UID+名", command=self._copy_lv0_uid_names).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(
            toolbar,
            text="浏览器打开",
            command=lambda: self._open_selected_in_browser(self.lv0_tree, self.lv0_records),
        ).grid(row=0, column=5, padx=(0, 12))

        self.lv0_count_label = ttk.Label(
            toolbar,
            text="共 0 个",
            foreground=COLORS["lv0_fg"],
            font=FONT_UI_BOLD,
            background=COLORS["bg"],
        )
        self.lv0_count_label.grid(row=0, column=6, sticky=tk.E)

        lv0_columns = ("seq", "date", "time", "uid", "username", "gibberish", "link")
        self.lv0_tree, _ = self._create_tree(
            parent,
            lv0_columns,
            [
                ("seq", "#", 42, False),
                ("date", "日期", 96, False),
                ("time", "时间", 72, False),
                ("uid", "UID", 88, False),
                ("username", "用户名", 160, True),
                ("gibberish", "乱码名", 56, False),
                ("link", "空间", 56, False),
            ],
            grid_row=1,
            tag_styles=[
                ("lv0", COLORS["lv0_fg"], COLORS["lv0_bg"]),
                ("lv0_alt", COLORS["lv0_fg"], COLORS["lv0_alt"]),
            ],
        )
        self.lv0_tree.bind("<Double-1>", lambda e: self._open_selected_in_browser(self.lv0_tree, self.lv0_records))

        hint = ttk.Label(
            parent,
            text="所有 Lv0 账号（不限用户名）· 保存于 lv0.json · 双击行打开空间",
            style="Muted.TLabel",
        )
        hint.grid(row=2, column=0, sticky=tk.W, pady=(6, 0))

    def _build_hit_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent, style="App.TFrame")
        toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="搜索", style="Muted.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.hit_search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.hit_search_var, width=22).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 12)
        )
        self.hit_search_var.trace_add("write", lambda *_: self._refresh_hit_table(scroll_to_end=False))

        ttk.Checkbutton(
            toolbar,
            text="最新优先",
            variable=self.hit_newest_first,
            command=lambda: self._refresh_hit_table(scroll_to_end=False),
        ).grid(row=0, column=2, sticky=tk.W, padx=(0, 12))

        ttk.Button(toolbar, text="复制 UID", command=self._copy_all_hit_uids).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(toolbar, text="复制 UID+名", command=self._copy_hit_uid_names).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(
            toolbar,
            text="浏览器打开",
            command=lambda: self._open_selected_in_browser(self.hit_tree, self.hit_records),
        ).grid(row=0, column=5, padx=(0, 12))

        self.hit_count_label = ttk.Label(
            toolbar,
            text="共 0 个",
            foreground=COLORS["hit_fg"],
            font=FONT_UI_BOLD,
            background=COLORS["bg"],
        )
        self.hit_count_label.grid(row=0, column=6, sticky=tk.E)

        hit_columns = ("seq", "date", "time", "uid", "username", "score", "detail", "link")
        self.hit_tree, _ = self._create_tree(
            parent,
            hit_columns,
            [
                ("seq", "#", 42, False),
                ("date", "日期", 96, False),
                ("time", "时间", 72, False),
                ("uid", "UID", 88, False),
                ("username", "用户名", 140, True),
                ("score", "评分", 52, False),
                ("detail", "判定详情", 220, True),
                ("link", "空间", 56, False),
            ],
            grid_row=1,
            tag_styles=[
                ("hit", COLORS["hit_fg"], COLORS["hit_bg"]),
                ("hit_alt", COLORS["hit_fg"], COLORS["hit_alt"]),
            ],
        )
        self.hit_tree.bind("<Double-1>", lambda e: self._open_selected_in_browser(self.hit_tree, self.hit_records))

        hint = ttk.Label(
            parent,
            text="乱码英文名 + Lv0 · 保存于 hits.json · 双击行打开空间",
            style="Muted.TLabel",
        )
        hint.grid(row=2, column=0, sticky=tk.W, pady=(6, 0))

    def _build_all_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent, style="App.TFrame")
        toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        toolbar.columnconfigure(3, weight=1)

        ttk.Label(toolbar, text="状态", style="Muted.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.filter_var = tk.StringVar(value="全部")
        ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=list(STATUS_FILTER_MAP.keys()),
            state="readonly",
            width=11,
        ).grid(row=0, column=1, sticky=tk.W, padx=(8, 16))
        self.filter_var.trace_add("write", lambda *_: self._refresh_all_table(scroll_to_end=False))

        ttk.Label(toolbar, text="搜索", style="Muted.TLabel").grid(row=0, column=2, sticky=tk.W)
        self.all_search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.all_search_var, width=24).grid(
            row=0, column=3, sticky=tk.EW, padx=(8, 12)
        )
        self.all_search_var.trace_add("write", lambda *_: self._refresh_all_table(scroll_to_end=False))

        ttk.Checkbutton(
            toolbar,
            text="最新优先",
            variable=self.all_newest_first,
            command=lambda: self._refresh_all_table(scroll_to_end=False),
        ).grid(row=0, column=4, sticky=tk.W, padx=(0, 8))

        ttk.Button(toolbar, text="清空筛选", command=self._clear_all_filters).grid(row=0, column=5)

        self.record_count_label = ttk.Label(
            toolbar, text="共 0 条", foreground=COLORS["muted"], background=COLORS["bg"], font=FONT_UI
        )
        self.record_count_label.grid(row=0, column=6, sticky=tk.E, padx=(12, 0))

        all_columns = ("seq", "date", "time", "uid", "username", "level", "score", "status", "detail")
        self.all_tree, _ = self._create_tree(
            parent,
            all_columns,
            [
                ("seq", "#", 42, False),
                ("date", "日期", 96, False),
                ("time", "时间", 72, False),
                ("uid", "UID", 88, False),
                ("username", "用户名", 120, True),
                ("level", "等级", 52, False),
                ("score", "评分", 52, False),
                ("status", "状态", 76, False),
                ("detail", "详情", 220, True),
            ],
            grid_row=1,
        )

    def _build_log_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        log_toolbar = ttk.Frame(parent, style="App.TFrame")
        log_toolbar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 6))
        ttk.Label(log_toolbar, text="实时运行输出", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Button(log_toolbar, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT)

        log_frame = ttk.Frame(parent, style="Panel.TFrame")
        log_frame.grid(row=1, column=0, sticky=tk.NSEW)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=FONT_MONO,
            state=tk.DISABLED,
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW, padx=1, pady=1)
        for tag, color in [
            ("hit", "#6a9955"),
            ("error", "#f44747"),
            ("warn", "#dcdcaa"),
            ("rest", "#ce9178"),
        ]:
            self.log_text.tag_configure(tag, foreground=color)

    def _build_status_bar(self, parent):
        bar = ttk.Frame(parent, style="Header.TFrame", padding=(10, 6))
        bar.grid(row=4, column=0, sticky=tk.EW, pady=(6, 0))

        self.copy_hint_label = ttk.Label(
            bar,
            text="提示：单击表格单元格复制 · 双击行打开 B 站空间",
            style="StatusBar.TLabel",
        )
        self.copy_hint_label.pack(side=tk.LEFT)

    def _create_tree(
        self,
        parent,
        columns: Tuple[str, ...],
        col_config: List[Tuple[str, str, int, bool]],
        grid_row: int = 0,
        tag_styles: Optional[List[Tuple[str, str, str]]] = None,
    ):
        wrap = ttk.Frame(parent, style="Panel.TFrame")
        wrap.grid(row=grid_row, column=0, sticky=tk.NSEW)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")
        for col, heading, width, stretch in col_config:
            tree.heading(col, text=heading, anchor=tk.CENTER if col == "seq" else tk.W)
            anchor = tk.CENTER if col in (
                "seq", "uid", "level", "score", "status", "link", "date", "time", "gibberish"
            ) else tk.W
            tree.column(col, width=width, anchor=anchor, minwidth=40, stretch=stretch)

        sy = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=tree.yview)
        sx = ttk.Scrollbar(wrap, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tree.grid(row=0, column=0, sticky=tk.NSEW)
        sy.grid(row=0, column=1, sticky=tk.NS)
        sx.grid(row=1, column=0, sticky=tk.EW)

        tag_styles = tag_styles or [
            ("hit", COLORS["hit_fg"], COLORS["hit_bg"]),
            ("hit_alt", COLORS["hit_fg"], COLORS["hit_alt"]),
            ("lv0", COLORS["lv0_fg"], COLORS["lv0_bg"]),
            ("lv0_alt", COLORS["lv0_fg"], COLORS["lv0_alt"]),
            ("normal", "#2c3e50", COLORS["panel"]),
            ("normal_alt", "#2c3e50", COLORS["row_alt"]),
            ("skipped", COLORS["skip_fg"], COLORS["skip_bg"]),
            ("skipped_alt", COLORS["skip_fg"], COLORS["row_alt"]),
            ("error", COLORS["error_fg"], COLORS["error_bg"]),
            ("error_alt", COLORS["error_fg"], "#fff5f5"),
        ]
        for tag, fg, bg in tag_styles:
            tree.tag_configure(tag, foreground=fg, background=bg)

        tree.bind("<ButtonRelease-1>", lambda e, t=tree, c=columns: self._on_tree_cell_click(e, t, c))
        return tree, wrap

    @staticmethod
    def _split_datetime(record: CheckRecord) -> Tuple[str, str]:
        full = (record.checked_at or record.timestamp or "").strip()
        if " " in full:
            date_part, time_part = full.split(" ", 1)
            return date_part, time_part[:8]
        if ":" in full and len(full) <= 8:
            return "—", full
        return full or "—", "—"

    @staticmethod
    def _dedupe_by_uid(records: List[CheckRecord]) -> List[CheckRecord]:
        by_uid: dict = {}
        for r in records:
            by_uid[r.uid] = r
        return list(by_uid.values())

    @staticmethod
    def _lv0_values(record: CheckRecord, seq: int) -> tuple:
        date, time_part = CheckerApp._split_datetime(record)
        gibberish = "是" if record.is_gibberish else "否"
        return (seq, date, time_part, record.uid, record.username, gibberish, "打开")

    @staticmethod
    def _hit_values(record: CheckRecord, seq: int) -> tuple:
        date, time_part = CheckerApp._split_datetime(record)
        detail = record.message or "乱码名+Lv0"
        score = f"{record.match_score:.0f}" if record.match_score else "—"
        return (seq, date, time_part, record.uid, record.username, score, detail, "打开")

    @staticmethod
    def _all_values(record: CheckRecord, seq: int) -> tuple:
        date, time_part = CheckerApp._split_datetime(record)
        score = f"{record.match_score:.0f}" if record.match_score else "—"
        detail = record.message or ("乱码名+Lv0" if record.status == "hit" else "")
        return (
            seq,
            date,
            time_part,
            record.uid,
            record.username,
            record.level_text,
            score,
            record.status_label,
            detail,
        )

    def _match_search(self, record: CheckRecord, keyword: str) -> bool:
        if not keyword:
            return True
        key = keyword.strip().lower()
        haystack = f"{record.uid} {record.username} {record.message}".lower()
        return key in haystack

    def _ordered_records(self, records: List[CheckRecord], newest_first: bool) -> List[CheckRecord]:
        if newest_first:
            return list(reversed(records))
        return records

    def _tag_for_row(self, base_tag: str, index: int) -> str:
        alt = f"{base_tag}_alt" if index % 2 else base_tag
        known = {
            "hit_alt", "lv0_alt", "normal_alt", "skipped_alt", "error_alt",
            "hit", "lv0", "normal", "skipped", "error",
        }
        return alt if alt in known else base_tag

    def _load_history_records(self):
        self.lv0_records = self._dedupe_by_uid(RecordStore.load_lv0())
        self.hit_records = self._dedupe_by_uid(RecordStore.load_hits())
        self.display_records = RecordStore.load_recent(limit=500)
        self._refresh_lv0_table(scroll_to_end=False)
        self._refresh_hit_table(scroll_to_end=False)
        self._refresh_all_table(scroll_to_end=False)
        if self.lv0_records:
            self._append_log(f"已加载 {len(self.lv0_records)} 个 Lv0 账号。")
        if self.hit_records:
            self._append_log(f"已加载 {len(self.hit_records)} 个命中账号。")

    def _reload_lv0_records(self):
        self.lv0_records = self._dedupe_by_uid(RecordStore.load_lv0())
        self._refresh_lv0_table(scroll_to_end=False)
        self._append_log(f"已刷新 Lv0 列表，共 {len(self.lv0_records)} 个账号。", tag="rest")
        self._show_copy_hint(f"Lv0 列表已刷新，共 {len(self.lv0_records)} 个")

    def _reload_hit_records(self):
        self.hit_records = self._dedupe_by_uid(RecordStore.load_hits())
        self._refresh_hit_table(scroll_to_end=False)
        self._append_log(f"已刷新命中列表，共 {len(self.hit_records)} 个账号。", tag="hit")
        self._show_copy_hint(f"命中列表已刷新，共 {len(self.hit_records)} 个")

    def _reload_all_lists(self):
        self._reload_lv0_records()
        self._reload_hit_records()

    def _refresh_lv0_table(self, scroll_to_end: bool = True):
        keyword = self.lv0_search_var.get().strip().lower() if hasattr(self, "lv0_search_var") else ""
        records = [r for r in self.lv0_records if self._match_search(r, keyword)]
        records = self._ordered_records(records, self.lv0_newest_first.get())

        for item in self.lv0_tree.get_children():
            self.lv0_tree.delete(item)

        first = last = None
        for seq, rec in enumerate(records, 1):
            tag = self._tag_for_row("lv0", seq)
            iid = self.lv0_tree.insert("", tk.END, values=self._lv0_values(rec, seq), tags=(tag,))
            if first is None:
                first = iid
            last = iid

        total = len(self.lv0_records)
        shown = len(records)
        self.lv0_count_label.config(
            text=f"显示 {shown} / 共 {total} 个" if keyword else f"共 {total} 个 Lv0"
        )
        target = last if scroll_to_end else first
        if target:
            self.lv0_tree.see(target)

    def _refresh_hit_table(self, scroll_to_end: bool = True):
        keyword = self.hit_search_var.get().strip().lower() if hasattr(self, "hit_search_var") else ""
        records = [r for r in self.hit_records if self._match_search(r, keyword)]
        records = self._ordered_records(records, self.hit_newest_first.get())

        for item in self.hit_tree.get_children():
            self.hit_tree.delete(item)

        first = last = None
        for seq, rec in enumerate(records, 1):
            tag = self._tag_for_row("hit", seq)
            iid = self.hit_tree.insert("", tk.END, values=self._hit_values(rec, seq), tags=(tag,))
            if first is None:
                first = iid
            last = iid

        total = len(self.hit_records)
        shown = len(records)
        self.hit_count_label.config(
            text=f"显示 {shown} / 共 {total} 个" if keyword else f"共 {total} 个命中"
        )
        target = last if scroll_to_end else first
        if target:
            self.hit_tree.see(target)

    def _refresh_all_table(self, scroll_to_end: bool = True):
        filt = STATUS_FILTER_MAP.get(self.filter_var.get())
        keyword = self.all_search_var.get().strip().lower() if hasattr(self, "all_search_var") else ""

        records = []
        for rec in self.display_records:
            if filt and rec.status != filt:
                continue
            if not self._match_search(rec, keyword):
                continue
            records.append(rec)

        records = self._ordered_records(records, self.all_newest_first.get())

        for item in self.all_tree.get_children():
            self.all_tree.delete(item)

        first = last = None
        for seq, rec in enumerate(records, 1):
            base_tag = RECORD_TAG_MAP.get(rec.status, "normal")
            tag = self._tag_for_row(base_tag, seq)
            iid = self.all_tree.insert("", tk.END, values=self._all_values(rec, seq), tags=(tag,))
            if first is None:
                first = iid
            last = iid

        visible = len(records)
        self.record_count_label.config(
            text=f"显示 {visible} / 共 {len(self.display_records)} 条"
        )
        target = last if scroll_to_end else first
        if target:
            self.all_tree.see(target)

    def _clear_all_filters(self):
        self.filter_var.set("全部")
        self.all_search_var.set("")
        self._refresh_all_table(scroll_to_end=False)

    def _show_lv0_tab(self):
        self.notebook.select(0)

    def _show_hit_tab(self):
        self.notebook.select(1)

    def _show_all_tab(self):
        self.notebook.select(2)

    def _show_log_tab(self):
        self.notebook.select(3)

    def _show_help(self):
        messagebox.showinfo(
            "使用说明",
            "1. 配置 UID 前缀与长度，点击「开始检查」\n"
            "2. 程序会自动启动 Chrome，无需手动配置\n"
            "3. 所有 Lv0 账号记录到 lv0.json / lv0.txt\n"
            "4. 乱码名+Lv0 命中账号记录到 hits.json / result.txt\n"
            "5. 菜单「文件」可更改数据存储位置",
        )

    def _get_uid_from_tree(self, tree: ttk.Treeview) -> Optional[int]:
        sel = tree.selection()
        if not sel:
            return None
        values = tree.item(sel[0], "values")
        if len(values) < 4:
            return None
        try:
            uid_idx = list(tree["columns"]).index("uid")
            return int(values[uid_idx])
        except (ValueError, IndexError, TypeError):
            try:
                return int(values[3])
            except (TypeError, ValueError):
                return None

    def _open_selected_in_browser(self, tree: ttk.Treeview, records: List[CheckRecord]):
        uid = self._get_uid_from_tree(tree)
        if uid is None:
            messagebox.showinfo("提示", "请先在列表中选中一行。")
            return
        webbrowser.open(f"https://space.bilibili.com/{uid}")
        self._show_copy_hint(f"已在浏览器打开 UID {uid}")

    def _parse_config(self) -> Optional[CheckerConfig]:
        try:
            config = CheckerConfig(
                uid_prefix=self.prefix_var.get().strip(),
                uid_length=int(self.length_var.get().strip()),
                time_limit_minutes=float(self.time_limit_var.get().strip() or "0"),
                min_delay=float(self.min_delay_var.get().strip()),
                max_delay=float(self.max_delay_var.get().strip()),
                max_checks=int(self.max_checks_var.get().strip() or "0"),
                rest_every_n=int(self.rest_every_var.get().strip() or "0"),
                rest_min_seconds=float(self.rest_min_var.get().strip()),
                rest_max_seconds=float(self.rest_max_var.get().strip()),
                max_consecutive_errors=int(self.max_consec_errors_var.get().strip()),
                long_rest_seconds=float(self.long_rest_var.get().strip()),
            )
        except ValueError:
            messagebox.showerror("配置错误", "请检查所有数字字段是否有效。")
            return None
        valid, err = validate_config(config)
        if not valid:
            messagebox.showerror("配置错误", err)
            return None
        return config

    def _on_start(self):
        if self.runner and self.runner.is_running:
            return
        config = self._parse_config()
        if not config:
            return
        self._set_running(True)
        self.progress["value"] = 0
        self._update_stats_display(CheckerStats(), 0, config.time_limit_minutes)
        self._append_log("—" * 36)
        self._append_log("开始检查（已启用休息与限速）", tag="rest")
        self.runner = CheckerRunner(
            config,
            on_log=lambda msg: self.log_queue.put(msg),
            on_stats=lambda s, e: self.root.after(
                0, lambda: self._update_stats_display(s, e, config.time_limit_minutes)
            ),
            on_record=lambda r: self.record_queue.put(r),
        )
        self.runner.start()
        self._watch_runner()

    def _on_stop(self):
        if self.runner:
            self.runner.request_stop()
            self._append_log("正在停止...", tag="warn")

    def _watch_runner(self):
        if self.runner and self.runner.is_running:
            self.root.after(300, self._watch_runner)
        else:
            self._set_running(False)

    def _set_running(self, running: bool):
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        for frame in (self.config_frame, self.safety_frame):
            if frame:
                self._set_frame_state(frame, running)

    def _set_frame_state(self, widget, running: bool):
        if isinstance(widget, (ttk.Entry, ttk.Spinbox)):
            widget.config(state=tk.DISABLED if running else tk.NORMAL)
        for child in widget.winfo_children():
            self._set_frame_state(child, running)

    def _update_stats_display(self, stats: CheckerStats, elapsed: float, time_limit: float):
        self.stat_value_labels["checked"].config(text=str(stats.checked))
        self.stat_value_labels["lv0"].config(text=str(stats.lv0_found))
        self.stat_value_labels["found"].config(text=str(stats.found))
        self.stat_value_labels["skipped"].config(text=str(stats.skipped))
        self.stat_value_labels["errors"].config(text=str(stats.errors))
        self.stat_value_labels["elapsed"].config(text=self._fmt_time(elapsed))
        limit_sec = time_limit * 60 if time_limit > 0 else 0
        if limit_sec > 0:
            self.progress["value"] = min(100, elapsed / limit_sec * 100)
        else:
            self.progress["value"] = 0
        if stats.resting:
            self.rest_status_label.config(
                text=f"⏸ {stats.rest_message} — 剩余 {int(stats.rest_remaining)} 秒（请勿关闭）"
            )
        else:
            self.rest_status_label.config(text="")

    @staticmethod
    def _fmt_time(sec: float) -> str:
        t = int(sec)
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _on_tree_cell_click(self, event, tree: ttk.Treeview, columns: Tuple[str, ...]):
        if tree.identify_region(event.x, event.y) != "cell":
            return
        row = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if not row or not col:
            return
        idx = int(col.replace("#", "")) - 1
        vals = tree.item(row, "values")
        if idx < 0 or idx >= len(vals):
            return

        col_name = columns[idx]
        if col_name == "link":
            tree.selection_set(row)
            try:
                uid_idx = columns.index("uid")
                uid = int(vals[uid_idx])
                webbrowser.open(f"https://space.bilibili.com/{uid}")
                self._show_copy_hint(f"已在浏览器打开 UID {uid}")
            except (ValueError, IndexError):
                uid_idx = 3 if len(vals) > 3 else None
                if uid_idx is not None:
                    uid = int(vals[uid_idx])
                    webbrowser.open(f"https://space.bilibili.com/{uid}")
                    self._show_copy_hint(f"已在浏览器打开 UID {uid}")
            return

        text = str(vals[idx]).strip()
        if not text or text == "—":
            return
        label = COLUMN_LABELS.get(col_name, col_name)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._show_copy_hint(f"已复制 {label}: {text}")

    def _show_copy_hint(self, msg: str):
        self.copy_hint_label.config(text=msg, style="CopyHint.TLabel")
        if self._copy_hint_after:
            self.root.after_cancel(self._copy_hint_after)
        self._copy_hint_after = self.root.after(
            3000,
            lambda: self.copy_hint_label.config(
                text="提示：单击表格单元格复制 · 双击行打开 B 站空间",
                style="StatusBar.TLabel",
            ),
        )

    def _copy_all_lv0_uids(self):
        if not self.lv0_records:
            messagebox.showinfo("提示", "暂无 Lv0 账号。")
            return
        text = "\n".join(str(r.uid) for r in self.lv0_records)
        self._copy_text(text, f"已复制 {len(self.lv0_records)} 个 Lv0 UID")

    def _copy_lv0_uid_names(self):
        if not self.lv0_records:
            messagebox.showinfo("提示", "暂无 Lv0 账号。")
            return
        lines = [f"{r.uid}\t{r.username}" for r in self.lv0_records]
        self._copy_text("\n".join(lines), f"已复制 {len(lines)} 条 Lv0 UID+用户名")

    def _copy_all_hit_uids(self):
        if not self.hit_records:
            messagebox.showinfo("提示", "暂无命中账号。")
            return
        text = "\n".join(str(r.uid) for r in self.hit_records)
        self._copy_text(text, f"已复制 {len(self.hit_records)} 个命中 UID")

    def _copy_hit_uid_names(self):
        if not self.hit_records:
            messagebox.showinfo("提示", "暂无命中账号。")
            return
        lines = [f"{r.uid}\t{r.username}" for r in self.hit_records]
        self._copy_text("\n".join(lines), f"已复制 {len(lines)} 条命中 UID+用户名")

    def _copy_text(self, text: str, hint: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._show_copy_hint(hint)

    def _export_lv0_txt(self):
        if not self.lv0_records:
            messagebox.showinfo("提示", "暂无 Lv0 账号可导出。")
            return
        path = filedialog.asksaveasfilename(
            title="导出 Lv0 列表",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="lv0_accounts.txt",
        )
        if not path:
            return
        lines = [
            f"UID: {r.uid} | 用户名: {r.username} | 乱码名: {'是' if r.is_gibberish else '否'}"
            for r in self.lv0_records
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._show_copy_hint(f"已导出 {len(lines)} 条 Lv0 到 {os.path.basename(path)}")
        except OSError as e:
            messagebox.showerror("导出失败", str(e))

    def _export_hit_txt(self):
        if not self.hit_records:
            messagebox.showinfo("提示", "暂无命中账号可导出。")
            return
        path = filedialog.asksaveasfilename(
            title="导出命中列表",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="hit_accounts.txt",
        )
        if not path:
            return
        lines = [
            f"UID: {r.uid} | 用户名: {r.username} | 评分: {r.match_score:.0f} | {r.message}"
            for r in self.hit_records
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._show_copy_hint(f"已导出 {len(lines)} 条命中到 {os.path.basename(path)}")
        except OSError as e:
            messagebox.showerror("导出失败", str(e))

    def _handle_new_record(self, record: CheckRecord):
        self.display_records.append(record)
        self._refresh_all_table(scroll_to_end=True)

        if record.is_lv0_account:
            if not any(r.uid == record.uid for r in self.lv0_records):
                self.lv0_records.append(record)
            self._refresh_lv0_table(scroll_to_end=True)

        if record.status == "hit":
            if not any(r.uid == record.uid for r in self.hit_records):
                self.hit_records.append(record)
            self._refresh_hit_table(scroll_to_end=True)
            self.notebook.select(1)
        elif record.status == "lv0":
            self.notebook.select(0)

    def _append_log(self, msg: str, tag: Optional[str] = None):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n", tag or "")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _poll_queues(self):
        for q, handler in [
            (
                self.log_queue,
                lambda m: self._append_log(
                    m,
                    "hit"
                    if "命中" in m
                    else "rest"
                    if "Lv0账号" in m or "休息" in m
                    else "error"
                    if "失败" in m or "出错" in m
                    else "warn"
                    if "跳过" in m or "停止" in m
                    else None,
                ),
            ),
            (self.record_queue, self._handle_new_record),
        ]:
            while True:
                try:
                    handler(q.get_nowait())
                except queue.Empty:
                    break
        self.root.after(100, self._poll_queues)

    def _open_file(self, path: str):
        abs_path = os.path.normpath(os.path.abspath(path))
        abs_norm = os.path.normcase(abs_path)
        data_dir = os.path.normcase(os.path.normpath(os.path.abspath(get_data_dir())))
        sep = os.path.normcase(os.sep)
        if abs_norm != data_dir and not abs_norm.startswith(data_dir + sep):
            messagebox.showerror("错误", "只能打开当前数据目录内的文件。")
            return
        if not os.path.isfile(abs_path):
            messagebox.showinfo("提示", f"文件尚未生成:\n{abs_path}")
            return
        if sys.platform == "win32":
            os.startfile(abs_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", abs_path], check=False)
        else:
            subprocess.run(["xdg-open", abs_path], check=False)


def _setup_storage(parent: tk.Tk) -> bool:
    """启动前配置数据存储目录；有效配置则跳过选择。"""
    parent.update_idletasks()
    saved_path, exists = read_storage_config()

    if saved_path and exists:
        try:
            configure_storage(saved_path)
            return True
        except ValueError as e:
            parent.deiconify()
            parent.update()
            messagebox.showwarning(
                "存储目录无效",
                f"{saved_path}\n\n{e}",
                parent=parent,
            )

    missing_path = saved_path if saved_path and not exists else None
    default_dir = saved_path or DEFAULT_DATA_DIR
    required = getattr(sys, "frozen", False) or bool(missing_path)

    if not required:
        try:
            configure_storage(DEFAULT_DATA_DIR)
        except ValueError:
            required = True
        else:
            save_storage_config(DEFAULT_DATA_DIR)
            return True

    parent.deiconify()
    parent.update()

    if missing_path:
        messagebox.showwarning(
            "存储目录不存在",
            f"之前保存的目录已不存在：\n{missing_path}\n\n请重新选择。",
            parent=parent,
        )
        clear_storage_config()

    dlg = StorageSetupDialog(
        parent,
        default_dir,
        required=required,
        missing_path=missing_path,
    )
    parent.wait_window(dlg)
    if not dlg.result:
        return False
    try:
        configure_storage(dlg.result)
    except ValueError as e:
        messagebox.showerror("错误", str(e), parent=parent)
        return False
    save_storage_config(dlg.result)
    return True


def launch_gui():
    root = tk.Tk()
    root.title("Bilibili UID 检查器")
    apply_window_icon(root)
    root.withdraw()
    root.update()

    if not _setup_storage(root):
        root.destroy()
        return

    root.deiconify()
    root.state("normal")
    root.lift()
    root.focus_force()
    CheckerApp(root)
    root.mainloop()
