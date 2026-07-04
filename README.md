# Bilibili UID 检查器

批量扫描哔哩哔哩早年被注册机批量注册、长期无人使用的 UID 账号。通过 DrissionPage 驱动本地 Chrome，随机生成 UID 访问 B 站用户空间，自动筛选「乱码英文用户名 + Lv0」的疑似机器注册账号，并提供 **GUI 图形界面**、**命令行模式** 与 **Windows exe 打包**。

---

## 作者与仓库

| 角色 | GitHub | 说明 |
|------|--------|------|
| **原作者** | [@f1shQAQ](https://github.com/f1shQAQ) | 项目最初实现与核心检查逻辑 |
| **上游仓库** | [f1shQAQ/bilibili_uid_checker](https://github.com/f1shQAQ/bilibili_uid_checker) | 原始开源仓库 |
| **Fork 维护者** | [@travelxiao](https://github.com/travelxiao) | GUI、打包、存储与安全等功能增强 |
| **本仓库** | [travelxiao/bilibili_uid_checker](https://github.com/travelxiao/bilibili_uid_checker) | 当前维护版本 |

> 本仓库基于 [f1shQAQ/bilibili_uid_checker](https://github.com/f1shQAQ/bilibili_uid_checker) Fork 并持续完善。感谢原作者的开源贡献。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🖥️ **GUI 界面** | Tkinter 图形界面，Lv0 / 命中 / 全部记录分标签展示 |
| 🤖 **自动 Chrome** | 程序自动启动 Chrome 调试模式，无需手动运行脚本 |
| 📦 **exe 打包** | 一键构建 `BilibiliUIDChecker.exe`，双击即可使用 |
| 📂 **分类存储** | Lv0 账号、命中账号、全部记录分别写入独立文件 |
| 💾 **存储配置** | 首次运行选择数据目录，配置持久化至 `app_config.json` |
| 🛡️ **安全限速** | 请求间隔、定时休息、连续错误冷却，降低风控风险 |
| 🔍 **乱码评分** | 辅音占比、连续辅音、字符分散等多维度评分判定 |
| 🧹 **清理脚本** | `clean.bat` 一键清理构建产物与运行数据 |

### 与上游原版的主要增强

- 新增 `gui.py` 图形界面与实时统计面板
- 支持 PyInstaller 单文件 exe 打包（`build_exe.bat`）
- Chrome 自动检测与启动，告别手动运行 `start_chrome_*.bat`
- Lv0 与命中账号分开记录（`lv0.json` / `hits.json`）
- 可配置数据存储目录，支持 JSON 持久化与路径校验
- Bilibili 风格应用图标与 exe 启动优化
- 项目目录整理（`data/`、`scripts/`）与 bug 修复

---

## 项目结构

```
bilibili_uid_checker/
├── bilibili_uid_checker.py   # 核心引擎（检查逻辑、存储、Chrome 连接）
├── gui.py                    # Tkinter 图形界面
├── assets/app.ico            # 应用图标
├── data/                     # 默认运行数据目录（gitignore）
├── scripts/
│   ├── build_icon.py         # Bilibili 风格图标生成
│   └── start_chrome_*.bat/sh # Chrome 调试模式脚本（备用）
├── build_exe.bat             # Windows 打包
├── clean.bat                 # 清理非核心文件
├── bilibili_uid_checker.spec # PyInstaller 配置
├── requirements.txt          # 运行依赖
├── requirements-build.txt    # 打包依赖
└── dist/                     # 打包输出（gitignore）
```

---

## 环境要求

- **Python** 3.7+
- **Google Chrome** 浏览器
- **DrissionPage**（见 `requirements.txt`）

## 安装

```bash
pip install -r requirements.txt
```

打包 exe 还需：

```bash
pip install -r requirements-build.txt
```

---

## 快速开始

### 方式一：GUI（推荐）

```bash
python bilibili_uid_checker.py
```

程序会在启动约 1 秒后**自动尝试连接 / 启动 Chrome**，无需手动运行启动脚本。

- 开发模式默认数据目录：`data/`
- 打包 exe 首次运行会提示选择**数据存储目录**，配置保存在 exe 同目录的 `app_config.json`

### 方式二：命令行

```bash
python bilibili_uid_checker.py --cli
```

按提示输入 UID 前缀、长度与运行时长，Ctrl+C 停止。

### 方式三：Windows 可执行文件

```bash
build_exe.bat
```

输出 `dist/BilibiliUIDChecker.exe`，双击即可运行（需本机已安装 Chrome）。

---

## 记录分类

| 类型 | 条件 | 文件 |
|------|------|------|
| **Lv0 账号** | 任意 Lv0 用户 | `lv0.json` / `lv0.txt` |
| **命中账号** | 乱码英文名 + Lv0 | `hits.json` / `result.txt` |
| **全部记录** | 每次检查 | `records.json` |

数据目录可在 GUI 菜单 **文件 → 更改数据存储位置** 中修改。

---

## 筛选规则（命中账号）

必须**同时满足**以下所有条件：

| 条件 | 说明 |
|------|------|
| 全小写英文 | 用户名仅由 a-z 组成，无数字、中文、特殊字符 |
| 长度 6~12 | 过短或过长的用户名排除 |
| 辅音占比 > 55% | 乱码用户名通常辅音密集（综合评分 ≥ 55 判定为乱码） |
| 无常见英文子串 | 不含 game、love、the、ing 等 100+ 常见单词/拼音片段 |
| 等级 Lv0 | 用户等级必须为 0 级 |

### 输出示例

`result.txt` / `hits.json` 中的命中记录：

```
UID: 1234567 | 用户名: xbjulymph
UID: 3987654 | 用户名: fmxhgdxfl
```

---

## 常用命令

```bash
# GUI 模式
python bilibili_uid_checker.py

# CLI 模式
python bilibili_uid_checker.py --cli

# 打包 exe
build_exe.bat

# 清理构建产物、缓存与运行数据（保留核心源码）
clean.bat

# 手动启动 Chrome 调试模式（通常不需要）
scripts/start_chrome_windows.bat   # Windows
./scripts/start_chrome_macos.sh    # macOS
./scripts/start_chrome_linux.sh    # Linux
```

---

## 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEBUGGING_PORT` | 9222 | Chrome CDP 调试端口 |
| `MIN_DELAY / MAX_DELAY` | 2.5~6 秒 | 请求间隔 |
| `DEFAULT_REST_EVERY_N` | 25 | 每 N 次检查休息一次 |
| `DEFAULT_MAX_CONSECUTIVE_ERRORS` | 4 | 连续错误触发长休息 |
| 数据目录 | `data/` 或用户指定 | 由 `app_config.json` 持久化 |

---

## 常见问题

### 连接 Chrome 失败

- 确保本机已安装 Google Chrome
- 关闭占用 9222 端口的旧 Chrome 进程后重试
- Windows：任务管理器结束多余 `chrome.exe`
- macOS / Linux：活动监视器或 `pkill -f chrome`

### exe 无法打开 / 无窗口

- 首次运行需选择数据存储目录；若之前目录已删除，按提示重新选择
- 查看 exe 同目录下的 `crash.log`

### 无法获取用户名或等级

- B 站页面 DOM 结构可能更新，需适配 `get_username()` / `get_user_level()` 中的 CSS 选择器
- 确保网络正常，页面能完整加载

### 修改调试端口

同时修改 `bilibili_uid_checker.py` 中的 `DEBUGGING_PORT` 与 `scripts/start_chrome_*.bat/sh` 脚本。

---

## 技术说明

- **浏览器自动化**：[DrissionPage](https://github.com/g1879/DrissionPage)（基于 Chrome DevTools Protocol，无需 chromedriver）
- **GUI 框架**：Tkinter（Python 标准库）
- **打包工具**：PyInstaller 单文件模式

Chrome 启动参数：

| 参数 | 作用 |
|------|------|
| `--remote-debugging-port=9222` | 开启调试端口，供脚本连接控制浏览器 |
| `--no-first-run` | 跳过 Chrome 首次运行向导 |
| `--no-default-browser-check` | 跳过默认浏览器检查 |
| `--user-data-dir=<临时路径>` | 使用独立配置目录，不影响日常 Chrome |

---

## 免责声明

本工具仅供学习与研究使用。请遵守 [哔哩哔哩用户协议](https://www.bilibili.com/protocal/licence.html) 及相关法律法规，合理控制访问频率，勿用于任何违规或滥用目的。使用者需自行承担使用本工具产生的一切后果。

---

## 致谢

- 感谢原作者 [@f1shQAQ](https://github.com/f1shQAQ) 的开源项目 [bilibili_uid_checker](https://github.com/f1shQAQ/bilibili_uid_checker)
- 感谢 [DrissionPage](https://github.com/g1879/DrissionPage) 提供的浏览器自动化能力

---

## License

本项目遵循上游仓库的开源协议。Fork 版本的增强功能同样开源共享，欢迎 Issue 与 Pull Request。
