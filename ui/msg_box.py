"""中文确认弹窗 helper：所有 Yes/No 都换成中文"""

from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


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


def show_about(parent, title: str, app_name: str, rows: list[tuple[str, str]]) -> None:
    """关于弹窗：无 OK 按钮 + 紧凑不留白 + 链接可点击 + × 可关闭。

    用 QDialog 自定义弹窗，绕开 QMessageBox 在 NoButton 模式下拦截 × 关闭的问题。
    × 按钮、ESC 均可关闭。URL 自动渲染为可点击链接（openExternalLinks）。
    弹窗宽度按内容自适应（不强制固定宽），减少右侧留白。
    """
    from PySide6.QtGui import QShortcut, QKeySequence

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    # 显式启用关闭按钮，确保右上角 × 可关闭
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowCloseButtonHint)
    # 弹窗宽度自适应：最小 320、最大 520（容纳 URL 自然换行）
    dlg.setMinimumWidth(320)
    dlg.setMaximumWidth(520)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(16, 14, 16, 14)
    # 标题与正文之间间距更大（Qt RichText 对 margin-top 支持不可靠，用 layout spacing 控制）
    layout.setSpacing(14)

    # 应用名（大号蓝色加粗）
    name_label = QLabel(app_name)
    name_label.setStyleSheet(
        "color: #2563EB; font-size: 16px; font-weight: bold;"
    )
    layout.addWidget(name_label)

    # 渲染每行（链接值自动加 <a>）
    def _value_html(value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            return f"<a href='{value}'>{value}</a>"
        return value

    body_html = "<br>".join(
        f"<b>{label}</b> {_value_html(value)}" for label, value in rows
    )
    body_label = QLabel(
        f"<div style='line-height:1.7; color:#333333;'>{body_html}</div>"
    )
    body_label.setTextFormat(Qt.TextFormat.RichText)
    body_label.setOpenExternalLinks(True)  # 让链接可点击打开外部链接
    body_label.setWordWrap(True)
    layout.addWidget(body_label)

    # ESC 键可关闭
    shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), dlg)
    shortcut.activated.connect(dlg.close)

    dlg.exec()