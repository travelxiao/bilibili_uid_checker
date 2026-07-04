"""
Bilibili UID 检查器
====================
连接本地 Chrome 浏览器，按配置生成 UID 访问 B 站用户空间，
筛选出「乱码英文用户名 + Lv0」的命中账号，并记录所有 Lv0 账号。

程序会自动启动 Chrome 调试模式，无需手动操作。
"""

import random
import re
import time
import os
import sys
import json
import logging
import threading
import socket
import subprocess
import shutil
from dataclasses import dataclass, asdict, fields
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from DrissionPage import ChromiumPage, ChromiumOptions


# ======================== 配置 ========================
def _app_dir() -> str:
    """脚本或 exe 所在目录（打包后输出文件写在此处）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()
CONFIG_FILE = os.path.join(APP_DIR, "app_config.json")
CHROME_PROFILE_DIR = os.path.join(APP_DIR, "chrome_temp_profile")

DATA_DIR = APP_DIR
OUTPUT_FILE = os.path.join(DATA_DIR, "result.txt")
LV0_OUTPUT_FILE = os.path.join(DATA_DIR, "lv0.txt")
RECORDS_FILE = os.path.join(DATA_DIR, "records.json")
HITS_FILE = os.path.join(DATA_DIR, "hits.json")
LV0_FILE = os.path.join(DATA_DIR, "lv0.json")
RECORDS_JSONL_LEGACY = os.path.join(DATA_DIR, "records.jsonl")
DEFAULT_MIN_DELAY = 2.5
DEFAULT_MAX_DELAY = 6.0
DEFAULT_REST_EVERY_N = 25
DEFAULT_REST_MIN = 45.0
DEFAULT_REST_MAX = 90.0
DEFAULT_LONG_REST = 180.0
DEFAULT_MAX_CONSECUTIVE_ERRORS = 4
ABSOLUTE_MIN_DELAY = 1.5
DEBUGGING_PORT = 9222
MAX_RETRIES = 3
RETRY_DELAY = 3
FLUSH_INTERVAL = 10
MAX_STORED_RECORDS = 50000
MIN_UID_LENGTH = 4
MAX_UID_LENGTH = 10

LOG_FILE = os.path.join(DATA_DIR, "checker.log")
_log_file_handler: Optional[logging.FileHandler] = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_data_dir() -> str:
    return DATA_DIR


def resource_path(relative: str) -> str:
    """获取内置资源路径（兼容 PyInstaller 打包）。"""
    base = getattr(sys, "_MEIPASS", APP_DIR)
    return os.path.join(base, relative)


def get_app_icon_path() -> Optional[str]:
    for candidate in (
        resource_path(os.path.join("assets", "app.ico")),
        os.path.join(APP_DIR, "assets", "app.ico"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def read_storage_config() -> Tuple[Optional[str], bool]:
    """读取配置，返回 (目录路径, 目录是否存在)。"""
    if not os.path.isfile(CONFIG_FILE):
        return None, False
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None, False
        data_dir = (payload.get("data_dir") or "").strip()
        if not data_dir:
            return None, False
        data_dir = os.path.normpath(os.path.abspath(data_dir))
        return data_dir, os.path.isdir(data_dir)
    except (IOError, json.JSONDecodeError, TypeError, OSError) as e:
        logger.warning(f"读取配置失败: {e}")
        return None, False


def load_storage_config() -> Optional[str]:
    """读取有效（目录存在）的存储路径。"""
    data_dir, exists = read_storage_config()
    return data_dir if exists else None


def validate_storage_path(path: str) -> Tuple[bool, str]:
    """校验存储目录是否可用（存在或可创建、可写）。"""
    if not path or not str(path).strip():
        return False, "路径不能为空"
    norm = os.path.normpath(os.path.abspath(path.strip()))
    if len(norm) > 240:
        return False, "路径过长，请选择较短的路径"
    root_drive = os.path.splitdrive(norm)[0] + "\\"
    if norm in (root_drive, os.path.abspath("/")):
        return False, "不能将磁盘根目录作为存储位置"

    try:
        os.makedirs(norm, exist_ok=True)
        probe = os.path.join(norm, ".write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        return False, f"目录不可用: {e}"
    return True, ""


def save_storage_config(data_dir: str):
    """原子写入配置，避免中断导致损坏。"""
    norm = os.path.normpath(os.path.abspath(data_dir))
    payload = {
        "data_dir": norm,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    tmp_path = CONFIG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CONFIG_FILE)
    logger.info(f"已保存存储配置: {norm}")


def clear_storage_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
        except OSError as e:
            logger.warning(f"清除配置失败: {e}")


def _update_log_file(log_path: str):
    global LOG_FILE, _log_file_handler
    LOG_FILE = log_path
    if _log_file_handler:
        logger.removeHandler(_log_file_handler)
        _log_file_handler.close()
        _log_file_handler = None
    _log_file_handler = logging.FileHandler(log_path, encoding="utf-8")
    _log_file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(_log_file_handler)


def configure_storage(data_dir: str) -> str:
    """设置记录/日志等文件的存储目录。"""
    global DATA_DIR, OUTPUT_FILE, LV0_OUTPUT_FILE, RECORDS_FILE, HITS_FILE
    global LV0_FILE, RECORDS_JSONL_LEGACY

    valid, err = validate_storage_path(data_dir)
    if not valid:
        raise ValueError(err)

    data_dir = os.path.normpath(os.path.abspath(data_dir))
    DATA_DIR = data_dir
    OUTPUT_FILE = os.path.join(data_dir, "result.txt")
    LV0_OUTPUT_FILE = os.path.join(data_dir, "lv0.txt")
    RECORDS_FILE = os.path.join(data_dir, "records.json")
    HITS_FILE = os.path.join(data_dir, "hits.json")
    LV0_FILE = os.path.join(data_dir, "lv0.json")
    RECORDS_JSONL_LEGACY = os.path.join(data_dir, "records.jsonl")
    _update_log_file(os.path.join(data_dir, "checker.log"))
    logger.info(f"数据存储目录: {data_dir}")
    return data_dir


configure_storage(APP_DIR)


# ======================== Chrome 自动启动 ========================
def is_debug_port_open(port: int = DEBUGGING_PORT, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def find_chrome_executable() -> Optional[str]:
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        candidates = []
        for name in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium"):
            path = shutil.which(name)
            if path:
                candidates.append(path)
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def launch_chrome_debug(port: int = DEBUGGING_PORT) -> Tuple[bool, str]:
    chrome = find_chrome_executable()
    if not chrome:
        return False, "未找到 Google Chrome，请先安装浏览器"

    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
    ]
    try:
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, **kwargs)
        return True, chrome
    except OSError as e:
        return False, str(e)


def ensure_chrome_debug(
    port: int = DEBUGGING_PORT,
    timeout: float = 25.0,
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """确保 Chrome 调试端口可用；未运行时自动启动 Chrome。"""
    log = on_log or (lambda msg: logger.info(msg))

    if is_debug_port_open(port):
        log(f"Chrome 调试端口 {port} 已就绪")
        return True, ""

    log("正在自动启动 Chrome 调试模式...")
    ok, detail = launch_chrome_debug(port)
    if not ok:
        return False, detail

    log(f"已启动 Chrome（独立配置，不影响日常浏览器）")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_debug_port_open(port):
            log("Chrome 已就绪，可以开始检查")
            return True, ""
        time.sleep(0.5)

    return False, f"Chrome 启动超时（{timeout:.0f} 秒），请检查是否已安装 Chrome"


@dataclass
class CheckerConfig:
    uid_prefix: str
    uid_length: int = 7
    time_limit_minutes: float = 0
    min_delay: float = DEFAULT_MIN_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    max_checks: int = 0              # 0 = 不限
    max_errors: int = 0              # 0 = 不限
    rest_every_n: int = DEFAULT_REST_EVERY_N
    rest_min_seconds: float = DEFAULT_REST_MIN
    rest_max_seconds: float = DEFAULT_REST_MAX
    max_consecutive_errors: int = DEFAULT_MAX_CONSECUTIVE_ERRORS
    long_rest_seconds: float = DEFAULT_LONG_REST

    @property
    def time_limit_seconds(self) -> float:
        return self.time_limit_minutes * 60 if self.time_limit_minutes > 0 else 0


@dataclass
class CheckerStats:
    checked: int = 0
    lv0_found: int = 0
    found: int = 0
    skipped: int = 0
    errors: int = 0
    resting: bool = False
    rest_message: str = ""
    rest_remaining: float = 0.0


@dataclass
class MatchResult:
    is_gibberish: bool
    is_level_0: bool
    is_hit: bool
    score: float
    detail: str


@dataclass
class CheckRecord:
    """单次 UID 检查结果。"""

    uid: int
    username: str
    level: int
    status: str          # hit | lv0 | normal | skipped | fetch_failed | error
    is_gibberish: bool
    is_level_0: bool
    timestamp: str
    message: str = ""
    match_score: float = 0.0
    checked_at: str = ""

    @property
    def status_label(self) -> str:
        return {
            "hit": "命中",
            "lv0": "Lv0",
            "normal": "不符合",
            "skipped": "跳过",
            "fetch_failed": "访问失败",
            "error": "解析错误",
            "rate_limited": "风控冷却",
        }.get(self.status, self.status)

    @property
    def is_lv0_hit(self) -> bool:
        return self.status == "hit" and self.is_level_0 and self.is_gibberish

    @property
    def is_lv0_account(self) -> bool:
        return self.is_level_0 and self.status in ("lv0", "hit")

    @property
    def level_text(self) -> str:
        return f"Lv{self.level}" if self.level >= 0 else "—"


# ======================== 乱码用户名判定 ========================
COMMON_SUBSTRINGS = [
    "the", "ing", "tion", "ment", "able", "ness", "ful", "less",
    "game", "love", "cool", "star", "fire", "dark", "blue", "king",
    "play", "hero", "wolf", "fox", "cat", "dog", "sky", "moon",
    "sun", "ice", "war", "pro", "max", "boy", "girl", "man",
    "fan", "god", "ace", "top", "big", "red", "hot", "old",
    "new", "one", "two", "day", "way", "eye", "her", "his",
    "you", "not", "all", "can", "out", "use", "how", "its",
    "may", "did", "get", "has", "him", "see", "now", "come",
    "than", "like", "just", "over", "know", "back", "only",
    "good", "some", "time", "very", "when", "with", "make",
    "hand", "high", "keep", "last", "long", "much", "own",
    "say", "she", "too", "any", "same", "tell", "each",
    "bilibili", "bili", "video", "anime", "music", "live",
    "chen", "wang", "zhang", "yang", "huang", "zhao", "zhou",
    "chun", "xiao", "ming", "hong", "feng", "jing", "ying",
    "qing", "long", "ping", "ling", "dong", "song", "tang",
]

VOWELS = set("aeiou")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def _max_run_length(name: str, charset: set) -> int:
    best = cur = 0
    for ch in name:
        if ch in charset:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _has_repeated_pattern(name: str, min_len: int = 3) -> bool:
    for length in range(1, len(name) // min_len + 1):
        for i in range(len(name) - length * min_len + 1):
            chunk = name[i:i + length]
            if chunk * min_len == name[i:i + length * min_len]:
                return True
    return False


def analyze_gibberish(name: str) -> MatchResult:
    """
    分析用户名是否为乱码式英文名，返回评分与详情。
    评分越高越像机器随机生成的名字。
    """
    if not name:
        return MatchResult(False, False, False, 0.0, "用户名为空")

    normalized = name.strip().lower()
    if not re.fullmatch(r"[a-z]+", normalized):
        return MatchResult(False, False, False, 0.0, "非纯小写英文")

    if not (6 <= len(normalized) <= 12):
        return MatchResult(False, False, False, 0.0, f"长度{len(normalized)}不在6~12")

    for sub in COMMON_SUBSTRINGS:
        if sub in normalized:
            return MatchResult(False, False, False, 0.0, f"含常见词根:{sub}")

    score = 0.0
    reasons: List[str] = []

    consonant_count = sum(1 for ch in normalized if ch in CONSONANTS)
    consonant_ratio = consonant_count / len(normalized)
    if consonant_ratio > 0.55:
        score += min(consonant_ratio, 0.85) * 35
        reasons.append(f"辅音{consonant_ratio:.0%}")

    max_cons = _max_run_length(normalized, CONSONANTS)
    if max_cons >= 3:
        score += min(max_cons, 6) / 6 * 25
        reasons.append(f"连续辅音{max_cons}")

    max_vowel_run = _max_run_length(normalized, VOWELS)
    if max_vowel_run <= 1 and sum(1 for ch in normalized if ch in VOWELS) <= 2:
        score += 15
        reasons.append("元音稀少")

    unique_ratio = len(set(normalized)) / len(normalized)
    if unique_ratio >= 0.65:
        score += 12
        reasons.append("字符分散")

    if _has_repeated_pattern(normalized):
        score += 10
        reasons.append("重复片段")

    # 首尾辅音夹心（典型随机串）
    if normalized[0] in CONSONANTS and normalized[-1] in CONSONANTS:
        score += 8

    is_gibberish = score >= 55 and consonant_ratio > 0.55
    detail = " · ".join(reasons) if reasons else "未达阈值"
    return MatchResult(is_gibberish, False, False, round(min(score, 100), 1), detail)


def is_gibberish_name(name: str) -> bool:
    return analyze_gibberish(name).is_gibberish


def evaluate_account(username: str, level: int) -> MatchResult:
    """综合用户名与等级判定是否命中。"""
    result = analyze_gibberish(username)
    is_level_0 = level == 0
    is_hit = result.is_gibberish and is_level_0
    return MatchResult(
        is_gibberish=result.is_gibberish,
        is_level_0=is_level_0,
        is_hit=is_hit,
        score=result.score,
        detail=result.detail if result.is_gibberish else (
            f"非乱码名({result.detail})" if username else "无用户名"
        ),
    )


def validate_config(config: CheckerConfig) -> Tuple[bool, str]:
    """校验检查器配置，返回 (是否有效, 错误信息)。"""
    prefix = config.uid_prefix.strip()
    if not prefix.isdigit():
        return False, "UID 前缀必须为纯数字"
    if prefix[0] == "0":
        return False, "UID 前缀不能以 0 开头"
    if not (MIN_UID_LENGTH <= config.uid_length <= MAX_UID_LENGTH):
        return False, f"UID 总长度须在 {MIN_UID_LENGTH}~{MAX_UID_LENGTH} 之间"
    if len(prefix) >= config.uid_length:
        return False, "UID 前缀长度必须小于 UID 总长度"
    if config.time_limit_minutes < 0:
        return False, "运行时长不能为负数（0 表示不限时）"
    if config.min_delay < ABSOLUTE_MIN_DELAY:
        return False, f"请求最小间隔不能低于 {ABSOLUTE_MIN_DELAY} 秒（防封禁）"
    if config.max_delay < ABSOLUTE_MIN_DELAY:
        return False, "请求最大间隔无效"
    if config.min_delay > config.max_delay:
        return False, "最小间隔不能大于最大间隔"
    if config.max_checks < 0 or config.max_errors < 0:
        return False, "最大检查数/错误数不能为负数（0=不限）"
    if config.rest_every_n < 0:
        return False, "休息间隔不能为负数（0=禁用定时休息）"
    if config.rest_every_n > 0 and config.rest_min_seconds <= 0:
        return False, "休息时长须大于 0"
    if config.rest_min_seconds > config.rest_max_seconds:
        return False, "休息最短时长不能大于最长时长"
    if config.max_consecutive_errors < 0:
        return False, "连续错误阈值不能为负数"
    return True, ""


def build_uid_generator(prefix: str, uid_length: int):
    """根据前缀与总长度，返回随机 UID 生成函数。"""
    prefix_len = len(prefix)
    random_digits = uid_length - prefix_len
    random_max = 10 ** random_digits - 1
    prefix_int = int(prefix)

    def generate() -> int:
        remaining = random.randint(0, random_max)
        return int(f"{prefix_int}{remaining:0{random_digits}d}")

    return generate


def get_user_level(page) -> int:
    """从 B 站用户空间页面提取用户等级。"""
    try:
        level_elem = page.ele("css:i.level-icon", timeout=5)
        if level_elem:
            cls = level_elem.attr("class") or ""
            match = re.search(r"user_level_(\d)", cls)
            if match:
                return int(match.group(1))

        level_elem = page.ele("css:i[class*='user_level_']", timeout=3)
        if level_elem:
            cls = level_elem.attr("class") or ""
            match = re.search(r"user_level_(\d)", cls)
            if match:
                return int(match.group(1))

        return -1
    except Exception:
        return -1


def get_username(page) -> str:
    """从 B 站用户空间页面提取用户名。"""
    try:
        name_elem = page.ele("css:div.nickname", timeout=5)
        if name_elem:
            return name_elem.text.strip()

        name_elem = page.ele("css:[class*='nickname']", timeout=3)
        if name_elem:
            return name_elem.text.strip()

        return ""
    except Exception:
        return ""


def fetch_page(page, uid: int, max_retries: int = MAX_RETRIES) -> bool:
    """访问指定 UID 的 B 站空间页面，失败时自动重试。"""
    url = f"https://space.bilibili.com/{uid}"
    for attempt in range(1, max_retries + 1):
        try:
            page.get(url)
            time.sleep(1.5)
            return True
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"UID {uid} 访问失败 (第 {attempt}/{max_retries} 次): {e}，"
                    f"{RETRY_DELAY}秒后重试..."
                )
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"UID {uid} 访问失败 (已达最大重试次数): {e}")
    return False


class ResultWriter:
    """缓冲写入命中结果。"""

    def __init__(self, filepath: str, flush_interval: int = FLUSH_INTERVAL):
        self.filepath = filepath
        self.flush_interval = flush_interval
        self._buffer: list[str] = []
        self._count = 0

    def write(self, uid: int, username: str):
        line = f"UID: {uid} | 用户名: {username}\n"
        self._buffer.append(line)
        self._count += 1
        if len(self._buffer) >= self.flush_interval:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.writelines(self._buffer)
            logger.debug(f"已刷新 {len(self._buffer)} 条命中到 {self.filepath}")
            self._buffer.clear()
        except IOError as e:
            logger.error(f"写入结果文件失败: {e}")

    @property
    def total(self) -> int:
        return self._count


class RecordStore:
    """持久化保存检查记录与命中结果（JSON 格式）。"""

    _file_lock = threading.Lock()

    def __init__(self, flush_interval: int = FLUSH_INTERVAL):
        self.flush_interval = flush_interval
        self._pending: List[CheckRecord] = []
        self._session_records: List[CheckRecord] = []
        migrate_legacy_jsonl()

    def append(self, record: CheckRecord):
        self._session_records.append(record)
        self._pending.append(record)
        if len(self._pending) >= self.flush_interval:
            self.flush()

    def flush(self):
        if not self._pending:
            return
        with self._file_lock:
            try:
                existing = self._load_all_records_unlocked()
                existing.extend(self._pending)
                self._save_records_unlocked(existing)

                new_hits = [r for r in self._pending if r.status == "hit"]
                if new_hits:
                    hits = self._load_hits_unlocked()
                    hits.extend(new_hits)
                    hits = self._dedupe_records_by_uid(hits)
                    self._save_hits_unlocked(hits)

                new_lv0 = [r for r in self._pending if r.is_lv0_account]
                if new_lv0:
                    lv0_list = self._load_lv0_unlocked()
                    lv0_list.extend(new_lv0)
                    lv0_list = self._dedupe_records_by_uid(lv0_list)
                    self._save_lv0_unlocked(lv0_list)

                logger.debug(f"已保存 {len(self._pending)} 条记录到 JSON")
                self._pending.clear()
            except IOError as e:
                logger.error(f"写入 JSON 记录失败: {e}")

    @property
    def session_records(self) -> List[CheckRecord]:
        return list(self._session_records)

    def clear_session(self):
        self._session_records.clear()

    @staticmethod
    def _record_to_dict(record: CheckRecord) -> dict:
        return asdict(record)

    @staticmethod
    def _dict_to_record(data: dict) -> Optional[CheckRecord]:
        try:
            known = {f.name for f in fields(CheckRecord)}
            filtered = {k: v for k, v in data.items() if k in known}
            if "uid" in filtered:
                filtered["uid"] = int(filtered["uid"])
            return CheckRecord(**filtered)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _read_json_list(cls, filepath: str, list_key: str) -> List[CheckRecord]:
        if not os.path.isfile(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return []
            items = payload.get(list_key, [])
            if not isinstance(items, list):
                return []
            if len(items) > MAX_STORED_RECORDS:
                items = items[-MAX_STORED_RECORDS:]
            records = []
            for item in items:
                if isinstance(item, dict):
                    rec = cls._dict_to_record(item)
                    if rec:
                        records.append(rec)
            return records
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"读取 {filepath} 失败: {e}")
            return []

    @staticmethod
    def _dedupe_records_by_uid(records: List[CheckRecord]) -> List[CheckRecord]:
        seen: set = set()
        out: List[CheckRecord] = []
        for rec in records:
            if rec.uid not in seen:
                seen.add(rec.uid)
                out.append(rec)
        return out

    @classmethod
    def _write_json_list(cls, filepath: str, list_key: str, records: List[CheckRecord]):
        if len(records) > MAX_STORED_RECORDS:
            records = records[-MAX_STORED_RECORDS:]
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(records),
            list_key: [cls._record_to_dict(r) for r in records],
        }
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)

    @classmethod
    def _load_all_records_unlocked(cls) -> List[CheckRecord]:
        return cls._read_json_list(RECORDS_FILE, "records")

    @classmethod
    def _load_hits_unlocked(cls) -> List[CheckRecord]:
        return cls._read_json_list(HITS_FILE, "hits")

    @classmethod
    def _load_lv0_unlocked(cls) -> List[CheckRecord]:
        return cls._read_json_list(LV0_FILE, "lv0")

    @classmethod
    def _save_records_unlocked(cls, records: List[CheckRecord]):
        cls._write_json_list(RECORDS_FILE, "records", records)

    @classmethod
    def _save_hits_unlocked(cls, hits: List[CheckRecord]):
        cls._write_json_list(HITS_FILE, "hits", hits)

    @classmethod
    def _save_lv0_unlocked(cls, lv0_records: List[CheckRecord]):
        cls._write_json_list(LV0_FILE, "lv0", lv0_records)

    @classmethod
    def load_all(cls) -> List[CheckRecord]:
        with cls._file_lock:
            return cls._load_all_records_unlocked()

    @classmethod
    def load_hits(cls) -> List[CheckRecord]:
        with cls._file_lock:
            hits = cls._load_hits_unlocked()
            return [h for h in hits if h.is_lv0_hit or h.status == "hit"]

    @classmethod
    def load_lv0(cls) -> List[CheckRecord]:
        with cls._file_lock:
            lv0_list = cls._load_lv0_unlocked()
            if lv0_list:
                return [r for r in lv0_list if r.is_lv0_account]
            records = cls._load_all_records_unlocked()
            return [r for r in records if r.is_level_0]

    @classmethod
    def load_recent(cls, limit: int = 500) -> List[CheckRecord]:
        records = cls.load_all()
        return records[-limit:]


def migrate_legacy_jsonl():
    """将旧版 records.jsonl 迁移为 JSON 格式。"""
    legacy_paths = [
        RECORDS_JSONL_LEGACY,
        os.path.join(APP_DIR, "records.jsonl"),
    ]
    legacy_file = next((p for p in legacy_paths if os.path.isfile(p)), None)
    if not legacy_file:
        return
    if os.path.isfile(RECORDS_FILE):
        return

    records: List[CheckRecord] = []
    try:
        with open(legacy_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = RecordStore._dict_to_record(data)
                    if rec:
                        records.append(rec)
                except json.JSONDecodeError:
                    continue
    except IOError as e:
        logger.error(f"迁移 jsonl 失败: {e}")
        return

    if not records:
        return

    with RecordStore._file_lock:
        RecordStore._save_records_unlocked(records)
        hits = [r for r in records if r.status == "hit"]
        if hits:
            RecordStore._save_hits_unlocked(hits)
        lv0_list = [r for r in records if r.is_level_0]
        if lv0_list:
            RecordStore._save_lv0_unlocked(lv0_list)
    logger.info(
        f"已从 records.jsonl 迁移 {len(records)} 条记录"
        f"（命中 {len(hits)} 条，Lv0 {len(lv0_list)} 条）"
    )


def make_check_record(
    uid: int,
    username: str = "",
    level: int = -1,
    status: str = "skipped",
    message: str = "",
    match_score: float = 0.0,
) -> CheckRecord:
    now = datetime.now()
    if username and level >= 0:
        match = evaluate_account(username, level)
        is_gibberish = match.is_gibberish
        is_level_0 = match.is_level_0
        if not match_score:
            match_score = match.score
    else:
        is_gibberish = is_gibberish_name(username) if username else False
        is_level_0 = level == 0

    return CheckRecord(
        uid=uid,
        username=username or "—",
        level=level,
        status=status,
        is_gibberish=is_gibberish,
        is_level_0=is_level_0,
        timestamp=now.strftime("%H:%M:%S"),
        checked_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        message=message,
        match_score=match_score,
    )


class SafetyGuard:
    """请求限速、错误熔断与定时休息。"""

    def __init__(self, config: CheckerConfig):
        self.config = config
        self.consecutive_errors = 0
        self.checks_since_rest = 0
        self.total_errors = 0

    def record_success(self):
        self.consecutive_errors = 0

    def record_check(self):
        self.checks_since_rest += 1

    def record_error(self):
        self.consecutive_errors += 1
        self.total_errors += 1

    def should_stop(self, total_checked: int) -> Optional[str]:
        if self.config.max_checks > 0 and total_checked >= self.config.max_checks:
            return f"已达最大检查数 {self.config.max_checks}"
        if self.config.max_errors > 0 and self.total_errors >= self.config.max_errors:
            return f"已达最大错误数 {self.config.max_errors}"
        return None

    def get_rest_plan(self) -> Tuple[bool, str, float]:
        if (
            self.config.max_consecutive_errors > 0
            and self.consecutive_errors >= self.config.max_consecutive_errors
        ):
            return True, "连续错误冷却", self.config.long_rest_seconds

        if (
            self.config.rest_every_n > 0
            and self.checks_since_rest >= self.config.rest_every_n
        ):
            duration = random.uniform(
                self.config.rest_min_seconds, self.config.rest_max_seconds
            )
            return True, "定时休息", duration

        return False, "", 0.0

    def after_rest(self):
        self.checks_since_rest = 0
        self.consecutive_errors = 0


class CheckerRunner:
    """在后台线程中运行的检查器。"""

    def __init__(
        self,
        config: CheckerConfig,
        on_log: Optional[Callable[[str], None]] = None,
        on_stats: Optional[Callable[[CheckerStats, float], None]] = None,
        on_record: Optional[Callable[[CheckRecord], None]] = None,
    ):
        self.config = config
        self.on_log = on_log or (lambda msg: print(msg))
        self.on_stats = on_stats
        self.on_record = on_record
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.stats = CheckerStats()
        self.start_time: Optional[float] = None
        self.record_store = RecordStore()

    def log(self, message: str):
        self.on_log(message)
        logger.info(message)

    def request_stop(self):
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self.stats = CheckerStats()
        self.record_store.clear_session()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _should_stop(self, elapsed: float) -> bool:
        if self._stop_event.is_set():
            return True
        limit = self.config.time_limit_seconds
        return limit > 0 and elapsed >= limit

    def _save_record(self, record: CheckRecord):
        self.record_store.append(record)
        if self.on_record:
            self.on_record(record)

    def _run(self):
        valid, err = validate_config(self.config)
        if not valid:
            self.log(f"配置无效: {err}")
            return

        prefix = self.config.uid_prefix.strip()
        generate_uid = build_uid_generator(prefix, self.config.uid_length)

        self.log(f"正在连接本地 Chrome (端口 {DEBUGGING_PORT})...")
        ok, chrome_err = ensure_chrome_debug(on_log=self.log)
        if not ok:
            self.log(f"Chrome 启动失败: {chrome_err}")
            return

        try:
            co = ChromiumOptions()
            co.set_local_port(DEBUGGING_PORT)
            page = ChromiumPage(co)
            self.log("成功连接 Chrome 浏览器")
        except Exception as e:
            self.log(f"连接 Chrome 失败: {e}")
            self.log("请确认已安装 Google Chrome 后重试")
            return

        writer = ResultWriter(OUTPUT_FILE)
        lv0_writer = ResultWriter(LV0_OUTPUT_FILE)
        safety = SafetyGuard(self.config)
        self.start_time = time.time()

        limit_text = (
            f"{self.config.time_limit_minutes:g} 分钟"
            if self.config.time_limit_minutes > 0
            else "不限"
        )
        rest_text = (
            f"每 {self.config.rest_every_n} 次休息 "
            f"{self.config.rest_min_seconds:g}~{self.config.rest_max_seconds:g}s"
            if self.config.rest_every_n > 0
            else "未启用"
        )
        self.log(
            f"开始检查 | 前缀: {prefix} | 长度: {self.config.uid_length} 位 | "
            f"时长: {limit_text} | 间隔: {self.config.min_delay}~{self.config.max_delay}s"
        )
        self.log(f"安全策略 | 定时休息: {rest_text} | 连续错误阈值: {self.config.max_consecutive_errors}")
        if self.config.max_checks > 0:
            self.log(f"安全策略 | 最大检查数: {self.config.max_checks}")
        self.log(f"命中结果: {OUTPUT_FILE} / {HITS_FILE}")
        self.log(f"Lv0 结果: {LV0_OUTPUT_FILE} / {LV0_FILE}")
        self.log(f"全部记录: {RECORDS_FILE}")

        try:
            while not self._should_stop(time.time() - self.start_time):
                stop_reason = safety.should_stop(self.stats.checked)
                if stop_reason:
                    self.log(f"安全停止: {stop_reason}")
                    break

                need_rest, rest_reason, rest_duration = safety.get_rest_plan()
                if need_rest:
                    if self._rest_sleep(rest_duration, rest_reason):
                        break
                    safety.after_rest()
                    continue

                uid = generate_uid()

                if not fetch_page(page, uid):
                    self.stats.errors += 1
                    self.stats.checked += 1
                    safety.record_error()
                    safety.record_check()
                    record = make_check_record(
                        uid, status="fetch_failed", message="访问失败（已重试）"
                    )
                    self._save_record(record)
                    self.log(f"[{self.stats.checked}] UID {uid} — 访问失败（已重试）")
                    self._emit_stats()
                    if self._interruptible_sleep(self._random_delay()):
                        break
                    continue

                parsed = False
                try:
                    username = get_username(page)
                    level = get_user_level(page)
                    parsed = True
                    self.stats.checked += 1
                    safety.record_check()
                    match = evaluate_account(username, level) if username and level >= 0 else None

                    if not username:
                        self.stats.skipped += 1
                        safety.record_success()
                        record = make_check_record(
                            uid, status="skipped", message="无法获取用户名"
                        )
                        self._save_record(record)
                        self.log(f"[{self.stats.checked}] UID {uid} — 无法获取用户名，跳过")
                    elif level == -1:
                        self.stats.skipped += 1
                        safety.record_success()
                        record = make_check_record(
                            uid, username=username, status="skipped", message="无法获取等级"
                        )
                        self._save_record(record)
                        self.log(f"[{self.stats.checked}] UID {uid} — 无法获取等级，跳过")
                    elif level == 0:
                        self.stats.lv0_found += 1
                        safety.record_success()
                        lv0_writer.write(uid, username)

                        if match and match.is_hit:
                            self.stats.found += 1
                            writer.write(uid, username)
                            record = make_check_record(
                                uid,
                                username=username,
                                level=level,
                                status="hit",
                                message=match.detail,
                                match_score=match.score,
                            )
                            self._save_record(record)
                            self.log(
                                f"[{self.stats.checked}] UID {uid} — 用户名: {username} | "
                                f"命中(乱码+Lv0) 评分{match.score} | Lv0累计 {self.stats.lv0_found} | "
                                f"命中累计 {self.stats.found}"
                            )
                        else:
                            detail = match.detail if match else "Lv0账号"
                            record = make_check_record(
                                uid,
                                username=username,
                                level=level,
                                status="lv0",
                                message=detail,
                                match_score=match.score if match else 0,
                            )
                            self._save_record(record)
                            self.log(
                                f"[{self.stats.checked}] UID {uid} — 用户名: {username} | "
                                f"Lv0账号 | Lv0累计 {self.stats.lv0_found}"
                            )
                    else:
                        safety.record_success()
                        detail = match.detail if match else "不符合"
                        record = make_check_record(
                            uid,
                            username=username,
                            level=level,
                            status="normal",
                            message=detail,
                            match_score=match.score if match else 0,
                        )
                        self._save_record(record)
                        self.log(
                            f"[{self.stats.checked}] UID {uid} — 用户名: {username} | "
                            f"等级: Lv{level} | 不符合 ({detail})"
                        )
                except Exception as e:
                    if not parsed:
                        self.stats.checked += 1
                        safety.record_check()
                    self.stats.errors += 1
                    safety.record_error()
                    logger.warning(f"UID {uid} 页面解析出错: {e}")
                    record = make_check_record(uid, status="error", message=str(e))
                    self._save_record(record)
                    self.log(f"[{self.stats.checked}] UID {uid} — 解析出错: {e}")

                self._emit_stats()

                if self._should_stop(time.time() - self.start_time):
                    break
                if self._interruptible_sleep(self._random_delay()):
                    break

        finally:
            writer.flush()
            lv0_writer.flush()
            self.record_store.flush()
            elapsed = time.time() - (self.start_time or time.time())
            if self._stop_event.is_set():
                stop_reason = "手动停止"
            elif (
                self.config.time_limit_seconds > 0
                and elapsed >= self.config.time_limit_seconds
            ):
                stop_reason = "已达时长限制"
            else:
                stop_reason = "已停止"

            self.log("=" * 40)
            self.log(f"检查结束 ({stop_reason})")
            self.log(f"共检查: {self.stats.checked} | Lv0: {self.stats.lv0_found} | "
                     f"命中: {self.stats.found} | 跳过: {self.stats.skipped} | "
                     f"错误: {self.stats.errors}")
            self.log(f"耗时: {self._format_duration(elapsed)}")
            self._emit_stats()

    def _random_delay(self) -> float:
        return random.uniform(self.config.min_delay, self.config.max_delay)

    def _rest_sleep(self, duration: float, reason: str) -> bool:
        """执行休息，返回 True 表示被中断停止。"""
        self.log(f"⏸ {reason}，休息 {int(duration)} 秒（降低风控风险）...")
        end = time.time() + duration
        while time.time() < end:
            remaining = end - time.time()
            self.stats.resting = True
            self.stats.rest_message = reason
            self.stats.rest_remaining = remaining
            self._emit_stats()
            if self._stop_event.is_set() or self._should_stop(
                time.time() - (self.start_time or time.time())
            ):
                self.stats.resting = False
                self.stats.rest_message = ""
                self.stats.rest_remaining = 0
                return True
            time.sleep(min(1.0, remaining))
        self.stats.resting = False
        self.stats.rest_message = ""
        self.stats.rest_remaining = 0
        self._emit_stats()
        self.log("▶ 休息结束，继续检查")
        return False

    def _emit_stats(self):
        if self.on_stats and self.start_time:
            self.on_stats(self.stats, time.time() - self.start_time)

    def _interruptible_sleep(self, duration: float) -> bool:
        """分段 sleep，便于及时响应停止信号。返回 True 表示被中断。"""
        end = time.time() + duration
        while time.time() < end:
            if self._stop_event.is_set() or (
                self.start_time
                and self.config.time_limit_seconds > 0
                and time.time() - self.start_time >= self.config.time_limit_seconds
            ):
                return True
            time.sleep(min(0.2, end - time.time()))
        return False

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}小时{m}分{s}秒"
        if m:
            return f"{m}分{s}秒"
        return f"{s}秒"


def main_cli():
    """命令行模式（保留原有交互方式）。"""
    saved_path, exists = read_storage_config()
    if saved_path and exists:
        configure_storage(saved_path)
    else:
        configure_storage(APP_DIR)

    logger.info("=" * 55)
    logger.info("   Bilibili UID 检查器 — CLI 模式")
    logger.info(f"   启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 55)

    while True:
        prefix_input = input(
            "\n请输入 UID 前缀（纯数字，不能以 0 开头）: "
        ).strip()
        if prefix_input.isdigit() and prefix_input[0] != "0":
            break
        print("输入无效，前缀须为不以 0 开头的数字。")

    while True:
        length_input = input(
            f"请输入 UID 总长度 ({MIN_UID_LENGTH}~{MAX_UID_LENGTH}，默认 7): "
        ).strip() or "7"
        if length_input.isdigit():
            uid_length = int(length_input)
            if MIN_UID_LENGTH <= uid_length <= MAX_UID_LENGTH:
                if len(prefix_input) < uid_length:
                    break
        print(f"长度无效，须为 {MIN_UID_LENGTH}~{MAX_UID_LENGTH} 且大于前缀长度。")

    while True:
        limit_input = input("运行时长限制（分钟，0=不限，默认 0）: ").strip() or "0"
        try:
            time_limit = float(limit_input)
            if time_limit >= 0:
                break
        except ValueError:
            pass
        print("请输入不小于 0 的数字。")

    config = CheckerConfig(
        uid_prefix=prefix_input,
        uid_length=uid_length,
        time_limit_minutes=time_limit,
    )
    runner = CheckerRunner(config)
    runner.start()
    try:
        while runner.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        runner.request_stop()
        while runner.is_running:
            time.sleep(0.2)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        main_cli()
    else:
        from gui import launch_gui
        launch_gui()
