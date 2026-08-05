"""缓存管理器 —— 记忆上次导入的文件。

设计目标：
- 工具首页导入的主合同文件与 Tab3 过保文件，首次人工导入时复制到程序运行目录的
  `tmp/` 缓存目录，并按功能入口统一命名（main_data.*、expiry_data.*）。
- 下次启动时自动检测 `tmp/` 目录，存在有效缓存则自动加载，无需手动再次导入。
- 防锁死：只识别固定命名约定的文件，忽略不相干文件；读取采用线程 + 超时 + 大小限制，
  避免因文件损坏 / 超大 / 被占用导致进程卡死。
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field

import pandas as pd

from ui.logger import log_info, log_error

# 缓存目录名（相对程序运行目录）
CACHE_DIR_NAME = "tmp"

# 两个功能入口的缓存文件命名（统一命名，便于下次识别）
MAIN_CACHE_NAME = "main_data.xlsx"
EXPIRY_CACHE_NAME = "expiry_data.xlsx"

# 防锁死限制
MAX_CACHE_FILE_MB = 200          # 单个缓存文件上限（MB），超大文件拒绝自动加载
READ_TIMEOUT_SEC = 30            # 读取文件超时（秒）
MIN_FILE_SIZE_BYTES = 100        # 缓存文件至少要有一定字节数，过滤空/损坏文件


@dataclass
class CacheFileInfo:
    """一次可加载的缓存条目。"""

    key: str            # 'main' 或 'expiry'
    path: str           # 缓存文件完整路径
    valid: bool = False
    reason: str = ""    # 无效原因


@dataclass
class CacheSnapshot:
    """tmp 目录的缓存扫描结果。"""

    main: CacheFileInfo = field(default_factory=lambda: CacheFileInfo("main", ""))
    expiry: CacheFileInfo = field(default_factory=lambda: CacheFileInfo("expiry", ""))
    junk: list[str] = field(default_factory=list)  # 不相干/无效的缓存文件


def get_cache_dir() -> str:
    """返回缓存目录绝对路径；打包后为 exe 所在目录/tmp，源码运行为项目根目录/tmp。"""
    import sys

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)  # 打包后 exe 所在目录
    return os.path.join(base, CACHE_DIR_NAME)


def ensure_cache_dir() -> str:
    """确保缓存目录存在，返回其路径。"""
    d = get_cache_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as e:
        log_error(f"创建缓存目录失败: {d} -> {e}")
    return d


def _is_valid_cache_file(path: str) -> tuple[bool, str]:
    """校验缓存文件是否有效（防锁死）。"""
    if not os.path.isfile(path):
        return False, "文件不存在"
    try:
        if os.path.getsize(path) < MIN_FILE_SIZE_BYTES:
            return False, "文件过小（空或损坏）"
        if os.path.getsize(path) > MAX_CACHE_FILE_MB * 1024 * 1024:
            return False, f"超过 {MAX_CACHE_FILE_MB}MB 限制"
    except Exception as e:
        return False, f"无法读取文件信息: {e}"
    return True, ""


def write_cache(source_path: str, key: str) -> str | None:
    """把用户导入的源文件复制到缓存目录（统一命名）。返回缓存路径，失败返回 None。"""
    if not source_path or not os.path.isfile(source_path):
        log_info(f"缓存写入跳过：源文件无效 {source_path}")
        return None

    target_name = MAIN_CACHE_NAME if key == "main" else EXPIRY_CACHE_NAME
    dest = os.path.join(ensure_cache_dir(), target_name)

    try:
        # 先写临时文件再原子替换，避免写一半导致下次读到损坏文件
        tmp_dest = dest + ".writing"
        if os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except Exception:
                pass
        shutil.copyfile(source_path, tmp_dest)
        os.replace(tmp_dest, dest)
        log_info(f"缓存已更新 [{key}] -> {dest}")
        return dest
    except Exception as e:
        log_error(f"缓存写入失败 [{key}]: {source_path} -> {e}")
        try:
            if os.path.exists(tmp_dest):
                os.remove(tmp_dest)
        except Exception:
            pass
        return None


def scan_cache() -> CacheSnapshot:
    """扫描缓存目录，识别 main / expiry 缓存与不相干文件。"""
    snap = CacheSnapshot()
    d = get_cache_dir()
    if not os.path.isdir(d):
        return snap

    main_path = os.path.join(d, MAIN_CACHE_NAME)
    expiry_path = os.path.join(d, EXPIRY_CACHE_NAME)

    snap.main.path = main_path
    snap.expiry.path = expiry_path
    snap.main.valid, snap.main.reason = _is_valid_cache_file(main_path)
    snap.expiry.valid, snap.expiry.reason = _is_valid_cache_file(expiry_path)

    # 找出不相干/无效的缓存文件（非固定命名且非 writing 临时文件）
    known = {MAIN_CACHE_NAME, EXPIRY_CACHE_NAME, MAIN_CACHE_NAME + ".writing", EXPIRY_CACHE_NAME + ".writing"}
    try:
        for name in os.listdir(d):
            if name in known:
                continue
            full = os.path.join(d, name)
            if os.path.isfile(full):
                snap.junk.append(full)
    except Exception as e:
        log_error(f"扫描缓存目录失败: {e}")

    return snap


def read_cached_df(path: str) -> pd.DataFrame | None:
    """在线程中读取缓存文件；返回 DataFrame，失败/超时返回 None（不抛异常）。"""
    result: dict = {"df": None, "error": ""}

    def _read():
        try:
            # 只认 Excel 缓存
            result["df"] = pd.read_excel(path)
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=READ_TIMEOUT_SEC)
    if t.is_alive():
        log_error(f"读取缓存超时（>{READ_TIMEOUT_SEC}s）: {path}")
        return None
    if result["error"]:
        log_info(f"缓存读取失败: {path} -> {result['error']}")
        return None
    return result["df"]


def remove_cache(key: str) -> bool:
    """删除指定 key（main/expiry）的缓存文件。用于加载失败时清除无效缓存。"""
    name = MAIN_CACHE_NAME if key == "main" else EXPIRY_CACHE_NAME
    path = os.path.join(get_cache_dir(), name)
    try:
        if os.path.exists(path):
            os.remove(path)
            log_info(f"已删除无效缓存: {path}")
        return True
    except Exception as e:
        log_error(f"删除缓存失败: {path} -> {e}")
        return False


def remove_expiry_cache() -> bool:
    """删除过保缓存文件。"""
    return remove_cache("expiry")


def remove_main_cache() -> bool:
    """删除主数据缓存文件。"""
    return remove_cache("main")


def clean_junk_files(snap: CacheSnapshot | None = None) -> int:
    """清理缓存目录中的不相干文件（防干扰）。返回清理数量。"""
    snap = snap or scan_cache()
    removed = 0
    for path in snap.junk:
        try:
            os.remove(path)
            log_info(f"清理无效缓存文件: {path}")
            removed += 1
        except Exception as e:
            log_error(f"清理缓存文件失败: {path} -> {e}")
    return removed
