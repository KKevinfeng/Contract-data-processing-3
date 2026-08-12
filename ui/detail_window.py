"""客户合同详情弹窗 (PySide6 版本)"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QTextEdit, QSplitter,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.logger import log_info
from utils import center_window, export_to_csv
from ui.dialog_utils import configure_dialog, install_close_handler


class CustomerDetailWindow:
    """弹出窗口：展示某客户在原始数据中的合同记录。"""

    @classmethod
    def show(cls, parent, df: pd.DataFrame, title_text: str, customer_name: str):
        dialog = QDialog(parent)

        configure_dialog(dialog)

        install_close_handler(dialog)
        dialog.setWindowTitle(f"客户合同详情 — {customer_name}")
        dialog.resize(1100, 600)
        dialog.setMinimumSize(800, 450)
        center_window(dialog, 1100, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 标题
        title = QLabel(title_text)
        title.setFont(QFont("Microsoft YaHei UI", 16))
        title.setStyleSheet("color: #1F6AA5; font-weight: bold;")
        layout.addWidget(title)

        # 上下分割：表格 + 详情
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 表格
        columns = list(df.columns)
        model = QStandardItemModel(len(df), len(columns))
        model.setHorizontalHeaderLabels(columns)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, col in enumerate(columns):
                val = row[col]
                if isinstance(val, float):
                    text = f"{val:,.2f}"
                elif isinstance(val, int):
                    text = f"{val:,}"
                elif pd.isna(val):
                    text = ""
                else:
                    text = str(val).replace("\n", " | ")
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(row_idx, col_idx, item)

        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        # 大多数列按内容自适应，"产品名称型号"列用 Stretch 占满剩余空间
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for col_idx, col in enumerate(columns):
            if "产品名称型号" in col or "产品名称" in col:
                table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
                break
        table.verticalHeader().setVisible(False)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.resizeColumnsToContents()
        splitter.addWidget(table)

        # 详情文本区
        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setMaximumHeight(150)
        detail_text.setFont(QFont("Microsoft YaHei UI", 11))
        splitter.addWidget(detail_text)

        # 找产品列
        product_col = None
        for c in columns:
            if "产品名称" in c and "型号" in c:
                product_col = c
                break

        # 选中行 → 显示详情
        def on_selection_changed():
            idx = table.currentIndex()
            if not idx.isValid():
                return
            row = idx.row()
            detail_text.clear()
            if product_col:
                val = df.iloc[row][product_col]
                text = str(val) if not pd.isna(val) else ""
                detail_text.setPlainText(text)
            else:
                lines = []
                for c in columns:
                    val = df.iloc[row][c]
                    lines.append(f"{c}：{val if not pd.isna(val) else ''}")
                detail_text.setPlainText("\n".join(lines))

        table.selectionModel().selectionChanged.connect(on_selection_changed)

        layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("accentBtn")
        export_btn.clicked.connect(lambda: export_to_csv(df, dialog, f"合同详情_{customer_name}.csv"))
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)
        dialog.exec()
