"""行业统计 Tab (PySide6 版本) —— 按一级行业 → 二级行业 → 客户逐层下钻"""

from __future__ import annotations

import pandas as pd

from ui.dialog_utils import configure_dialog, install_close_handler
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QPushButton, QLabel,
    QLineEdit, QListWidget, QTableView, QHeaderView, QTabWidget, QMessageBox,
    QFrame, QComboBox, QMenu,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.base_tab import QtBaseTab
from ui.industry_dict import (
    get_primary as dict_primary, get_secondary as dict_secondary,
    add_primary, add_secondary, remove_primary, remove_secondary, merge_from_dataframe,
)
from ui.industry_overrides import apply_overrides, set_override, remove_override, get_all
from ui.msg_box import confirm, info, warn, error
from ui.logger import log_info, log_error
from utils import center_window, export_to_csv


class IndustryTab(QtBaseTab):
    """一级行业统计表 — 双击下钻查看二级行业和客户。"""

    def __init__(self, on_double_click=None):
        super().__init__(
            tab_name="行业统计",
            columns=["一级行业", "数量", "行业总金额"],
            on_double_click=on_double_click,
            has_star=False,
            search_column="一级行业",
        )
        self._raw_df: pd.DataFrame | None = None
        self._load_df: pd.DataFrame | None = None

    def build(self):
        frame = super().build()

        edit_btn = QPushButton("编辑行业")
        edit_btn.setObjectName("ghostBtn")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedHeight(32)
        edit_btn.clicked.connect(self._open_override_manager)

        dict_btn = QPushButton("数据字典")
        dict_btn.setObjectName("ghostBtn")
        dict_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dict_btn.setFixedHeight(32)
        dict_btn.clicked.connect(self._show_data_dict_dialog)

        # 把按钮塞到搜索栏的导出按钮之前
        if self.search_bar is not None:
            # 插入到搜索框和导出按钮之间：搜索框 | 编辑行业 | 数据字典 | 导出 CSV
            self.search_bar.layout().insertWidget(1, edit_btn)
            self.search_bar.layout().insertWidget(2, dict_btn)
        else:
            # 没有搜索栏时（tab 没设 search_column），新建一行顶部按钮栏
            top_bar = QHBoxLayout()
            top_bar.setContentsMargins(0, 0, 0, 0)
            top_bar.setSpacing(8)
            top_bar.addWidget(edit_btn)
            top_bar.addWidget(dict_btn)
            top_bar.addStretch()
            top_bar_w = QWidget()
            top_bar_w.setLayout(top_bar)
            # 把这一行插在表格之前
            outer_layout = frame.layout()
            if outer_layout is not None:
                outer_layout.insertWidget(0, top_bar_w)

        # 设置双击事件
        self.table.doubleClicked.connect(self._on_table_double_click)
        return frame

    def compute_data(self, df: pd.DataFrame) -> pd.DataFrame:
        from data_processor import compute_industry_stats

        full_df = df.copy()
        full_df["一级行业"] = full_df["一级行业"].fillna("未知")
        full_df["二级行业"] = full_df["二级行业"].fillna("未知")
        full_df = full_df[full_df["一级行业"] != "未知"]

        self._load_df = df.copy()
        self._raw_df = full_df[["一级行业", "二级行业", "最终客户名称"]].copy()
        merge_from_dataframe(self._raw_df)

        full_df = apply_overrides(full_df)
        self._raw_df = full_df[["一级行业", "二级行业", "最终客户名称"]].copy()

        result = compute_industry_stats(full_df)

        # 补上字典里有但当前数据里没有的"一级行业"（确保新加的字典项能在表格里看到）
        primaries_in_dict = set(dict_primary())
        present = set(result["一级行业"].astype(str)) if not result.empty else set()
        missing = primaries_in_dict - present
        if missing:
            # 找年份列（int 类型的列）
            year_cols = [c for c in result.columns if isinstance(c, int)] if not result.empty else []
            base_columns = list(result.columns)
            new_rows = []
            for name in missing:
                row = {col: 0 for col in base_columns}
                row["一级行业"] = name
                new_rows.append(row)
            if new_rows:
                extra = pd.DataFrame(new_rows)
                # 确保列对齐
                for c in base_columns:
                    if c not in extra.columns:
                        extra[c] = 0
                extra = extra[base_columns]
                result = pd.concat([result, extra], ignore_index=True)
                # 重新按总金额降序
                result = result.sort_values("行业总金额", ascending=False).reset_index(drop=True)
        return result

    def _on_table_double_click(self, index):
        model = self.table.model()
        if model is None:
            return
        row = index.row()
        col = index.column()
        primary = str(model.item(row, 1).text())  # 一级行业在 col 1（col 0 是 #）
        log_info(f"行业统计下钻: 一级行业「{primary}」")
        self._show_secondary_popup(primary)

    def _refresh_tab_after_override(self):
        if self._load_df is None:
            return
        try:
            new_data = self.compute_data(self._load_df)
            self.populate(new_data)
        except Exception as e:
            log_error(f"应用行业覆盖规则时出错: {e}")

    # ── 数据字典弹窗 ──

    def _show_data_dict_dialog(self):
        dialog = QDialog(self.frame.window())
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle("行业数据字典")
        dialog.resize(550, 460)
        center_window(dialog, 550, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        tab1 = QWidget()
        tabs.addTab(tab1, "一级行业")
        self._build_dict_tab(tab1, "一级行业", dict_primary, add_primary, remove_primary)

        tab2 = QWidget()
        tabs.addTab(tab2, "二级行业")
        self._build_dict_tab(tab2, "二级行业", dict_secondary, add_secondary, remove_secondary)

        dialog.exec()
        self._refresh_tab_after_override()

    def _build_dict_tab(self, parent, title, get_items_fn, add_fn, remove_fn):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 6, 8, 6)

        toolbar = QHBoxLayout()
        title_lbl = QLabel(f"{title}列表")
        title_lbl.setStyleSheet("color: #1F6AA5; font-size: 16px; font-weight: bold;")
        toolbar.addWidget(title_lbl)

        entry = QLineEdit()
        entry.setPlaceholderText(f"输入新{title}...")
        toolbar.addWidget(entry)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("accentBtn")
        toolbar.addWidget(add_btn)
        layout.addLayout(toolbar)

        listbox = QListWidget()
        listbox.setFont(QFont("Microsoft YaHei", 11))

        def refresh():
            listbox.clear()
            for item in get_items_fn():
                listbox.addItem(item)

        refresh()

        add_btn.clicked.connect(lambda: (
            add_fn(entry.text().strip()) if entry.text().strip() else None,
            entry.clear(),
            refresh(),
            self._refresh_tab_after_override(),
        ))

        del_btn = QPushButton("删除选中")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(lambda: self._delete_dict_item(listbox, remove_fn, refresh))

        layout.addWidget(listbox)
        layout.addWidget(del_btn)

    def _delete_dict_item(self, listbox, remove_fn, refresh):
        sel = listbox.currentItem()
        if not sel:
            QMessageBox.warning(self.frame, "提示", "请先选择一项")
            return
        name = sel.text()
        if not confirm(self.frame, "确认删除", f"确定要删除「{name}」吗？"):
            return
        remove_fn(name)
        refresh()
        self._refresh_tab_after_override()

    # ── 覆盖规则管理 ──

    def _open_override_manager(self):
        dialog = QDialog(self.frame.window())
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle("行业覆盖规则管理")
        dialog.resize(620, 560)
        center_window(dialog, 620, 560)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 8, 10, 8)

        toolbar = QHBoxLayout()
        title = QLabel("行业覆盖规则")
        title.setStyleSheet("color: #1F6AA5; font-size: 16px; font-weight: bold;")
        toolbar.addWidget(title)
        self._ov_count_label = QLabel()
        toolbar.addWidget(self._ov_count_label)
        toolbar.addStretch()

        add_btn = QPushButton("新增规则")
        add_btn.setObjectName("accentBtn")
        toolbar.addWidget(add_btn)
        layout.addLayout(toolbar)

        table = QTableView()
        model = QStandardItemModel(0, 4)
        model.setHorizontalHeaderLabels(["#", "客户名称", "一级行业", "二级行业"])
        table.setModel(model)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        # # 列固定窄
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 50)
        # 客户名称列自适应拉伸（占据大部分空间）
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # 一级行业、二级行业列固定窄
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 90)
        table.setColumnWidth(3, 120)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        def fill():
            model.setRowCount(0)
            data = get_all()
            self._ov_count_label.setText(f"共 {len(data)} 条规则")
            for i, (cust, mapping) in enumerate(data.items(), 1):
                items = [
                    QStandardItem(str(i)),
                    QStandardItem(cust),
                    QStandardItem(mapping.get("一级行业", "")),
                    QStandardItem(mapping.get("二级行业", "")),
                ]
                for item in items:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(Qt.ItemFlag(item.flags() & ~Qt.ItemFlag.ItemIsEditable))
                model.appendRow(items)

        fill()

        add_btn.clicked.connect(lambda: (self._show_override_edit_dialog("", dialog, fill)))
        table.doubleClicked.connect(lambda: self._edit_override_from_table(table, model, dialog, fill))

        btn_row = QHBoxLayout()
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("warningBtn")
        edit_btn.clicked.connect(lambda: self._edit_override_from_table(table, model, dialog, fill))
        btn_row.addWidget(edit_btn)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(lambda: self._delete_override_from_table(table, model, fill))
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        dialog.exec()
        self._refresh_tab_after_override()

    def _edit_override_from_table(self, table, model, parent_dialog, fill_fn):
        idx = table.currentIndex()
        if not idx.isValid():
            QMessageBox.warning(parent_dialog, "提示", "请先选择一条记录")
            return
        row = idx.row()
        name = model.item(row, 1).text()
        self._show_override_edit_dialog(name, parent_dialog, fill_fn)

    def _delete_override_from_table(self, table, model, fill_fn):
        sel = table.selectionModel().selectedRows()
        if not sel:
            return
        names = [model.item(r.row(), 1).text() for r in sel]
        msg = f"确定要删除 {len(names)} 条规则吗？\n\n" + "\n".join(names)
        reply = confirm(table, "确认删除", msg)
        if reply:
            for name in names:
                remove_override(name)
            fill_fn()
            self._refresh_tab_after_override()

    def _show_override_edit_dialog(self, customer_name: str = "", parent_popup=None, on_save=None):
        existing = get_all().get(customer_name.strip(), {})
        existing_primary = existing.get("一级行业", "")

        all_primary = dict_primary()
        all_secondary = dict_secondary()
        if self._raw_df is not None:
            from_raw = sorted(self._raw_df["一级行业"].dropna().unique().tolist())
            for v in from_raw:
                if v != "未知" and v not in all_primary:
                    all_primary.append(v)
            from_raw2 = sorted(self._raw_df["二级行业"].dropna().unique().tolist())
            for v in from_raw2:
                if v != "未知" and v not in all_secondary:
                    all_secondary.append(v)

        if existing_primary and existing_primary not in all_primary:
            all_primary.insert(0, existing_primary)
        existing_secondary = existing.get("二级行业", "")
        if existing_secondary and existing_secondary not in all_secondary:
            all_secondary.insert(0, existing_secondary)

        customer_names = []
        if self._raw_df is not None:
            customer_names = sorted(
                self._raw_df["最终客户名称"].dropna().astype(str).str.strip().unique().tolist()
            )

        dialog = QDialog(parent_popup or self.frame.window())
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle(f"修正行业 — {customer_name}" if customer_name else "新增行业覆盖规则")
        dialog.resize(440, 340)
        center_window(dialog, 440, 340)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 客户名称（带搜索）
        cal = QHBoxLayout()
        cal.addWidget(QLabel("客户名称:"))
        cust_edit = QLineEdit(customer_name)
        cust_edit.setFixedWidth(260)
        cal.addWidget(cust_edit)
        cal.addStretch()
        layout.addLayout(cal)

        original_name = customer_name.strip()

        # 一级行业
        pl = QHBoxLayout()
        pl.addWidget(QLabel("一级行业:"))
        primary_combo = QComboBox()
        primary_combo.setFixedWidth(260)
        primary_combo.addItems(all_primary if all_primary else ["（无）"])
        if existing_primary:
            primary_combo.setCurrentText(existing_primary)
        pl.addWidget(primary_combo)
        pl.addStretch()
        layout.addLayout(pl)

        # 二级行业
        sl = QHBoxLayout()
        sl.addWidget(QLabel("二级行业:"))
        secondary_combo = QComboBox()
        secondary_combo.setFixedWidth(260)
        secondary_combo.addItems(all_secondary if all_secondary else ["（无）"])
        if existing_secondary:
            secondary_combo.setCurrentText(existing_secondary)
        sl.addWidget(secondary_combo)
        sl.addStretch()
        layout.addLayout(sl)

        layout.addStretch()

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setObjectName("accentBtn")
        def save():
            name = cust_edit.text().strip()
            primary = primary_combo.currentText().strip()
            secondary = secondary_combo.currentText().strip()
            if not name:
                return
            if primary == "（无）":
                primary = ""
            if secondary == "（无）":
                secondary = ""
            if original_name and original_name != name:
                remove_override(original_name)
            if not primary and not secondary:
                remove_override(name)
            else:
                set_override(name, primary, secondary)
            dialog.accept()
            self._refresh_tab_after_override()
            if on_save:
                on_save()

        save_btn.clicked.connect(save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    # ── 下钻弹窗 ──

    def _show_secondary_popup(self, primary: str):
        from data_processor import get_secondary_industries

        if self._raw_df is None:
            return

        dialog = QDialog(self.frame.window())
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle(f"一级行业「{primary}」— 二级行业统计")
        dialog.resize(520, 420)
        center_window(dialog, 520, 420)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 8, 10, 10)

        toolbar = QHBoxLayout()
        lbl = QLabel(f"一级行业「{primary}」的二级行业统计")
        lbl.setStyleSheet("color: #1F6AA5; font-size: 16px; font-weight: bold;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("accentBtn")
        layout.addLayout(toolbar)

        df = get_secondary_industries(self._raw_df, primary)

        table = QTableView()
        model = QStandardItemModel(len(df), 3)
        model.setHorizontalHeaderLabels(["#", "二级行业", "数量"])
        for idx, (_, row) in enumerate(df.iterrows()):
            for ci, val in enumerate([str(idx + 1), str(row["二级行业"]), str(int(row["数量"]))]):
                item = QStandardItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(idx, ci, item)

        table.setModel(model)
        # # 列固定 60px，其余均分
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 60)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.resizeColumnsToContents()

        export_btn.clicked.connect(lambda: export_to_csv(df, dialog, f"二级行业_{primary}.csv"))

        def on_dbl_click(idx):
            row = idx.row()
            secondary = str(model.item(row, 1).text())
            log_info(f"行业统计下钻: 二级行业「{secondary}」→ 客户名单")
            self._show_customers_popup(primary, secondary, dialog)

        table.doubleClicked.connect(on_dbl_click)
        layout.addWidget(table)

        dialog.exec()

    def _show_customers_popup(self, primary: str, secondary: str, parent_dialog):
        from data_processor import get_industry_customers

        if self._raw_df is None:
            return

        dialog = QDialog(parent_dialog)
        configure_dialog(dialog)
        install_close_handler(dialog)
        dialog.setWindowTitle(f"二级行业「{secondary}」— 客户名单")
        dialog.resize(480, 400)
        center_window(dialog, 480, 400)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 8, 10, 10)

        toolbar = QHBoxLayout()
        lbl = QLabel(f"二级行业「{secondary}」的客户名单")
        lbl.setStyleSheet("color: #1F6AA5; font-size: 16px; font-weight: bold;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        df = get_industry_customers(self._raw_df, primary, secondary)

        table = QTableView()
        model = QStandardItemModel(len(df), 2)
        model.setHorizontalHeaderLabels(["#", "最终客户名称"])
        for idx, (_, row) in enumerate(df.iterrows()):
            for ci, val in enumerate([str(idx + 1), str(row["最终客户名称"])]):
                item = QStandardItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(idx, ci, item)

        table.setModel(model)
        # # 列固定 60px，「最终客户名称」列占满剩余
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 60)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.resizeColumnsToContents()

        # 右键菜单：修正一二级行业
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table: self._show_customer_context_menu(t, pos, parent_dialog)
        )

        layout.addWidget(table)

        dialog.exec()

    def _show_customer_context_menu(self, table, pos: QPoint, parent_dialog):
        """客户名单表格的右键菜单：修正一二级行业。"""
        index = table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        name_item = table.model().item(row, 1)  # 客户名称在第 2 列
        if not name_item:
            return
        customer_name = name_item.text().strip()
        if not customer_name:
            return

        menu = QMenu(table)
        menu.addAction(
            "修正一二级行业",
            lambda n=customer_name, dlg=parent_dialog: self._on_correct_industry(n, dlg),
        )
        menu.exec(table.viewport().mapToGlobal(pos))

    def _on_correct_industry(self, customer_name: str, parent_dialog):
        """右键选了「修正一二级行业」后弹出编辑弹窗。"""
        self._show_override_edit_dialog(customer_name, parent_dialog)
