"""重点客户过保合同弹窗 (PySide6 版本)"""

from __future__ import annotations

import math
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.logger import log_info
from ui.column_filter_popup import ColumnFilterPopup
from utils import center_window, export_to_csv
from ui.dialog_utils import configure_dialog, install_close_handler


class ExpiryStarredView:
    """弹窗展示重点客户的过保合同（仅 P 类）。"""

    SEQ_COL = "#"
    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    def __init__(self, parent, df: pd.DataFrame):
        self.original_df = df
        self.sort_col: str | None = None
        self.sort_asc: bool = True
        self.active_filters: dict[str, set] = {}
        self._build(parent)

    def _build(self, parent):
        dialog = QDialog(parent)

        configure_dialog(dialog, show_close_button=True)

        install_close_handler(dialog)
        dialog.setWindowTitle("重点客户过保合同")
        dialog.resize(1000, 620)
        dialog.setMinimumSize(600, 400)
        center_window(dialog, 1000, 620)
        self.dialog = dialog

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title = QLabel(f"重点客户过保合同（仅 P 类）— 共 {len(self.original_df)} 条记录")
        title.setFont(QFont("Microsoft YaHei UI", 16))
        title.setStyleSheet("color: #1F6AA5; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.filter_layout = QHBoxLayout()
        layout.addLayout(self.filter_layout)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_click)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("accentBtn")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

        self._fill_table(self.original_df)
        self._build_filter_bar()
        dialog.exec()

    @staticmethod
    def _reorder_columns(columns) -> list:
        cols = list(columns)
        priority = []
        for kw in ["过保日期", "客户意向", "不续保原因"]:
            for c in cols:
                if kw in str(c) and c not in priority:
                    priority.append(c)
                    break
        result = [c for c in priority if c in cols]
        result += [c for c in cols if c not in result]
        return result

    def _fill_table(self, df: pd.DataFrame):
        self._display_df = df.copy()
        reordered = self._reorder_columns(list(df.columns))
        display_cols = [self.SEQ_COL] + reordered

        model = QStandardItemModel(len(df), len(display_cols))
        model.setHorizontalHeaderLabels(display_cols)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            item = QStandardItem(str(row_idx + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
            model.setItem(row_idx, 0, item)

            for col_idx, col in enumerate(reordered):
                val = row[col]
                text = self._fmt_val(val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(row_idx, col_idx + 1, item)

        self.table.setModel(model)
        self.table.resizeColumnsToContents()

    def _build_filter_bar(self):
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filter_cols = [c for c in self.original_df.columns
                       for kw in self.FILTER_KEYWORDS if kw in str(c)]
        if not filter_cols:
            return

        label = QLabel("筛选：")
        label.setStyleSheet("color: #888888; font-size: 12px;")
        self.filter_layout.addWidget(label)

        for col in filter_cols:
            clean = self._clean_col(col)
            vals = sorted(self.original_df[col].dropna().astype(str).unique().tolist())
            btn = QPushButton(f"▽ {clean}")
            btn.setObjectName("filterBtn")
            btn.clicked.connect(lambda checked, c=col, vs=vals: self._open_filter(c, vs))
            self.filter_layout.addWidget(btn)

        self.filter_layout.addStretch()

    def _open_filter(self, col: str, vals: list[str]):
        selected = self.active_filters.get(col, set(vals))
        ColumnFilterPopup(self.dialog, self._clean_col(col), vals, selected,
                          on_apply=self._apply_filter)

    def _apply_filter(self, col: str, selected: set):
        self.active_filters[col] = selected
        self.sort_col = None
        self.sort_asc = True
        self._fill_table(self._get_display_df())
        self._build_filter_bar()

    def _get_display_df(self):
        df = self.original_df.copy()
        for col, allowed in self.active_filters.items():
            if col not in df.columns:
                continue
            if not allowed:
                return df.iloc[:0].copy()
            ser = df[col].fillna("（空）").astype(str)
            df = df[ser.isin(allowed)]
        if self.sort_col and self.sort_col in df.columns:
            df = df.sort_values(self.sort_col, ascending=self.sort_asc).reset_index(drop=True)
        return df

    def _on_header_click(self, logical_index: int):
        model = self.table.model()
        col = model.headerData(logical_index, Qt.Orientation.Horizontal)
        if col == self.SEQ_COL or "名称" in str(col):
            return

        df = self._get_display_df()
        if col not in df.columns:
            return

        self.sort_asc = not self.sort_asc if self.sort_col == col else True
        self.sort_col = col
        df = df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)
        self._fill_table(df)

    @staticmethod
    def _clean_col(col: str) -> str:
        return col.replace("\n", " ") if isinstance(col, str) else str(col)

    @staticmethod
    def _fmt_val(val) -> str:
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return ""
            if val == int(val):
                return f"{int(val):,}"
            return f"{val:,.2f}"
        if isinstance(val, int):
            return f"{val:,}"
        if pd.isna(val):
            return ""
        return str(val)

    def _export_csv(self):
        df = getattr(self, "_display_df", None)
        if df is None or df.empty:
            QMessageBox.warning(self.dialog, "提示", "没有数据可导出")
            return
        log_info(f"导出CSV [重点客户过保合同]: 重点客户过保合同.csv，共 {len(df)} 行")
        export_to_csv(df, self.dialog, "重点客户过保合同.csv")

    @classmethod
    def show(cls, parent, df: pd.DataFrame):
        cls(parent, df)
