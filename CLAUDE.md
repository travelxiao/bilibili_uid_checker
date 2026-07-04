# CLAUDE.md

本文件为 Claude Code 在此仓库中工作时提供指引。

## 项目概述

Bilibili UID 检查器 — 通过 DrissionPage 连接本地 Chrome（CDP 9222），随机生成 UID 访问 B 站用户空间，筛选疑似机器注册账号。支持 GUI、CLI 与 PyInstaller 单文件 exe。

## 常用命令

```bash
pip install -r requirements.txt
python bilibili_uid_checker.py          # GUI（默认）
python bilibili_uid_checker.py --cli    # 命令行

build_exe.bat    # 打包 dist/BilibiliUIDChecker.exe
clean.bat        # 清理 build/ 与 __pycache__

start_chrome_windows.bat   # 手动 Chrome 调试模式（GUI 会自动启动，通常不需要）
```

## 代码架构

| 文件 | 职责 |
|------|------|
| `bilibili_uid_checker.py` | 核心引擎：`CheckerRunner`、`RecordStore`、`SafetyGuard`、Chrome 自动启动、存储配置 |
| `gui.py` | Tkinter GUI：Lv0/命中/全部记录标签页、运行控制、存储目录设置 |
| `scripts/build_icon.py` | 生成 `assets/app.ico`（Bilibili TV 风格多尺寸图标） |
| `bilibili_uid_checker.spec` | PyInstaller 单文件打包配置 |

### 核心类与函数

| 符号 | 职责 |
|------|------|
| `analyze_gibberish()` / `is_gibberish_name()` | 乱码用户名评分与判定 |
| `evaluate_account()` | 综合用户名 + 等级判定 |
| `CheckerRunner` | 检查主循环（DrissionPage 延迟导入） |
| `RecordStore` | JSON 持久化（records / hits / lv0） |
| `ensure_chrome_debug()` | 检测并自动启动 Chrome |
| `configure_storage()` | 设置数据目录与输出文件路径 |
| `launch_gui()` | GUI 入口，含首次存储目录对话框 |

### 记录类型

| status | 条件 | 文件 |
|--------|------|------|
| `lv0` | Lv0 用户 | `lv0.json`, `lv0.txt` |
| `hit` | 乱码英文 + Lv0 | `hits.json`, `result.txt` |
| （全部） | 每次检查 | `records.json` |

### 筛选规则（命中，须同时满足）

1. 仅小写英文字母 a-z
2. 长度 6~12
3. 辅音占比 > 60%
4. 不含 100+ 常见英文/拼音子串
5. 用户等级 Lv0

## 关键配置

- `DEBUGGING_PORT = 9222`
- `APP_DIR`：脚本/exe 所在目录；打包后 `sys.frozen` 时使用 exe 目录
- `app_config.json`：持久化 `data_dir`（gitignore）
- `get_app_icon_path()`：优先 exe 同目录 `assets/app.ico`，其次打包资源

## 打包注意

- `build_exe.bat` 使用 `requirements-build.txt`（含 PyInstaller、Pillow）
- 打包后复制 `app.ico` 到 `dist/` 与 `dist/assets/`
- `upx=False` 以加快 exe 冷启动
- frozen 模式异常写入 `crash.log`

## GUI 启动要点

- `launch_gui()` 先 `withdraw()` 再 `_setup_storage()`；弹窗前必须 `deiconify()`，否则 Windows 下模态框不可见
- 历史记录与 Chrome 连接延迟加载（10ms / 1200ms）以加快界面显示

## 注意事项

- DrissionPage 仅在 `CheckerRunner._run` 内导入，避免拖慢 exe 启动
- B 站 DOM 更新时需适配 `.nickname`、`i.level-icon` 等选择器
- 运行数据文件（`records.json`、`lv0.json` 等）均在 gitignore 中，勿提交
