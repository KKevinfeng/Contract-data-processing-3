"""Tab 6：客户画像展示 (PySide6 版本)"""

from __future__ import annotations

import pandas as pd

from ui.dialog_utils import configure_dialog, install_close_handler
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QTableView, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.base_tab import QtBaseTab
from data_processor import compute_customer_total
from utils import classify_contract, parse_product_lines, center_window


class CustomerProfileTab(QtBaseTab):
    """客户画像展示页 — 支持重点客户标记展示。"""

    def __init__(self, on_double_click=None, get_starred_names=None):
        super().__init__(
            tab_name="客户画像展示",
            columns=["是否重点客户", "客户名称"],
            on_double_click=on_double_click,
            has_star=False,
            get_starred_names=get_starred_names,
            search_column="客户名称",
        )
        self._raw_df: pd.DataFrame | None = None

    def compute_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        self._raw_df = raw_df.copy()
        totals = compute_customer_total(raw_df)
        starred = set(self._get_starred()) if self._get_starred else set()
        totals["_sort"] = totals["最终客户名称"].apply(lambda n: 0 if n in starred else 1)
        totals = totals.sort_values(["_sort", "合同总金额"], ascending=[True, False]).reset_index(drop=True)

        result = pd.DataFrame()
        result["是否重点客户"] = totals["最终客户名称"].apply(
            lambda n: "重点客户" if n in starred else ""
        )
        result["客户名称"] = totals["最终客户名称"]
        return result

    def _on_double_click(self, index):
        model = self.table.model()
        if model is None:
            return
        row = index.row()
        name_item = model.item(row, 2)  # 客户名称在列 2
        if name_item:
            self._show_profile_detail(name_item.text())

    def _show_profile_detail(self, customer_name: str):
        raw_df = self._raw_df
        if raw_df is None:
            return

        from ui.industry_overrides import get_all as get_overrides

        cust_df = raw_df[raw_df["最终客户名称"] == customer_name].copy()
        if cust_df.empty:
            return

        overrides = get_overrides()
        override = overrides.get(customer_name, {})
        primary = override.get("一级行业", "") or str(
            cust_df["一级行业"].dropna().iloc[0]
        ) if "一级行业" in cust_df.columns and not cust_df["一级行业"].dropna().empty else ""
        secondary = override.get("二级行业", "") or str(
            cust_df["二级行业"].dropna().iloc[0]
        ) if "二级行业" in cust_df.columns and not cust_df["二级行业"].dropna().empty else ""

        total_amount = cust_df["合同金额（元）*"].sum()
        cust_df["合同类型"] = cust_df["合同编号*"].apply(classify_contract)
        p_amount = cust_df[cust_df["合同类型"] == "P"]["合同金额（元）*"].sum()
        m_amount = cust_df[cust_df["合同类型"] == "M"]["合同金额（元）*"].sum()
        s_amount = cust_df[cust_df["合同类型"] == "S"]["合同金额（元）*"].sum()

        product_totals: dict[str, int] = {}
        ps_df = cust_df[cust_df["合同类型"].isin(["P", "S"])]
        for _, r in ps_df.iterrows():
            for prod in parse_product_lines(r["产品名称型号"]):
                name = prod["name"]
                product_totals[name] = product_totals.get(name, 0) + prod["qty"]

        dialog = QDialog(self.frame)
        configure_dialog(dialog, show_close_button=True)
        install_close_handler(dialog)
        dialog.setWindowTitle(f"{customer_name} - 客户画像")
        dialog.resize(780, 600)
        dialog.setMinimumSize(600, 450)
        center_window(dialog, 780, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 16, 20, 16)

        # 标题
        title = QLabel(customer_name)
        title.setFont(QFont("Microsoft YaHei UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1F6AA5;")
        layout.addWidget(title)

        # 信息卡片（去掉灰底框，纯文字 + 间距，参考 2.X 老版本风格）
        card = QFrame()
        card.setStyleSheet("QFrame { background: transparent; border: none; }")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)

        row0 = QHBoxLayout()
        row0.setContentsMargins(0, 0, 0, 0)
        row0.setSpacing(40)
        row0.addLayout(self._info_pair("一级行业", primary or "未知", "#333"))
        row0.addLayout(self._info_pair("二级行业", secondary or "未知", "#333"))
        row0.addStretch()
        cl.addLayout(row0)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(40)
        row1.addLayout(self._info_pair("下单总额", f"{total_amount:,.2f} 元", "#1F6AA5"))
        row1.addLayout(self._info_pair("P 产品", f"{p_amount:,.2f} 元", "#E67E22"))
        row1.addLayout(self._info_pair("M 维保", f"{m_amount:,.2f} 元", "#27AE60"))
        row1.addLayout(self._info_pair("S 服务", f"{s_amount:,.2f} 元", "#8E44AD"))
        row1.addStretch()
        cl.addLayout(row1)

        layout.addWidget(card)

        # 产品清单
        prod_header = QLabel("下单产品清单（P / S 类）")
        prod_header.setStyleSheet("color: #555; font-weight: bold; font-size: 13px;")
        layout.addWidget(prod_header)

        sorted_products = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)
        model = QStandardItemModel(len(sorted_products), 3)
        model.setHorizontalHeaderLabels(["#", "产品名称", "数量"])
        for pi, (pname, pqty) in enumerate(sorted_products):
            for ci, val in enumerate([str(pi + 1), pname, f"{pqty:,}"]):
                item = QStandardItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(pi, ci, item)

        table = QTableView()
        table.setModel(model)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        # # 列固定窄
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 50)
        # 产品名称列自适应拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # 数量列固定窄
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 100)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table, 1)

        dialog.exec()

    @staticmethod
    def _info_pair(label_text: str, value_text: str, value_color: str) -> QHBoxLayout:
        """返回一组 (label + value) 的横向 layout，不使用 QWidget 容器，避免出现 cell 边框。"""
        lo = QHBoxLayout()
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(6)
        lb = QLabel(label_text + ":")
        lb.setStyleSheet("color: #888; font-size: 13px; background: transparent;")
        lo.addWidget(lb)
        vl = QLabel(value_text)
        vl.setStyleSheet(f"color: {value_color}; font-weight: bold; font-size: 13px; background: transparent;")
        lo.addWidget(vl)
        return lo
