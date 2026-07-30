"""对话框工具函数 — 配置对话框窗口属性并安装关闭事件处理器"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Qt


def configure_dialog(dialog: QDialog, show_close_button: bool = True):
    """配置对话框窗口属性。

    Args:
        dialog: 要配置的 QDialog 实例
        show_close_button: 是否确保关闭按钮可见
    """
    dialog.setWindowFlags(
        Qt.Window
        | Qt.WindowMinimizeButtonHint
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowCloseButtonHint
    )

    dialog.setAttribute(Qt.WA_DeleteOnClose, False)

    if show_close_button:
        dialog.setWindowFlag(Qt.WindowCloseButtonHint, True)


def install_close_handler(dialog: QDialog):
    """为对话框安装关闭事件处理器。

    重写 closeEvent，正确调用 dialog.done() 关闭对话框，
    避免直接销毁导致的潜在问题。

    Args:
        dialog: QDialog 实例
    """

    def safe_close_event(event):
        try:
            event.accept()
            dialog.done(QDialog.Accepted)
        except Exception:
            event.accept()
            dialog.reject()

    dialog.closeEvent = safe_close_event
