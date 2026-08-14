"""Tab 4：产品销量统计 (PySide6 版本)"""

import json
import os
import pandas as pd
from PySide6.QtWidgets import QPushButton, QMessageBox, QHeaderView
from PySide6.QtCore import Qt

from ui.base_tab import QtBaseTab
from data_processor import compute_product_sales, get_product_p_contracts
from ui.merge_dialog import ProductMergeDialog
from ui.logger import log_error, log_info

RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "merge_rules.json")


def _load_rules() -> dict[str, set[str]]:
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {k: set(v) for k, v in raw.items()}
    except Exception as e:
        log_error(f"加载产品合并规则失败: {e}")
    return {}


def _save_rules(rules: dict[str, set[str]]):
    try:
        data = {k: sorted(v) for k, v in rules.items()}
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error(f"保存产品合并规则失败: {e}")


class ProductSalesTab(QtBaseTab):
    """产品销量统计页 —— 展示各产品售卖台数，支持产品名称合并。"""

    def __init__(self, on_double_click=None, on_data_change=None):
        super().__init__(
            tab_name="产品销量统计",
            columns=["产品名称", "售卖总台数"],
            on_double_click=on_double_click,
            search_column="产品名称",
        )
        self.merge_rules: dict[str, set[str]] = _load_rules()
        self._on_data_change = on_data_change
        self._raw_df = None

    def build(self):
        frame = super().build()

        # 注意：列宽/resize 模式不能在 build() 里设置，
        # 因为此时表格尚未绑定模型（0 列），setSectionResizeMode/setColumnWidth 会越界，
        # 导致 PySide6 在 C++ 层访问冲突崩溃（0xc0000005 / 0xc000001d）。
        # 列宽统一在 _rebuild_model() 中设置（此时模型已就位，列数正确）。

        merge_btn = QPushButton("产品名称合并")
        merge_btn.setObjectName("ghostBtn")
        merge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        merge_btn.setFixedHeight(32)
        merge_btn.clicked.connect(self._open_merge_dialog)

        # 把按钮塞到搜索栏的导出按钮之前
        if self.search_bar is not None:
            self.search_bar.layout().insertWidget(1, merge_btn)
        return frame

    def compute_data(self, raw_df):
        self._raw_df = raw_df
        return compute_product_sales(raw_df, merge_rules=self.merge_rules or None)

    def _rebuild_model(self, df: pd.DataFrame):
        super()._rebuild_model(df)
        # 基类会调用 resizeColumnsToContents + setStretchLastSection(True) 覆盖列宽，
        # 这里重新应用本 tab 的自定义列宽（产品名称 stretch，售卖总台数固定）
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 120)

    def _open_merge_dialog(self):
        if self._raw_df is None:
            QMessageBox.warning(self.frame, "提示", "请先加载数据文件")
            return

        original = compute_product_sales(self._raw_df, merge_rules=None)
        product_names = sorted(original["产品名称"].unique().tolist())

        def on_apply(rules: dict):
            self.merge_rules = {k: set(v) for k, v in rules.items()}
            _save_rules(self.merge_rules)
            if self._on_data_change:
                self._on_data_change()

        ProductMergeDialog.show(
            self.frame.window(),
            product_names,
            self.merge_rules,
            on_apply,
        )
