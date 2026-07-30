"""手动录入重点客户弹窗 (PySide6 版本)"""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.logger import log_info
from ui.starred_cache import StarredCache
from utils import center_window
from ui.dialog_utils import configure_dialog, install_close_handler


class StarredInputDialog:
    """弹窗：粘贴客户名（任意分隔符/换行），一键导入到缓存表。

    点击「确认录入」后：
    - 自动识别新客户与已存在客户
    - 自动导入新客户到缓存表
    - 弹窗关闭，通过 on_done 回调通知上层
    """

    def __init__(self, parent, starred_cache: StarredCache, on_done=None):
        self.starred_cache = starred_cache
        self.on_done = on_done

        self.dialog = QDialog(parent)
        configure_dialog(self.dialog)
        install_close_handler(self.dialog)
        self.dialog.setWindowTitle("手动录入重点客户")
        self.dialog.resize(600, 500)
        self.dialog.setMinimumSize(480, 360)
        center_window(self.dialog, 600, 500)

        layout = QVBoxLayout(self.dialog)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(6)

        # 提示
        hint = QLabel("请输入/粘贴重点客户名称，支持任意符号或换行分隔：")
        hint.setStyleSheet("color: #555555; font-size: 13px;")
        layout.addWidget(hint)

        # 文本输入框
        self.textbox = QTextEdit()
        self.textbox.setFont(QFont("Microsoft YaHei UI", 13))
        self.textbox.setStyleSheet(
            "QTextEdit { border: 1px solid #D0D0D0; border-radius: 8px; padding: 8px; }"
        )
        layout.addWidget(self.textbox, 1)

        # 状态/预览提示
        self.preview_label = QLabel("")
        self.preview_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.preview_label)

        # 按钮栏
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.confirm_btn = QPushButton("确认录入")
        self.confirm_btn.setObjectName("accentBtn")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.confirm_btn)

        layout.addLayout(btn_row)

        self.dialog.show()

    @staticmethod
    def _parse_names(text: str) -> list[str]:
        parts = re.split(r'[\n\r,;，；、。|/\\\s\t]+', text)
        names = []
        for p in parts:
            p = p.strip().strip("'").strip('"')
            if p:
                names.append(p)
        return names

    def _on_confirm(self):
        text = self.textbox.toPlainText().strip()
        if not text:
            self.preview_label.setText("请输入客户名称")
            return

        names = self._parse_names(text)
        if not names:
            self.preview_label.setText("未识别到有效的客户名称")
            return

        # 去重（保持顺序）
        seen = set()
        unique_input = [n for n in names if not (n in seen or seen.add(n))]

        existing = set(self.starred_cache.get_all())
        new_names = [n for n in unique_input if n not in existing]
        dup_names = [n for n in unique_input if n in existing]

        # 一键导入新客户
        if new_names:
            self.starred_cache.add_batch(new_names)
            log_info(f"手动导入重点客户，共 {len(new_names)} 个")

        # 关闭弹窗，回调通知上层（按新的四参格式）
        self.dialog.accept()
        if self.on_done:
            self.on_done(len(new_names), len(dup_names), len(unique_input))
