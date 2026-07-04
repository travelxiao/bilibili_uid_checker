# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Bilibili UID 检查器 — 通过 DrissionPage 驱动本地 Chrome 浏览器，随机生成 7 位 UID 访问 B 站用户空间，自动筛选「乱码英文用户名 + 0 级」的疑似机器注册账号并记录到 `result.txt`。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行主程序（需先启动 Chrome 调试模式）
python bilibili_uid_checker.py

# Windows 启动 Chrome 调试模式
start_chrome_windows.bat

# macOS 启动 Chrome 调试模式
chmod +x start_chrome_macos.sh && ./start_chrome_macos.sh

# Linux 启动 Chrome 调试模式
chmod +x start_chrome_linux.sh && ./start_chrome_linux.sh
```

## 代码架构

- **单文件项目**：`bilibili_uid_checker.py` (~250 行)
- **浏览器自动化**：DrissionPage（基于 CDP 协议连接本地 Chrome 9222 端口）
- **无 WebDriver**：不需要 chromedriver，直接通过 Chrome DevTools Protocol 控制

### 核心模块

| 函数 | 职责 |
|------|------|
| `is_gibberish_name(name)` | 乱码用户名判定（纯小写英文 + 6~12位 + 辅音>60% + 无常见子串） |
| `get_user_level(page)` | CSS 选择器从 B 站空间页提取 `user_level_X` |
| `get_username(page)` | CSS 选择器从 B 站空间页提取用户名 |
| `main()` | 主循环：生成随机 UID → 访问页面 → 提取信息 → 判定记录 |

### 筛选规则（必须同时满足）

1. 仅由小写英文字母 a-z 组成
2. 长度 6~12
3. 辅音字母占比 > 60%
4. 不含 100+ 常见英文/拼音子串
5. 用户等级为 Lv0

## 关键配置

- `DEBUGGING_PORT = 9222`：Chrome 调试端口（需与启动脚本一致）
- `MIN_DELAY / MAX_DELAY`：请求间隔 2~5 秒
- `OUTPUT_FILE`：结果输出路径（`result.txt`，脚本同目录）
- `COMMON_SUBSTRINGS`：常见英文/拼音子串黑名单（100+ 条目）

## 注意事项

- 启动前必须完全关闭所有 Chrome 进程，否则调试端口无法生效
- B 站页面 DOM 结构可能更新，选择器 `.nickname` 和 `i.level-icon` 可能需要适配
- 仅依赖 DrissionPage 一个第三方库
