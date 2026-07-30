"""日志查看弹窗 —— PySide6 版本"""

from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils import center_window
from ui.logger import get_log_dir
from ui.dialog_utils import configure_dialog, install_close_handler


class LogViewer:
    """日志查看器。"""

    @staticmethod
    def _build_window(parent, title: str, content: str) -> None:
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.resize(800, 500)
        configure_dialog(dialog)
        install_close_handler(dialog)
        center_window(dialog, 800, 500)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 11))
        text.setPlainText(content)
        layout.addWidget(text)

        dialog.exec()

    @staticmethod
    def show_error(parent) -> None:
        """查看报错日志。"""
        log_dir = get_log_dir()
        err_path = os.path.join(log_dir, "error.log")
        if os.path.exists(err_path):
            try:
                with open(err_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"读取报错日志失败: {e}"
            title = "报错日志 — error.log"
        else:
            content = "暂无报错日志。"
            title = "报错日志"
        LogViewer._build_window(parent, title, content)

    @staticmethod
    def show_run(parent) -> None:
        """查看运行日志。"""
        log_dir = get_log_dir()
        today = datetime.now().strftime("%Y%m%d")
        run_path = os.path.join(log_dir, f"run_{today}.log")
        if os.path.exists(run_path):
            try:
                with open(run_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"读取运行日志失败: {e}"
            title = f"运行日志 — run_{today}.log"
        else:
            content = "暂无运行日志。"
            title = "运行日志"
        LogViewer._build_window(parent, title, content)
