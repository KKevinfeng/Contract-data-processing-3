"""进度弹窗 —— PySide6 版本，使用 QProgressDialog。"""

from __future__ import annotations

from PySide6.QtWidgets import QProgressDialog, QApplication
from PySide6.QtCore import Qt


class ProgressPopup:
    """模态进度弹窗，显示状态文字、百分比和进度条。"""

    def __init__(self, parent=None, title: str = "正在导入...", on_close=None):
        self._dialog = QProgressDialog(title, None, 0, 100, parent)
        self._dialog.setWindowTitle(title)
        self._dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setCancelButton(None)
        self._dialog.setAutoClose(False)
        self._dialog.setAutoReset(False)
        self._dialog.setValue(0)
        self._dialog.setStyleSheet(
            "QProgressDialog { font-family: 'Microsoft YaHei UI'; font-size: 13px; }"
            "QProgressBar { border: none; border-radius: 6px; background: #E8F0FE; "
            "text-align: center; height: 20px; }"
            "QProgressBar::chunk { background: #1F6AA5; border-radius: 6px; }"
        )
        # 用户点击 × 关闭弹窗时回调（用于取消后台加载）
        self._on_close = on_close
        if on_close is not None:
            self._dialog.canceled.connect(on_close)

    def set_progress(self, value: float, status: str = ""):
        """设置进度 0.0 ~ 1.0，可附带状态文字。"""
        pct = int(value * 100)
        self._dialog.setValue(pct)
        if status:
            self._dialog.setLabelText(status)
        QApplication.processEvents()

    def close(self):
        """关闭弹窗。"""
        self._dialog.close()
