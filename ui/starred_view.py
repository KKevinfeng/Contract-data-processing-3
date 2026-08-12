"""查看重点客户弹窗 (PySide6 版本)"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.msg_box import confirm, info, warn, error
from ui.logger import log_info
from utils import center_window, export_to_csv
from ui.dialog_utils import configure_dialog, install_close_handler


class StarredView:
    """重点客户弹窗 —— 从缓存展示标星客户表，支持删除与清空。"""

    def __init__(self, parent, cache, on_changed=None):
        self.cache = cache
        self.on_changed = on_changed
        self._dirty = False
        self._build(parent)
        self._refresh_table()  # 先填数据，再 exec() 显示
        self.dialog.exec()

    def _build(self, parent):
        self.dialog = QDialog(parent)

        configure_dialog(self.dialog, show_close_button=True)

        install_close_handler(self.dialog)
        self.dialog.setWindowTitle("重点客户")
        self.dialog.resize(600, 480)
        self.dialog.setFixedSize(600, 480)
        center_window(self.dialog, 600, 480)

        layout = QVBoxLayout(self.dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 标题栏
        title_row = QHBoxLayout()
        title = QLabel("重点客户")
        title.setFont(QFont("Microsoft YaHei UI", 16))
        title.setStyleSheet("color: #1F6AA5; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888888; font-size: 13px;")
        title_row.addWidget(self.count_label)

        self.clear_btn = QPushButton("清空全部")
        self.clear_btn.setObjectName("dangerBtn")
        self.clear_btn.clicked.connect(self._on_clear_all)
        title_row.addWidget(self.clear_btn)
        layout.addLayout(title_row)

        # 表格
        self.model = QStandardItemModel(0, 3)
        self.model.setHorizontalHeaderLabels(["序号", "最终客户名称", "操作"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        # 序号列固定窄
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 60)
        # 客户名称列自适应拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # 操作列固定窄
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_cell_click)
        layout.addWidget(self.table, 1)  # stretch=1 填充剩余空间

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("accentBtn")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

        self.dialog.finished.connect(self._on_close)

    def _refresh_table(self):
        df = self.cache.get_dataframe()
        count = len(df)
        self.count_label.setText(f"共 {count} 个客户")
        self.clear_btn.setEnabled(count > 0)

        self.model.setRowCount(count)
        for idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, val in enumerate([str(row["序号"]), str(row["最终客户名称"]), "删除"]):
                item = QStandardItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                self.model.setItem(idx, col_idx, item)

    def _on_close(self):
        if self._dirty and self.on_changed:
            self.on_changed()

    def _on_cell_click(self, index):
        if index.column() != 2:
            return
        name = self.model.item(index.row(), 1)
        if not name:
            return
        name = name.text().strip()
        if not name:
            return

        reply = confirm(self.dialog, "确认删除", f"确定要删除重点客户「{name}」吗？\n\n此操作不可撤销。")
        if reply:
            self.cache.remove(name)
            log_info(f"重点客户删除: {name}")
            self._dirty = True
            self._refresh_table()

    def _on_clear_all(self):
        df = self.cache.get_dataframe()
        count = len(df)
        if count == 0:
            return

        reply = confirm(self.dialog, "确认清空", f"确定要清空全部 {count} 个重点客户吗？\n\n此操作不可撤销。")
        if reply:
            self.cache.clear_all()
            log_info(f"重点客户全部清空，共 {count} 个")
            self._dirty = True
            self._refresh_table()

    def _export_csv(self):
        df = self.cache.get_dataframe()
        if df is None or df.empty:
            QMessageBox.warning(self.dialog, "提示", "没有数据可导出")
            return
        log_info(f"导出CSV [重点客户]: 重点客户.csv，共 {len(df)} 行")
        export_to_csv(df, self.dialog, "重点客户.csv")

    @classmethod
    def show(cls, parent, cache, on_changed=None):
        cls(parent, cache, on_changed=on_changed)
        parent_dialog = parent.findChild(QDialog)
