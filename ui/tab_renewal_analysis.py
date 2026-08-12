"""Tab 4：过保数据分析 (PySide6 版本) — 基于 Tab3 数据展示 P 类合同"""

from __future__ import annotations

import math
import os
import threading

import pandas as pd

from ui.dialog_utils import configure_dialog, install_close_handler
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QDialog,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont

from ui.column_filter_popup import ColumnFilterPopup
from ui.msg_box import confirm, info, warn, error
from ui.logger import log_error, log_info
from utils import classify_contract, extract_contract_year, center_window, export_to_csv

RENEWAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "renewal_details.xlsx")
GIFT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gift_channels.xlsx")


def _safe_read_excel(path: str) -> pd.DataFrame:
    """读取 xlsx 文件，自动处理 UTF-16 BOM 前缀（早期版本误存格式）。"""
    import io
    with open(path, "rb") as f:
        raw = f.read()
    # 跳过 UTF-16-LE BOM
    if raw[:2] == b"\xff\xfe":
        text = raw[2:].decode("utf-16-le", errors="ignore")
        cleaned = text.encode("latin-1", errors="ignore")
        return pd.read_excel(io.BytesIO(cleaned))
    return pd.read_excel(path)


class RenewalAnalysisTab:
    """过保数据分析页 — 数据来源于 Tab3，统计续保情况。"""

    SEQ_COL = "#"
    RENEWED_FILTER = {1: "已有续保合同", 2: "未有续保合同"}
    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    DISPLAY_COLS = [
        "#", "最终客户名称", "合同编码", "合同金额", "负责销售", "过保年份",
        "*客户意向", "不续保原因", "维保合同", "维保金额",
    ]

    def __init__(self, expiry_tab, main_df_provider=None):
        self.expiry_tab = expiry_tab
        self.main_df_provider = main_df_provider
        self.frame = None
        self.table = None
        self.source_df: pd.DataFrame | None = None
        self.sort_col: str | None = None
        self.sort_asc: bool = True
        self.filter_has_renewed: set | None = None
        self.filter_year: set | None = None
        self.active_filters: dict = {}
        self._renewal_details: list[tuple[str, str, str]] = []
        self._renewal_index: dict[str, list[tuple[str, str, str]]] = {}
        self._gift_channels: set[str] = set()

    def build(self) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self._hint_label = QLabel("请先在「过保情况统计」中导入过保数据表")
        self._hint_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self._hint_label)

        # 筛选栏
        self.filter_layout = QHBoxLayout()
        filter_label = QLabel("筛选：")
        filter_label.setStyleSheet("color: #888; font-size: 12px;")
        self.filter_layout.addWidget(filter_label)

        self._renewed_btn = QPushButton("▽ 是否续保")
        self._renewed_btn.clicked.connect(self._open_renewed_filter)
        self._btn_gray(self._renewed_btn)
        self._renewed_btn.setCheckable(True)
        self.filter_layout.addWidget(self._renewed_btn)

        self._year_btn = QPushButton("▽ 筛选年份")
        self._year_btn.clicked.connect(self._open_year_filter)
        self._btn_gray(self._year_btn)
        self._year_btn.setCheckable(True)
        self.filter_layout.addWidget(self._year_btn)

        self._intent_btn = QPushButton("▽ 客户意向")
        self._intent_btn.clicked.connect(lambda: self._open_column_filter("*客户意向"))
        self._btn_gray(self._intent_btn)
        self._intent_btn.setCheckable(True)
        self.filter_layout.addWidget(self._intent_btn)

        self._reason_btn = QPushButton("▽ 不续保原因")
        self._reason_btn.clicked.connect(lambda: self._open_column_filter("不续保原因"))
        self._btn_gray(self._reason_btn)
        self._reason_btn.setCheckable(True)
        self.filter_layout.addWidget(self._reason_btn)

        self._sales_btn = QPushButton("▽ 负责销售")
        self._sales_btn.clicked.connect(lambda: self._open_column_filter("负责销售"))
        self._btn_gray(self._sales_btn)
        self._sales_btn.setCheckable(True)
        self.filter_layout.addWidget(self._sales_btn)

        # 列名 -> 筛选按钮的映射（弹窗关闭后用于复位）
        self.filter_buttons = {
            "*客户意向": self._intent_btn,
            "不续保原因": self._reason_btn,
            "负责销售": self._sales_btn,
        }

        self._clear_filter_btn = QPushButton("清除筛选")
        self._clear_filter_btn.setObjectName("dangerBtn")
        self._clear_filter_btn.clicked.connect(self._clear_filters)
        self._clear_filter_btn.setVisible(False)  # 初始无激活筛选，不显示
        self.filter_layout.addWidget(self._clear_filter_btn)
        self.filter_layout.addStretch()
        layout.addLayout(self.filter_layout)

        self._hide_filter_bar = False
        self._toggle_filter_visible()

        # 表格
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click_row)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_click)

        # 顶部操作按钮（续保明细 / 大礼包标记 / 导出 CSV），与筛选栏同一行，靠右对齐（参者 Tab6）
        renewal_btn = QPushButton("续保明细")
        renewal_btn.setObjectName("ghostBtn")
        renewal_btn.clicked.connect(self._open_renewal_detail)

        self._gift_btn = QPushButton("大礼包标记")
        self._gift_btn.setObjectName("ghostBtn")
        self._gift_btn.clicked.connect(self._open_gift_channel_manager)

        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("ghostBtn")
        export_btn.clicked.connect(self._export_csv)

        # 重新构建 layout 顺序：hint → 顶部按钮栏(筛选+操作) → 表格
        # 将原 layout 里的元素都取出，然后按新顺序重新添加
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        # 最终 layout 顺序
        layout.addWidget(self._hint_label)
        # 筛选栏 + 操作按钮同一行
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addLayout(self.filter_layout)
        top_bar.addStretch()
        top_bar.addWidget(renewal_btn)
        top_bar.addWidget(self._gift_btn)
        top_bar.addWidget(export_btn)
        layout.addLayout(top_bar)
        layout.addWidget(self.table, 1)

        self.frame = frame
        return frame

    @staticmethod
    def _btn_gray(btn):
        btn.setObjectName("filterBtn")

    def _toggle_filter_visible(self):
        """设置筛选栏所有控件可见性（不 takeAt，否则会从 layout 中移除）。
        当 Tab3 未导入数据时整个筛选栏自动隐藏，保持界面整洁。"""
        has_data = self.source_df is not None and not self.source_df.empty
        visible = (not self._hide_filter_bar) and has_data
        for i in range(self.filter_layout.count()):
            item = self.filter_layout.itemAt(i)
            w = item.widget()
            if not w:
                continue
            if w is self._clear_filter_btn:
                # 清除按钮只在该列有激活筛选时显示（无数据时强制隐藏），
                # 不受整栏 visible 的"有数据即显示"逻辑影响。
                w.setVisible(visible and self._has_active_filters())
            else:
                w.setVisible(visible)

    # ── 数据加载 ──

    def load_data(self):
        self.refresh()

    def refresh(self):
        if self.expiry_tab.source_df is None:
            self.source_df = None
            self._toggle_filter_visible()  # 无数据时隐藏筛选栏
            return
        if getattr(self, "_loading", False):
            return
        self._loading = True
        self._hint_label.setText("正在分析过保数据...")

        self._load_renewal_details()
        renewal_snapshot = list(self._renewal_details)
        expiry_df = self.expiry_tab.source_df

        def worker():
            try:
                self._result_df = self._process_data(expiry_df.copy(), renewal_snapshot)
            except Exception as e:
                log_error(f"过保数据分析失败: {e}")
                self._load_error = str(e)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        QTimer.singleShot(100, lambda: self._poll_result(thread))

    def _poll_result(self, thread):
        if thread.is_alive():
            QTimer.singleShot(100, lambda: self._poll_result(thread))
            return
        self._loading = False
        if getattr(self, "_load_error", None):
            self._hint_label.setText(f"分析失败: {self._load_error}")
            return
        if getattr(self, "_result_df", None) is not None:
            self.source_df = self._result_df
            self._load_renewal_details()
            self._load_gift_channels()
            self._fill_table()
            self._toggle_filter_visible()  # 数据更新后重新评估筛选栏可见性

    # ── 数据处理（完整逻辑从原始代码保留）──

    def _find_columns(self, df):
        contract_col = gift_col = enduser_col = expiry_col = intent_col = reason_col = sales_col = product_amount_col = None
        for c in df.columns:
            s = str(c).replace("\n", " ")
            if contract_col is None and ("合同编码" in s or "合同编号" in s):
                contract_col = c
            if gift_col is None and ("大礼包" in s and "客户" in s) and "原因" not in s and "意向" not in s:
                gift_col = c
            if enduser_col is None and "最终客户" in s and "大礼包" not in s:
                enduser_col = c
            if expiry_col is None and "过保日期" in s:
                expiry_col = c
            if intent_col is None and "客户意向" in s:
                intent_col = c
            if reason_col is None and "不续保原因" in s:
                reason_col = c
            if sales_col is None and "销售跟踪人" in s:
                sales_col = c
            if product_amount_col is None and "产品金额" in s:
                product_amount_col = c
        # 兜底（在循环之后运行，避免先于"最终客户"被匹配）
        if enduser_col is None:
            for c in df.columns:
                s = str(c).replace("\n", " ")
                if "合同单位" in s or "合同使用单位" in s:
                    enduser_col = c
                    break
        if enduser_col is None:
            for c in df.columns:
                s = str(c).replace("\n", " ")
                if "客户" in s and "意向" not in s and "原因" not in s and "大礼包" not in s:
                    enduser_col = c
                    break
        return contract_col, gift_col, enduser_col, expiry_col, intent_col, reason_col, sales_col, product_amount_col

    @staticmethod
    def _resolve_customer(row, gift_col, enduser_col):
        if gift_col:
            val = row.get(gift_col, "")
            if pd.notna(val) and str(val).strip():
                return str(val).strip()
        if enduser_col:
            val = row.get(enduser_col, "")
            if pd.notna(val):
                return str(val).strip()
        return ""

    @staticmethod
    def _format_year(values):
        result = []
        for v in values:
            if pd.isna(v):
                result.append("")
                continue
            try:
                dt = pd.to_datetime(v, errors="coerce")
                if pd.notna(dt):
                    result.append(dt.strftime("%Y"))
                else:
                    result.append(str(v).strip()[:4])
            except Exception:
                result.append(str(v).strip()[:4])
        return result

    def _process_data(self, expiry_df, renewal_snapshot):
        df = expiry_df.copy()
        contract_col, gift_col, enduser_col, expiry_col, intent_col, reason_col, sales_col, product_amount_col = self._find_columns(df)
        if contract_col is None:
            raise ValueError("未找到合同编号列")

        df["_type"] = df[contract_col].apply(classify_contract)
        df = df[df["_type"] == "P"].copy()
        if df.empty:
            raise ValueError("过保数据中无 P 类合同")

        df["最终客户名称"] = df.apply(lambda r: self._resolve_customer(r, gift_col, enduser_col), axis=1)

        sales_map = {}
        if sales_col:
            for _, r in df.iterrows():
                cust = str(r["最终客户名称"]).strip()
                if not cust or cust in sales_map:
                    continue
                v = r.get(sales_col, "")
                if pd.notna(v) and str(v).strip():
                    sales_map[cust] = str(v).strip()

        contract_amount_map = {}
        if product_amount_col:
            for _, r in df.iterrows():
                code = str(r[contract_col]).strip()
                cust = str(r["最终客户名称"]).strip()
                if not code or not cust:
                    continue
                key = (code, cust)
                try:
                    amt = float(r[product_amount_col]) if pd.notna(r[product_amount_col]) else 0.0
                except (TypeError, ValueError):
                    amt = 0.0
                contract_amount_map[key] = contract_amount_map.get(key, 0.0) + amt

        result = pd.DataFrame()
        result["最终客户名称"] = df["最终客户名称"]
        if enduser_col:
            result["_原始最终客户"] = df[enduser_col].astype(str).str.strip()
        else:
            result["_原始最终客户"] = df["最终客户名称"]
        result["合同编码"] = df[contract_col].astype(str).str.strip()
        result["过保年份"] = self._format_year(df[expiry_col]) if expiry_col else ""
        result["*客户意向"] = df[intent_col] if intent_col else ""
        result["不续保原因"] = df[reason_col] if reason_col else ""

        result = result.sort_values(["最终客户名称", "合同编码", "过保年份"], ascending=[True, True, False])
        result = result.groupby(["最终客户名称", "合同编码"], as_index=False).agg({
            "_原始最终客户": "first",
            "过保年份": "first",
            "*客户意向": lambda s: next((v for v in s if pd.notna(v) and str(v).strip()), ""),
            "不续保原因": lambda s: next((v for v in s if pd.notna(v) and str(v).strip()), ""),
        })

        def lookup_amount(row):
            key = (str(row["合同编码"]).strip(), str(row["最终客户名称"]).strip())
            total = contract_amount_map.get(key, 0.0)
            return f"{total:,.2f}" if total else ""
        result["合同金额"] = result.apply(lookup_amount, axis=1)
        result["负责销售"] = result["最终客户名称"].map(sales_map).fillna("")

        renewal_lookup = {}
        for old, new, _ in renewal_snapshot:
            renewal_lookup.setdefault(old, []).append(new)
        result["维保合同"] = result["合同编码"].apply(
            lambda c: ", ".join(renewal_lookup.get(c, [])) if c in renewal_lookup else ""
        )

        def sum_amount(codes_str):
            if not codes_str:
                return ""
            total = 0.0
            for code in codes_str.split(", "):
                amt = self._lookup_main_amount(code)
                if amt:
                    try:
                        total += float(amt.replace(",", ""))
                    except (ValueError, TypeError):
                        pass
            return f"{total:,.2f}" if total else ""
        result["维保金额"] = result["维保合同"].apply(sum_amount)

        result["_year"] = result["合同编码"].apply(extract_contract_year)
        result["_year"] = result["_year"].fillna(0).astype(int)
        result = result.sort_values(["_year", "过保年份", "合同编码"], ascending=[False, False, True]).reset_index(drop=True)
        result = result.drop(columns=["_year"])
        return result

    def _lookup_main_amount(self, wb_contract: str) -> str:
        if not wb_contract:
            return ""
        df = self.main_df_provider() if self.main_df_provider else None
        if df is None or df.empty or "合同编号*" not in df.columns:
            return ""
        mask = df["合同编号*"].astype(str).str.strip() == wb_contract
        if not mask.any():
            return ""
        amt = df.loc[mask, "合同金额（元）*"].iloc[0]
        if pd.isna(amt):
            return ""
        return f"{float(amt):,.2f}"

    # ── 表格填充 ──

    def _fill_table(self):
        df = self.source_df
        if df is None:
            return

        display_df = self._apply_filters(df)

        # 统计表格里实际标绿的"已续保"行数（用 _is_contract_renewed 判定，
        # 与表格里的绿色行一一对应）
        renewed_count = 0
        if not display_df.empty and "合同编码" in display_df.columns:
            for _, row in display_df.iterrows():
                contract = str(row.get("合同编码", ""))
                if not contract:
                    continue
                customer = str(row.get("最终客户名称", ""))
                expiry_year = str(row.get("过保年份", ""))
                if self._is_contract_renewed(contract, customer, expiry_year):
                    renewed_count += 1

        self._hint_label.setText(
            f"已加载 {len(df)} 条 P 类合同 / 已续保 {renewed_count} 条"
            + ("（当前筛选结果为空）" if display_df.empty else "")
        )

        if display_df.empty:
            self.table.setModel(QStandardItemModel())
            return

        model = QStandardItemModel(len(display_df), len(self.DISPLAY_COLS))
        model.setHorizontalHeaderLabels(self.DISPLAY_COLS)

        for idx, (_, row) in enumerate(display_df.iterrows()):
            contract = str(row["合同编码"]) if pd.notna(row["合同编码"]) else ""
            customer = str(row["最终客户名称"]) if pd.notna(row["最终客户名称"]) else ""
            expiry_year = str(row["过保年份"]) if pd.notna(row["过保年份"]) else ""
            orig_enduser = str(row["_原始最终客户"]) if pd.notna(row["_原始最终客户"]) else ""
            is_renewed = self._is_contract_renewed(contract, customer, expiry_year)
            is_gift = orig_enduser in self._gift_channels

            values = [
                str(idx + 1),
                customer,
                contract,
                str(row["合同金额"]) if pd.notna(row["合同金额"]) else "",
                str(row["负责销售"]) if pd.notna(row["负责销售"]) else "",
                str(row["过保年份"]) if pd.notna(row["过保年份"]) else "",
                str(row["*客户意向"]) if pd.notna(row["*客户意向"]) else "",
                str(row["不续保原因"]) if pd.notna(row["不续保原因"]) else "",
                str(row["维保合同"]) if pd.notna(row["维保合同"]) else "",
                str(row["维保金额"]) if pd.notna(row["维保金额"]) else "",
            ]

            for ci, val in enumerate(values):
                item = QStandardItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                # 颜色标记（用 setData(role) 而不是 setBackground 以避免 QSS 屏蔽）
                if is_gift and is_renewed:
                    item.setData(QColor("#66BB6A"), Qt.ItemDataRole.BackgroundRole)
                    item.setData(QColor("#C62828"), Qt.ItemDataRole.ForegroundRole)
                elif is_gift:
                    item.setData(QColor("#F4F4F5") if idx % 2 == 0 else QColor("#FCFCFC"),
                                  Qt.ItemDataRole.BackgroundRole)
                    item.setData(QColor("#C62828"), Qt.ItemDataRole.ForegroundRole)
                elif is_renewed:
                    item.setData(QColor("#66BB6A"), Qt.ItemDataRole.BackgroundRole)
                    item.setData(QColor("#FFFFFF"), Qt.ItemDataRole.ForegroundRole)
                else:
                    item.setData(QColor("#F4F4F5") if idx % 2 == 0 else QColor("#FCFCFC"),
                                  Qt.ItemDataRole.BackgroundRole)
                model.setItem(idx, ci, item)

        self.table.setModel(model)
        # 列宽策略：先按内容自动算宽度（resizeColumnsToContents），
        # # 列固定窄（序号），最终客户名称列额外按内容长度增加宽度
        self.table.resizeColumnsToContents()
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)

        if header.count() >= 10:
            # 调小不需要太宽的列，腾出空间给客户名
            for i in (3, 4, 5, 6, 9):  # 合同金额、负责销售、过保年份、*客户意向、维保金额
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(i, max(80, min(self.table.columnWidth(i), 110)))
            # # 列固定 50
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(0, 50)
            # 客户名称按内容自动（stretch 不限宽度）
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            # 合同编码、维保合同、不续保原因按内容（允许较宽）
            for i in (2, 7, 8):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    # ── 筛选 ──

    def _apply_filters(self, df, skip_column=None):
        """应用所有筛选到 df。
        skip_column: 在计算某个筛选列的可用选项时，跳过该列的自身筛选（模拟 Excel 行为）"""
        result = df.copy()
        if self.filter_has_renewed is not None and self.filter_has_renewed != {"Y", "N"}:
            if "Y" in self.filter_has_renewed and "N" not in self.filter_has_renewed:
                result = result[result.apply(
                    lambda r: self._is_contract_renewed(
                        str(r["合同编码"][0]) if isinstance(r["合同编码"], list) else str(r["合同编码"]) if pd.notna(r["合同编码"]) else "",
                        str(r["最终客户名称"]) if pd.notna(r["最终客户名称"]) else "",
                        str(r["过保年份"]) if pd.notna(r["过保年份"]) else "",
                    ), axis=1
                )]
            elif "N" in self.filter_has_renewed:
                result = result[~result.apply(
                    lambda r: self._is_contract_renewed(
                        str(r["合同编码"]) if pd.notna(r["合同编码"]) else "",
                        str(r["最终客户名称"]) if pd.notna(r["最终客户名称"]) else "",
                        str(r["过保年份"]) if pd.notna(r["过保年份"]) else "",
                    ), axis=1
                )]

        if self.filter_year is not None:
            if not self.filter_year:
                return result.iloc[:0]
            result = result[result["过保年份"].astype(str).isin(self.filter_year)]

        for col, allowed in self.active_filters.items():
            if col == skip_column:          # 跳过自身的筛选
                continue
            if col not in result.columns:
                continue
            if not allowed:
                return result.iloc[:0]
            ser = result[col].fillna("（空）").astype(str)
            result = result[ser.isin(allowed)]
        return result

    def _open_renewed_filter(self):
        values = ["已有续保合同", "未有续保合同"]
        selected = set(values)
        if self.filter_has_renewed is not None:
            selected = set()
            if "Y" in self.filter_has_renewed:
                selected.add("已有续保合同")
            if "N" in self.filter_has_renewed:
                selected.add("未有续保合同")
        ColumnFilterPopup(self.frame, "是否续保", values, selected,
                          on_apply=lambda _, sel: self._on_renewed_filter_apply(sel))
        # 弹窗关闭后复位：未筛选才复位为原色
        if self.filter_has_renewed is None:
            self._renewed_btn.setChecked(False)

    def _open_year_filter(self):
        if self.source_df is None or self.source_df.empty:
            return
        # 计算可用年份时跳过年份筛选本身（模拟 Excel：能看到全部年份）
        saved_year = self.filter_year
        self.filter_year = None
        df = self._apply_filters(self.source_df)
        self.filter_year = saved_year
        years = sorted({str(y) for y in df["过保年份"].dropna().astype(str).unique()}, reverse=True)
        if not years:
            return
        values = sorted(years)
        ColumnFilterPopup(self.frame, "过保年份", values,
                          set(values) if self.filter_year is None else self.filter_year,
                          on_apply=lambda _, sel: self._on_year_filter_apply(sel))
        # 弹窗关闭后复位：未筛选才复位为原色
        if self.filter_year is None:
            self._year_btn.setChecked(False)

    def _open_column_filter(self, col):
        if self.source_df is None or self.source_df.empty:
            return
        all_values = self._get_filter_values(col, skip_col=col)
        if not all_values:
            return
        selected = self.active_filters.get(col, set(all_values))
        ColumnFilterPopup(self.frame, str(col).replace("*", "").strip(), all_values, selected,
                          on_apply=lambda _, sel: self._on_column_filter_apply(col, sel))
        # 弹窗关闭后复位按钮：如果筛选未激活才恢复到原色，否则保持蓝色（由 _refresh_filter_buttons 设置）
        btn = self.filter_buttons.get(col)
        if btn is not None and col not in self.active_filters:
            btn.setChecked(False)

    def _on_renewed_filter_apply(self, selected):
        mapped = set()
        if "已有续保合同" in selected:
            mapped.add("Y")
        if "未有续保合同" in selected:
            mapped.add("N")
        self.filter_has_renewed = None if (not mapped or mapped == {"Y", "N"}) else mapped
        self._refresh_filter_buttons()
        self._fill_table()

    def _on_year_filter_apply(self, selected):
        df = self._apply_filters(self.source_df)
        all_years = {str(y) for y in df["过保年份"].dropna().astype(str).unique()}
        selected = {str(s) for s in selected}
        self.filter_year = None if (not selected or selected == all_years) else selected
        self._refresh_filter_buttons()
        self._fill_table()

    def _on_column_filter_apply(self, col, selected):
        # 计算全部可用值时要跳过自身筛选，否则筛选后重开会丢失未选值（如 Excel 行为）
        all_values = set(self._get_filter_values(col, skip_col=col))
        selected = {str(s) for s in selected}
        if not selected or selected == all_values:
            self.active_filters.pop(col, None)
        else:
            self.active_filters[col] = selected
        self._refresh_filter_buttons()
        self._fill_table()

    def _get_filter_values(self, col, skip_col=None):
        if self.source_df is None or col not in self.source_df.columns:
            return []
        df = self._apply_filters(self.source_df, skip_column=skip_col)
        vals = df[col].fillna("（空）").astype(str).unique().tolist()
        return sorted(set(vals))

    def _clear_filters(self):
        self.filter_has_renewed = None
        self.filter_year = None
        self.active_filters.clear()
        self._refresh_filter_buttons()
        self._fill_table()

    def _has_active_filters(self):
        if self.filter_has_renewed is not None:
            return True
        if self.filter_year is not None:
            return True
        return bool(self.active_filters)

    def _refresh_filter_buttons(self):
        """同步筛选按钮的选中态（变色显示哪些列有激活的筛选）。"""
        renewed_active = self.filter_has_renewed is not None
        self._renewed_btn.setChecked(renewed_active)
        year_active = self.filter_year is not None
        self._year_btn.setChecked(year_active)
        # 列筛选按钮（客户意向、不续保原因等）
        for col, btn in self.filter_buttons.items():
            btn.setChecked(col in self.active_filters)
        self._clear_filter_btn.setVisible(self._has_active_filters())

    # ── 排序 ──

    def _on_header_click(self, logical_index):
        col = self.DISPLAY_COLS[logical_index] if logical_index < len(self.DISPLAY_COLS) else None
        if col is None or col == "#" or col not in self.source_df.columns:
            return
        self.sort_asc = not self.sort_asc if self.sort_col == col else True
        self.sort_col = col
        self.source_df = self.source_df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)
        self._fill_table()

    # ── 双击 ──

    def _on_double_click_row(self, index):
        model = self.table.model()
        if model is None:
            return
        row = index.row()
        contract = model.item(row, 2).text().strip()
        customer = model.item(row, 1).text().strip()
        if not contract:
            return

        expiry_df = self.expiry_tab.source_df
        if expiry_df is None:
            QMessageBox.information(self.frame, "提示", "Tab3 过保数据未加载")
            return

        contract_col, gift_col, enduser_col, _, _, _, _, _ = self._find_columns(expiry_df)
        if contract_col is None:
            return

        matched = [r for _, r in expiry_df.iterrows()
                   if str(r.get(contract_col, "")).strip() == contract
                   and self._resolve_customer(r, gift_col, enduser_col).strip() == customer]

        if not matched:
            QMessageBox.information(self.frame, "产品明细", f"合同编码: {contract}\n客户: {customer}\n\n未找到匹配记录。")
            return

        product_lines = []
        for row_data in matched:
            parts = []
            for col_key in ("产品名称", "产品型号", "产品模块"):
                found = next((c for c in expiry_df.columns if col_key in str(c).replace("\n", " ")), None)
                parts.append(str(row_data.get(found, "")) if found and pd.notna(row_data.get(found)) else "")
            line = " | ".join(parts)
            if line.strip("| "):
                product_lines.append(line)

        renewal_lines = []
        for old, new, cust in self._renewal_details:
            if old != contract:
                continue
            amount = self._lookup_main_amount(new)
            renewal_lines.append(f"{new} | {amount if amount else '—'} 元")

        product_text = "\n".join(f"{i}. {line}" for i, line in enumerate(product_lines, 1)) or "无产品明细"
        renewal_text = "\n".join(f"{i}. {line}" for i, line in enumerate(renewal_lines, 1)) or "无续保明细"

        dialog = QDialog(self.frame)
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle(f"合同明细 - {contract}")
        dialog.resize(700, 550)
        center_window(dialog, 700, 550)

        dl = QVBoxLayout(dialog)
        dl.setContentsMargins(16, 12, 16, 12)

        header = QLabel(f"合同编码: {contract}    客户: {customer}")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        dl.addWidget(header)

        dl.addWidget(QLabel(f"产品明细（共 {len(product_lines)} 条）:"))
        pt = QTextEdit()
        pt.setReadOnly(True)
        pt.setFont(QFont("Microsoft YaHei UI", 11))
        pt.setPlainText(product_text)
        pt.setMaximumHeight(150)
        dl.addWidget(pt)

        dl.addWidget(QLabel(f"续保明细（共 {len(renewal_lines)} 条）:"))
        rt = QTextEdit()
        rt.setReadOnly(True)
        rt.setFont(QFont("Microsoft YaHei UI", 11))
        rt.setPlainText(renewal_text)
        rt.setMaximumHeight(150)
        dl.addWidget(rt)

        dialog.exec()

    # ── 续保明细管理 ──

    def _load_renewal_details(self):
        self._renewal_details.clear()
        self._renewal_index.clear()
        try:
            if os.path.exists(RENEWAL_FILE):
                df = _safe_read_excel(RENEWAL_FILE)
                for _, row in df.iterrows():
                    old = str(row.get("关联老合同", "")).strip()
                    new = str(row.get("续保合同号", "")).strip()
                    cust = str(row.get("客户名称", "")).strip() if "客户名称" in df.columns else ""
                    if old and new:
                        self._renewal_details.append((old, new, cust))
                        self._renewal_index.setdefault(old, []).append((old, new, cust))
        except Exception as e:
            log_error(f"加载续保明细失败: {e}")

    def _save_renewal_details(self):
        try:
            df = pd.DataFrame([
                {"关联老合同": old, "续保合同号": new, "客户名称": cust}
                for old, new, cust in self._renewal_details
            ])
            df.to_excel(RENEWAL_FILE, index=False)
        except Exception as e:
            log_error(f"保存续保明细失败: {e}")

    def _is_contract_renewed(self, contract, customer, expiry_year=""):
        """判定客户是否续保。
        当一个合同号在续保明细缓存表里关联了多个维保合同时，
        只有"最新一次的续保合同在当前系统年份（或更晚）"才算真正续保。
        旧年份的续保不算数。
        """
        if not contract:
            return False
        from datetime import datetime
        current_year = datetime.now().year
        latest_renewal_year = None
        # 用合同号索引 O(1) 定位，避免每次全表线性扫描（旧实现 O(N*M)，
        # 在 _fill_table 中每行调用、筛选时多次全表遍历，数据量大时可能卡死主线程）
        entries = self._renewal_index.get(contract)
        if not entries:
            return False
        for old, new, cust in entries:
            renewal_year = extract_contract_year(new)
            if renewal_year is None:
                continue
            if expiry_year and int(renewal_year) < int(expiry_year):
                continue
            # 客户名不匹配也跳过（保留原匹配逻辑）
            map_cust = cust.strip() if cust else ""
            if map_cust and map_cust != customer:
                continue
            # 记录最新的续保年份
            if latest_renewal_year is None or renewal_year > latest_renewal_year:
                latest_renewal_year = renewal_year
        # 最新续保必须在当前年份才算续保
        return latest_renewal_year is not None and int(latest_renewal_year) >= current_year

    def _open_renewal_detail(self):
        self._load_renewal_details()
        details = list(self._renewal_details)

        dialog = QDialog(self.frame)
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle("续保明细管理")
        dialog.resize(750, 480)
        center_window(dialog, 750, 480)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)

        table = QTableView()
        model = QStandardItemModel(0, 4)
        model.setHorizontalHeaderLabels(["#", "续保合同号", "关联老合同", "客户名称"])
        table.setModel(model)
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        # # 列固定窄
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 40)
        # 续保合同号、关联老合同、客户名称按内容伸展
        for i in (1, 2, 3):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        def refresh_table():
            model.setRowCount(len(details))
            for i, (old, new, cust) in enumerate(details):
                for ci, val in enumerate([str(i + 1), new, old, cust]):
                    item = QStandardItem(val)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                    model.setItem(i, ci, item)

        refresh_table()

        def add_dialog_func():
            ad = QDialog(dialog)
            configure_dialog(ad, show_close_button=True)
            install_close_handler(ad)
            ad.setWindowTitle("新增续保明细")
            ad.resize(420, 280)
            center_window(ad, 420, 280)
            al = QVBoxLayout(ad)
            al.setSpacing(10)

            def labeled_input(label_text):
                row_lo = QHBoxLayout()
                row_lo.addWidget(QLabel(label_text))
                edit = QLineEdit()
                edit.setFixedWidth(240)
                row_lo.addWidget(edit)
                row_lo.addStretch()
                al.addLayout(row_lo)
                return edit

            old_edit = labeled_input("关联老合同:")
            new_edit = labeled_input("续保合同号:")
            cust_edit = labeled_input("客户名称:")

            def save():
                o = old_edit.text().strip()
                n = new_edit.text().strip()
                c = cust_edit.text().strip()
                if not n:
                    return
                if not o:
                    o = n
                details.append((o, n, c))
                refresh_table()
                ad.accept()

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(save)
            save_btn.setObjectName("accentBtn")
            al.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            ad.exec()

        def edit_dialog_func():
            idx = table.currentIndex()
            if not idx.isValid():
                QMessageBox.warning(dialog, "提示", "请先选择一条记录")
                return
            row = idx.row()
            old_c, new_c, cust_c = details[row]

            ed = QDialog(dialog)
            configure_dialog(ed, show_close_button=True)
            install_close_handler(ed)
            ed.setWindowTitle("编辑续保明细")
            ed.resize(420, 280)
            center_window(ed, 420, 280)
            el = QVBoxLayout(ed)
            el.setSpacing(10)

            old_edit = QLineEdit(old_c)
            new_edit = QLineEdit(new_c)
            cust_edit = QLineEdit(cust_c)
            for label, edit in [("关联老合同:", old_edit), ("续保合同号:", new_edit), ("客户名称:", cust_edit)]:
                row_lo = QHBoxLayout()
                row_lo.addWidget(QLabel(label))
                edit.setFixedWidth(240)
                row_lo.addWidget(edit)
                row_lo.addStretch()
                el.addLayout(row_lo)

            def save():
                details[row] = (old_edit.text().strip(), new_edit.text().strip(), cust_edit.text().strip())
                refresh_table()
                ed.accept()

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(save)
            save_btn.setObjectName("accentBtn")
            el.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            ed.exec()

        btn_bar = QHBoxLayout()
        add_btn = QPushButton("新增")
        add_btn.clicked.connect(add_dialog_func)
        add_btn.setObjectName("accentBtn")
        btn_bar.addWidget(add_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(edit_dialog_func)
        edit_btn.setObjectName("grayBtn")
        btn_bar.addWidget(edit_btn)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("dangerBtn")
        def delete_fn():
            idx = table.currentIndex()
            if not idx.isValid():
                return
            row = idx.row()
            if not confirm(dialog, "确认删除", "确定要删除？"):
                return
            details.pop(row)
            refresh_table()
        del_btn.clicked.connect(delete_fn)
        btn_bar.addWidget(del_btn)

        btn_bar.addStretch()

        def save_and_close():
            self._renewal_details = list(details)
            # 明细变化后同步重建合同号索引，保证 _is_contract_renewed 读到最新数据
            self._renewal_index.clear()
            for old, new, cust in self._renewal_details:
                self._renewal_index.setdefault(old, []).append((old, new, cust))
            self._save_renewal_details()
            self._fill_table()
            # 不要调用 dialog.accept()——finished 信号已经是关闭触发的，
            # 再 accept 会无限递归 → 整个工具卡死

        dialog.finished.connect(save_and_close)
        layout.addLayout(btn_bar)
        dialog.exec()

    # ── 大礼包渠道管理 ──

    def _load_gift_channels(self):
        self._gift_channels.clear()
        try:
            if os.path.exists(GIFT_FILE):
                df = _safe_read_excel(GIFT_FILE)
                for _, row in df.iterrows():
                    name = str(row.get("渠道名称", "")).strip()
                    if name:
                        self._gift_channels.add(name)
        except Exception as e:
            log_error(f"加载大礼包渠道失败: {e}")
        self._update_gift_btn()

    def _update_gift_btn(self):
        count = len(self._gift_channels)
        self._gift_btn.setText(f"大礼包标记({count})" if count else "大礼包标记")

    def _save_gift_channels(self):
        try:
            df = pd.DataFrame(sorted(self._gift_channels), columns=["渠道名称"])
            df.to_excel(GIFT_FILE, index=False)
        except Exception as e:
            log_error(f"保存大礼包渠道失败: {e}")

    def _open_gift_channel_manager(self):
        self._load_gift_channels()
        channels = sorted(self._gift_channels)

        dialog = QDialog(self.frame)
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle("大礼包渠道标记")
        dialog.resize(480, 520)
        center_window(dialog, 480, 520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)

        table = QTableView()
        model = QStandardItemModel(0, 2)
        model.setHorizontalHeaderLabels(["#", "渠道名称"])
        table.setModel(model)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        def refresh_table():
            model.setRowCount(len(channels))
            for i, name in enumerate(channels):
                for ci, val in enumerate([str(i + 1), name]):
                    item = QStandardItem(val)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                    model.setItem(i, ci, item)

        refresh_table()

        btn_bar = QHBoxLayout()
        add_btn = QPushButton("新增")
        add_btn.clicked.connect(lambda: self._gift_add_dialog(dialog, channels, refresh_table))
        add_btn.setObjectName("accentBtn")
        btn_bar.addWidget(add_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(lambda: self._gift_edit_dialog(dialog, table, channels, refresh_table))
        edit_btn.setObjectName("grayBtn")
        btn_bar.addWidget(edit_btn)

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._gift_delete(table, channels, refresh_table))
        del_btn.setObjectName("dangerBtn")
        btn_bar.addWidget(del_btn)
        btn_bar.addStretch()

        dialog.finished.connect(lambda: (
            setattr(self, '_gift_channels', set(channels)),
            self._save_gift_channels(),
            self._update_gift_btn(),
            self._fill_table(),
        ))
        layout.addLayout(btn_bar)
        dialog.exec()

    def _gift_add_dialog(self, parent, channels, refresh_fn):
        d = QDialog(parent)
        configure_dialog(d, show_close_button=True)
        install_close_handler(d)
        d.setWindowTitle("新增渠道")
        d.resize(400, 150)
        center_window(d, 400, 150)
        lo = QVBoxLayout(d)
        lo.setContentsMargins(16, 16, 16, 16)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("渠道名称:"))
        edit = QLineEdit()
        hl.addWidget(edit)
        lo.addLayout(hl)

        def save():
            name = edit.text().strip()
            if not name:
                return
            if name in channels:
                QMessageBox.warning(d, "提示", "该渠道名称已存在")
                return
            channels.append(name)
            channels.sort()
            refresh_fn()
            d.accept()

        btn = QPushButton("保存")
        btn.clicked.connect(save)
        btn.setObjectName("accentBtn")
        lo.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        d.exec()

    def _gift_edit_dialog(self, parent, table, channels, refresh_fn):
        idx = table.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        old_name = channels[row]
        d = QDialog(parent)
        configure_dialog(d, show_close_button=True)
        install_close_handler(d)
        d.setWindowTitle("编辑渠道")
        d.resize(400, 150)
        center_window(d, 400, 150)
        lo = QVBoxLayout(d)
        lo.setContentsMargins(16, 16, 16, 16)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("渠道名称:"))
        edit = QLineEdit(old_name)
        hl.addWidget(edit)
        lo.addLayout(hl)

        def save():
            name = edit.text().strip()
            if not name:
                return
            if name != old_name and name in channels:
                QMessageBox.warning(d, "提示", "该渠道名称已存在")
                return
            channels[row] = name
            channels.sort()
            refresh_fn()
            d.accept()

        btn = QPushButton("保存")
        btn.clicked.connect(save)
        btn.setObjectName("accentBtn")
        lo.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        d.exec()

    def _gift_delete(self, table, channels, refresh_fn):
        idx = table.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        name = channels[row]
        if not confirm(table, "确认删除", f"确定要删除渠道？\n\n{name}"):
            return
        channels.pop(row)
        refresh_fn()

    def _export_csv(self):
        df = self.source_df
        if df is None or df.empty:
            QMessageBox.warning(self.frame, "提示", "没有数据可导出")
            return
        export_df = self._apply_filters(df)
        renewal_lookup = {}
        for old, new, _ in self._renewal_details:
            renewal_lookup.setdefault(old, []).append(new)
        export_df["续保合同号"] = export_df["合同编码"].apply(
            lambda c: ", ".join(renewal_lookup.get(c, [])) if c in renewal_lookup else ""
        )
        export_to_csv(export_df, self.frame, "过保数据分析.csv")
