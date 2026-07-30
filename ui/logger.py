"""日志模块 —— 运行日志按天写入、Error 日志独立管理，均支持 5MB 轮转"""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from datetime import datetime


def _get_app_dir() -> str:
    """返回 exe 或脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_log_dir() -> str:
    """返回 logs 目录路径，不存在则创建。"""
    log_dir = os.path.join(_get_app_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# ── 自动轮转 Handler ──────────────────────────────────────────

class _SizeRotatingHandler(logging.FileHandler):
    """文件超过 5 MB 自动轮转。

    命名规则：
        error.log → error-1.log → error-2.log → ...
        run_20260721.log → run_20260721-1.log → run_20260721-2.log → ...
    """

    MAX_BYTES = 5 * 1024 * 1024  # 5 MB

    def emit(self, record):
        try:
            if self.stream is not None:
                try:
                    if os.path.getsize(self.baseFilename) >= self.MAX_BYTES:
                        self._do_rotate()
                except OSError:
                    pass
        except Exception:
            pass
        super().emit(record)

    def _do_rotate(self):
        """关闭当前文件 → 按序号改名 → 下次 emit 时自动打开新文件。"""
        self.close()
        base = self.baseFilename
        name, ext = os.path.splitext(base)
        i = 1
        while os.path.exists(f"{name}-{i}{ext}"):
            i += 1
        os.rename(base, f"{name}-{i}{ext}")


# ── 初始化 Logger ─────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("maintenance_app")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_dir = _get_log_dir()
    today = datetime.now().strftime("%Y%m%d")

    # 运行日志 —— 按天分文件，同一天追加写入
    run_handler = _SizeRotatingHandler(
        os.path.join(log_dir, f"run_{today}.log"),
        encoding="utf-8",
    )
    run_handler.setLevel(logging.INFO)
    run_handler.setFormatter(fmt)
    logger.addHandler(run_handler)

    # 错误日志 —— 所有错误汇总到一个文件
    err_handler = _SizeRotatingHandler(
        os.path.join(log_dir, "error.log"),
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)
    logger.addHandler(err_handler)

    return logger


APP_LOGGER = _setup_logger()


# ── 公共接口 ──────────────────────────────────────────────────

def log_info(message: str) -> None:
    """记录普通信息（仅写入当日运行日志）。"""
    APP_LOGGER.info(message)


def log_error(message: str) -> None:
    """记录错误（同时写入运行日志和 error.log）。"""
    APP_LOGGER.error(f"{message}\n{traceback.format_exc()}")


def get_log_dir() -> str:
    """返回 logs 目录路径。"""
    return _get_log_dir()


# ── 全局异常捕获 ──────────────────────────────────────────────

def install_exception_hook() -> None:
    """安装全局未捕获异常钩子，覆盖主线程、子线程、Tkinter 回调三个渠道。"""

    # 1. 主线程未捕获异常
    def _main_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        APP_LOGGER.critical(f"主线程未捕获异常:\n{tb_text}")
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _main_hook

    # 2. 子线程未捕获异常（Python 3.8+）
    def _thread_hook(args: threading.ExceptHookArgs):
        tb_text = "".join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        ))
        APP_LOGGER.critical(f"子线程未捕获异常:\n{tb_text}")

    threading.excepthook = _thread_hook


def install_qt_hook() -> None:
    """安装 Qt 消息处理器，将 Qt 运行时警告输出到日志。"""
    def _qt_handler(msg_type, context):
        msg = f"Qt {msg_type.name}: {context}"
        APP_LOGGER.warning(msg)

    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType
        qInstallMessageHandler(_qt_handler)
    except ImportError:
        pass
