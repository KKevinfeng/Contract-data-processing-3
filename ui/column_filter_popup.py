"""列筛选弹窗 (PySide6 版本)"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils import center_window
from ui.dialog_utils import configure_dialog, install_close_handler


class ColumnFilterPopup:
    """可复用的列值多选筛选弹窗。"""

    def __init__(self, parent, col_name: str, all_values: list[str],
                 selected: set[str], on_apply):
        self.col_name = col_name
        self.on_apply = on_apply
        self.selected = set(selected) if selected else set(all_values)
        self.all_values = all_values
        self.cb_widgets: dict[str, QCheckBox] = {}

        self._build(parent)

    def _build(self, parent):
        dialog = QDialog(parent)

        configure_dialog(dialog, show_close_button=True)

        install_close_handler(dialog)
        dialog.setWindowTitle(f"筛选 - {self.col_name}")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.dialog = dialog

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 按钮行
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.setObjectName("grayBtn")
        select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(select_all_btn)

        select_none_btn = QPushButton("取消全选")
        select_none_btn.setObjectName("grayBtn")
        select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(select_none_btn)

        btn_row.addStretch()
        count_label = QLabel(f"共 {len(self.all_values)} 项")
        count_label.setStyleSheet("color: #888888; font-size: 12px;")
        btn_row.addWidget(count_label)
        layout.addLayout(btn_row)

        # 可滚动复选框列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(2)

        for val in self.all_values:
            display_text = str(val) if val else "（空）"
            cb = QCheckBox(display_text)
            cb.setChecked(val in self.selected)
            cb.setFont(QFont("Microsoft YaHei UI", 13))
            cb.stateChanged.connect(
                lambda state, v=val: self._on_toggle(v, state)
            )
            self.cb_widgets[val] = cb
            list_layout.addWidget(cb)

        list_layout.addStretch()
        scroll.setWidget(list_widget)
        layout.addWidget(scroll)

        # 确定按钮
        apply_btn = QPushButton("确定")
        apply_btn.setObjectName("accentBtn")
        apply_btn.clicked.connect(self._apply)
        layout.addWidget(apply_btn)

        # 尺寸
        item_count = len(self.all_values)
        visible = min(item_count, 12)
        win_w = max(min(max(len(str(v)) for v in self.all_values) * 10 + 60, 500), 240)
        dialog.resize(win_w, max(280, visible * 32 + 110))
        center_window(dialog, win_w, dialog.height())

        dialog.exec()

    def _on_toggle(self, val: str, state):
        if state == Qt.CheckState.Checked.value:
            self.selected.add(val)
        else:
            self.selected.discard(val)

    def _select_all(self):
        for v, cb in self.cb_widgets.items():
            cb.setChecked(True)

    def _select_none(self):
        for v, cb in self.cb_widgets.items():
            cb.setChecked(False)

    def _apply(self):
        self.selected = {v for v, cb in self.cb_widgets.items() if cb.isChecked()}
        self.dialog.accept()
        if self.on_apply:
            self.on_apply(self.col_name, self.selected)
