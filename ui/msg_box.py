"""中文确认弹窗 helper：所有 Yes/No 都换成中文"""

from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def confirm(parent, title: str, text: str) -> bool:
    """弹出中文"是 / 否"确认弹窗。返回 True 表示用户选了"是"。

    用 QMessageBox 自定义按钮，因为 .question() 默认是英文 Yes/No。
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setWindowTitle(title)
    msg.setText(text)

    yes_btn = msg.addButton("是", QMessageBox.ButtonRole.YesRole)
    no_btn = msg.addButton("否", QMessageBox.ButtonRole.NoRole)
    msg.setDefaultButton(no_btn)

    msg.exec()
    return msg.clickedButton() == yes_btn


def info(parent, title: str, text: str) -> None:
    """中文信息提示（用 QMessageBox.information 即可，标题自带"提示"）。"""
    QMessageBox.information(parent, title, text)


def warn(parent, title: str, text: str) -> None:
    """中文警告。"""
    QMessageBox.warning(parent, title, text)


def error(parent, title: str, text: str) -> None:
    """中文错误提示。"""
    QMessageBox.critical(parent, title, text)
