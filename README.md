# Bilibili UID 检查器

随机生成 UID 访问 B 站用户空间，筛选「乱码英文用户名 + Lv0」的疑似机器注册账号，并提供 GUI 与 exe 打包。

[视频教程](https://www.bilibili.com/video/BV1xjAMzsEsB)

## 项目结构

```
bilibili_uid_checker/
├── bilibili_uid_checker.py   # 核心引擎（检查逻辑、存储、Chrome 连接）
├── gui.py                    # Tkinter 图形界面
├── assets/app.ico            # 应用图标
├── scripts/build_icon.py     # 图标生成脚本
├── build_exe.bat             # Windows 打包
├── clean.bat                 # 清理构建缓存
├── bilibili_uid_checker.spec # PyInstaller 配置
├── requirements.txt          # 运行依赖
├── requirements-build.txt    # 打包依赖
├── start_chrome_*.bat/sh     # Chrome 调试模式脚本（备用）
└── dist/                     # 打包输出（gitignore）
```

## 环境要求

- Python 3.7+
- Google Chrome

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

### 方式一：GUI（推荐）

```bash
python bilibili_uid_checker.py
```

程序会自动尝试启动 Chrome 调试模式，无需手动运行启动脚本。首次运行 exe 时会提示选择**数据存储目录**，配置保存在 `app_config.json`。

### 方式二：命令行

```bash
python bilibili_uid_checker.py --cli
```

### 方式三：Windows 可执行文件

```bash
build_exe.bat
```

输出 `dist/BilibiliUIDChecker.exe`，双击即可运行。

## 记录分类

| 类型 | 条件 | 文件 |
|------|------|------|
| Lv0 账号 | 任意 Lv0 用户 | `lv0.json` / `lv0.txt` |
| 命中账号 | 乱码英文名 + Lv0 | `hits.json` / `result.txt` |
| 全部记录 | 每次检查 | `records.json` |

数据目录可在 GUI 菜单 **文件 → 更改数据存储位置** 中修改。

## 筛选规则（命中账号）

必须**同时满足**：

| 条件 | 说明 |
|------|------|
| 全小写英文 | 仅 a-z，无数字、中文、符号 |
| 长度 6~12 | |
| 辅音占比 > 60% | |
| 无常见英文子串 | 100+ 黑名单词条 |
| 等级 Lv0 | |

## 常用命令

```bash
# GUI
python bilibili_uid_checker.py

# CLI
python bilibili_uid_checker.py --cli

# 打包 exe
build_exe.bat

# 清理 build/ 与 __pycache__
clean.bat

# 手动启动 Chrome 调试模式（通常不需要）
start_chrome_windows.bat   # Windows
./start_chrome_macos.sh    # macOS
./start_chrome_linux.sh    # Linux
```

## 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEBUGGING_PORT` | 9222 | Chrome CDP 调试端口 |
| `MIN_DELAY / MAX_DELAY` | 2~5 秒 | 请求间隔 |
| 数据目录 | 项目目录或用户指定 | 由 `app_config.json` 持久化 |

## 常见问题

### 连接 Chrome 失败

- 确保本机已安装 Google Chrome
- 关闭占用 9222 端口的旧 Chrome 进程后重试
- GUI 会在启动约 1 秒后自动尝试连接 Chrome

### exe 无法打开 / 无窗口

- 首次运行需选择数据存储目录；若之前目录已删除，按提示重新选择
- 查看 exe 同目录下的 `crash.log`

### 修改调试端口

同时修改 `bilibili_uid_checker.py` 中的 `DEBUGGING_PORT` 与对应 `start_chrome_*.bat/sh` 脚本。

## 开发说明

- 浏览器自动化：[DrissionPage](https://github.com/g1879/DrissionPage)（CDP 协议，无需 chromedriver）
- B 站页面 DOM 变更时，需适配 `get_username()` / `get_user_level()` 中的选择器
